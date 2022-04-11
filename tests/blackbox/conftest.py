import asyncio

from pytest import fixture
from yellowbox.clients import docker_client as _docker_client
from yellowbox_heksher.heksher_service import HeksherService


@fixture(scope='session')
def docker_client():
    with _docker_client() as dc:
        yield dc


@fixture(scope='module')
def _heksher_service(docker_client):
    with HeksherService.run(docker_client, heksher_startup_context_features="user") as service:
        yield service


@fixture(scope='function')
async def heksher_service(_heksher_service: HeksherService):
    yield _heksher_service
    await _heksher_service.clear()


@fixture(scope='session')
def event_loop(request):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
