from __future__ import annotations

import asyncio
import queue
from abc import ABC, abstractmethod
from collections import defaultdict
from contextvars import ContextVar
from logging import getLogger
from typing import (
    AsyncContextManager, Collection, ContextManager, Dict, Iterable, Mapping, MutableMapping, Sequence, Set, Tuple,
    TypeVar, Union
)
from weakref import WeakValueDictionary

from httpx import Response
from ordered_set import OrderedSet

import heksher.main_client
from heksher.clients.util import collate_rules
from heksher.heksher_client import BaseHeksherClient, TemporaryClient
from heksher.setting import RuleBranch, Setting

logger = getLogger(__name__)

T = TypeVar('T')

TRACK_ALL = '*'


class V1APIClient(BaseHeksherClient, ABC):
    """
    A client base class with shared logic for heksher's v1 HTTP API.
    """
    _undeclared: Union[asyncio.Queue, queue.Queue]
    _context_features: OrderedSet[str]

    def __init__(self, context_features: Sequence[str]):
        """
        Args:
            context_features: The context features to store as default in the client
        """
        super().__init__()
        self._context_features: OrderedSet[str] = OrderedSet(context_features)

        self._tracked_context_options: Dict[str, Union[Set[str], str]] = defaultdict(set)
        # the tracked options can also include the sentinel value TRACK_ALL
        # value will always be a set or TRACK_ALL, Literal is not supported in python 3.7
        self._tracked_settings: MutableMapping[str, Setting] = WeakValueDictionary()

    def collate_rules(self, rules: Iterable[Tuple[Sequence[Tuple[str, str]], T]]) -> RuleBranch[T]:
        """
        Collate a list of rules, according to the client's context features

        Args:
            rules: an iterable of rules

        Returns:
            The root rule branch

        """
        return collate_rules(self._context_features, rules)

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
            if self._tracked_context_options[k] == TRACK_ALL:
                raise RuntimeError("cannot track a specific value after the feature's been set to TRACK_ALL")
            self._tracked_context_options[k].update(v)  # type: ignore

    def _context_feature_options(self):
        return {k: (TRACK_ALL if v == TRACK_ALL else list(v))
                for k, v in self._tracked_context_options.items()}

    def _handle_declaration_response(self, setting: Setting, response: Response):
        """
        Inner utility method to handle a setting declaration response
        Args:
            setting: the setting declared
            response: the http response from the service

        """
        response.raise_for_status()
        response_data = response.json()
        incomplete = response_data['incomplete']
        if incomplete:
            logger.warning('some setting entries are incomplete in declaration',
                           extra={'setting': setting.name, 'incomplete': incomplete})
        changed = response_data['changed']
        if changed:
            logger.warning('some setting entries were changed by declaration',
                           extra={'setting': setting.name, 'changed': changed})
        logger.info('setting declared', extra={'setting': setting.name})
        self._tracked_settings[setting.name] = setting

    def _update_settings_from_query(self, updated_settings: Mapping[str, dict]):
        """
        Inner utility method to handle a setting update
        Args:
            updated_settings: A mapping of settings, with updated rules from the HTTP service
        """
        for setting_name, rule_mappings in updated_settings.items():
            setting = self._tracked_settings[setting_name]
            rules = ((rm['context_features'], setting.type.convert(rm['value'])) for rm in rule_mappings)
            setting.update(self, self._context_features, rules)

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
    _context_features: Collection[str]

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

    @abstractmethod
    async def close(self):
        pass

    async def __aenter__(self):
        await self.set_as_main()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
