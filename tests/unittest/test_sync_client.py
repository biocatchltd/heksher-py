from copy import deepcopy
from logging import ERROR, WARNING
from time import sleep

from pytest import mark

from heksher.clients.sync_client import SyncHeksherClient
from heksher.setting import Setting
from tests.unittest.util import assert_logs


def test_init_works(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    with SyncHeksherClient(fake_heksher_service.url, 100000, ['a', 'b', 'c']):
        pass


def test_declare_before_main(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'created': True, 'changed': [], 'incomplete': {}
    })

    setting = Setting('cache_size', int, ['b', 'c'], 50)
    fake_heksher_service.query_response = {
        'rules': {
            'cache_size': [
                {'context_features': [], 'value': 100}
            ]
        }
    }

    with SyncHeksherClient(fake_heksher_service.url, 100000, ['a', 'b', 'c']):
        assert setting.get(a='', b='', c='') == 100


def test_declare_after_main(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'created': True, 'changed': [], 'incomplete': {}
    })

    with SyncHeksherClient(fake_heksher_service.url, 100000, ['a', 'b', 'c']) as client:
        setting = Setting('cache_size', int, ['b', 'c'], 50)
        assert not client._undeclared.empty()
        client._undeclared.join()
        assert setting.get(a='', b='', c='') == 50

        fake_heksher_service.query_response = {
            'rules': {
                'cache_size': [
                    {'context_features': [], 'value': 100}
                ]
            }
        }
        client.reload()
        assert setting.get(a='', b='', c='') == 100


def test_regular_update(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'created': True, 'changed': [], 'incomplete': {}
    })

    setting = Setting('cache_size', int, ['b', 'c'], 50)

    with SyncHeksherClient(fake_heksher_service.url, 0.02, ['a', 'b', 'c']):
        assert setting.get(a='', b='', c='') == 50
        fake_heksher_service.query_response = {
            'rules': {
                'cache_size': [
                    {'context_features': [], 'value': 100}
                ]
            }
        }
        sleep(0.1)
        assert setting.get(a='', b='', c='') == 100


def test_heksher_unreachable(caplog):
    setting = Setting('cache_size', int, ['b', 'c'], 50)

    with assert_logs(caplog, ERROR):
        with SyncHeksherClient('http://notreal.fake.notreal', 10000, ['a', 'b', 'c']):
            assert setting.get(a='', b='', c='') == 50


def test_trackcontexts(fake_heksher_service, monkeypatch):
    fake_heksher_service.query_requests.clear()

    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'created': True, 'changed': [], 'incomplete': {}
    })

    setting = Setting('cache_size', int, ['b', 'c'], 50)
    fake_heksher_service.query_response = {
        'rules': {
            'cache_size': [
                {'context_features': [['b', 'B']], 'value': 100}
            ]
        }
    }

    client = SyncHeksherClient(fake_heksher_service.url, 100000, ['a', 'b', 'c'])
    client.track_contexts(b='B', a=['a0', 'a1'])

    with client:
        assert setting.get(a='', b='B', c='') == 100

    order_invariant_requests = deepcopy(fake_heksher_service.query_requests)
    for req in order_invariant_requests:
        req['cf_options'] = {k: set(v) for (k, v) in req['cf_options'].items()}

    assert order_invariant_requests == [{
        'setting_names': ['cache_size'],
        'cf_options': {'b': {'B'}, 'a': {'a0', 'a1'}},
        'include_metadata': False,
    }]


@mark.parametrize('expected', [
    [],
    ['a'],
    ['b', 'a'],
    ['a', 'b', 'c', 'd'],
    ['e', 'f', 'g']
])
def test_cf_mismatch(fake_heksher_service, caplog, monkeypatch, expected):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])

    with assert_logs(caplog, WARNING):
        with SyncHeksherClient(fake_heksher_service.url, 1000, expected) as client:
            assert client._context_features == ['a', 'b', 'c']


def test_redundant_defaults(fake_heksher_service, caplog, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'created': True, 'changed': [], 'incomplete': {}
    })

    setting = Setting('cache_size', int, ['b', 'c'], 50)
    fake_heksher_service.query_response = {
        'rules': {
            'cache_size': [
                {'context_features': [['b', 'B']], 'value': 100}
            ]
        }
    }

    with assert_logs(caplog, WARNING):
        with SyncHeksherClient(fake_heksher_service.url, 1000, ['a', 'b', 'c']) as client:
            client.set_defaults(b='B', d='im redundant')
            assert setting.get(a='', c='') == 100
