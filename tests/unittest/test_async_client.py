from asyncio import sleep
from enum import IntFlag, auto
from logging import ERROR, WARNING

from httpx import HTTPError
from pytest import mark, raises
from starlette.responses import JSONResponse, Response

from heksher import TRACK_ALL
from heksher.clients.async_client import AsyncHeksherClient
from heksher.clients.util import SettingData
from heksher.setting import Setting
from tests.unittest.util import assert_logs

atest = mark.asyncio


@atest
async def test_init_works(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    async with AsyncHeksherClient(fake_heksher_service.local_url(), 10000000, ['a', 'b', 'c']):
        pass


@atest
async def test_declare_before_main(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'outcome': 'created'
    })

    setting = Setting('cache_size', int, ['b', 'c'], 50)
    with fake_heksher_service.query_rules.patch(JSONResponse({
        'settings': {
            'cache_size': {
                'rules': [{'context_features': [], 'value': 100, 'rule_id': 1}], 'default_value': 100
            }
        }
    })):
        async with AsyncHeksherClient(fake_heksher_service.local_url(), 10000000, ['a', 'b', 'c']):
            assert setting.get(b='', c='') == 100


@atest
async def test_declare_after_main(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'outcome': 'created'
    })

    async with AsyncHeksherClient(fake_heksher_service.local_url(), 10000000, ['a', 'b', 'c']) as client:
        setting = Setting('cache_size', int, ['b', 'c'], 50)
        assert not client._undeclared.empty()
        await client._undeclared.join()
        assert setting.get(b='', c='') == 50

        with fake_heksher_service.query_rules.patch(JSONResponse({
            'settings': {
                'cache_size': {
                    'rules': [{'context_features': [], 'value': 100, 'rule_id': 1}], 'default_value': 100
                }
            }
        })):
            await client.reload()
            assert setting.get(b='', c='') == 100


@atest
async def test_regular_update(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'outcome': 'created'
    })

    setting = Setting('cache_size', int, ['b', 'c'], 50)

    async with AsyncHeksherClient(fake_heksher_service.local_url(), 0.02, ['a', 'b', 'c']):
        assert setting.get(b='', c='') == 50
        with fake_heksher_service.query_rules.patch(JSONResponse({
            'settings': {
                'cache_size': {
                    'rules': [{'context_features': [], 'value': 100, 'rule_id': 1}], 'default_value': 100
                }
            }
        })):
            await sleep(1)
            assert setting.get(b='', c='') == 100


@atest
async def test_heksher_unreachable(caplog):
    setting = Setting('cache_size', int, ['b', 'c'], 50)
    caplog.clear()
    with assert_logs(caplog, ERROR), raises(HTTPError):
        async with AsyncHeksherClient('http://notreal.fake.notreal', 10000000, ['a', 'b', 'c']):
            pass
    assert setting.get(b='', c='') == 50


@atest
@mark.parametrize('expected', [
    [],
    ['a'],
    ['b', 'a'],
    ['a', 'b', 'c', 'd'],
    ['e', 'f', 'g']
])
async def test_cf_mismatch(fake_heksher_service, caplog, monkeypatch, expected):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])

    with assert_logs(caplog, WARNING):
        async with AsyncHeksherClient(fake_heksher_service.local_url(), 1000, expected) as client:
            assert client._context_features == expected


@atest
async def test_redundant_defaults(fake_heksher_service, caplog, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'outcome': 'created'
    })

    setting = Setting('cache_size', int, ['b', 'c'], 50)
    with fake_heksher_service.query_rules.patch(JSONResponse({
        'settings': {
            'cache_size': {
                'rules': [{'context_features': [['b', 'B']], 'value': 100, 'rule_id': 1}], 'default_value': 100
            }
        }
    })):
        with assert_logs(caplog, WARNING):
            async with AsyncHeksherClient(fake_heksher_service.local_url(), 1000, ['a', 'b', 'c']) as client:
                client.set_defaults(b='B', d='im redundant')
                assert setting.get(c='') == 100


@atest
async def test_trackcontexts(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c', 'd'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'outcome': 'created'
    })

    setting = Setting('cache_size', int, ['b', 'c'], 50)
    with fake_heksher_service.query_rules.patch(JSONResponse({
        'settings': {
            'cache_size': {
                'rules': [{'context_features': [['b', 'B']], 'value': 100, 'rule_id': 1}], 'default_value': 100
            }
        }
    })), fake_heksher_service.query_rules.capture_calls() as query_calls:
        client = AsyncHeksherClient(fake_heksher_service.local_url(), 100000, ['a', 'b', 'c', 'd'])
        client.track_contexts(b='B', a=['a0', 'a1'], d=TRACK_ALL)

        async with client:
            assert setting.get(b='B', c='') == 100

    query_calls.assert_requested_once_with(
        query_params={'settings': ['cache_size'], 'context_filters': ['a:(a0,a1),b:(B),d:*'],
                      'include_metadata': ['false']}
    )


@atest
async def test_redundant_trackings(caplog):
    client = AsyncHeksherClient('bla', 0, ['a', 'b', 'c'])
    with assert_logs(caplog, WARNING):
        client.track_contexts(a='j', d='t')


@atest
async def test_bad_tracking_all_first(caplog):
    client = AsyncHeksherClient('bla', 0, ['a', 'b', 'c'])
    client.track_contexts(a=TRACK_ALL)
    with raises(RuntimeError):
        client.track_contexts(a='a')


@atest
async def test_bad_tracking_all_second(caplog):
    client = AsyncHeksherClient('bla', 0, ['a', 'b', 'c'])
    client.track_contexts(a='a')
    with raises(RuntimeError):
        client.track_contexts(a=TRACK_ALL)


@atest
async def test_outdated_declaration(fake_heksher_service, monkeypatch, caplog):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'outcome': 'outdated',
        'latest_version': '2.0',
        'differences': []
    })

    setting = Setting('cache_size', int, ['b', 'c'], 50)

    with assert_logs(caplog, WARNING):
        async with AsyncHeksherClient(fake_heksher_service.local_url(), 10000000, ['a', 'b', 'c']):
            pass


@atest
async def test_outdated_declaration_different_default(fake_heksher_service, monkeypatch, caplog):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'outcome': 'outdated',
        'latest_version': '2.0',
        'differences': [
            {'level': 'minor', 'attribute': 'default_value', 'latest_value': 100}
        ]
    })

    setting = Setting('cache_size', int, ['b', 'c'], 50)

    with assert_logs(caplog, WARNING):
        async with AsyncHeksherClient(fake_heksher_service.local_url(), 10000000, ['a', 'b', 'c']):
            assert setting.get(b='', c='') == 100


@atest
async def test_upgraded_declaration_different_default(fake_heksher_service, monkeypatch, caplog):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'outcome': 'upgraded',
        'latest_version': '0.5',
        'differences': [
            {'level': 'minor', 'attribute': 'default_value', 'latest_value': 100}
        ]
    })

    setting = Setting('cache_size', int, ['b', 'c'], 50)

    async with AsyncHeksherClient(fake_heksher_service.local_url(), 10000000, ['a', 'b', 'c']):
        assert setting.get(b='', c='') == 50


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

    c = Setting('c', Color, 'abc', default_value=Color(0))
    with fake_heksher_service.query_rules.patch(JSONResponse({
        'settings': {
            'c': {
                'rules': [{'context_features': [], 'value': ['green', 'blue', 'white'], 'rule_id': 1}],
                'default_value': []
            }
        }
    })):
        caplog.clear()
        with assert_logs(caplog, WARNING):
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
        with assert_logs(caplog, WARNING):
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
        with assert_logs(caplog, WARNING):
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
                'default_value': [['blank']]
            }
        }
    })):
        caplog.clear()
        with assert_logs(caplog, WARNING):
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
        with assert_logs(caplog, WARNING):
            async with AsyncHeksherClient(fake_heksher_service.local_url(), 1000, ['a', 'b', 'c']):
                assert c.get(a='x', b='', c='') == Color.green | Color.blue


@atest
async def test_health_OK(fake_heksher_service):
    client = AsyncHeksherClient(fake_heksher_service.local_url(), 1000, ['a', 'b', 'c'])
    await client.ping()
    await client.close()


@atest
async def test_health_err(fake_heksher_service, monkeypatch):
    with fake_heksher_service.health.patch(Response(status_code=403)):
        client = AsyncHeksherClient(fake_heksher_service.local_url(), 1000, ['a', 'b', 'c'])
        with raises(HTTPError):
            await client.ping()
        await client.close()


@atest
async def test_health_unreachable():
    client = AsyncHeksherClient('http://notreal.fake.notreal', 1000, ['a', 'b', 'c'])
    with raises(HTTPError):
        await client.ping()
    await client.close()


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
        await client.close()


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
        await client1.close()
        with assert_logs(caplog, WARNING):  # it should warn you you're doing bad things
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
        await client2.close()


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
        await client1.close()
        with assert_logs(caplog, WARNING):  # it should warn you you're doing bad things, and that your tracking differs
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
        await client2.close()


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
    await client1.close()
    with raises(RuntimeError):  # not allowed
        await client2.set_as_main()
    await client2.close()


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
    await client1.close()
    setting2 = Setting('conf2', int, ['b'], 26)
    client2 = AsyncHeksherClient(fake_heksher_service.local_url(), 10000000, ['a', 'b'])
    client2.track_contexts(a=['a', 'b'], b=TRACK_ALL)
    with raises(RuntimeError):  # not allowed
        await client2.set_as_main()
    await client2.close()


@atest
async def test_no_rules(fake_heksher_service, monkeypatch):
    monkeypatch.setattr(fake_heksher_service, 'context_features', ['a', 'b', 'c'])
    monkeypatch.setitem(fake_heksher_service.declare_responses, 'cache_size', {
        'outcome': 'created'
    })

    setting = Setting('cache_size', int, ['b', 'c'], 50)
    with fake_heksher_service.query_rules.patch(JSONResponse({
        'settings': {
            'cache_size': {
                'rules': [], 'default_value': 100
            }
        }
    })):
        async with AsyncHeksherClient(fake_heksher_service.local_url(), 10000000, ['a', 'b', 'c']):
            assert setting.get(b='', c='') == 100


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
