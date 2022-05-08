from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Collection, ContextManager, Generic, Mapping, TypeVar, Union, cast
from unittest.mock import MagicMock

try:
    from unittest.mock import AsyncMock  # type: ignore[attr-defined]
except ImportError:
    # asyncmock only available for python 3.8 and up, for earlier versions, we use the backport
    from mock import AsyncMock  # type: ignore[attr-defined]

import heksher.main_client
from heksher.clients.subclasses import AsyncContextManagerMixin, ContextFeaturesMixin, ContextManagerMixin
from heksher.setting import QueriedRule, Setting

T = TypeVar('T')

__all__ = ['Rule', 'SyncStubHeksherClient', 'AsyncStubHeksherClient']


@dataclass
class Rule(Generic[T]):
    """
    A rule for stub clients, to emulate setting rules
    """
    match_conditions: Mapping[str, str]
    """
    The match conditions for the rule.
    """
    value: T
    """
    The value of a setting that matches the conditions
    """


@dataclass
class PreviousValue:
    value: Any


class SettingPatcher(Generic[T]):
    def __init__(self, setting: Setting[T], client: StubClient):
        self.setting = setting
        self.client = client

    @property
    def rules(self):
        return PreviousValue(self.setting.last_ruleset)

    @rules.setter
    def rules(self, value: Union[T, Collection[Rule[T]]]):
        if isinstance(value, PreviousValue):
            self.setting.last_ruleset = value.value
            return
        if not isinstance(value, Collection) or not isinstance(next(iter(value), None), Rule):
            value = [Rule(match_conditions={}, value=cast(T, value))]
        rules = [
            (rule.value, QueriedRule(None, list(rule.match_conditions.items())))
            for rule in value
        ]
        self.setting.update(self.client, rules)


class StubClient(ContextFeaturesMixin):
    """
    An abstract stub heksher client, usable for testing.
    """

    class _Patch(ContextManager):
        """
        A context manager for a stubbed setting
        """

        def __init__(self, patcher: SettingPatcher):
            self.patcher = patcher
            self.previous = patcher.rules

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.patcher.rules = self.previous
            return None

    def add_settings(self, settings):
        pass

    def track_contexts(self, **context_values: Union[str, Collection[str]]):
        pass

    def patch(self, setting: Setting[T], value: Union[T, Collection[Rule[T]]]) -> ContextManager:
        """
        Stub the value of a particular setting. Deprecated.

        Args:
            setting: The setting whose value to set.
            value: The value of the setting, or a collection of rules to be collated.

        Returns:
            A context manager that will reset the value of the setting upon exit.
        """
        patcher = self[setting]
        ret = self._Patch(patcher)  # initialize the patch first so it can know the previous value
        patcher.rules = value
        return ret

    def __getitem__(self, item: Setting[T]) -> SettingPatcher[T]:
        return SettingPatcher(item, self)

    def _set_as_main(self):
        heksher.main_client.Main = self


class AsyncStubHeksherClient(StubClient, AsyncContextManagerMixin):
    """
    An asynchronous heksher client. Compatible with AsyncHeksherClient.
    """
    aclose = None

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.reload = AsyncMock()
        self.aclose = AsyncMock()
        self.ping = AsyncMock()

    async def set_as_main(self):
        super()._set_as_main()


class SyncStubHeksherClient(StubClient, ContextManagerMixin):
    """
    A synchronous heksher client. Compatible with ThreadHeksherClient.
    """
    close = None

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.reload = MagicMock()
        self.close = MagicMock()
        self.ping = MagicMock()

    def set_as_main(self):
        super()._set_as_main()
