import termios
import sys
import logging

from websocketproxy.websocketclient import WebSocketClient
from websocketproxy.websocketbase import WebSocket
from websocketproxy.websocketproxy import WebSocketProxy

LOG = logging.getLogger('websocket-proxy')

target_list = {"579484fa-1f8b-4b0a-9579-8e988ba46cf0":"ws://kevin-mint:2375/v1.22/containers/f9b69ee2c2fdc6526e783306d185db1e5995cd714ed2ff10060d3e4fba96a27b/attach/ws?logs=0&stream=1&stdin=1&stdout=1&stderr=1",
               "9ea692b0-8937-4d16-b021-5b0f92ebd1bd":"ws://kevin-mint:2375/v1.22/containers/cee85845f2fcd151885fecc367dcb67df4f049baa20a3472de19ff2785709571/attach/ws?logs=0&stream=1&stdin=1&stdout=1&stderr=1"}

clients = []
class SimpleProxy(WebSocket):
    def handleMessage(self):
        self.target.ws.send(self.data)

    def handleConnected(self):
       print(self.address, 'connected')
       target_url = target_list.get(self.headerid, None)
       if target_url:
           escape = "~"
           close_wait = 0.5
           wscls = WebSocketClient(host_url=target_url, escape=escape, close_wait=close_wait)
           wscls.connect()
           self.target = wscls

    def handleClose(self):
       print(self.address, 'closed')

def main():
    server = WebSocketProxy('', 13256, SimpleProxy)
    server.proxy()

if __name__ == '__main__':
    main()
