from logging import WARNING

from pytest import mark, raises
from starlette.responses import JSONResponse

from heksher import TRACK_ALL
from heksher.clients.async_client import AsyncHeksherClient
from heksher.setting import Setting
from tests.unittest.util import assert_logs

atest = mark.asyncio


@atest
async def test_switch_main_from_temp(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'conf1', {
        'outcome': 'created'
    })
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'conf2', {
        'outcome': 'created'
    })
    setting1 = Setting('conf1', int, ['a'], 74)
    client = AsyncHeksherClient(fake_heksher_service.local_url(), 10000000, ['a', 'b'])
    client.track_contexts(a=['a', 'b'], b=TRACK_ALL)
    await client.set_as_main()
    setting2 = Setting('conf2', int, ['b'], 26)
    with fake_heksher_service.query_rules.patch(JSONResponse({
        'settings': {
            'conf1': {
                'rules': [{'context_features': [], 'value': 5, 'rule_id': 1}],
                'default_value': 74
            },
            'conf2': {
                'rules': [{'context_features': [], 'value': 4, 'rule_id': 2}],
                'default_value': 26
            }
        }
    })):
        await client.reload()
        assert setting1.get(a='') == 5
        assert setting2.get(b='') == 4
        await client.aclose()


@atest
async def test_switch_main(fake_heksher_service, monkeypatch, caplog):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'conf1', {
        'outcome': 'created'
    })
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'conf2', {
        'outcome': 'created'
    })
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'conf3', {
        'outcome': 'created'
    })
    setting1 = Setting('conf1', int, ['a'], 74)
    client1 = AsyncHeksherClient(fake_heksher_service.local_url(), 10000000, ['a', 'b'])
    client1.track_contexts(a=['a', 'b'], b=TRACK_ALL)
    await client1.set_as_main()
    setting2 = Setting('conf2', int, ['b'], 26)
    with fake_heksher_service.query_rules.patch(JSONResponse({
        'settings': {
            'conf1': {
                'rules': [{'context_features': [], 'value': 5, 'rule_id': 1}],
                'default_value': 74
            },
            'conf2': {
                'rules': [{'context_features': [], 'value': 4, 'rule_id': 2}],
                'default_value': 26
            }
        }
    })):
        await client1.reload()
        assert len(client1._tracked_settings) == 2
        assert setting1.get(a='') == 5
        assert setting2.get(b='') == 4
        client2 = AsyncHeksherClient(fake_heksher_service.local_url(), 10000000, ['a', 'b'])
        client2.track_contexts(a=['a', 'b'], b=TRACK_ALL)
        await client1.aclose()
        with assert_logs(caplog, WARNING, r'.+ NOT recommended! .+'):  # it should warn you you're doing bad things
            await client2.set_as_main()
    setting3 = Setting('conf3', int, ['b'], 59)
    with fake_heksher_service.query_rules.patch(JSONResponse({
        'settings': {
            'conf1': {
                'rules': [{'context_features': [], 'value': 5, 'rule_id': 1}],
                'default_value': 74
            },
            'conf2': {
                'rules': [{'context_features': [], 'value': 4, 'rule_id': 2}],
                'default_value': 26
            },
            'conf3': {
                'rules': [{'context_features': [], 'value': 3, 'rule_id': 3}],
                'default_value': 59
            }
        }
    })):
        await client2.reload()
        assert setting1.get(a='') == 5
        assert setting2.get(b='') == 4
        assert setting3.get(b='') == 3
        await client2.aclose()


@atest
async def test_switch_main_different_tracking(fake_heksher_service, monkeypatch, caplog):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'conf1', {
        'outcome': 'created'
    })
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'conf2', {
        'outcome': 'created'
    })
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'conf3', {
        'outcome': 'created'
    })
    setting1 = Setting('conf1', int, ['a'], 74)
    client1 = AsyncHeksherClient(fake_heksher_service.local_url(), 10000000, ['a', 'b'])
    client1.track_contexts(a=['a', 'b'], b=TRACK_ALL)
    await client1.set_as_main()
    setting2 = Setting('conf2', int, ['b'], 26)
    with fake_heksher_service.query_rules.patch(JSONResponse({
        'settings': {
            'conf1': {
                'rules': [{'context_features': [], 'value': 5, 'rule_id': 1}],
                'default_value': 74
            },
            'conf2': {
                'rules': [{'context_features': [], 'value': 4, 'rule_id': 2}],
                'default_value': 26
            }
        }
    })):
        await client1.reload()
        assert len(client1._tracked_settings) == 2
        assert setting1.get(a='') == 5
        assert setting2.get(b='') == 4
        client2 = AsyncHeksherClient(fake_heksher_service.local_url(), 10000000, ['a', 'b'])
        client2.track_contexts(a=['a', 'b', 'c'], b="shoobidoobi")
        await client1.aclose()
        with assert_logs(caplog, WARNING, r'.+ tracks different context .+'):
            # it should warn you you're doing bad things, and that your tracking differs
            await client2.set_as_main()
    setting3 = Setting('conf3', int, ['b'], 59)
    with fake_heksher_service.query_rules.patch(JSONResponse({
        'settings': {
            'conf1': {
                'rules': [{'context_features': [], 'value': 5, 'rule_id': 1}],
                'default_value': 74,
            },
            'conf2': {
                'rules': [{'context_features': [], 'value': 4, 'rule_id': 2}],
                'default_value': 26,
            },
            'conf3': {
                'rules': [{'context_features': [], 'value': 3, 'rule_id': 3}],
                'default_value': 59,
            }
        }
    })):
        await client2.reload()
        assert setting1.get(a='') == 5
        assert setting2.get(b='') == 4
        assert setting3.get(b='') == 3
        await client2.aclose()


@atest
async def test_switch_main_different_contexts(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'conf1', {
        'outcome': 'created'
    })
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'conf2', {
        'outcome': 'created'
    })
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'conf3', {
        'outcome': 'created'
    })
    setting1 = Setting('conf1', int, ['a'], 74)
    client1 = AsyncHeksherClient(fake_heksher_service.local_url(), 10000000, ['a', 'b'])
    client1.track_contexts(a=['a', 'b'], b=TRACK_ALL)
    await client1.set_as_main()
    setting2 = Setting('conf2', int, ['b'], 26)
    with fake_heksher_service.query_rules.patch(JSONResponse({
        'settings': {
            'conf1': {
                'rules': [{'context_features': [], 'value': 5, 'rule_id': 1}],
                'default_value': 74
            },
            'conf2': {
                'rules': [{'context_features': [], 'value': 4, 'rule_id': 2}],
                'default_value': 26
            }
        }
    })):
        await client1.reload()
        assert len(client1._tracked_settings) == 2
        assert setting1.get(a='') == 5
        assert setting2.get(b='') == 4
    client2 = AsyncHeksherClient(fake_heksher_service.local_url(), 10000000, ['b', 'c'])
    client2.track_contexts(a=['a', 'b'], b=TRACK_ALL)
    await client1.aclose()
    with raises(RuntimeError):  # not allowed
        await client2.set_as_main()
    await client2.aclose()


@atest
async def test_switch_main_unclosed(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'conf1', {
        'outcome': 'created'
    })
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'conf2', {
        'outcome': 'created'
    })
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'conf3', {
        'outcome': 'created'
    })
    setting1 = Setting('conf1', int, ['a'], 74)
    client1 = AsyncHeksherClient(fake_heksher_service.local_url(), 10000000, ['a', 'b'])
    client1.track_contexts(a=['a', 'b'], b=TRACK_ALL)
    await client1.set_as_main()
    await client1.aclose()
    setting2 = Setting('conf2', int, ['b'], 26)
    client2 = AsyncHeksherClient(fake_heksher_service.local_url(), 10000000, ['a', 'b'])
    client2.track_contexts(a=['a', 'b'], b=TRACK_ALL)
    with raises(RuntimeError):  # not allowed
        await client2.set_as_main()
    await client2.aclose()
