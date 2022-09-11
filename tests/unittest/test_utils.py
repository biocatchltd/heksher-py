from logging import ERROR

from pytest import mark, raises

from heksher.clients.util import collate_rules
from tests.unittest.util import assert_logs


def test_collate():
    expected = {
        'A0': {
            'B0': {
                None: 2
            },
            None: {
                None: 1
            }
        },
        None: {
            'B1': {
                None: 3
            },
            None: {
                None: 0
            }
        }
    }
    assert collate_rules('abc', [
        ([], 0),
        ([('a', 'A0')], 1),
        ([('a', 'A0'), ('b', 'B0')], 2),
        ([('b', 'B1')], 3)
    ]) == expected


def test_collate_null():
    assert collate_rules('', [
        ([], 0)
    ]) == 0


@mark.parametrize('features', ['abc', 'a'])
def test_collate_norules(features):
    assert collate_rules(features, []) == {}


def test_collate_norules_nocf():
    assert collate_rules('', []) == {}


def test_collate_cf_mismatch():
    with raises(AssertionError):
        collate_rules('', [
            ([('a', 'A0')], 0),
        ])

    with raises(AssertionError):
        collate_rules('abc', [
            ([('D', 'D0')], 0),
        ])


def test_collate_conflict(caplog):
    expected = {
        'A0': {
            'B0': {
                None: 2
            },
            None: {
                None: 5
            }
        },
        None: {
            'B1': {
                None: 3
            },
            None: {
                None: 0
            }
        }
    }
    with assert_logs(caplog, ERROR, r'^rule conflict.+'):
        assert collate_rules('abc', [
            ([], 0),
            ([('a', 'A0')], 1),
            ([('a', 'A0'), ('b', 'B0')], 2),
            ([('b', 'B1')], 3),
            ([('a', 'A0')], 5),
        ]) == expected


def test_collate_conflict_nill(caplog):
    with assert_logs(caplog, ERROR, r'^rule conflict.+'):
        assert collate_rules('', [
            ([], 0),
            ([], 1)
        ]) == 1
