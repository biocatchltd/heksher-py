from itertools import repeat

from typing import Iterable, TypeVar, Callable, Tuple

T = TypeVar('T')
T0 = TypeVar('T0')
T1 = TypeVar('T1')


def zip_supersequence(supersequence: Iterable[T0], subsequence: Iterable[T1],
                      superseq_key: Callable[[T0], T] = None, subseq_key: Callable[[T1], T] = None,
                      subseq_default: T1 = None) -> Iterable[Tuple[T0, T1]]:
    superseq_key = superseq_key or (lambda x: x)
    subseq_key = subseq_key or (lambda x: x)

    sub_iter = iter(subsequence)
    super_iter = iter(supersequence)
    try:
        next_expected_sub = next(sub_iter)
    except StopIteration:
        pass
    else:
        next_expected_sub_key = subseq_key(next_expected_sub)

        for super_element in super_iter:
            super_key = superseq_key(super_element)
            if super_key == next_expected_sub_key:
                yield super_element, next_expected_sub
                try:
                    next_expected_sub = next(sub_iter)
                except StopIteration:
                    break
                next_expected_sub_key = subseq_key(next_expected_sub)
            else:
                yield super_element, subseq_default
        else:
            raise AssertionError('not a supersequence')

    yield from zip(super_iter, repeat(subseq_default))
