import termios
import sys
import logging
import argparse
from websocketproxy.websocketclient import WebSocketClient as Client
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

    openstack.add_openstack_args(p)

    p.add_argument('target',
                   help='A server name, uuid, or (with --url) '
                   'a websocket url')

    p.set_defaults(loglevel=logging.WARN)

    return p.parse_args()


def main(argv):
    args = parse_args()
    logging.basicConfig(level=args.loglevel) 

    if args.url or args.target.startswith('ws://'):
        console_url = args.target

    server = WebsocketServer(13254, host='0.0.0.0', loglevel=logging.DEBUG)
    server.run_forever()

    #websocketclient.do_attach(console_url, args.escape, args.close_wait)


if __name__ == '__main__':
    main()
