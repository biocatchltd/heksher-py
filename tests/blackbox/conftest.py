import asyncio
from typing import Sequence

from pytest import fixture
from yellowbox.clients import docker_client as _docker_client
from yellowbox_heksher.heksher_service import HeksherService

import heksher.main_client
from heksher.heksher_client import TemporaryClient
from tests.blackbox.app.utils import CreateRuleParams


@fixture(scope='session')
def docker_client():
    with _docker_client() as dc:
        yield dc


@fixture(scope='module')
def _heksher_service(docker_client):
    with HeksherService.run(docker_client, heksher_startup_context_features="a;b;c", remove=True) as service:
        yield service


@fixture(scope='function')
async def heksher_service(_heksher_service: HeksherService):
    yield _heksher_service
    _heksher_service.clear()


@fixture(scope='session')
def event_loop(request):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@fixture(scope="function")
def add_rules(heksher_service: HeksherService):
    async def _add_rules(rules: Sequence[CreateRuleParams]):
        for rule in rules:
            resp = (heksher_service.http_client.post('/api/v1/rules', content=rule.json()))
            if resp.is_error:
                raise Exception(resp.content)

    yield _add_rules


@fixture(autouse=True)
def reset_main_client():
    try:
        yield
    finally:
        heksher.main_client.Main = TemporaryClient()
