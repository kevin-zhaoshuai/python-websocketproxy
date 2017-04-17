#
#    Copyright (C) 2014 Red Hat, Inc
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
#

"""Base proxy module used to create compatible consoles
for OpenStack Nova."""

import os
import sys
import websocketproxy
import websocketserver

ssl_only = False
key = None
cert = 'self.pem'
web = False
daemon = False
record = None
traffic = not daemon
source_is_ipv6 = False


def exit_with_error(msg, errno=-1):
    sys.stderr.write(msg + '\n')
    sys.exit(errno)


def proxy(host, port):

    if ssl_only and not os.path.exists(cert):
        exit_with_error("SSL only and %s not found" % cert)

    # Check to see if tty html/js/css files are present
    if web and not os.path.exists(web):
        exit_with_error("Can not find html/js files at %s." % web)

    # Create and start the NovaWebSockets proxy
    websocketserver.TryWebSocketProxy(
        listen_host=host,
        listen_port=port,
        source_is_ipv6=source_is_ipv6,
        cert=cert,
        key=key,
        ssl_only=ssl_only,
        daemon=daemon,
        record=record,
        traffic=not daemon,
        web=web,
        file_only=True,
        RequestHandlerClass=websocketserver.ProxyRequestHandler
    ).start_server()

def main():
    proxy("0.0.0.0", 13688)


if __name__ == '__main__':
    main()
