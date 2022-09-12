from asyncio import sleep
from logging import WARNING

from orjson import orjson
from pytest import mark
from yellowbox_heksher.heksher_service import HeksherService

from heksher import TRACK_ALL, AsyncHeksherClient, Setting
from tests.blackbox.app.utils import CreateRuleParams
from tests.unittest.util import assert_logs


@mark.asyncio
async def test_health_check(heksher_service):
    heksher_service.http_client.get('/api/health').raise_for_status()
    assert heksher_service.postgres_service.is_alive()


@mark.asyncio
async def test_init_works(heksher_service: HeksherService):
    heksher_service.http_client.post('/api/v1/context_features', json={'context_feature': 'context'})
    async with AsyncHeksherClient(heksher_service.local_url, 10000000, ['a', 'b', 'c']):
        pass


@mark.asyncio
async def test_get_setting_names(heksher_service: HeksherService):
    settings = (
        Setting("test_config", type=int, configurable_features=['a', 'b', 'c'], default_value=1,
                metadata={"description": "test"})
    )
    async with AsyncHeksherClient(heksher_service.local_url, update_interval=60,
                                  context_features=['a', 'b', 'c']) as client:
        assert heksher_service.get_setting_names() == ["test_config"]


@mark.asyncio
async def test_declare_before_main(heksher_service, monkeypatch, add_rules):
    setting = Setting('cache_size', type=int, configurable_features=['b', 'c'], default_value=50)

    client = AsyncHeksherClient(heksher_service.local_url, 10000000, ['a', 'b', 'c'])
    client.track_contexts(b='0')

    async with client:
        add_rules([CreateRuleParams(setting='cache_size', feature_values={'b': '0'}, value=100)])
        await client.reload()
        assert setting.get(b='0', c='') == 100


@mark.asyncio
async def test_declare_after_main(heksher_service, add_rules):
    client = AsyncHeksherClient(heksher_service.local_url, 10000000, ['a', 'b', 'c'])
    client.track_contexts(b='5')

    async with client:
        setting = Setting('cache_size', type=int, configurable_features=['b', 'c'], default_value=50)
        assert not client._undeclared.empty()
        await client._undeclared.join()
        assert setting.get(b='', c='') == 50
        add_rules([CreateRuleParams(setting='cache_size', feature_values={'b': '5'}, value=100)])
        await client.reload()
        assert setting.get(b='5', c='') == 100


@mark.asyncio
async def test_regular_update(heksher_service, add_rules):
    setting = Setting('cache_size', type=int, configurable_features=['b', 'c'], default_value=50)
    client = AsyncHeksherClient(heksher_service.local_url, 0.02, ['a', 'b', 'c'])
    client.track_contexts(b='0')

    async with client:
        add_rules([CreateRuleParams(setting='cache_size', feature_values={'b': '0'}, value=100)])
        await sleep(0.1)
        assert setting.get(b='0', c='') == 100


@mark.asyncio
@mark.parametrize('expected', [
    [],
    ['a'],
    ['b', 'a'],
    ['a', 'b', 'c', 'd'],
    ['e', 'f', 'g']
])
async def test_cf_mismatch(heksher_service, caplog, expected):
    with assert_logs(caplog, WARNING, 'context feature mismatch'):
        async with AsyncHeksherClient(heksher_service.local_url, 1000, expected) as client:
            assert client._context_features == expected


@mark.asyncio
async def test_redundant_defaults(heksher_service, add_rules, caplog):
    setting = Setting('cache_size', type=int, configurable_features=['b', 'c'], default_value=50)
    client = AsyncHeksherClient(heksher_service.local_url, 10000000, ['a', 'b', 'c'])
    client.track_contexts(b='B')

    async with client:
        add_rules([CreateRuleParams(setting='cache_size', feature_values={'b': 'B'}, value=100)])
        await client.reload()

        with assert_logs(caplog, WARNING, r'.+ not specified .+'):
            client.set_defaults(b='B', d='im redundant')
            assert setting.get(c='') == 100


@mark.asyncio
async def test_trackcontexts(heksher_service, add_rules):
    setting = Setting('cache_size', int, ['b', 'c'], 50)
    client = AsyncHeksherClient(heksher_service.local_url, 10000000, ['a', 'b', 'c'])
    client.track_contexts(b='B', a=TRACK_ALL)

    async with client:
        add_rules([CreateRuleParams(setting='cache_size', feature_values={'b': 'B'}, value=100)])
        await client.reload()
        assert setting.get(b='B', c='') == 100


@mark.asyncio
async def test_outdated_declaration(heksher_service, caplog):
    heksher_service.http_client.post('api/v1/settings/declare', content=orjson.dumps(
        {'name': 'cache_size',
         'type': 'int',
         'configurable_features': ['a', 'b', 'c'],
         'default_value': 70,
         'version': '1.0'}
    )).raise_for_status()
    heksher_service.http_client.post('api/v1/settings/declare', content=orjson.dumps(
        {'name': 'cache_size',
         'type': 'int',
         'configurable_features': ['a', 'b', 'c'],
         'default_value': 60,
         'version': '2.0'}
    )).raise_for_status()

    async with AsyncHeksherClient(heksher_service.local_url, 10000000, ['a', 'b', 'c']) as client:
        with assert_logs(caplog, WARNING, r'.+ outdated .+'):
            setting = Setting('cache_size', type=int, configurable_features=['a', 'b'], default_value=80, version='1.0')
            await client._undeclared.join()
            assert setting.get(a='', b='') == 60


@mark.asyncio
async def test_upgraded_declaration(heksher_service, caplog):
    setting = Setting('cache_size', type=int, configurable_features=['a', 'b', 'c'], default_value=50,
                      version='1.0')

    async with AsyncHeksherClient(heksher_service.local_url, 10000000, ['a', 'b', 'c']) as client:
        setting = Setting('cache_size', type=int, configurable_features=['a', 'b'], default_value=80, version='2.0')
        await client._undeclared.join()
        assert setting.get(b='') == 80


@mark.asyncio
async def test_no_rules(heksher_service):
    setting = Setting('cache_size', int, ['b', 'c'], 100)
    async with AsyncHeksherClient(heksher_service.local_url, 10000000, ['a', 'b', 'c']):
        assert setting.get(b='', c='') == 100
