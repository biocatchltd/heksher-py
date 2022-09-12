from asyncio import sleep
from logging import ERROR, WARNING

from httpx import HTTPError
from pytest import mark, raises
from starlette.responses import JSONResponse, Response

from heksher import TRACK_ALL
from heksher.clients.async_client import AsyncHeksherClient
from heksher.setting import Setting
from tests.unittest.util import assert_logs

atest = mark.asyncio


@atest
async def test_init_works(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    async with AsyncHeksherClient(fake_heksher_service.local_url(), 10000000, ['a', 'b', 'c']):
        pass


@atest
async def test_declare_before_main(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'outcome': 'created'
    })

    setting = Setting('cache_size', int, ['b', 'c'], 50)
    with fake_heksher_service.query_rules.patch(JSONResponse({
        'settings': {
            'cache_size': {
                'rules': [{'context_features': [['b', '0']], 'value': 100, 'rule_id': 1}], 'default_value': 50
            }
        }
    })):
        async with AsyncHeksherClient(fake_heksher_service.local_url(), 10000000, ['a', 'b', 'c']):
            assert setting.get(b='0', c='') == 100


@atest
async def test_declare_after_main(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'outcome': 'created'
    })

    async with AsyncHeksherClient(fake_heksher_service.local_url(), 10000000, ['a', 'b', 'c']) as client:
        setting = Setting('cache_size', int, ['b', 'c'], 50)
        assert not client._undeclared.empty()
        await client._undeclared.join()
        assert setting.get(b='', c='') == 50

        with fake_heksher_service.query_rules.patch(JSONResponse({
            'settings': {
                'cache_size': {
                    'rules': [{'context_features': [], 'value': 100, 'rule_id': 1}], 'default_value': 100
                }
            }
        })):
            await client.reload()
            assert setting.get(b='', c='') == 100


@atest
async def test_regular_update(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'outcome': 'created'
    })

    setting = Setting('cache_size', int, ['b', 'c'], 50)

    async with AsyncHeksherClient(fake_heksher_service.local_url(), 0.02, ['a', 'b', 'c']):
        assert setting.get(b='', c='') == 50
        with fake_heksher_service.query_rules.patch(JSONResponse({
            'settings': {
                'cache_size': {
                    'rules': [{'context_features': [], 'value': 100, 'rule_id': 1}], 'default_value': 100
                }
            }
        })):
            await sleep(1)
            assert setting.get(b='', c='') == 100


@atest
async def test_heksher_unreachable(caplog):
    setting = Setting('cache_size', int, ['b', 'c'], 50)
    caplog.clear()
    with assert_logs(caplog, ERROR, r'^failure .+'), raises(HTTPError):
        async with AsyncHeksherClient('http://notreal.fake.notreal', 10000000, ['a', 'b', 'c']):
            pass
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

    with assert_logs(caplog, WARNING, 'context feature mismatch'):
        async with AsyncHeksherClient(fake_heksher_service.local_url(), 1000, expected) as client:
            assert client._context_features == expected


@atest
async def test_redundant_defaults(fake_heksher_service, caplog, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'outcome': 'created'
    })

    setting = Setting('cache_size', int, ['b', 'c'], 50)
    with fake_heksher_service.query_rules.patch(JSONResponse({
        'settings': {
            'cache_size': {
                'rules': [{'context_features': [['b', 'B']], 'value': 100, 'rule_id': 1}], 'default_value': 100
            }
        }
    })):
        with assert_logs(caplog, WARNING, r'.+ not specified .+'):
            async with AsyncHeksherClient(fake_heksher_service.local_url(), 1000, ['a', 'b', 'c']) as client:
                client.set_defaults(b='B', d='im redundant')
                assert setting.get(c='') == 100


@atest
async def test_trackcontexts(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c', 'd'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'outcome': 'created'
    })

    setting = Setting('cache_size', int, ['b', 'c'], 50)
    with fake_heksher_service.query_rules.patch(JSONResponse({
        'settings': {
            'cache_size': {
                'rules': [{'context_features': [['b', 'B']], 'value': 100, 'rule_id': 1}], 'default_value': 100
            }
        }
    })), fake_heksher_service.query_rules.capture_calls() as query_calls:
        client = AsyncHeksherClient(fake_heksher_service.local_url(), 100000, ['a', 'b', 'c', 'd'])
        client.track_contexts(b='B', a=['a0', 'a1'], d=TRACK_ALL)

        async with client:
            assert setting.get(b='B', c='') == 100

    query_calls.assert_requested_once_with(
        query_params={'settings': ['cache_size'], 'context_filters': ['a:(a0,a1),b:(B),d:*'],
                      'include_metadata': ['false']}
    )


@atest
async def test_redundant_trackings(caplog):
    client = AsyncHeksherClient('bla', 0, ['a', 'b', 'c'])
    with assert_logs(caplog, WARNING, r'^context features .+'):
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
async def test_outdated_declaration(fake_heksher_service, monkeypatch, caplog):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'outcome': 'outdated',
        'latest_version': '2.0',
        'differences': []
    })

    setting = Setting('cache_size', int, ['b', 'c'], 50)

    with assert_logs(caplog, WARNING, r'.+ outdated .+'):
        async with AsyncHeksherClient(fake_heksher_service.local_url(), 10000000, ['a', 'b', 'c']):
            pass


@atest
async def test_outdated_declaration_different_default(fake_heksher_service, monkeypatch, caplog):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'outcome': 'outdated',
        'latest_version': '2.0',
        'differences': [
            {'level': 'minor', 'attribute': 'default_value', 'latest_value': 100}
        ]
    })

    setting = Setting('cache_size', int, ['b', 'c'], 50)

    with assert_logs(caplog, WARNING, r'.+ outdated .+'):
        async with AsyncHeksherClient(fake_heksher_service.local_url(), 10000000, ['a', 'b', 'c']):
            assert setting.get(b='', c='') == 100


@atest
async def test_upgraded_declaration_different_default(fake_heksher_service, monkeypatch, caplog):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'outcome': 'upgraded',
        'latest_version': '0.5',
        'differences': [
            {'level': 'minor', 'attribute': 'default_value', 'latest_value': 100}
        ]
    })

    setting = Setting('cache_size', int, ['b', 'c'], 50)

    async with AsyncHeksherClient(fake_heksher_service.local_url(), 10000000, ['a', 'b', 'c']):
        assert setting.get(b='', c='') == 50


@atest
async def test_health_OK(fake_heksher_service):
    client = AsyncHeksherClient(fake_heksher_service.local_url(), 1000, ['a', 'b', 'c'])
    await client.ping()
    await client.aclose()


@atest
async def test_health_err(fake_heksher_service, monkeypatch):
    with fake_heksher_service.health.patch(Response(status_code=403)):
        client = AsyncHeksherClient(fake_heksher_service.local_url(), 1000, ['a', 'b', 'c'])
        with raises(HTTPError):
            await client.ping()
        await client.aclose()


@atest
async def test_health_unreachable():
    client = AsyncHeksherClient('http://notreal.fake.notreal', 1000, ['a', 'b', 'c'])
    with raises(HTTPError):
        await client.ping()
    await client.aclose()


@atest
async def test_no_rules(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'outcome': 'created'
    })

    setting = Setting('cache_size', int, ['b', 'c'], 50)
    with fake_heksher_service.query_rules.patch(JSONResponse({
        'settings': {
            'cache_size': {
                'rules': [], 'default_value': 100
            }
        }
    })):
        async with AsyncHeksherClient(fake_heksher_service.local_url(), 10000000, ['a', 'b', 'c']):
            assert setting.get(b='', c='') == 100
