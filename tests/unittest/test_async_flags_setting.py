from enum import IntFlag, auto
from logging import WARNING

from pytest import mark
from starlette.responses import JSONResponse

from heksher.clients.async_client import AsyncHeksherClient
from heksher.clients.util import SettingData
from heksher.setting import Setting
from tests.unittest.util import assert_logs

atest = mark.asyncio


@atest
async def test_get_settings(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    settings = {'settings': [
        {
            'name': 'foo',
            'configurable_features': ['a', 'b'],
            'type': 'int',
            'default_value': None,
            'metadata': {},
            'aliases': [],
            'version': '1.0',
        }
    ]}
    with fake_heksher_service.get_settings.patch(JSONResponse(settings)):
        async with AsyncHeksherClient(fake_heksher_service.local_url(), 10000000, ['a', 'b', 'c']) as client:
            response = await client.get_settings()
            assert response == {"foo": SettingData(name="foo",
                                                   configurable_features=['a', 'b'],
                                                   type='int',
                                                   default_value=None,
                                                   metadata={}, aliases=[], version='1.0')}


@atest
async def test_flags_setting(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'c', {
        'outcome': 'created'
    })

    class Color(IntFlag):
        blue = auto()
        red = auto()
        green = auto()

    c = Setting('c', Color, 'abc', default_value=Color(0))
    with fake_heksher_service.query_rules.patch(JSONResponse({
        'settings': {
            'c': {
                'rules': [{'context_features': [], 'value': ['green', 'blue'], 'rule_id': 1}],
                'default_value': []
            }
        }
    })):
        async with AsyncHeksherClient(fake_heksher_service.local_url(), 1000, ['a', 'b', 'c']):
            assert c.get(a='', b='', c='') == Color.green | Color.blue


@atest
async def test_flags_setting_coerce(fake_heksher_service, monkeypatch, caplog):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'c', {
        'outcome': 'created'
    })

    class Color(IntFlag):
        blue = auto()
        red = auto()
        green = auto()

    c = Setting('c', Color, 'abc', default_value=Color(3))
    with fake_heksher_service.query_rules.patch(JSONResponse({
        'settings': {
            'c': {
                'rules': [{'context_features': [], 'value': ['green', 'blue', 'white'], 'rule_id': 1}],
                'default_value': ['white']
            }
        }
    })):
        caplog.clear()
        with assert_logs(caplog, WARNING, r'.+ coerced .+'):
            async with AsyncHeksherClient(fake_heksher_service.local_url(), 1000, ['a', 'b', 'c']):
                assert c.get(a='', b='', c='') == Color.green | Color.blue


@atest
async def test_flags_setting_coerce_default(fake_heksher_service, monkeypatch, caplog):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'c', {
        'outcome': 'created'
    })

    class Color(IntFlag):
        blue = auto()
        red = auto()
        green = auto()

    c = Setting('c', Color, 'abc', default_value=Color(0))
    with fake_heksher_service.query_rules.patch(JSONResponse({
        'settings': {
            'c': {
                'rules': [{'context_features': [['a', 'f']], 'value': ['green', 'blue'], 'rule_id': 1}],
                'default_value': ['white', 'blue']
            }
        }
    })):
        caplog.clear()
        with assert_logs(caplog, WARNING, r'.+ default value coerced .+'):
            async with AsyncHeksherClient(fake_heksher_service.local_url(), 1000, ['a', 'b', 'c']):
                assert c.get(a='re', b='', c='') == Color.blue


@atest
async def test_flags_setting_reject_value(fake_heksher_service, monkeypatch, caplog):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'c', {
        'outcome': 'created'
    })

    class Color(IntFlag):
        blue = auto()
        red = auto()
        green = auto()

    c = Setting('c', Color, 'abc', default_value=Color(0))
    with fake_heksher_service.query_rules.patch(JSONResponse({
        'settings': {
            'c': {
                'rules': [{'context_features': [['a', 'x']], 'value': ['green', 'blue'], 'rule_id': 1},
                          {'context_features': [['a', 'y']], 'value': ['green', 'blue', ['abc']], 'rule_id': 2}],
                'default_value': []
            }
        }
    })):
        caplog.clear()
        with assert_logs(caplog, WARNING, r'.+ rejected .+'):
            async with AsyncHeksherClient(fake_heksher_service.local_url(), 1000, ['a', 'b', 'c']):
                assert c.get(a='x', b='', c='') == Color.green | Color.blue


@atest
async def test_flags_setting_reject_default(fake_heksher_service, monkeypatch, caplog):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'c', {
        'outcome': 'created'
    })

    class Color(IntFlag):
        blue = auto()
        red = auto()
        green = auto()

    c = Setting('c', Color, 'abc', default_value=Color(0))
    with fake_heksher_service.query_rules.patch(JSONResponse({
        'settings': {
            'c': {
                'rules': [{'context_features': [['a', 'f']], 'value': ['green', 'blue'], 'rule_id': 1}],
                'default_value': ['blank']
            }
        }
    })):
        caplog.clear()
        with assert_logs(caplog, WARNING, r'.+ default value coerced .+'):
            async with AsyncHeksherClient(fake_heksher_service.local_url(), 1000, ['a', 'b', 'c']):
                assert c.get(a='re', b='', c='') == Color(0)


@atest
async def test_flags_setting_reject_context(fake_heksher_service, monkeypatch, caplog):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'c', {
        'outcome': 'created'
    })

    class Color(IntFlag):
        blue = auto()
        red = auto()
        green = auto()

    c = Setting('c', Color, 'abc', default_value=Color(0))
    with fake_heksher_service.query_rules.patch(JSONResponse({
        'settings': {
            'c': {
                'rules': [{'context_features': [['a', 'x'], ['z', 'foo']], 'value': ['green', 'red'], 'rule_id': 1},
                          {'context_features': [['a', 'x']], 'value': ['green', 'blue'], 'rule_id': 2}],
                'default_value': []
            }
        }
    })):
        caplog.clear()
        with assert_logs(caplog, WARNING, r'.+ rejected .+'):
            async with AsyncHeksherClient(fake_heksher_service.local_url(), 1000, ['a', 'b', 'c']):
                assert c.get(a='x', b='', c='') == Color.green | Color.blue


@atest
async def test_flags_setting_validator(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'c', {
        'outcome': 'created'
    })

    class Color(IntFlag):
        blue = auto()
        red = auto()
        green = auto()

    c = Setting('c', Color, 'abc', default_value=Color(0))

    @c.add_validator
    def add_red(value, *_):
        return value | Color.red

    with fake_heksher_service.query_rules.patch(JSONResponse({
        'settings': {
            'c': {
                'rules': [{'context_features': [['a', 'x']], 'value': ['green', 'blue'], 'rule_id': 1}],
                'default_value': []
            }
        }
    })):
        async with AsyncHeksherClient(fake_heksher_service.local_url(), 1000, ['a', 'b', 'c']):
            assert c.get(a='x', b='', c='') == Color.green | Color.blue | Color.red
            assert c.get(a='y', b='', c='') == Color.red
