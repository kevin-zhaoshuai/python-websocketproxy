# Copyright (c) 2012 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

'''
Websocket proxy that is compatible with OpenStack.
Leverages websockify.py
'''

import socket
import sys

import logging
from six.moves import http_cookies as Cookie
import six.moves.urllib.parse as urlparse
import websockify
import websocket
import exceptions
from websocketclient import WebSocketClient
from websocketproxy import WebSocketProxy, WebSocket

LOG = logging.getLogger(__name__)

class ProxyRequestHandlerBase(object):
    def address_string(self):
        # NOTE(rpodolyaka): override the superclass implementation here and
        # explicitly disable the reverse DNS lookup, which might fail on some
        # deployments due to DNS configuration and break VNC access completely
        return str(self.client_address[0])

    def verify_origin_proto(self, connection_info, origin_proto):
        access_url = connection_info.get('access_url')
        if not access_url:
            detail = "No access_url in connection_info. " \
                     "Cannot validate protocol"
            raise exceptions.ValidationError(detail)
        expected_protos = [urlparse.urlparse(access_url).scheme]
        # NOTE: For serial consoles the expected protocol could be ws or
        # wss which correspond to http and https respectively in terms of
        # security.
        if 'ws' in expected_protos:
            expected_protos.append('http')
        if 'wss' in expected_protos:
            expected_protos.append('https')

        return origin_proto in expected_protos

    def new_websocket_client(self):
        """Called after a new WebSocket connection has been established."""
        # Reopen the eventlet hub to make sure we don't share an epoll
        # fd with parent and/or siblings, which would be bad
        from eventlet import hubs
        hubs.use_hub()

        # The nova expected behavior is to have token
        # passed to the method GET of the request
        parse = urlparse.urlparse(self.path)
        if parse.scheme not in ('http', 'https'):
            # From a bug in urlparse in Python < 2.7.4 we cannot support
            # special schemes (cf: http://bugs.python.org/issue9374)
            if sys.version_info < (2, 7, 4):
                raise exceptions.VersionMismatch("We do not support scheme '%s' "
                                                 "under Python < 2.7.4,please use "
                                                 "http or https" % parse.scheme)

        query = parse.query
        token = urlparse.parse_qs(query).get("token", [""]).pop()
        print token
        #connect_info = rpcapi.check_token(ctxt, token=token)
        if token == "e6448a2f-375d-4763-88a1-04410321bbbb":
            connection_port = 13256
            connect_info = "ws://kevin-mint:2375/v1.22/containers/cee85845f2fcd151885fecc367dcb67df4f049baa20a3472de19ff2785709571/attach/ws?logs=0&stream=1&stdin=1&stdout=1&stderr=1"
        elif token == "e6448a2f-375d-4763-88a1-04410321aaaa":
            connection_port = 13257
            connect_info = "ws://kevin-mint:2375/v1.22/containers/f9b69ee2c2fdc6526e783306d185db1e5995cd714ed2ff10060d3e4fba96a27b/attach/ws?logs=0&stream=1&stdin=1&stdout=1&stderr=1"

        if not connect_info:
            raise exceptions.InvalidToken(token)

        # Verify Origin
        #expected_origin_hostname = self.headers.get('Host')
        #if ':' in expected_origin_hostname:
        #    e = expected_origin_hostname
        #    if '[' in e and ']' in e:
        #        expected_origin_hostname = e.split(']')[0][1:]
        #    else:
        #        expected_origin_hostname = e.split(':')[0]
        #expected_origin_hostnames = None
        #expected_origin_hostnames.append(expected_origin_hostname)
        #origin_url = self.headers.get('Origin')
        # missing origin header indicates non-browser client which is OK
        #if origin_url is not None:
        #    origin = urlparse.urlparse(origin_url)
        #    origin_hostname = origin.hostname
        #    origin_scheme = origin.scheme
        #    if origin_hostname == '' or origin_scheme == '':
        #        detail = "Origin header not valid."
        #        raise exceptions.ValidationError(detail)
        #    if origin_hostname not in expected_origin_hostnames:
        #        detail = "Origin header does not match this host."
        #        raise exceptions.ValidationError(detail)
        #    if not self.verify_origin_proto(connect_info, origin_scheme):
        #        detail = "Origin header protocol does not match this host."
        #        raise exceptions.ValidationError(detail)

        print('connect info: %s', connect_info)

        escape = "~"
        close_wait = 0.5
        wscls = WebSocketClient(host_url=connect_info, escape=escape, close_wait=close_wait)
        wscls.connect()
        # Handshake as necessary
#        if connect_info.get('internal_access_path'):
#            wscls.ws.send("CONNECT %s HTTP/1.1\r\n\r\n" %
#                        connect_info['internal_access_path'])
#            while True:
#                data = wscls.ws.recv(4096, socket.MSG_PEEK)
#                if data.find("\r\n\r\n") != -1:
#                    if data.split("\r\n")[0].find("200") == -1:
#                        raise exceptions.InvalidConnectionInfo()
#                    wscls.ws.recv(len(data))
#                    break

        print("handshaked successfully")
        server = WebSocketProxy('', connection_port, SimpleProxy, wscls)
        try:
            server.proxy()
        except socket.error as e:
            raise exceptions.ConnectionFailed(e)
        except websocket.WebSocketConnectionClosedException as e:
            raise exceptions.Disconnected(e)
        finally:
            if wscls:
                wscls.ws.shutdown(socket.SHUT_RDWR)
                wscls.ws.close()


class ProxyRequestHandler(ProxyRequestHandlerBase,
                              websockify.ProxyRequestHandler):
    def __init__(self, *args, **kwargs):
        websockify.ProxyRequestHandler.__init__(self, *args, **kwargs)

    def socket(self, *args, **kwargs):
        return websockify.WebSocketServer.socket(*args, **kwargs)


class TryWebSocketProxy(websockify.WebSocketProxy):
    @staticmethod
    def get_logger():
        return LOG


clients = []
class SimpleProxy(WebSocket):
    def handleMessage(self):
        self.target.ws.send(self.data)

    def handleConnected(self):
       print(self.address, 'connected')
       for client in clients:
          client.sendMessage(self.address[0] + u' - connected')

       clients.append(self)

    def handleClose(self):
       clients.remove(self)
       print(self.address, 'closed')
       for client in clients:
          client.sendMessage(self.address[0] + u' - disconnected')
