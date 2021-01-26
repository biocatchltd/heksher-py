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
    with SyncStubHeksherClient() as client:
        client[a] = [
            Rule({'x': '0'}, 0),
            Rule({'x': '1'}, 1)
        ]
        assert a.get(x='0') == 0
        assert a.get(x='1') == 1
        assert a.get(x='15') == -1
        with raises(RuntimeError):
            a.get()

        client.set_defaults(x='0')
        assert a.get(x='1') == 1


def test_resolve_nodefault():
    a = Setting('a', int, 'abc')
    with SyncStubHeksherClient() as client:
        client[a] = [
            Rule({'x': '0'}, 0),
            Rule({'x': '1'}, 1)
        ]
        assert a.get(x='0') == 0
        assert a.get(x='1') == 1
        with raises(NoMatchError):
            a.get(x='15')


def test_multi_update():
    a = Setting('a', int, 'abc', default_value=-1)
    with SyncStubHeksherClient() as client:
        client[a] = 10
        assert a.get() == 10
        client[a] = [
            Rule({'x': '0'}, 0),
            Rule({'x': '1'}, 1)
        ]
        assert a.get(x='0') == 0
        assert a.get(x='1') == 1
        assert a.get(x='15') == -1


def test_multi_switch(caplog):
    a = Setting('a', int, 'abc', default_value=-1)
    c1 = SyncStubHeksherClient()
    c1.set_as_main()
    c1[a] = 10
    assert a.get() == 10
    heksher.main_client.Main = TemporaryClient()

    c2 = SyncStubHeksherClient()
    c2.set_as_main()
    with assert_logs(caplog, WARNING):
        c2[a] = [
            Rule({'x': '0'}, 0),
            Rule({'x': '1'}, 1)
        ]
    assert a.get(x='0') == 0
    assert a.get(x='1') == 1
    assert a.get(x='15') == -1


def test_multi_switch_safe(caplog):
    a = Setting('a', int, 'abc', default_value=-1)
    c1 = SyncStubHeksherClient()
    ref1 = ref(c1)
    c1.set_as_main()
    c1[a] = 10
    assert a.get() == 10
    heksher.main_client.Main = TemporaryClient()
    del c1
    gc.collect(0)
    assert not ref1()

    c2 = SyncStubHeksherClient()
    c2.set_as_main()
    with assert_no_logs(caplog, WARNING):
        c2[a] = [
            Rule({'x': '0'}, 0),
            Rule({'x': '1'}, 1)
        ]
    assert a.get(x='0') == 0
    assert a.get(x='1') == 1
    assert a.get(x='15') == -1
