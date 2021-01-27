import gc
from weakref import ref
from logging import WARNING

from pytest import raises

import heksher.main_client
from heksher.clients.stub import SyncStubHeksherClient, Rule
from heksher.exceptions import NoMatchError
from heksher.heksher_client import TemporaryClient
from heksher.setting import Setting
from tests.unittest.util import assert_logs, assert_no_logs


def test_resolve():
    a = Setting('a', int, 'abc', default_value=-1)
    with SyncStubHeksherClient() as client, \
            client.patch(a, [
                Rule({'x': '0'}, 0),
                Rule({'x': '1'}, 1)
            ]):
        assert a.get(x='0') == 0
        assert a.get(x='1') == 1
        assert a.get(x='15') == -1
        with raises(RuntimeError):
            a.get()

        client.set_defaults(x='0')
        assert a.get(x='1') == 1


def test_resolve_nodefault():
    a = Setting('a', int, 'abc')
    with SyncStubHeksherClient() as client, \
            client.patch(a, [
                Rule({'x': '0'}, 0),
                Rule({'x': '1'}, 1)
            ]):
        assert a.get(x='0') == 0
        assert a.get(x='1') == 1
        with raises(NoMatchError):
            a.get(x='15')


def test_multi_update():
    a = Setting('a', int, 'abc', default_value=-1)
    with SyncStubHeksherClient() as client:
        client.patch(a, 10)
        assert a.get() == 10
        with client.patch(a, [
            Rule({'x': '0'}, 0),
            Rule({'x': '1'}, 1)
        ]):
            assert a.get(x='0') == 0
            assert a.get(x='1') == 1
            assert a.get(x='15') == -1
        assert a.get(x='0') == 10


def test_nested_update():
    a = Setting('a', int, 'abc', default_value=-1)
    with SyncStubHeksherClient() as client:
        assert a.get() == -1
        with client.patch(a, 0):
            assert a.get() == 0
            with client.patch(a, 1):
                assert a.get() == 1
            assert a.get() == 0
        assert a.get() == -1


def test_multi_switch(caplog):
    a = Setting('a', int, 'abc', default_value=-1)
    c1 = SyncStubHeksherClient()
    c1.set_as_main()
    c1.patch(a, 10)
    assert a.get() == 10
    heksher.main_client.Main = TemporaryClient()

    c2 = SyncStubHeksherClient()
    c2.set_as_main()
    with assert_logs(caplog, WARNING):
        c2.patch(a, [
            Rule({'x': '0'}, 0),
            Rule({'x': '1'}, 1)
        ])
    assert a.get(x='0') == 0
    assert a.get(x='1') == 1
    assert a.get(x='15') == -1


def test_multi_switch_safe(caplog):
    a = Setting('a', int, 'abc', default_value=-1)
    c1 = SyncStubHeksherClient()
    ref1 = ref(c1)
    c1.set_as_main()
    c1.patch(a, 10)
    assert a.get() == 10
    heksher.main_client.Main = TemporaryClient()
    del c1
    gc.collect(0)
    assert not ref1()

    c2 = SyncStubHeksherClient()
    c2.set_as_main()
    with assert_no_logs(caplog, WARNING):
        c2.patch(a, [
            Rule({'x': '0'}, 0),
            Rule({'x': '1'}, 1)
        ])
    assert a.get(x='0') == 0
    assert a.get(x='1') == 1
    assert a.get(x='15') == -1
