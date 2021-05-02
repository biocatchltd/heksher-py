from asyncio import sleep
from copy import deepcopy
from enum import IntFlag, auto
from logging import ERROR, WARNING

import orjson
from httpx import HTTPError
from pytest import mark, raises

from heksher import TRACK_ALL
from heksher.clients.async_client import AsyncHeksherClient
from heksher.clients.util import SettingData
from heksher.setting import Setting
from tests.unittest.util import assert_logs

atest = mark.asyncio


@atest
async def test_init_works(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    async with AsyncHeksherClient(fake_heksher_service.url, 10000000, ['a', 'b', 'c']):
        pass


@atest
async def test_declare_before_main(fake_heksher_service, monkeypatch):
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

    async with AsyncHeksherClient(fake_heksher_service.url, 10000000, ['a', 'b', 'c']):
        assert setting.get(b='', c='') == 100


@atest
async def test_declare_after_main(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'created': True, 'changed': [], 'incomplete': {}
    })

    async with AsyncHeksherClient(fake_heksher_service.url, 10000000, ['a', 'b', 'c']) as client:
        setting = Setting('cache_size', int, ['b', 'c'], 50)
        assert not client._undeclared.empty()
        await client._undeclared.join()
        assert setting.get(b='', c='') == 50

        monkeypatch.setattr(fake_heksher_service, 'query_response', {
            'rules': {
                'cache_size': [
                    {'context_features': [], 'value': 100}
                ]
            }
        })
        await client.reload()
        assert setting.get(b='', c='') == 100


@atest
async def test_regular_update(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'created': True, 'changed': [], 'incomplete': {}
    })

    setting = Setting('cache_size', int, ['b', 'c'], 50)

    async with AsyncHeksherClient(fake_heksher_service.url, 0.02, ['a', 'b', 'c']):
        assert setting.get(b='', c='') == 50
        monkeypatch.setattr(fake_heksher_service, 'query_response', {
            'rules': {
                'cache_size': [
                    {'context_features': [], 'value': 100}
                ]
            }
        })
        await sleep(1)
        assert setting.get(b='', c='') == 100


@atest
async def test_heksher_unreachable(caplog):
    setting = Setting('cache_size', int, ['b', 'c'], 50)
    caplog.clear()
    with assert_logs(caplog, ERROR):
        async with AsyncHeksherClient('http://notreal.fake.notreal', 10000000, ['a', 'b', 'c']):
            assert setting.get(b='', c='') == 50


@atest
@mark.parametrize('expected', [
    [],
    ['a'],
    ['b', 'a'],
    ['a', 'b', 'c', 'd'],
    ['e', 'f', 'g']
])
async def test_cf_mismatch(fake_heksher_service, caplog, monkeypatch, expected):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])

    with assert_logs(caplog, WARNING):
        async with AsyncHeksherClient(fake_heksher_service.url, 1000, expected) as client:
            assert client._context_features == ['a', 'b', 'c']


@atest
async def test_redundant_defaults(fake_heksher_service, caplog, monkeypatch):
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
        async with AsyncHeksherClient(fake_heksher_service.url, 1000, ['a', 'b', 'c']) as client:
            client.set_defaults(b='B', d='im redundant')
            assert setting.get(c='') == 100


@atest
async def test_trackcontexts(fake_heksher_service, monkeypatch):
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

    client = AsyncHeksherClient(fake_heksher_service.url, 100000, ['a', 'b', 'c', 'd'])
    client.track_contexts(b='B', a=['a0', 'a1'], d=TRACK_ALL)

    async with client:
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


@atest
async def test_redundant_trackings(caplog):
    client = AsyncHeksherClient('bla', 0, ['a', 'b', 'c'])
    with assert_logs(caplog, WARNING):
        client.track_contexts(a='j', d='t')


@atest
async def test_bad_tracking_all_first(caplog):
    client = AsyncHeksherClient('bla', 0, ['a', 'b', 'c'])
    client.track_contexts(a=TRACK_ALL)
    with raises(RuntimeError):
        client.track_contexts(a='a')


@atest
async def test_bad_tracking_all_second(caplog):
    client = AsyncHeksherClient('bla', 0, ['a', 'b', 'c'])
    client.track_contexts(a='a')
    with raises(RuntimeError):
        client.track_contexts(a=TRACK_ALL)


@atest
@mark.parametrize('changed,incomplete', [
    (['x', 'y'], {}),
    ([], {'a': 'b'}),
    (['x', 'y'], {'a': 'b'}),
])
async def test_incomplete_declaration(fake_heksher_service, monkeypatch, changed, incomplete, caplog):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'created': True, 'changed': changed, 'incomplete': incomplete
    })

    setting = Setting('cache_size', int, ['b', 'c'], 50)

    with assert_logs(caplog, WARNING):
        async with AsyncHeksherClient(fake_heksher_service.url, 10000000, ['a', 'b', 'c']):
            pass


@atest
async def test_flags_setting(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'c', {
        'created': True, 'changed': [], 'incomplete': {}
    })

    class Color(IntFlag):
        blue = auto()
        red = auto()
        green = auto()

    c = Setting('c', Color, 'abc', default_value=Color(0))
    monkeypatch.setattr(fake_heksher_service, 'query_response', {
        'rules': {
            'c': [
                {'context_features': [], 'value': ['green', 'blue']}
            ]
        }
    })
    async with AsyncHeksherClient(fake_heksher_service.url, 1000, ['a', 'b', 'c']):
        assert c.get(a='', b='', c='') == Color.green | Color.blue


@atest
async def test_health_OK(fake_heksher_service):
    client = AsyncHeksherClient(fake_heksher_service.url, 1000, ['a', 'b', 'c'])
    await client.ping()
    await client.close()


@atest
async def test_health_err(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'health_response', 403)

    client = AsyncHeksherClient(fake_heksher_service.url, 1000, ['a', 'b', 'c'])
    with raises(HTTPError):
        await client.ping()
    await client.close()


@atest
async def test_health_unreachable():
    client = AsyncHeksherClient('http://notreal.fake.notreal', 1000, ['a', 'b', 'c'])
    with raises(HTTPError):
        await client.ping()
    await client.close()


@atest
async def test_get_settings(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    settings = {'settings': [
        {
            'name': 'settings',
            'configurable_features': ['a', 'b'],
            'type': 'test_type',
            'default_value': None,
            'metadata': {}
        }
    ]}
    monkeypatch.setattr(fake_heksher_service, 'settings_response', orjson.dumps(settings))
    async with AsyncHeksherClient(fake_heksher_service.url, 10000000, ['a', 'b', 'c']) as client:
        response = await client.get_settings()
        assert response == [SettingData(**setting) for setting in settings['settings']]
