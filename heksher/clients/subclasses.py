from __future__ import annotations

import asyncio
import queue
from abc import ABC, abstractmethod
from contextvars import ContextVar
from logging import getLogger
from typing import (
    Any, AsyncContextManager, Collection, ContextManager, Iterable, Mapping, MutableMapping, Sequence, Tuple, TypeVar,
    Union
)
from weakref import WeakValueDictionary

from deprecated import deprecated
from httpx import Response
from ordered_set import OrderedSet
from sortedcontainers import SortedDict, SortedList

import heksher.main_client
from heksher.heksher_client import BaseHeksherClient, TemporaryClient
from heksher.setting import QueriedRule, Setting

logger = getLogger(__name__)

T = TypeVar('T')

TRACK_ALL = '*'


def apply_difference(setting: Setting, difference: Mapping[str, Any]) -> None:
    attr = difference.get('attribute')
    # right now we only know how to handle the 'default_value' attribute difference
    if attr == 'default_value':
        server_default_value = difference.get('latest_value')
        try:
            convert = setting.convert_server_value(server_default_value, None)
        except TypeError:
            logger.warning('server default was discarded due to coercion error during declaration',
                           exc_info=True,
                           extra={'setting_name': setting.name, 'server_default_value': server_default_value})
        else:
            if convert.coercions:
                logger.warning('server default was coerced to local value during declaration', extra={
                    'setting_name': setting.name, 'server_default_value': server_default_value,
                    'coercions': convert.coercions})
            setting.server_default_value = convert.value


class V1APIClient(BaseHeksherClient, ABC):
    """
    A client base class with shared logic for heksher's v1 HTTP API.
    """
    _undeclared: Union[asyncio.Queue, queue.Queue]

    def __init__(self, context_features: Sequence[str]):
        """
        Args:
            context_features: The context features to store as default in the client
        """
        super().__init__()
        self._context_features: OrderedSet[str] = OrderedSet(context_features)

        self._tracked_context_options: SortedDict[str, Union[SortedList[str], str]] = SortedDict()
        # the tracked options can also include the sentinel value TRACK_ALL
        # value will always be a set or TRACK_ALL, Literal is not supported in python 3.7
        self._tracked_settings: MutableMapping[str, Setting] = WeakValueDictionary()

    def add_settings(self, settings: Iterable[Setting]):
        for s in settings:
            self._undeclared.put_nowait(s)

    def track_contexts(self, **context_values: Union[str, Collection[str]]):
        """
        Register the context feature options to be tracked by the client. An option must be tracked for any rules
         pertaining to it to be used.

        Args:
            **context_values: context features, mapped to either a single possible value or a collection.
        """
        redundant_keys = context_values.keys() - self._context_features
        if redundant_keys:
            logger.warning('context features are not specified in server', extra={
                'redundant_keys': redundant_keys
            })
        for k, v in context_values.items():
            if v == TRACK_ALL:
                if self._tracked_context_options.get(k) is not None:
                    raise RuntimeError("cannot set TRACK_ALL to a feature that's already been used to track")
                self._tracked_context_options[k] = TRACK_ALL
                continue
            if isinstance(v, str):
                v = (v,)
            existing = self._tracked_context_options.get(k)
            if existing == TRACK_ALL:
                raise RuntimeError("cannot track a specific value after the feature's been set to TRACK_ALL")
            if existing is None:
                self._tracked_context_options[k] = SortedList(v)
            else:
                self._tracked_context_options[k].update(v)  # type: ignore

    def _context_filters(self):
        def context_filter(filter_):
            if filter_ == TRACK_ALL:
                return '*'
            return '(' + ','.join(filter_) + ')'

        return ','.join((f'{k}:{context_filter(v)}' for k, v in self._tracked_context_options.items()))

    def _handle_declaration_response(self, setting: Setting, response: Response):
        """
        Inner utility method to handle a setting declaration response
        Args:
            setting: the setting declared
            response: the http response from the service

        """
        if response.status_code == 409:
            # we have encountered an upgrade conflict. We report it and attempt to cope
            logger.error('conflict when declaring setting', extra={'setting_name': setting.name,
                                                                   'response_content': response.content})
        elif response.is_error:
            logger.error('error when declaring setting', extra={'setting_name': setting.name,
                                                                'response_content': response.content})
            response.raise_for_status()

        try:
            response_data = response.json()
        except ValueError:
            # if the content is not json, it's probably an error response, do nothing (we already reported error
            # responses)
            if response.is_success:
                logger.warning('unexpected response from service', extra={'response_content': response.content})
            return

        outcome = response_data.get('outcome')
        if outcome == 'outdated':
            latest_version_str = response_data.get('latest_version')
            if latest_version_str is None:
                logger.error('outdated setting without latest version', extra={'setting_name': setting.name})
                latest_version: Tuple[int, int] = (float('inf'), float('inf'))  # type: ignore[assignment]
            else:
                latest_version = tuple(map(int, latest_version_str.split('.', 1)))  # type: ignore[assignment]
            if latest_version[0] != setting.version[0]:
                logger.warning('setting is outdated by a major version',
                               extra={'setting_name': setting.name, 'differences': response_data.get('differences'),
                                      'latest_version': latest_version_str, 'current_version': setting.version_str})
            else:
                logger.info('setting is outdated',
                            extra={'setting_name': setting.name, 'differences': response_data.get('differences'),
                                   'latest_version': latest_version_str, 'declared_version': setting.version_str})
            for difference in response_data.get('differences', ()):
                apply_difference(setting, difference)
        elif outcome in ('created', 'uptodate', 'upgraded', 'mismatch', 'outofdate', 'rejected'):
            # no special behaviour for these cases
            pass
        else:
            logger.warning('unexpected outcome from service', extra={'setting_name': setting.name, 'outcome': outcome})

        self._tracked_settings[setting.name] = setting

    def _update_settings_from_query(self, updated_settings: Mapping[str, dict]):
        """
        Inner utility method to handle a setting update
        Args:
            updated_settings: A mapping of settings, with updated rules from the HTTP service
        """
        for setting_name, setting_results in updated_settings.items():
            rejected_rules = []
            coercions = []
            setting = self._tracked_settings[setting_name]
            rule_mappings = setting_results['rules']
            rules = []
            for rule_mapping in rule_mappings:
                context_features = rule_mapping['context_features']
                cf_keys = frozenset(cf for (cf, _) in context_features)
                unrecognized_cf = cf_keys - setting.configurable_features
                if unrecognized_cf:
                    rejected_rules.append(
                        (rule_mapping['rule_id'], f'rule refers to unrecognized features {unrecognized_cf}'))
                    continue
                raw_value = rule_mapping['value']
                rule = QueriedRule(rule_mapping['rule_id'], context_features)
                try:
                    conv = setting.convert_server_value(raw_value, rule)
                except TypeError as e:
                    rejected_rules.append((rule_mapping['rule_id'], f'rule value could not be converted: {e!r}'))
                    continue
                else:
                    if conv.coercions:
                        coercions.append((rule_mapping['rule_id'], conv.coercions))
                    rules.append((conv.value, rule))
            if rejected_rules:
                logger.warning('setting update rejected rules', extra={'setting_name': setting_name,
                                                                       'rejected_rules': rejected_rules})
            if coercions:
                logger.info('setting update coerced values', extra={'setting_name': setting_name,
                                                                    'coercions': coercions})
            new_default = setting_results['default_value']
            try:
                convert = setting.convert_server_value(new_default, None)
            except TypeError:
                logger.warning('setting default value discarded default due to conversion error', exc_info=True,
                               extra={'setting_name': setting_name, 'new_default': new_default})
            else:
                if convert.coercions:
                    logger.warning('setting default value coerced to local value', extra={
                        'setting_name': setting_name, 'new_default': new_default, 'coercions': convert.coercions})
                setting.server_default_value = convert.value
            setting.update(self, rules)

    def context_namespace(self, user_namespace: Mapping[str, str]) -> Mapping[str, str]:
        redundant_keys = user_namespace.keys() - self._context_features
        if redundant_keys:
            logger.warning('context features are not specified in server', extra={
                'redundant_keys': redundant_keys
            })

        for k, v in user_namespace.items():
            if k in redundant_keys:
                # all redundant keys have already been handled
                continue
            tracked_contexts_options = self._tracked_context_options.get(k, ())
            if v not in tracked_contexts_options and tracked_contexts_options != TRACK_ALL:
                logger.warning('context feature value is not tracked by client',
                               extra={'context_feature': k, 'context_feature_value': v})
        return super().context_namespace(user_namespace)

    def _set_as_main(self):
        """
        Transfer "main-ness" to self, either from a temporary client or another v1 client
        """
        previous_main: BaseHeksherClient = heksher.main_client.Main  # for readability of this function
        if isinstance(previous_main, TemporaryClient):
            self.add_settings(previous_main.undeclared)
        elif isinstance(previous_main, V1APIClient):
            # know when you've fucked up
            logger.warning("switching main heksher clients! this is NOT recommended! (unless this is a test)")
            if not previous_main._undeclared.empty():
                raise RuntimeError("previous main heksher client still has unprocessed declarations, "
                                   "did you forget to close it?")
            if self._context_features != previous_main._context_features:
                # now you've really fucked up
                raise RuntimeError(f"new main heksher client has different contexts, "
                                   f"previous: {previous_main._context_features}, new: {self._context_features}")
            # if we are using the same contexts, we can safely add the same settings to this client
            # no need to redeclare them, so we just track them
            for setting_name, setting in previous_main._tracked_settings.items():
                if setting_name in self._tracked_settings:
                    continue
                self._tracked_settings[setting.name] = setting
            if self._tracked_context_options != previous_main._tracked_context_options:
                # this won't cause errors, but it will cause some settings to have the wrong values, be warned
                logger.warning("new main heksher client tracks different context options",
                               extra={"previous_options": previous_main._tracked_context_options,
                                      "new_options": self._tracked_context_options})
        else:
            raise TypeError(f'cannot change main client from type '
                            f'{type(previous_main).__name__} to type {type(self).__name__}')
        heksher.main_client.Main = self


class ContextFeaturesMixin(BaseHeksherClient, ABC):
    """
    A mixin class to handle default context feature values, either from contextvars or string constants.
    """

    def __init__(self):
        super().__init__()
        self._const_context_features: MutableMapping[str, str] = {}
        self._contextvar_context_features: MutableMapping[str, ContextVar[str]] = {}

    def set_defaults(self, **kwargs: Union[str, ContextVar[str]]):
        existing_keys = kwargs.keys() & (self._const_context_features.keys() | self._contextvar_context_features.keys())
        if existing_keys:
            raise ValueError(f'defaults for context features {existing_keys} have already been added')

        for k, v in kwargs.items():
            if isinstance(v, str):
                self._const_context_features[k] = v
            else:
                self._contextvar_context_features[k] = v

    def context_namespace(self, user_namespace: Mapping[str, str]) -> Mapping[str, str]:
        ret = dict(self._const_context_features)
        ret.update(user_namespace)

        for k, cv in self._contextvar_context_features.items():
            if k in ret:
                # skip the context value since the ns already provided a value
                continue

            try:
                value = cv.get()
            except LookupError:
                continue
            ret[k] = value
        return ret


class ContextManagerMixin(BaseHeksherClient, ContextManager):
    """
    Mixin class to treat a client as a synchronous context manager
    """

    @abstractmethod
    def set_as_main(self):
        self._set_as_main()

    @abstractmethod
    def close(self):
        pass

    def __enter__(self):
        self.set_as_main()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class AsyncContextManagerMixin(BaseHeksherClient, AsyncContextManager):
    """
    Mixin class to treat a client as an asynchronous context manager
    """

    @abstractmethod
    async def set_as_main(self):
        self._set_as_main()

    @deprecated(version="0.2.0", reason="use aclose() instead")
    async def close(self):
        return await self.aclose()

    @abstractmethod
    async def aclose(self):
        pass

    async def __aenter__(self):
        await self.set_as_main()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()
