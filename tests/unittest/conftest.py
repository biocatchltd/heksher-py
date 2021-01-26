import json
from urllib.parse import parse_qs

from pytest import fixture
from yellowbox.extras.http_server import HttpService, RouterHTTPRequestHandler

import heksher.main_client
from heksher.heksher_client import TemporaryClient


@fixture(scope='session')
def fake_heksher_service():
    with HttpService(host='localhost').start() as service:
        service.declare_responses = {}
        service.context_features = []
        service.query_response = None
        service.query_requests = []

        service.url = f'http://127.0.0.1:{service.server_port}'

        @service.patch_route('PUT', '/api/v1/settings/declare')
        def declare(handler: RouterHTTPRequestHandler):
            request = json.loads(handler.body())
            setting_name = request['name']
            if setting_name in service.declare_responses:
                return json.dumps(service.declare_responses[setting_name])
            if '*' in service.declare_responses:
                return json.dumps(service.declare_responses['*'])
            return 422

        @service.patch_route('GET', '/api/v1/context_features/')
        def get_cfs(handler):
            return json.dumps({'context_features': service.context_features})

        @service.patch_route('GET', '/api/v1/rules/query')
        def query(handler):
            params = json.loads(handler.body())
            service.query_requests.append(params)
            if service.query_response:
                ret = service.query_response
                service.query_response = None
                return json.dumps(ret)
            return json.dumps({'rules': {}})

        with declare, get_cfs, query:
            yield service

@fixture(autouse=True)
def reset_main_client():
    try:
        yield
    finally:
        heksher.main_client.Main = TemporaryClient()