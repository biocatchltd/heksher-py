from asyncio import sleep
from enum import IntFlag, auto
from logging import WARNING

from orjson import orjson
from pytest import mark, raises
from yellowbox_heksher.heksher_service import HeksherService

from heksher import TRACK_ALL, AsyncHeksherClient, Setting
from heksher.clients.util import SettingData
from heksher.setting_type import HeksherFlags, setting_type
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
    with assert_logs(caplog, WARNING):
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

        with assert_logs(caplog, WARNING):
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
        with assert_logs(caplog, WARNING):
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
async def test_flags_setting(heksher_service, add_rules):
    class Color(IntFlag):
        blue = auto()
        red = auto()
        green = auto()

    setting = Setting('c', Color, ['a', 'b', 'c'], default_value=Color(0))

    client = AsyncHeksherClient(heksher_service.local_url, 10000000, ['a', 'b', 'c'])
    client.track_contexts(c='blue')

    async with client:
        add_rules([CreateRuleParams(setting='c', feature_values={'c': 'blue'}, value=['blue', 'green'])])
        await client.reload()
        assert setting.get(a='', b='', c='blue') == Color.green | Color.blue


@mark.asyncio
async def test_flags_setting_coerce(heksher_service, add_rules, caplog):
    class Color(IntFlag):
        blue = auto()
        green = auto()
        red = auto()

    t = setting_type(HeksherFlags(Color))
    heksher_service.http_client.post('api/v1/settings/declare', content=orjson.dumps(
        {'name': 'c',
         'configurable_features': ['a', 'b', 'c'],
         'type': t.heksher_string(),
         'default_value': t.convert_to_heksher(x=Color(2)),
         'version': '1.0'}
    )).raise_for_status()
    heksher_service.http_client.post('api/v1/settings/declare', content=orjson.dumps(
        {'name': 'c',
         'configurable_features': ['a', 'b', 'c'],
         'type': 'Flags["blue", "green", "white"]',
         'default_value': ["white", "blue"],
         'version': '2.0'}
    )).raise_for_status()

    setting = Setting('c', Color, ['a', 'b', 'c'], default_value=Color(2))

    client = AsyncHeksherClient(heksher_service.local_url, 10000000, ['a', 'b', 'c'])
    client.track_contexts(a=TRACK_ALL, b=TRACK_ALL, c=TRACK_ALL)
    caplog.clear()

    with assert_logs(caplog, WARNING):
        async with client:
            add_rules([CreateRuleParams(setting='c', feature_values={'c': 'x'}, value=['green', 'blue', 'white'])])
            await client.reload()
            assert setting.get(a='', b='', c='') == Color.blue
            assert setting.get(a='', b='', c='x') == Color.green | Color.blue


@mark.asyncio
async def test_flags_setting_reject_default(heksher_service, add_rules, caplog):
    heksher_service.http_client.post('api/v1/settings/declare', content=orjson.dumps(
        {'name': 'c',
         'configurable_features': ['a', 'b', 'c'],
         'type': 'Flags["blue", "green", "blank"]',
         'default_value': ["blank"],
         'version': '1.0'}
    )).raise_for_status()

    class Color(IntFlag):
        blue = auto()
        red = auto()
        green = auto()

    c = Setting('c', Color, 'abc', default_value=Color(0))
    client = AsyncHeksherClient(heksher_service.local_url, 1000, ['a', 'b', 'c'])
    client.track_contexts(a='f')
    caplog.clear()
    with assert_logs(caplog, WARNING):
        async with client:
            add_rules([CreateRuleParams(setting='c', feature_values={'a': 'f'}, value=['green', 'blue'])])
            await client.reload()
            assert c.get(a='re', b='', c='') == Color(0)


@mark.asyncio
async def test_flags_setting_reject_context(heksher_service, add_rules, caplog):
    heksher_service.http_client.post('api/v1/settings/declare', content=orjson.dumps(
        {'name': 'c',
         'configurable_features': ['a', 'b', 'c', 'z'],
         'type': 'Flags["blue", "red", "green"]',
         'default_value': [],
         'version': '1.0'}
    )).raise_for_status()

    class Color(IntFlag):
        blue = auto()
        red = auto()
        green = auto()

    c = Setting('c', Color, 'abc', default_value=Color(0))
    client = AsyncHeksherClient(heksher_service.local_url, 1000, ['a', 'b', 'c'])
    client.track_contexts(a='x', b=TRACK_ALL, c=TRACK_ALL)
    caplog.clear()
    with assert_logs(caplog, WARNING):
        async with client:
            add_rules([CreateRuleParams(setting='c', feature_values={'a': 'x', 'z': 'foo'}, value=['green', 'red'])])
            add_rules([CreateRuleParams(setting='c', feature_values={'a': 'x'}, value=['green', 'blue'])])
            await client.reload()
            assert c.get(a='x', b='', c='') == Color.green | Color.blue


@mark.asyncio
async def test_get_setting(heksher_service, caplog):
    setting = Setting('foo', type=int, configurable_features=['a', 'b'], default_value=5)

    async with AsyncHeksherClient(heksher_service.local_url, 10000000, ['a', 'b', 'c']) as client:
        response = await client.get_settings()
        assert response == {"foo": SettingData(name="foo",
                                               configurable_features=['a', 'b'],
                                               type='int',
                                               default_value=5,
                                               metadata={}, aliases=[], version='1.0')}


@mark.asyncio
async def test_switch_main_from_temp(heksher_service, add_rules):
    setting1 = Setting('conf1', int, ['a'], 74)
    client = AsyncHeksherClient(heksher_service.local_url, 10000000, ['a', 'b'])
    client.track_contexts(a=['x', 'y'], b=TRACK_ALL)
    setting2 = Setting('conf2', int, ['b'], 26)
    await client.set_as_main()

    add_rules([
        CreateRuleParams(setting='conf1', feature_values={'a': 'x'}, value=5),
        CreateRuleParams(setting='conf2', feature_values={'b': 'y'}, value=4)
    ])
    await client.reload()
    assert setting1.get(a='x') == 5
    assert setting2.get(b='y') == 4
    await client.aclose()


@mark.asyncio
async def test_switch_main(heksher_service, add_rules, caplog):
    setting1 = Setting('conf1', int, ['a'], 74)
    setting2 = Setting('conf2', int, ['b'], 26)
    client1 = AsyncHeksherClient(heksher_service.local_url, 10000000, ['a', 'b'])
    client1.track_contexts(a=['x', 'y'], b=TRACK_ALL)
    async with client1:
        add_rules([
            CreateRuleParams(setting='conf1', feature_values={'a': 'x'}, value=5),
            CreateRuleParams(setting='conf2', feature_values={'b': 'y'}, value=4)
        ])
        await client1.reload()
        assert len(client1._tracked_settings) == 2
        assert setting1.get(a='x') == 5
        assert setting2.get(b='y') == 4

    client2 = AsyncHeksherClient(heksher_service.local_url, 10000000, ['a', 'b'])
    client2.track_contexts(a=['w', 'z'], b=TRACK_ALL)
    with assert_logs(caplog, WARNING):  # it should warn you you're doing bad things
        await client2.set_as_main()
    setting3 = Setting('conf3', int, ['b'], 59)
    await client2._undeclared.join()
    add_rules([
        CreateRuleParams(setting='conf1', feature_values={'a': 'w'}, value=6),
        CreateRuleParams(setting='conf2', feature_values={'b': 's'}, value=7),
        CreateRuleParams(setting='conf3', feature_values={'b': 'z'}, value=10)
    ])
    await client2.reload()
    assert setting1.get(a='w') == 6
    assert setting2.get(b='s') == 7
    assert setting3.get(b='z') == 10
    await client2.aclose()


@mark.asyncio
async def test_switch_main_different_tracking(heksher_service, add_rules, caplog):
    setting1 = Setting('conf1', int, ['a'], 74)
    setting2 = Setting('conf2', int, ['b'], 26)
    client1 = AsyncHeksherClient(heksher_service.local_url, 10000000, ['a', 'b'])
    client1.track_contexts(a=['x', 'y'], b=TRACK_ALL)
    async with client1:
        add_rules([
            CreateRuleParams(setting='conf1', feature_values={'a': 'x'}, value=5),
            CreateRuleParams(setting='conf2', feature_values={'b': 'walla'}, value=4)
        ])
        await client1.reload()
        assert len(client1._tracked_settings) == 2
        assert setting1.get(a='x') == 5
        assert setting2.get(b='walla') == 4

    client2 = AsyncHeksherClient(heksher_service.local_url, 10000000, ['a', 'b'])
    client2.track_contexts(a=['x', 'y', 'z'], b="shoobidoobi")
    with assert_logs(caplog, WARNING):  # it should warn you you're doing bad things, and that your tracking differs
        await client2.set_as_main()

    setting3 = Setting('conf3', int, ['b'], 59)
    await client2._undeclared.join()
    add_rules([
        CreateRuleParams(setting='conf3', feature_values={'b': 'shoobidoobi'}, value=8),
    ])
    await client2.reload()
    assert len(client2._tracked_settings) == 3
    assert setting1.get(a='x') == 5
    assert setting3.get(b='shoobidoobi') == 8
    await client2.aclose()


@mark.asyncio
async def test_switch_main_different_contexts(heksher_service, add_rules):
    setting1 = Setting('conf1', int, ['a'], 74)
    setting2 = Setting('conf2', int, ['b'], 26)
    client1 = AsyncHeksherClient(heksher_service.local_url, 10000000, ['a', 'b'])
    client1.track_contexts(a=['x', 'y'], b=TRACK_ALL)
    async with client1:
        add_rules([
            CreateRuleParams(setting='conf1', feature_values={'a': 'x'}, value=5),
            CreateRuleParams(setting='conf2', feature_values={'b': 'walla'}, value=4)
        ])

        await client1.reload()
        assert len(client1._tracked_settings) == 2
        assert setting1.get(a='x') == 5
        assert setting2.get(b='walla') == 4

    client2 = AsyncHeksherClient(heksher_service.local_url, 10000000, ['a', 'b', 'c', 'd'])
    client2.track_contexts(a=['x', 'y'], b=TRACK_ALL)
    with raises(RuntimeError):  # not allowed
        await client2.set_as_main()
    await client2.aclose()


@mark.asyncio
async def test_switch_main_unclosed(heksher_service):
    setting1 = Setting('conf1', int, ['a'], 74)
    client1 = AsyncHeksherClient(heksher_service.local_url, 10000000, ['a', 'b'])
    client1.track_contexts(a=['a', 'b'], b=TRACK_ALL)
    await client1.set_as_main()
    await client1.aclose()
    setting2 = Setting('conf2', int, ['b'], 26)
    client2 = AsyncHeksherClient(heksher_service.local_url, 10000000, ['a', 'b'])
    client2.track_contexts(a=['a', 'b'], b=TRACK_ALL)
    with raises(RuntimeError):  # not allowed
        await client2.set_as_main()
    await client2.aclose()


@mark.asyncio
async def test_no_rules(heksher_service):
    setting = Setting('cache_size', int, ['b', 'c'], 100)
    async with AsyncHeksherClient(heksher_service.local_url, 10000000, ['a', 'b', 'c']):
        assert setting.get(b='', c='') == 100


@mark.asyncio
async def test_flags_setting_validator(heksher_service, add_rules):
    class Color(IntFlag):
        blue = auto()
        red = auto()
        green = auto()

    c = Setting('c', Color, 'abc', default_value=Color(0))

    @c.add_validator
    def add_red(value, *_):
        return value | Color.red

    client = AsyncHeksherClient(heksher_service.local_url, 1000, ['a', 'b', 'c'])
    client.track_contexts(a='x', b=TRACK_ALL, c=TRACK_ALL)
    async with client:
        add_rules([CreateRuleParams(setting='c', feature_values={'a': 'x'}, value=['green', 'blue'])])
        await client.reload()
        assert c.get(a='x', b='', c='') == Color.green | Color.blue | Color.red
        assert c.get(a='y', b='', c='') == Color.red
