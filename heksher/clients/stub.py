from __future__ import annotations

from dataclasses import dataclass
from itertools import groupby
from typing import TypeVar, Mapping, Optional, Generic, Union, Collection
from unittest.mock import MagicMock

try:
    from unittest.mock import AsyncMock
except ImportError:
    # asyncmock only available for python 3.8 and up, for earlier versions, we use the backport
    from mock import AsyncMock

from heksher.clients.subclasses import ContextFeaturesMixin, AsyncContextManagerMixin, ContextManagerMixin
from heksher.clients.util import collate_rules
from heksher.setting import Setting

T = TypeVar('T')


@dataclass
class Rule(Generic[T]):
    exact_match_conditions: Mapping[str, Optional[str]]
    value: T  # pytype: disable=not-supported-yet


class StubClient(ContextFeaturesMixin):
    def add_undeclared(self, settings):
        pass

    def handover_main(self, other):
        raise RuntimeError(f'cannot handover from {type(self)}')

    def track_contexts(self, **context_values: Union[str, Collection[str]]):
        pass

    def __setitem__(self, key: Setting[T], value: Union[T, Collection[Rule[T]]]):
        # check for rule collection
        if isinstance(value, Collection) and isinstance(next(iter(value), None), Rule):
            # we need to make sure all the rules have exactly the same context_features
            grouped = groupby(value, lambda rule: tuple(rule.exact_match_conditions.keys()))
            first, _ = next(grouped)
            try:
                second, _ = next(grouped)
            except StopIteration:
                pass
            else:
                raise RuntimeError('stubbing.__setattr__ with a rule list requires that all the rules have the exact'
                                   f' same features (got {first} and {second})')
            rules = [
                ([(k, v) for k, v in rule.exact_match_conditions.items() if v is not None], rule.value)
                for rule in value
            ]
            root = collate_rules(first, rules)
            key.update(self, first, root)
        else:
            key.update(self, (), value)


class AsyncStubHeksherClient(StubClient, AsyncContextManagerMixin):
    reload = None
    close = None

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.reload = AsyncMock()
        self.close = AsyncMock()

    async def set_as_main(self):
        super()._set_as_main()


class SyncStubHeksherClient(StubClient, ContextManagerMixin):
    reload = None
    close = None

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.reload = MagicMock()
        self.close = MagicMock()

    def set_as_main(self):
        super()._set_as_main()
