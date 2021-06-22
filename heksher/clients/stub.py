from __future__ import annotations

from dataclasses import dataclass
from itertools import groupby
from typing import Collection, ContextManager, Generic, Mapping, Optional, TypeVar, Union
from unittest.mock import MagicMock

try:
    from unittest.mock import AsyncMock  # type: ignore[attr-defined]
except ImportError:
    # asyncmock only available for python 3.8 and up, for earlier versions, we use the backport
    from mock import AsyncMock  # type: ignore[attr-defined]

from heksher.clients.subclasses import AsyncContextManagerMixin, ContextFeaturesMixin, ContextManagerMixin
from heksher.clients.util import collate_rules
from heksher.setting import Setting

T = TypeVar('T')

__all__ = ['Rule', 'SyncStubHeksherClient', 'AsyncStubHeksherClient']


@dataclass
class Rule(Generic[T]):
    """
    A rule for stub clients, to emulate setting rules
    """
    match_conditions: Mapping[str, Optional[str]]
    """
    The match conditions for the rule, with "None" as a wildcard.
    Notes:
        in StubClients, when multiple rules are given, they must have the exact same keys, in exactly the same order.
        These keys will be interpreted as the setting's context features.
    """
    value: T
    """
    The value of a setting that matches the conditions
    """


class StubClient(ContextFeaturesMixin):
    """
    An abstract stub heksher client, usable for testing.
    """

    class _Patch(ContextManager):
        """
        A context manager for a stubbed setting
        """

        def __init__(self, setting: Setting):
            self.setting = setting
            self.previous = setting.last_ruleset

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.setting.last_ruleset = self.previous
            return None

    def add_settings(self, settings):
        pass

    def track_contexts(self, **context_values: Union[str, Collection[str]]):
        pass

    def patch(self, setting: Setting[T], value: Union[T, Collection[Rule[T]]]) -> ContextManager:
        """
        Stub the value of a particular setting.

        Args:
            setting: The setting whose value to set.
            value: The value of the setting, or a collection of rules to be collated.

        Returns:
            A context manager that will reset the value of the setting upon exit.
        """
        ret = self._Patch(setting)  # initialize the patch first so it can know the previous value
        # check for rule collection
        if isinstance(value, Collection) and isinstance(next(iter(value), None), Rule):
            # we need to make sure all the rules have exactly the same context_features
            grouped = groupby(value, lambda rule: tuple(rule.match_conditions.keys()))
            first, _ = next(grouped)
            try:
                second, _ = next(grouped)
            except StopIteration:
                pass
            else:
                raise RuntimeError('StubClient.patch with a rule list requires that all the rules have the exact'
                                   f' same features (got {first} and {second})')
            rules = [
                ([(k, v) for k, v in rule.match_conditions.items() if v is not None], rule.value)
                for rule in value
            ]
            root = collate_rules(first, rules)
            setting.update(self, first, root)
        else:
            setting.update(self, (), value)  # type: ignore

        return ret


class AsyncStubHeksherClient(StubClient, AsyncContextManagerMixin):
    """
    An asynchronous heksher client. Compatible with AsyncHeksherClient.
    """
    close = None

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.reload = AsyncMock()
        self.close = AsyncMock()
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
