import gc
from logging import WARNING
from weakref import ref

from pytest import raises

import heksher.main_client
from heksher.clients.stub import Rule, SyncStubHeksherClient
from heksher.heksher_client import TemporaryClient
from heksher.setting import Setting
from tests.unittest.util import assert_logs, assert_no_logs


def test_resolve():
    a = Setting('a', int, 'abcx', default_value=-1)
    with SyncStubHeksherClient() as client, \
            client.patch(a, [
                Rule({'x': '0'}, 0),
                Rule({'x': '1'}, 1)
            ]):
        client.set_defaults(a='', b='', c='')
        assert a.get(x='0') == 0
        assert a.get(x='1') == 1
        assert a.get(x='15') == -1
        with raises(RuntimeError):
            a.get()

        client.set_defaults(x='0')
        assert a.get(x='1') == 1


def test_multi_update():
    a = Setting('a', int, 'abcx', default_value=-1)
    with SyncStubHeksherClient() as client:
        client.set_defaults(a='', b='', c='')
        client.patch(a, 10)
        assert a.get(x='') == 10
        with client.patch(a, [
            Rule({'x': '0'}, 0),
            Rule({'x': '1'}, 1)
        ]):
            assert a.get(x='0') == 0
            assert a.get(x='1') == 1
            assert a.get(x='15') == -1
        assert a.get(x='0') == 10


def test_nested_update():
    a = Setting('a', int, 'abcx', default_value=-1)
    with SyncStubHeksherClient() as client:
        client.set_defaults(a='', b='', c='', x='')
        assert a.get() == -1
        with client.patch(a, 0):
            assert a.get() == 0
            with client.patch(a, 1):
                assert a.get() == 1
            assert a.get() == 0
        assert a.get() == -1


def test_multi_switch(caplog):
    a = Setting('a', int, 'abcx', default_value=-1)
    c1 = SyncStubHeksherClient()
    c1.set_defaults(a='', b='', c='')
    c1.set_as_main()
    c1.patch(a, 10)
    assert a.get(x='') == 10
    heksher.main_client.Main = TemporaryClient()

    c2 = SyncStubHeksherClient()
    c2.set_defaults(a='', b='', c='')
    c2.set_as_main()
    with assert_logs(caplog, WARNING, r'.+ multiple clients'):
        c2.patch(a, [
            Rule({'x': '0'}, 0),
            Rule({'x': '1'}, 1)
        ])
    assert a.get(x='0') == 0
    assert a.get(x='1') == 1
    assert a.get(x='15') == -1


def test_multi_switch_safe(caplog):
    a = Setting('a', int, 'abcx', default_value=-1)
    c1 = SyncStubHeksherClient()
    c1.set_defaults(a='', b='', c='')
    ref1 = ref(c1)
    c1.set_as_main()
    c1.patch(a, 10)
    assert a.get(x='') == 10
    heksher.main_client.Main = TemporaryClient()
    del c1
    gc.collect(0)
    assert not ref1()

    c2 = SyncStubHeksherClient()
    c2.set_defaults(a='', b='', c='')
    c2.set_as_main()
    with assert_no_logs(caplog, WARNING):
        c2.patch(a, [
            Rule({'x': '0'}, 0),
            Rule({'x': '1'}, 1)
        ])
    assert a.get(x='0') == 0
    assert a.get(x='1') == 1
    assert a.get(x='15') == -1


def test_useless_vals():
    a = Setting('a', int, 'abcx', default_value=-1)
    with raises(ValueError):
        a.get(a='', b='', c='', x='', d='')


def test_setting_callback_stub():
    # stubs don't trigger conversion
    a = Setting('a', int, 'abcx', default_value=-1)

    def setting_callback_1(value: int, rule, setting: Setting) -> int:
        if setting.name == 'a' and value == 10:
            return 12
        return value

    def setting_callback_2(value: int, rule, setting: Setting) -> int:
        if setting.name == 'a' and value == 12:
            return 7
        return value

    a.add_validator(setting_callback_1)
    a.add_validator(setting_callback_2)
    c1 = SyncStubHeksherClient()
    c1.set_as_main()
    c1.set_defaults(a='', b='', c='', x='')
    c1.patch(a, 10)
    assert a.get() == 10


def test_setting_rules_collection_callback():
    a = Setting('a', int, 'abcx', default_value=-1)

    def setting_callback_1(value: int, rule, setting: Setting) -> int:
        if setting.name == 'a' and value == 0:
            return 3
        return value

    def setting_callback_2(value: int, rule, setting: Setting) -> int:
        if setting.name == 'a' and value == 3:
            return 7
        return value

    a.add_validator(setting_callback_1)
    a.add_validator(setting_callback_2)
    c1 = SyncStubHeksherClient()
    c1.set_as_main()
    c1.set_defaults(a='', b='', c='', x='')

    c1.patch(a, [
        Rule({'x': '0'}, 0)
    ])
    assert a.get(x='0') == 0
    assert a.get(x='1') == -1


def test_v1_body():
    a = Setting('aaa', int, 'abcx', default_value=-1, metadata={"some": "thing"}, alias='aaaa', version='3.6')
    assert a.to_v1_declaration_body() == {
        'name': 'aaa',
        'configurable_features': list('abcx'),
        'type': 'int',
        'metadata': {"some": "thing"},
        'alias': 'aaaa',
        'default_value': -1,
        'version': '3.6',
    }
