import json

from pytest import fixture
from yellowbox.extras.webserver import WebServer, class_http_endpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

import heksher.main_client
from heksher.heksher_client import TemporaryClient


class FakeHeksher(WebServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.declare_responses = {}
        self.context_features = []

    @class_http_endpoint('PUT', '/api/v1/settings/declare')
    async def declare_settings(self, request: Request):
        data = await request.json()
        setting_name = data['name']
        if setting_name in self.declare_responses:
            return JSONResponse(self.declare_responses[setting_name])
        if '*' in self.declare_responses:
            return JSONResponse(self.declare_responses['*'])
        return Response(status_code=422)

    @class_http_endpoint('GET', '/api/v1/context_features')
    async def get_context_features(self, request: Request):
        return JSONResponse({'context_features': self.context_features})

    query_rules = class_http_endpoint('GET', '/api/v1/rules/query', JSONResponse({'settings': {}}))
    health = class_http_endpoint('GET', '/api/health', Response())
    get_settings = class_http_endpoint('GET', '/api/v1/settings', JSONResponse({}))


@fixture(scope='session')
def fake_heksher_service():
    with FakeHeksher('fakeheksher').start() as service:
        yield service


@fixture(autouse=True)
def reset_main_client():
    try:
        yield
    finally:
        heksher.main_client.Main = TemporaryClient()
