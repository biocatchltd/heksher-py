from logging import getLogger
from operator import itemgetter
from typing import Iterable, Tuple, Sequence, TypeVar

from heksher.setting import RuleBranch, MISSING
from heksher.util import zip_supersequence

logger = getLogger(__name__)
T = TypeVar('T')


# pytype: disable=invalid-annotation
def collate_rules(keys: Sequence[str], rules: Iterable[Tuple[Sequence[Tuple[str, str]], T]]) -> RuleBranch[T]:
    # pytype: enable=invalid-annotation
    """
    Gather a set of rules into a rule-branch root
    Args:
        keys: The context features to collate by
        rules: An iterable of rules to collate. Each rule is a two-tuple, first the sequence of exact-match condition
         (in hierarchical order), the second the value.

    Returns:
        The rule branch root for the rules, using the context features.

    """
    if not keys:
        # special case for no cfs, return value will be a single value
        rule_iter = iter(rules)
        try:
            conds, ret = next(rule_iter)
        except StopIteration:
            # no rules at all
            return MISSING
        assert not conds
        # we assert that there is, at most, one rule
        try:
            conds, ret = next(rule_iter)
        except StopIteration:
            pass
        else:
            assert not conds
            logger.error('rule conflict, overlapping values for context in service without context features',
                         stack_info=True)
        return ret

    root = {}
    for conditions, value in rules:
        # we constantly point the current node in the tree by storing its parent and the path to get there
        parent = None
        child_key = None  # root is without a path
        for cf, condition in zip_supersequence(keys, conditions, subseq_key=itemgetter(0)):
            if condition:
                # exact_match condition
                _, key = condition
            else:
                # wildcard
                key = None

            if parent is None:
                # we were pointing at the root
                parent = root
            else:
                parent = parent.setdefault(child_key, {})

            child_key = key
        if child_key in parent:
            # rule conflict
            logger.error('rule conflict, overlapping values for context', extra={'conditions': conditions},
                         stack_info=True)
        assert parent is not None
        parent[child_key] = value
    return root
