# -*- coding: utf-8 -*-
"""
    proxy.py
    ~~~~~~~~
    ⚡⚡⚡ Fast, Lightweight, Pluggable, TLS interception capable proxy server focused on
    Network monitoring, controls & Application development, testing, debugging.

    :copyright: (c) 2013-present by Abhinav Singh and contributors.
    :license: BSD, see LICENSE for more details.
"""
import json
import threading
import time
from typing import List, Tuple

from logged_groups import logged_group, logging_context
from neon_py.utils import gen_unique_id

from ..http.codes import httpStatusCodes
from ..http.parser import HttpParser
from ..http.websocket import WebsocketFrame
from ..http.server import HttpWebServerBasePlugin, httpProtocolTypes

from ..common.utils import build_http_response
from ..common_neon.solana_tx_error_parser import SolTxError
from ..common_neon.errors import EthereumError

from ..neon_rpc_api_model import NeonRpcApiWorker
from ..statistics_exporter.prometheus_proxy_exporter import PrometheusExporter

modelInstanceLock = threading.Lock()
modelInstance = None


@logged_group("neon.Proxy")
class NeonRpcApiPlugin(HttpWebServerBasePlugin):
    """Extend in-built Web Server to add Reverse Proxy capabilities.
    """

    SOLANA_PROXY_LOCATION: str = r'/solana$'
    SOLANA_PROXY_PASS = [
        b'http://localhost:8545/'
    ]

    def __init__(self, *args):
        HttpWebServerBasePlugin.__init__(self, *args)
        self._stat_exporter = PrometheusExporter()
        self.model = NeonRpcApiPlugin.getModel()
        self.model.set_stat_exporter(self._stat_exporter)

    @classmethod
    def getModel(cls):
        global modelInstanceLock
        global modelInstance
        with modelInstanceLock:
            if modelInstance is None:
                modelInstance = NeonRpcApiWorker()
            return modelInstance

    def routes(self) -> List[Tuple[int, str]]:
        return [
            (httpProtocolTypes.HTTP, NeonRpcApiPlugin.SOLANA_PROXY_LOCATION),
            (httpProtocolTypes.HTTPS, NeonRpcApiPlugin.SOLANA_PROXY_LOCATION)
        ]

    def process_request(self, request):
        response = {
            'jsonrpc': '2.0',
            'id': request.get('id', None),
        }

        try:
            if (not hasattr(self.model, request['method'])) or (not self.model.is_allowed_api(request["method"])):
                response['error'] = {'code': -32601, 'message': f'method {request["method"]} is not supported'}
            else:
                method = getattr(self.model, request['method'])
                params = request.get('params', [])
                response['result'] = method(*params)
        except SolTxError as err:
            # traceback.print_exc()
            response['error'] = {'code': -32000, 'message': err.error}
        except EthereumError as err:
            # traceback.print_exc()
            response['error'] = err.getError()
        except BaseException as exc:
            self.debug('Exception on process request', exc_info=exc)
            response['error'] = {'code': -32000, 'message': str(exc)}

        return response

    def handle_request(self, request: HttpParser) -> None:
        req_id = gen_unique_id()
        with logging_context(req_id=req_id):
            self.handle_request_impl(request)
            self.info("Request processed")

    def handle_request_impl(self, request: HttpParser) -> None:
        if request.method == b'OPTIONS':
            self.client.queue(memoryview(build_http_response(
                httpStatusCodes.OK, body=None,
                headers={
                    b'Access-Control-Allow-Origin': b'*',
                    b'Access-Control-Allow-Methods': b'POST, GET, OPTIONS',
                    b'Access-Control-Allow-Headers': b'Content-Type',
                    b'Access-Control-Max-Age': b'86400'
                })))
            return
        start_time = time.time()

        try:
            self.info('handle_request <<< %s 0x%x %s', threading.get_ident(), id(self.model),
                      request.body.decode('utf8'))
            request = json.loads(request.body)
            if isinstance(request, list):
                response = []
                if len(request) == 0:
                    raise Exception("Empty batch request")
                for r in request:
                    response.append(self.process_request(r))
            elif isinstance(request, dict):
                response = self.process_request(request)
            else:
                raise Exception("Invalid request")
        except Exception as err:
            # traceback.print_exc()
            response = {'jsonrpc': '2.0', 'error': {'code': -32000, 'message': str(err)}}

        resp_time_ms = (time.time() - start_time)*1000  # convert this into milliseconds

        method = '---'
        if isinstance(request, dict):
            method = request.get('method', '---')

        self.info('handle_request >>> %s 0x%0x %s %s resp_time_ms= %s',
                  threading.get_ident(),
                  id(self.model),
                  json.dumps(response),
                  method,
                  resp_time_ms)

        self.client.queue(memoryview(build_http_response(
            httpStatusCodes.OK, body=json.dumps(response).encode('utf8'),
            headers={
                b'Content-Type': b'application/json',
                b'Access-Control-Allow-Origin': b'*',
            })))

        self._stat_exporter.stat_commit_request_and_timeout(method, resp_time_ms)

    def on_websocket_open(self) -> None:
        pass

    def on_websocket_message(self, frame: WebsocketFrame) -> None:
        pass

    def on_websocket_close(self) -> None:
        pass
