from enum import IntFlag, auto
from logging import WARNING

from orjson import orjson
from pytest import mark

from heksher import TRACK_ALL, AsyncHeksherClient, Setting
from heksher.clients.util import SettingData
from heksher.setting_type import HeksherFlags, setting_type
from tests.blackbox.app.utils import CreateRuleParams
from tests.unittest.util import assert_logs


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

    with assert_logs(caplog, WARNING, r'.+ coerced .+'):
        async with client:
            add_rules([CreateRuleParams(setting='c', feature_values={'c': 'x'}, value=['green', 'blue', 'white'])])
            await client.reload()
            assert setting.get(a='', b='', c='') == Color.blue
            assert setting.get(a='', b='', c='x') == Color.green | Color.blue


@mark.asyncio
async def test_flags_setting_coerce_default(heksher_service, monkeypatch, caplog):
    heksher_service.http_client.post('api/v1/settings/declare', content=orjson.dumps(
        {'name': 'c',
         'configurable_features': ['a', 'b', 'c'],
         'type': 'Flags["blue", "green", "white"]',
         'default_value': ['white', 'blue'],
         'version': '1.0'}
    )).raise_for_status()

    class Color(IntFlag):
        blue = auto()
        red = auto()
        green = auto()

    c = Setting('c', Color, 'abc', default_value=Color(0))

    caplog.clear()
    with assert_logs(caplog, WARNING, r'^conflict .+'), assert_logs(caplog, WARNING, r'.+ default value coerced .+'):
        async with AsyncHeksherClient(heksher_service.local_url, 1000, ['a', 'b', 'c']):
            assert c.get(a='re', b='', c='') == Color.blue


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
    client.track_contexts(a=TRACK_ALL, b=TRACK_ALL, c=TRACK_ALL)
    caplog.clear()
    with assert_logs(caplog, WARNING, r'^conflict .+'), assert_logs(caplog, WARNING, r'.+ coerced .+'):
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
    with assert_logs(caplog, WARNING, r'^conflict .+'):
        async with client:
            add_rules([CreateRuleParams(setting='c', feature_values={'a': 'x', 'z': 'foo'}, value=['green', 'red'])])
            add_rules([CreateRuleParams(setting='c', feature_values={'a': 'x'}, value=['green', 'blue'])])
            await client.reload()
            assert c.get(a='x', b='', c='') == Color.green | Color.blue


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
