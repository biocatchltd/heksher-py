from logging import WARNING

from pytest import mark, raises

from heksher import TRACK_ALL, AsyncHeksherClient, Setting
from tests.blackbox.app.utils import CreateRuleParams
from tests.unittest.util import assert_logs


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
    client1.track_contexts(a=['x', 'y', 'z'], b=TRACK_ALL)
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
    client2.track_contexts(a=['x', 'y', 'z'], b=TRACK_ALL)
    with assert_logs(caplog, WARNING, r'.+ NOT recommended! .+'):  # it should warn you you're doing bad things
        await client2.set_as_main()
    setting3 = Setting('conf3', int, ['b'], 59)
    await client2._undeclared.join()
    add_rules([
        CreateRuleParams(setting='conf1', feature_values={'a': 'z'}, value=6),
        CreateRuleParams(setting='conf2', feature_values={'b': 's'}, value=7),
        CreateRuleParams(setting='conf3', feature_values={'b': 'z'}, value=10)
    ])
    await client2.reload()
    assert setting1.get(a='z') == 6
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
    with assert_logs(caplog, WARNING, r'.+ tracks different context .+'):
        # it should warn you you're doing bad things, and that your tracking differs
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
