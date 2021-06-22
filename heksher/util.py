from itertools import repeat
from typing import Callable, Iterable, Tuple, TypeVar

T = TypeVar('T')
T0 = TypeVar('T0')
T1 = TypeVar('T1')


def zip_supersequence(supersequence: Iterable[T0], subsequence: Iterable[T1],
                      superseq_key: Callable[[T0], T] = None, subseq_key: Callable[[T1], T] = None,
                      subseq_default: T1 = None) -> Iterable[Tuple[T0, T1]]:
    """
    zip a supersequence and subsequence together, coupling supersequence elements without a subsequence element with a
     default value.
    Args:
        supersequence: The supersequence iterable
        subsequence: The subsequence iterable
        superseq_key: The supersequence key, if provided, equivalence to subsequence elements is made with this key
         function.
        subseq_key: The subsequence key, if provided, equivalence to supersequence elements is made with this key
         function.
        subseq_default: The value to couple with supersequence elements that have no matching subsequence elements.

    Returns:
        A generator of tuples, each member of which is a 2-tuple, of a supersequence member and either an equivalent
         subsequence member or subseq_default.

    Notes:
        The elements match eagerly

    """
    superseq_key_altered = superseq_key or (lambda x: x)  # type: ignore
    subseq_key_altered = subseq_key or (lambda x: x)  # type: ignore

    sub_iter = iter(subsequence)
    super_iter = iter(supersequence)
    try:
        next_expected_sub = next(sub_iter)
    except StopIteration:
        pass
    else:
        next_expected_sub_key = subseq_key_altered(next_expected_sub)

        for super_element in super_iter:
            super_key = superseq_key_altered(super_element)
            if super_key == next_expected_sub_key:
                yield super_element, next_expected_sub
                try:
                    next_expected_sub = next(sub_iter)
                except StopIteration:
                    break
                next_expected_sub_key = subseq_key_altered(next_expected_sub)
            else:
                yield super_element, subseq_default
        else:
            raise AssertionError('not a supersequence')

    yield from zip(super_iter, repeat(subseq_default))
