# Copyright 2010 Jacob Kaplan-Moss
# Copyright 2011 OpenStack Foundation
# Copyright 2012 Grid Dynamics
# Copyright 2013 OpenStack Foundation
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


import errno
import exceptions
import socket
import sys
import websocket
import websocketbase

from select import select


class WebSocketProxy(object):
    def __init__(self, host, port, websocketclass, selectInterval=0.1):
        self.websocketclass = websocketclass
        self.serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.serversocket.bind((host, port))
        self.serversocket.listen(5)
        self.selectInterval = selectInterval
        self.connections = {}
        self.listeners = [self.serversocket]

    def _constructWebSocket(self, sock, address):
        return self.websocketclass(self, sock, address)

    def close(self):
        self.serversocket.close()
        for desc, conn in self.connections.items():
            conn.close()
            conn.handleClose()

    def _handlerList(self, rList):
        for ready in rList:
            if isinstance(ready, websocket._core.WebSocket):
                for fileno in self.listeners:
                    if isinstance(fileno, int):
                        client = self.connections[fileno]
                        if ready == client.target.ws:
                            data = client.target.handle_recv()
                            client.sendMessage(data)

            if ready == self.serversocket:
                try:
                    sock, address = self.serversocket.accept()
                    fileno = sock.fileno()
                    self.connections[fileno] = \
                        self._constructWebSocket(sock, address)
                    self.listeners.append(fileno)
                except Exception as n:
                    if sock is not None:
                        sock.close()
                    raise exceptions.SockerError(str(n))

            if isinstance(ready, int):
                client = self.connections[ready]
                try:
                    client._handleData(self)
                except Exception as n:
                    client.client.close()
                    client.handleClose()
                    del self.connections[ready]
                    self.listeners.remove(ready)

    def _handlewList(self, wList):
        for ready in wList:
            client = self.connections[ready]
            try:
                while client.sendq:
                    opcode, payload = client.sendq.popleft()
                    remaining = client._sendBuffer(payload)
                    if remaining is not None:
                        client.sendq.appendleft((opcode, remaining))
                        break
                    else:
                        if opcode == websocketbase.CLOSE:
                            raise exceptions.ReceivedClientClose()
            except Exception:
                client.client.close()
                client.handleClose()
                del self.connections[ready]
                self.listeners.remove(ready)

    def _handlexList(self, xList):
        for failed in xList:
            if failed == self.serversocket:
                self.close()
                raise exceptions.SockerError("client failed")
            else:
                if failed not in self.connections:
                    continue
                client = self.connections[failed]
                client.client.close()
                client.handleClose()
                del self.connections[failed]
                self.listeners.remove(failed)

    def proxy(self):
        while True:
            writers = []
            for fileno in self.listeners:
                if isinstance(fileno, int):
                    client = self.connections[fileno]
                    if client.sendq:
                        writers.append(fileno)

            try:
                rList, wList, xList = select(self.listeners, writers,
                                             [], self.selectInterval)
            except (select.error, OSError):
                exc = sys.exc_info()[1]
                if hasattr(exc, 'errno'):
                    err = exc.errno
                else:
                    err = exc[0]
                if err != errno.EINTR:
                    raise exceptions.SockerError(err)
                else:
                    continue

            self._handlewList(wList)

            self._handlerList(rList)

            self._handlexList(xList)
