from __future__ import annotations

from dataclasses import dataclass
from logging import getLogger
from operator import attrgetter
from typing import Any, Generic, Mapping, Optional, Sequence, TypeVar, Union
from weakref import ref

from ordered_set import OrderedSet

import heksher.main_client
from heksher.exceptions import NoMatchError
from heksher.setting_type import setting_type

logger = getLogger(__name__)

T = TypeVar('T')

MISSING = object()


class Setting(Generic[T]):
    """
    A setting object, that stores a ruleset and can be updated by heksher clients
    """

    def __init__(self, name: str, type, configurable_features: Sequence[str],
                 default_value: T = MISSING,  # type: ignore
                 metadata: Optional[Mapping[str, Any]] = None):
        """
        Args:
            name: The name of the setting.
            type: The type of the setting, either a primitive type (int, str, bool, float), an enum class, a FlagInt
             class, or a generic alias of List or Dict.
            configurable_features: The configurable features of the setting.
            default_value: The default value of the setting, this value will be returned if no rules match the current
             context.
            metadata: Additional metadata of the setting.
        Notes:
            Creating a setting automatically registers it to be declared at the main heksher client.
        """
        self.name = name
        self.type = setting_type(type)
        self.configurable_features = OrderedSet(configurable_features)
        self.default_value = default_value
        self.metadata = metadata or {}

        self.last_ruleset: Optional[RuleSet] = None

        heksher.main_client.Main.add_settings((self,))

    def get(self, **contexts) -> T:
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
        """
        Update a setting's rules from a client

        Args:
            client: The client updating the setting.
            context_features: The context features the root was collated by.
            root: A collated rulebranch root.
        """
        if self.last_ruleset:
            last_client = self.last_ruleset.client()
            if last_client and last_client is not client:
                logger.warning('setting received rule set from multiple clients',
                               extra={'setting': self.name, 'new_client': client, 'last_client': last_client})
        self.last_ruleset = RuleSet(ref(client), context_features, root)


RuleBranch = Union[Mapping[Optional[str], 'RuleBranch[T]'], T]  # type: ignore[misc]
"""
A RuleBranch is a nested collation of rules or sub-rules, stored in a uniform-depth tree structure.
For example, the following set of rules:
{user: john} -> 100
{user: jim, trust: admin} -> 200
{user: jim} -> 50
{trust: guest, theme: dark} -> 20
{trust: guest} -> 10

Will be collated to the following rulebranch:
{
  "john": {
    None: {
      None:100
    }
  },
  "jim": {
    "admin": {
      None: 200
    },
    None: {
      None: 50
    }
  },
  None: {
    "guest": {
      "dark": 20,
      None: 10
    }
  }
}
"""


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
    context_features: Sequence[str]
    """
    The context features the root rulebranch was collated against
    """
    root: RuleBranch[T]
    """
    The root rulebranch
    """

    def resolve(self, context_namespace: Mapping[str, str], setting: Setting):
        """
        Args:
            context_namespace: A namespace of context features and their values. If the client is available, its
             context_namespace method is used beforehand.

        Returns:
            The value of the deepest-matched rule

        Raises:
            NoMatchError, if no rules matched the namespace
        """
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
            if depth == len(self.context_features):
                # leaf node
                return RuleMatch(current, exact_match_depth)

            assert isinstance(current, Mapping)

            feature = self.context_features[depth]
            if feature in setting.configurable_features:
                feature_value = context_namespace.get(feature)
                if feature_value is None:
                    raise RuntimeError(f'configurable context feature {feature} is missing from both the default'
                                       ' namespace and arguments')

                exact = (feature_value in current) and _resolve(current[feature_value], depth + 1, depth)
            else:
                exact = None

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
