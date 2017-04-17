# Copyright 2014
# The Cloudscaling Group, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


class WebSocketException(Exception):
    'base for all ContainerWebSocket interactive generated exceptions'
    def __init__(self, wrapped=None, message=None):
        self.wrapped = wrapped
        if message:
            self.message = message
        if wrapped:
            formatted_string = "%s:%s" % (self.message, str(self.wrapped))
        else:
            formatted_string = "%s" % self.message
        super(WebSocketException, self).__init__(formatted_string)


class UserExit(WebSocketException):
    message = "User requested disconnect the container"


class Disconnected(WebSocketException):
    message = "Remote host closed connection"


class ConnectionFailed(WebSocketException):
    message = "Failed to connect to remote host"


class InvalidWebSocketLink(WebSocketException):
    message = "Invalid websocket link when attach container"


class ControlFrameOverLimit(WebSocketException):
    message = "control frame length can not be > 125"


class UnknownOPCCode(WebSocketException):
    message = "Unknown OPC Code"


class MessageFragmentFail(WebSocketException):
    message = "control messages can not be fragmented"


class FragmentProtocolError(WebSocketException):
    message = "fragmentation protocol error"


class InvalidUtf8Payload(WebSocketException):
    message = "invalid utf-8 payload"


class ExcceedSize(WebSocketException):
    message = "exceeded allowable size:"


class RemoteSocketClose(WebSocketException):
    message = "remote socket closed"

class HandshakeFailed(WebSocketException):
    message = "handshake failed:"


class SockerError(WebSocketException):
    message = "Socket Error"


class RSVBitError(WebSocketException):
    message = "RSV bit must be 0"


class ReceivedClientClose(WebSocketException):
    message = "received client closed"


class ValidationError(WebSocketException):
    message = "validation error: "


class VersionMismatch(WebSocketException):
    message = "Version: "


class InvalidToken(WebSocketException):
    message = "Invalid Token"

