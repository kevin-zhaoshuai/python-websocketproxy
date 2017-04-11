import termios
import sys
import logging
import argparse
from websocketproxy.websocketclient import WebSocketClient
from SimpleWebSocketServer import SimpleWebSocketServer, WebSocket

LOG = logging.getLogger('websocket-proxy')


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--url',
                   action='store_true',
                   help='Target specifies a websocket url '
                   'rather than nova server name.  Using this '
                   'option does not require authentication.')
    p.add_argument('--escape', '-e',
                   default='~',
                   help='Character used to start escape sequences when '
                   'connected. Defaults to "~".')
    p.add_argument('--close-wait', '-w',
                   default=0.5,
                   type=float,
                   help='How long to wait for remote output when reading '
                   'from a pipe.')
    p.add_argument('--no-subprotocols', '-N', action='store_true',
                   help='Disable explicit subprotocol request.')

    g = p.add_argument_group('Logging options')
    g.add_argument('--debug', '-d',
                   action='store_const',
                   const=logging.DEBUG,
                   dest='loglevel')
    g.add_argument('--verbose', '-v',
                   action='store_const',
                   const=logging.INFO,
                   dest='loglevel')

    p.add_argument('target',
                   help='A server name, uuid, or (with --url) '
                   'a websocket url')

    p.set_defaults(loglevel=logging.WARN)

    return p.parse_args()


clients = []
class SimpleChat(WebSocket):
    def handleMessage(self):
       for client in clients:
    #      if client != self:
          if self.wscls is not None:
             self.wscls.ws.send(self.data)

    def handleConnected(self):
       print(self.address, 'connected')
       for client in clients:
          client.sendMessage(self.address[0] + u' - connected')

       clients.append(self)
       url = "ws://kevin-mint:2375/v1.22/containers/d6be9aba74547a277c35eba5c1c4530c31b09f03f791631b9d522a0276a0af57/attach/ws?logs=0&stream=1&stdin=1&stdout=1&stderr=1"
       escape = "~"
       close_wait = 0.5
       self.wscls = WebSocketClient(host_url=url, escape=escape, close_wait=close_wait)
       self.wscls.connect()
       self.wscls.configure_websocketcls()
       self.connected_server = True

    def handleClose(self):
       clients.remove(self)
       print(self.address, 'closed')
       for client in clients:
          client.sendMessage(self.address[0] + u' - disconnected')

def main():
#    args = parse_args()

#    logging.basicConfig(level=args.loglevel)

#    if args.url or args.target.startswith('ws://'):
#        console_url = args.target
    server = SimpleWebSocketServer('', 13256, SimpleChat)
    server.serveforever()

    #websocketclient.do_attach(console_url, args.escape, args.close_wait)


if __name__ == '__main__':
    main()
