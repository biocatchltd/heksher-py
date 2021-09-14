from copy import deepcopy
from logging import ERROR, WARNING
from time import sleep

import orjson
from httpx import HTTPError
from pytest import mark, raises

from heksher import TRACK_ALL
from heksher.clients.thread_client import ThreadHeksherClient
from heksher.clients.util import SettingData
from heksher.setting import Setting
from tests.unittest.util import assert_logs


def test_init_works(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    with ThreadHeksherClient(fake_heksher_service.url, 100000, ['a', 'b', 'c']):
        pass


def test_declare_before_main(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'created': True, 'changed': [], 'incomplete': {}
    })

    setting = Setting('cache_size', int, ['b', 'c'], 50)
    monkeypatch.setattr(fake_heksher_service, 'query_response', {
        'rules': {
            'cache_size': [
                {'context_features': [], 'value': 100}
            ]
        }
    })

    with ThreadHeksherClient(fake_heksher_service.url, 100000, ['a', 'b', 'c']):
        assert setting.get(b='', c='') == 100


def test_declare_after_main(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'created': True, 'changed': [], 'incomplete': {}
    })

    with ThreadHeksherClient(fake_heksher_service.url, 100000, ['a', 'b', 'c']) as client:
        setting = Setting('cache_size', int, ['b', 'c'], 50)
        assert not client._undeclared.empty()
        client._undeclared.join()
        assert setting.get(b='', c='') == 50

        monkeypatch.setattr(fake_heksher_service, 'query_response', {
            'rules': {
                'cache_size': [
                    {'context_features': [], 'value': 100}
                ]
            }
        })
        client.reload()
        assert setting.get(b='', c='') == 100


def test_regular_update(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'created': True, 'changed': [], 'incomplete': {}
    })

    setting = Setting('cache_size', int, ['b', 'c'], 50)

    with ThreadHeksherClient(fake_heksher_service.url, 0.02, ['a', 'b', 'c']):
        assert setting.get(b='', c='') == 50
        monkeypatch.setattr(fake_heksher_service, 'query_response', {
            'rules': {
                'cache_size': [
                    {'context_features': [], 'value': 100}
                ]
            }
        })
        sleep(0.1)
        assert setting.get(b='', c='') == 100


def test_heksher_unreachable(caplog):
    setting = Setting('cache_size', int, ['b', 'c'], 50)

    with assert_logs(caplog, ERROR):
        with ThreadHeksherClient('http://notreal.fake.notreal', 10000, ['a', 'b', 'c']):
            assert setting.get(b='', c='') == 50


def test_trackcontexts(fake_heksher_service, monkeypatch):
    fake_heksher_service.query_requests.clear()

    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c', 'd'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'created': True, 'changed': [], 'incomplete': {}
    })

    setting = Setting('cache_size', int, ['b', 'c'], 50)
    monkeypatch.setattr(fake_heksher_service, 'query_response', {
        'rules': {
            'cache_size': [
                {'context_features': [['b', 'B']], 'value': 100}
            ]
        }
    })

    client = ThreadHeksherClient(fake_heksher_service.url, 100000, ['a', 'b', 'c', 'd'])
    client.track_contexts(b='B', a=['a0', 'a1'], d=TRACK_ALL)

    with client:
        assert setting.get(b='B', c='') == 100

    order_invariant_requests = deepcopy(fake_heksher_service.query_requests)
    for req in order_invariant_requests:
        req['context_features_options'] = {
            k: (v if isinstance(v, str) else set(v)) for (k, v) in req['context_features_options'].items()
        }

    assert order_invariant_requests == [{
        'setting_names': ['cache_size'],
        'context_features_options': {'b': {'B'}, 'a': {'a0', 'a1'}, 'd': '*'},
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
        with ThreadHeksherClient(fake_heksher_service.url, 1000, expected) as client:
            assert client._context_features == ['a', 'b', 'c']


def test_redundant_defaults(fake_heksher_service, caplog, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'created': True, 'changed': [], 'incomplete': {}
    })

    setting = Setting('cache_size', int, ['b', 'c'], 50)
    monkeypatch.setattr(fake_heksher_service, 'query_response', {
        'rules': {
            'cache_size': [
                {'context_features': [['b', 'B']], 'value': 100}
            ]
        }
    })

    with assert_logs(caplog, WARNING):
        with ThreadHeksherClient(fake_heksher_service.url, 1000, ['a', 'b', 'c']) as client:
            client.set_defaults(b='B', d='im redundant')
            assert setting.get(c='') == 100


def test_health_OK(fake_heksher_service):
    client = ThreadHeksherClient(fake_heksher_service.url, 1000, ['a', 'b', 'c'])
    client.ping()


def test_health_err(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'health_response', 403)

    client = ThreadHeksherClient(fake_heksher_service.url, 1000, ['a', 'b', 'c'])
    with raises(HTTPError):
        client.ping()


def test_health_unreachable():
    client = ThreadHeksherClient('http://notreal.fake.notreal', 1000, ['a', 'b', 'c'])
    with raises(HTTPError):
        client.ping()


def test_get_settings(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    settings = {'settings': [
        {
            'name': 'foo',
            'configurable_features': ['a', 'b'],
            'type': 'int',
            'default_value': None,
            'metadata': {}
        }
    ]}
    monkeypatch.setattr(fake_heksher_service, 'settings_response', orjson.dumps(settings))
    with ThreadHeksherClient(fake_heksher_service.url, 1000, ['a', 'b', 'c']) as client:
        response = client.get_settings()
        assert response == {"foo": SettingData(name="foo",
                                               configurable_features=['a', 'b'],
                                               type='int',
                                               default_value=None,
                                               metadata={})
                            }


def test_switch_main_from_temp(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'conf1', {
        'created': True, 'changed': [], 'incomplete': {}
    })
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'conf2', {
        'created': True, 'changed': [], 'incomplete': {}
    })
    setting1 = Setting('conf1', int, ['a'], 74)
    client = ThreadHeksherClient(fake_heksher_service.url, 10000000, ['a', 'b'])
    client.track_contexts(a=['a', 'b'], b=TRACK_ALL)
    client.set_as_main()
    setting2 = Setting('conf2', int, ['b'], 26)
    monkeypatch.setattr(fake_heksher_service, 'query_response', {
        'rules': {
            'conf1': [
                {'context_features': [], 'value': 5}
            ],
            'conf2': [
                {'context_features': [], 'value': 4}
            ]
        }
    })
    client.reload()
    assert setting1.get(a='') == 5
    assert setting2.get(b='') == 4


def test_switch_main(fake_heksher_service, monkeypatch, caplog):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'conf1', {
        'created': True, 'changed': [], 'incomplete': {}
    })
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'conf2', {
        'created': True, 'changed': [], 'incomplete': {}
    })
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'conf3', {
        'created': True, 'changed': [], 'incomplete': {}
    })
    setting1 = Setting('conf1', int, ['a'], 74)
    client1 = ThreadHeksherClient(fake_heksher_service.url, 10000000, ['a', 'b'])
    client1.track_contexts(a=['a', 'b'], b=TRACK_ALL)
    client1.set_as_main()
    setting2 = Setting('conf2', int, ['b'], 26)
    monkeypatch.setattr(fake_heksher_service, 'query_response', {
        'rules': {
            'conf1': [
                {'context_features': [], 'value': 5}
            ],
            'conf2': [
                {'context_features': [], 'value': 4}
            ]
        }
    })
    client1.reload()
    assert len(client1._tracked_settings) == 2
    assert setting1.get(a='') == 5
    assert setting2.get(b='') == 4
    client2 = ThreadHeksherClient(fake_heksher_service.url, 10000000, ['a', 'b'])
    client2.track_contexts(a=['a', 'b'], b=TRACK_ALL)
    client1.close()
    with assert_logs(caplog, WARNING):  # it should warn you you're doing bad things
        client2.set_as_main()
    setting3 = Setting('conf3', int, ['b'], 59)
    monkeypatch.setattr(fake_heksher_service, 'query_response', {
        'rules': {
            'conf1': [
                {'context_features': [], 'value': 5}
            ],
            'conf2': [
                {'context_features': [], 'value': 4}
            ],
            'conf3': [
                {'context_features': [], 'value': 3}
            ]
        }
    })
    client2.reload()
    assert setting1.get(a='') == 5
    assert setting2.get(b='') == 4
    assert setting3.get(b='') == 3


def test_switch_main_different_tracking(fake_heksher_service, monkeypatch, caplog):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'conf1', {
        'created': True, 'changed': [], 'incomplete': {}
    })
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'conf2', {
        'created': True, 'changed': [], 'incomplete': {}
    })
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'conf3', {
        'created': True, 'changed': [], 'incomplete': {}
    })
    setting1 = Setting('conf1', int, ['a'], 74)
    client1 = ThreadHeksherClient(fake_heksher_service.url, 10000000, ['a', 'b'])
    client1.track_contexts(a=['a', 'b'], b=TRACK_ALL)
    client1.set_as_main()
    setting2 = Setting('conf2', int, ['b'], 26)
    monkeypatch.setattr(fake_heksher_service, 'query_response', {
        'rules': {
            'conf1': [
                {'context_features': [], 'value': 5}
            ],
            'conf2': [
                {'context_features': [], 'value': 4}
            ]
        }
    })
    client1.reload()
    assert len(client1._tracked_settings) == 2
    assert setting1.get(a='') == 5
    assert setting2.get(b='') == 4
    client2 = ThreadHeksherClient(fake_heksher_service.url, 10000000, ['a', 'b'])
    client2.track_contexts(a=['a', 'b', 'c'], b="shoobidoobi")
    client1.close()
    with assert_logs(caplog, WARNING):  # it should warn you you're doing bad things, and that your tracking differs
        client2.set_as_main()
    setting3 = Setting('conf3', int, ['b'], 59)
    monkeypatch.setattr(fake_heksher_service, 'query_response', {
        'rules': {
            'conf1': [
                {'context_features': [], 'value': 5}
            ],
            'conf2': [
                {'context_features': [], 'value': 4}
            ],
            'conf3': [
                {'context_features': [], 'value': 3}
            ]
        }
    })
    client2.reload()
    assert setting1.get(a='') == 5
    assert setting2.get(b='') == 4
    assert setting3.get(b='') == 3


def test_switch_main_different_contexts(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'conf1', {
        'created': True, 'changed': [], 'incomplete': {}
    })
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'conf2', {
        'created': True, 'changed': [], 'incomplete': {}
    })
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'conf3', {
        'created': True, 'changed': [], 'incomplete': {}
    })
    setting1 = Setting('conf1', int, ['a'], 74)
    client1 = ThreadHeksherClient(fake_heksher_service.url, 10000000, ['a', 'b'])
    client1.track_contexts(a=['a', 'b'], b=TRACK_ALL)
    client1.set_as_main()
    setting2 = Setting('conf2', int, ['b'], 26)
    monkeypatch.setattr(fake_heksher_service, 'query_response', {
        'rules': {
            'conf1': [
                {'context_features': [], 'value': 5}
            ],
            'conf2': [
                {'context_features': [], 'value': 4}
            ]
        }
    })
    client1.reload()
    assert len(client1._tracked_settings) == 2
    assert setting1.get(a='') == 5
    assert setting2.get(b='') == 4
    client2 = ThreadHeksherClient(fake_heksher_service.url, 10000000, ['b', 'c'])
    client2.track_contexts(a=['a', 'b'], b=TRACK_ALL)
    client1.close()
    with raises(RuntimeError):  # not allowed
        client2.set_as_main()


def test_switch_main_unclosed(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'conf1', {
        'created': True, 'changed': [], 'incomplete': {}
    })
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'conf2', {
        'created': True, 'changed': [], 'incomplete': {}
    })
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'conf3', {
        'created': True, 'changed': [], 'incomplete': {}
    })
    setting1 = Setting('conf1', int, ['a'], 74)
    client1 = ThreadHeksherClient(fake_heksher_service.url, 10000000, ['a', 'b'])
    client1.track_contexts(a=['a', 'b'], b=TRACK_ALL)
    client1.set_as_main()
    client1.close()
    setting2 = Setting('conf2', int, ['b'], 26)
    client2 = ThreadHeksherClient(fake_heksher_service.url, 10000000, ['a', 'b'])
    client2.track_contexts(a=['a', 'b'], b=TRACK_ALL)
    with raises(RuntimeError):  # not allowed
        client2.set_as_main()
