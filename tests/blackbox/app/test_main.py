from asyncio import sleep
from logging import WARNING

from pytest import mark
from yellowbox_heksher.heksher_service import HeksherService

from heksher import AsyncHeksherClient, Setting
from tests.blackbox.app.utils import CreateRuleParams
from tests.unittest.util import assert_logs


@mark.asyncio
async def test_health_check(heksher_service):
    heksher_service.http_client.get('/api/health').raise_for_status()
    assert heksher_service.postgres_service.is_alive()


@mark.asyncio
async def test_init_works(heksher_service: HeksherService):
    resp = heksher_service.http_client.post('/api/v1/context_features', json={'context_feature': 'razi'})
    resp.raise_for_status()

    res = heksher_service.http_client.get('/api/v1/context_features')
    res.raise_for_status()

    client = AsyncHeksherClient(heksher_service.local_url, 10000000, ['a', 'b', 'c'])
    await client.aclose()


@mark.asyncio
async def test_get_setting_names(heksher_service: HeksherService):
    settings = (
        Setting("test_config", type=int, configurable_features=['a', 'b', 'c'], default_value=1,
                metadata={"description": "test"})
    )
    heksher = AsyncHeksherClient(heksher_service.local_url, update_interval=60, context_features=['a', 'b', 'c'])
    await heksher.set_as_main()  # we only want to declare settings
    await heksher.aclose()

    assert heksher_service.get_setting_names() == ["test_config"]


@mark.asyncio
async def test_declare_before_main(heksher_service, monkeypatch, add_rules):
    setting = Setting('cache_size', type=int, configurable_features=['b', 'c'], default_value=50)

    client = AsyncHeksherClient(heksher_service.local_url, 10000000, ['a', 'b', 'c'])
    await client.set_as_main()
    client.track_contexts(b='0')

    await add_rules([CreateRuleParams(setting='cache_size', feature_values={'b': '0'}, value=100)])
    await client.reload()
    assert setting.get(b='0', c='') == 100
    await client.aclose()


@mark.asyncio
async def test_declare_after_main(heksher_service, monkeypatch, add_rules):
    client = AsyncHeksherClient(heksher_service.local_url, 10000000, ['a', 'b', 'c'])
    await client.set_as_main()
    setting = Setting('cache_size', type=int, configurable_features=['b', 'c'], default_value=50)
    assert not client._undeclared.empty()
    await client._undeclared.join()
    assert setting.get(b='', c='') == 50
    client.track_contexts(b='5')
    await add_rules([CreateRuleParams(setting='cache_size', feature_values={'b': '5'}, value=100)])
    await client.reload()
    assert setting.get(b='5', c='') == 100
    await client.aclose()


@mark.asyncio
async def test_regular_update(heksher_service, monkeypatch, add_rules):
    setting = Setting('cache_size', type=int, configurable_features=['b', 'c'], default_value=50)

    client = AsyncHeksherClient(heksher_service.local_url, 0.02, ['a', 'b', 'c'])
    await client.set_as_main()
    client.track_contexts(b='0')

    await add_rules([CreateRuleParams(setting='cache_size', feature_values={'b': '0'}, value=100)])
    await sleep(1)
    assert setting.get(b='0', c='') == 100
    await client.aclose()


@mark.asyncio
@mark.parametrize('expected', [
    [],
    ['a'],
    ['b', 'a'],
    ['a', 'b', 'c', 'd'],
    ['e', 'f', 'g']
])
async def test_cf_mismatch(heksher_service, caplog, monkeypatch, expected):
    print(f"!!!!{expected=}")
    with assert_logs(caplog, WARNING):
        async with AsyncHeksherClient(heksher_service.local_url, 1000, expected) as client:
            assert client._context_features == expected


@mark.asyncio
async def test_redundant_defaults(heksher_service, add_rules, caplog):
    setting = Setting('cache_size', type=int, configurable_features=['b', 'c'], default_value=50)
    client = AsyncHeksherClient(heksher_service.local_url, 10000000, ['a', 'b', 'c'])
    await client.set_as_main()

    client.track_contexts(b='B')
    await add_rules([CreateRuleParams(setting='cache_size', feature_values={'b': 'B'}, value=100)])
    await client.reload()

    with assert_logs(caplog, WARNING):
        client.set_defaults(b='B', d='im redundant')
        assert setting.get(c='') == 100
    await client.aclose()
