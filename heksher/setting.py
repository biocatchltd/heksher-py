from __future__ import annotations

from dataclasses import dataclass
from logging import getLogger
from operator import attrgetter
from typing import Any, Callable, Dict, Generic, Iterable, List, Mapping, Optional, Sequence, Tuple, TypeVar, Union
from weakref import ref

from ordered_set import OrderedSet

import heksher.main_client
from heksher.clients.util import RuleBranch, collate_rules
from heksher.exceptions import NoMatchError
from heksher.setting_type import Conversion, setting_type

no_match = object()

logger = getLogger(__name__)

T = TypeVar('T')


@dataclass
class QueriedRule:
    rule_id: Optional[int]
    context_features: Sequence[Tuple[str, str]]


Validator = Callable[[T, Optional[QueriedRule], 'Setting'], T]


def _reject_on_coerce(x, _0, _1, _2, setting):
    raise TypeError(f'coercion is disabled for {setting.name}, coercions: {x.coercions}')


class Setting(Generic[T]):
    """
    A setting object, that stores a ruleset and can be updated by heksher clients
    """

    def __init__(self, name: str, type: Any, configurable_features: Sequence[str], default_value: T,
                 metadata: Optional[Mapping[str, Any]] = None, alias: Optional[str] = None, version: str = '1.0',
                 on_coerce: Optional[Callable[[T, Any, Sequence[str], Optional[QueriedRule], 'Setting'], T]]
                 = lambda x, *args: x):
        """
        Args:
            name: The name of the setting.
            type: The type of the setting, either a primitive type (int, str, bool, float), an enum class, a FlagInt
             class, or a generic alias of List or Dict.
            configurable_features: The configurable features of the setting.
            default_value: The default value of the setting, this value will be returned if no rules match the current
             context.
            metadata: Additional metadata of the setting.
            alias: An alias for the setting.
            version: The version of the setting.
            on_coerce: A function to be called after a server value resulter in coercion. Should return a local value,
             or raise a TypeError. Set to None to always raise a type error.
        Notes:
            Creating a setting automatically registers it to be declared at the main heksher client.
        """
        self.name = name
        self.type = setting_type(type)
        self.configurable_features = OrderedSet(configurable_features)
        self.default_value = default_value
        self.metadata = metadata or {}
        self.alias = alias
        self.version_str = version
        self.version = tuple(int(x) for x in version.split('.', 1))

        if on_coerce is None:
            on_coerce = _reject_on_coerce

        self.on_coerce = on_coerce

        self.last_ruleset: Optional[RuleSet] = None

        self._validators: List[Validator[T]] = []
        self.server_default_value: Optional[T] = None

        heksher.main_client.Main.add_settings((self,))

    def convert_server_value(self, raw_value: Any, rule: Optional[QueriedRule]) -> Conversion[T]:
        convert = self.type.convert_from_heksher(raw_value)
        if convert.coercions:
            value = self.on_coerce(convert.value, raw_value, convert.coercions, rule, self)
        else:
            value = convert.value
        for validator in self._validators:
            value = validator(value, rule, self)
        return Conversion(value, convert.coercions)

    def add_validator(self, validator: Validator[T]) -> Validator[T]:
        """
        Add a validator to be called when the setting's value is updated.
        If multiple callbacks are added, they are called in the order they are added.
        Args:
            validator: the validator to be added.
            A validator must have three positional arguments: value, rule and Setting.
            The return value of the validator will be the new value of the rule.

        Returns:
            The validator given, so the method can be used as a decorator
        """
        self._validators.append(validator)
        return validator

    def get(self, **contexts: str) -> T:
        """
        Get the value of the setting for the context features.
        Args:
            **contexts: The context features along with their values, to use to resolve the ruleset. Any missing context
             features must be filled in by the client.

        Returns:
            The value for the rule matching the context, or the default value.

        Raises:
            NoMatchError if no rules matched and a default value is not defined.
        """
        redundant_keys = contexts.keys() - self.configurable_features
        if redundant_keys:
            raise ValueError(f'the following keys are not configurable: {redundant_keys}')

        if self.last_ruleset:
            try:
                from_rules = self.last_ruleset.resolve(contexts, self)
            except NoMatchError:
                from_rules = no_match
        else:
            logger.info('the value of setting was never retrieved from service', extra={'setting': self.name})
            from_rules = no_match

        if from_rules is no_match:
            return self.server_default_value if self.server_default_value is not None else self.default_value
        return from_rules

    def update(self, client, rules: Iterable[Tuple[T, QueriedRule]]):
        """
        Update a setting's rules from a client

        Args:
            client: The client updating the setting.
            rules: An iterable of rules to collate.
        """
        if self.last_ruleset:
            last_client = self.last_ruleset.client()
            if last_client and last_client is not client:
                logger.warning('setting received rule set from multiple clients',
                               extra={'setting': self.name, 'new_client': client, 'last_client': last_client})

        validated_rules = [(rule.context_features, value) for (value, rule) in rules]
        root = collate_rules(self.configurable_features, validated_rules)
        self.last_ruleset = RuleSet(ref(client), root)

    def to_v1_declaration_body(self) -> Dict[str, Any]:
        """
        Creates the request body for v1 declaration of this setting
        """
        return {
            'name': self.name,
            'configurable_features': list(self.configurable_features),
            'type': self.type.heksher_string(),
            'metadata': self.metadata,
            'alias': self.alias,
            'default_value': self.type.convert_to_heksher(self.default_value),
            'version': self.version_str,
        }


@dataclass(frozen=True)
class RuleMatch(Generic[T]):
    """
    An internal structure for resolution, representing a value belonging to a rule that matched the
     current namespace
    """
    value: T
    """
    The value of the matched rule
    """
    exact_match_depth: int
    """
    The index of the last context feature that had an exact match condition within the rule
    """


@dataclass(frozen=True)
class RuleSet(Generic[T]):
    """
    A complete set of rules, resolvable through a namespace
    """
    client: ref
    """
    A weakref to the client that supplied the ruleset
    """
    root: RuleBranch[T]
    """
    The root rulebranch
    """

    def resolve(self, context_namespace: Mapping[str, str], setting: Setting):
        client = self.client()
        if client:
            context_namespace = client.context_namespace(context_namespace)

        def _resolve(current: RuleBranch[T], depth: int = 0, exact_match_depth: int = -1) \
                -> Union[RuleMatch, bool]:  # my kingdom for a Literal!
            """
            Args:
                current: The branch being resolved
                depth: The depth of the branch (in relation to the root)
                exact_match_depth: The depth of the latest exact-match in the path from root to current, where -1
                 indicates that no exact match occurred.

            Returns:
                Either False for no matches within the branch, or a RuleMatch with the maximal branch.

            """
            if depth == len(setting.configurable_features):
                # leaf node
                return RuleMatch(current, exact_match_depth)

            assert isinstance(current, Mapping)

            feature = setting.configurable_features[depth]
            feature_value = context_namespace.get(feature)
            if feature_value is None:
                raise RuntimeError(f'configurable context feature {feature} is missing from both the default'
                                   ' namespace and arguments')

            exact = (feature_value in current) and _resolve(current[feature_value], depth + 1, depth)

            wildcard = (None in current) and _resolve(current[None], depth + 1, exact_match_depth)

            if exact and wildcard:
                # in case both wildcard and exact produced a match, we want the match with the deepest exact condition,
                # with tie-break advantage to the exact
                return max(exact, wildcard, key=attrgetter('exact_match_depth'))
            return exact or wildcard

        ret = _resolve(self.root)
        if not ret:
            raise NoMatchError
        assert isinstance(ret, RuleMatch)
        return ret.value
