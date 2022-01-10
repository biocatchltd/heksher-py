from contextvars import ContextVar
from typing import Mapping

from pytest import mark, raises

from heksher.clients.stub import AsyncStubHeksherClient, Rule, SyncStubHeksherClient
from heksher.setting import Setting

atest = mark.asyncio


def test_sync_stub():
    a = Setting('a', int, ['user', 'theme'], default_value=0)

    with SyncStubHeksherClient() as client:
        b = Setting('b', Mapping[str, int], ['user', 'theme'], default_value=0)
        with client.patch(a, 10), client.patch(b, {
            't': 1,
            'z': 2
        }):
            c = Setting('c', int, ['user', 'theme'], default_value=0)
            client.patch(c, [
                Rule({}, 0),
                Rule({'theme': 'dark'}, 1),
                Rule({'user': 'admin'}, 2)
            ])

            assert a.get(user='', theme='') == 10
            assert b.get(user='', theme='') == {
                't': 1,
                'z': 2
            }
            assert c.get(user='', theme='') == 0
            assert c.get(user='', theme='dark') == 1
            assert c.get(user='admin', theme='') == 2
            assert c.get(user='admin', theme='dark') == 1


@atest
async def test_async_stub():
    a = Setting('a', int, ['user', 'theme'], default_value=0)

    async with AsyncStubHeksherClient() as client:
        b = Setting('b', Mapping[str, int], ['user', 'theme'], default_value=0)
        with client.patch(a, 10), client.patch(b, {
            't': 1,
            'z': 2
        }):
            c = Setting('c', int, ['user', 'theme'], default_value=0)
            client.patch(c, [
                Rule({}, 0),
                Rule({'theme': 'dark'}, 1),
                Rule({'user': 'admin', 'theme': None}, 2)
            ])

            assert a.get(user='', theme='') == 10
            assert b.get(user='', theme='') == {
                't': 1,
                'z': 2
            }
            assert c.get(user='', theme='') == 0
            assert c.get(user='', theme='dark') == 1
            assert c.get(user='admin', theme='') == 2
            assert c.get(user='admin', theme='dark') == 1


def test_repeat_default():
    with SyncStubHeksherClient() as client:
        client.set_defaults(a='a')
        with raises(ValueError):
            client.set_defaults(a='a')


a = ContextVar('a')
b = ContextVar('b', default='beta')
c = ContextVar('c', default='charlie')
d = ContextVar('d')


def test_default_context_var():
    with SyncStubHeksherClient() as client:
        client.set_defaults(a=a, b=b, c=c, d=d)
        c.set('cookie')
        d.set('delta')
        assert client.context_namespace({}) == {'b': 'beta', 'c': 'cookie', 'd': 'delta'}


def test_sync_stub_patcher(monkeypatch):
    a = Setting('a', int, ['user', 'theme'], default_value=0)

    with SyncStubHeksherClient() as client:
        b = Setting('b', Mapping[str, int], ['user', 'theme'], default_value=0)
        monkeypatch.setattr(client[a], 'rules', 10)
        monkeypatch.setattr(client[b], 'rules', {
            't': 1,
            'z': 2
        })
        c = Setting('c', int, ['user', 'theme'], default_value=0)
        monkeypatch.setattr(client[c], 'rules', [
            Rule({}, 0),
            Rule({'theme': 'dark'}, 1),
            Rule({'user': 'admin'}, 2)
        ])

        assert a.get(user='', theme='') == 10
        assert b.get(user='', theme='') == {
            't': 1,
            'z': 2
        }
        assert c.get(user='', theme='') == 0
        assert c.get(user='', theme='dark') == 1
        assert c.get(user='admin', theme='') == 2
        assert c.get(user='admin', theme='dark') == 1


@atest
async def test_async_stub_patcher(monkeypatch):
    a = Setting('a', int, ['user', 'theme'], default_value=0)

    async with AsyncStubHeksherClient() as client:
        b = Setting('b', Mapping[str, int], ['user', 'theme'], default_value=0)
        monkeypatch.setattr(client[a], 'rules', 10)
        monkeypatch.setattr(client[b], 'rules', {
            't': 1,
            'z': 2
        })
        c = Setting('c', int, ['user', 'theme'], default_value=0)
        monkeypatch.setattr(client[c], 'rules', [
            Rule({}, 0),
            Rule({'theme': 'dark'}, 1),
            Rule({'user': 'admin'}, 2)
        ])

        assert a.get(user='', theme='') == 10
        assert b.get(user='', theme='') == {
            't': 1,
            'z': 2
        }
        assert c.get(user='', theme='') == 0
        assert c.get(user='', theme='dark') == 1
        assert c.get(user='admin', theme='') == 2
        assert c.get(user='admin', theme='dark') == 1
