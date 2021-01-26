from __future__ import annotations

from logging import getLogger
from operator import attrgetter
from weakref import ref
from typing import Generic, TypeVar, Sequence, Optional, Mapping, Any, NamedTuple, Union, Tuple

import heksher.main_client
from heksher.exceptions import NoMatchError
from heksher.setting_type import SettingTypeInput, setting_type

logger = getLogger(__name__)

T = TypeVar('T')

MISSING = object()


class Setting(Generic[T]):
    def __init__(self, name: str, type_: SettingTypeInput,
                 configurable_features: Sequence[str], default_value: T = MISSING,
                 metadata: Optional[Mapping[str, Any]] = None):
        self.name = name
        self.type = setting_type(type_)
        self.configurable_features = configurable_features
        self.default_value = default_value
        self.metadata = metadata

        self.last_ruleset: Optional[RuleSet] = None

        heksher.main_client.Main.add_undeclared((self,))  # pytype: disable=pyi-error

    def get(self, **contexts) -> T:
        if self.last_ruleset:
            try:
                from_rules = self.last_ruleset.resolve(contexts)
            except NoMatchError:
                from_rules = MISSING
        else:
            logger.warning('the value of setting was never retrieved from service', extra={'setting': self.name})
            from_rules = MISSING

        if from_rules is MISSING:
            if self.default_value is MISSING:
                raise NoMatchError(self.name)
            return self.default_value
        return from_rules

    def update(self, client, context_features: Sequence[str], root: RuleBranch[T]):
        if self.last_ruleset:
            last_client = self.last_ruleset.client()
            if last_client and last_client is not client:
                logger.warning('setting received rule set from multiple clients',
                               extra={'setting': self.name, 'new_client': client, 'last_client': last_client})
        self.last_ruleset = RuleSet(ref(client), context_features, root)


PrimitiveRule = Tuple[Mapping[str, str], T]

RuleBranch = Union[Mapping[Optional[str], 'RuleBranch[T]'], T]  # pytype: disable=not-supported-yet


class RuleMatch(NamedTuple, Generic[T]):
    value: T  # pytype: disable=not-supported-yet
    exact_match_depth: int


class RuleSet(NamedTuple, Generic[T]):
    client: ref
    context_features: Sequence[str]
    root: RuleBranch[T]

    def resolve(self, context_namespace: Mapping[str, str]):
        client = self.client()
        if client:
            context_namespace = {**client.default_context_namespace(), **context_namespace}

        def _resolve(current: RuleBranch[T], depth: int = 0, exact_match_depth=-1) -> Union[RuleMatch, bool]:
            if depth == len(self.context_features):
                return RuleMatch(current, exact_match_depth)

            feature = self.context_features[depth]
            if feature not in context_namespace:
                raise RuntimeError(f'context feature {feature} is missing from both the default namespace and'
                                   ' arguments')
            feature_value = context_namespace[feature]

            exact = (feature_value in current) and _resolve(current[feature_value], depth + 1, depth)
            wildcard = (None in current) and _resolve(current[None], depth + 1, exact_match_depth)

            if exact and wildcard:
                return max(exact, wildcard, key=attrgetter('exact_match_depth'))
            return exact or wildcard

        ret = _resolve(self.root)
        if not ret:
            raise NoMatchError
        assert isinstance(ret, RuleMatch)
        return ret.value
