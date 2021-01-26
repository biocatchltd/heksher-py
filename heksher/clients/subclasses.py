from __future__ import annotations

from _contextvars import ContextVar
from abc import ABC, abstractmethod
from asyncio import Queue
from collections import defaultdict
from logging import getLogger
from typing import Dict, MutableMapping, Sequence, Iterable, Tuple, TypeVar, Union, Collection, Set, ContextManager, \
    AsyncContextManager, Mapping
from weakref import WeakValueDictionary

from httpx import Response

from heksher.clients.util import collate_rules
from heksher.heksher_client import BaseHeksherClient
from heksher.setting import Setting, RuleBranch

logger = getLogger(__name__)

T = TypeVar('T')


class V1APIClient(BaseHeksherClient, ABC):
    _undeclared: Queue[Setting]
    _context_features: Sequence[str]

    def __init__(self, context_features: Sequence[str]):
        """
        Args:
            update_interval: the interval, in seconds to wait between any two regular update calls.
        """
        super().__init__()
        self._context_features = context_features

        self._tracked_context_options: Dict[str, Set[str]] = defaultdict(set)
        self._tracked_settings: MutableMapping[str, Setting] = WeakValueDictionary()

    # pytype: disable=invalid-annotation
    def collate_rules(self, rules: Iterable[Tuple[Sequence[Tuple[str, str]], T]]) -> RuleBranch[T]:
        # pytype: enable=invalid-annotation
        return collate_rules(self._context_features, rules)

    def handover_main(self, other: BaseHeksherClient):
        raise RuntimeError(f'cannot handover from {type(self)}')

    def add_undeclared(self, settings):
        for s in settings:
            self._undeclared.put_nowait(s)

    def track_contexts(self, **context_values: Union[str, Collection[str]]):
        redundant_keys = context_values.keys() - set(self._context_features)
        if redundant_keys:
            logger.warning('context features are not specified in the client', extra={
                'redundant_keys': redundant_keys
            })
        for k, v in context_values.items():
            if isinstance(v, str):
                v = (v,)
            self._tracked_context_options[k].update(v)

    def _handle_declaration_response(self, setting: Setting, response: Response):
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
        for setting_name, rule_mappings in updated_settings.items():
            setting = self._tracked_settings[setting_name]
            rules = ((rm['context_features'], setting.type.convert(rm['value'])) for rm in rule_mappings)
            branch = self.collate_rules(rules)
            setting.update(self, self._context_features, branch)


class ContextFeaturesMixin(BaseHeksherClient, ABC):
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

    def default_context_namespace(self):
        ret = dict(self._const_context_features)
        for k, cv in self._contextvar_context_features.items():
            try:
                value = cv.get()
            except LookupError:
                continue
            ret[k] = value
        return ret


class ContextManagerMixin(BaseHeksherClient, ContextManager):
    @abstractmethod
    def set_as_main(self):
        self._set_as_main()

    @abstractmethod
    def close(self):
        pass

    def __enter__(self: T) -> T:
        self.set_as_main()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return None


class AsyncContextManagerMixin(BaseHeksherClient, AsyncContextManager):
    @abstractmethod
    async def set_as_main(self):
        self._set_as_main()

    @abstractmethod
    async def close(self):
        pass

    async def __aenter__(self: T) -> T:
        await self.set_as_main()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return None
