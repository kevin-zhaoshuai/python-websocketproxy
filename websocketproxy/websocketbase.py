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


import base64
from BaseHTTPServer import BaseHTTPRequestHandler
import codecs
from collections import deque
import errno
import exceptions
import hashlib
import socket
from StringIO import StringIO
import struct


def _check_unicode(val):
    return isinstance(val, unicode)


class HTTPRequest(BaseHTTPRequestHandler):
    def __init__(self, request_text):
        self.rfile = StringIO(request_text)
        self.raw_requestline = self.rfile.readline()
        self.error_code = self.error_message = None
        self.parse_request()

_VALID_STATUS_CODES = [1000, 1001, 1002, 1003, 1007, 1008,
                       1009, 1010, 1011, 3000, 3999, 4000, 4999]

HANDSHAKE_STR = ("HTTP/1.1 101 Switching Protocols\r\n"
                 "Upgrade: WebSocket\r\n"
                 "Connection: Upgrade\r\n"
                 "Sec-WebSocket-Accept: %(acceptstr)s\r\n\r\n")

GUID_STR = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'

STREAM = 0x0
TEXT = 0x1
BINARY = 0x2
CLOSE = 0x8
PING = 0x9
PONG = 0xA

HEADERB1 = 1
HEADERB2 = 3
LENGTHSHORT = 4
LENGTHLONG = 5
MASK = 6
MAXHEADER = 65536
MAXPAYLOAD = 33554432
PAYLOAD = 7


class WebSocket(object):
    def __init__(self, server, sock, address):
        self.server = server
        self.client = sock
        self.address = address

        self.handshaked = False
        self.headerbuffer = bytearray()
        self.headertoread = 2048

        self.fin = 0
        self.data = bytearray()
        self.opcode = 0
        self.hasmask = 0
        self.maskarray = None
        self.length = 0
        self.lengtharray = None
        self.index = 0
        self.request = None
        self.usingssl = False

        self.frag_start = False
        self.frag_type = BINARY
        self.frag_buffer = None
        self.frag_decoder = \
            codecs.getincrementaldecoder('utf-8')(errors='strict')
        self.closed = False
        self.sendq = deque()
        self.target = None
        self.headerid = None

        self.state = HEADERB1

        # restrict the size of header and payload for security reasons
        self.maxheader = MAXHEADER
        self.maxpayload = MAXPAYLOAD

    def handleMessage(self):
        """message handling

        Called when websocket frame is received. To access the frame data
        call self.data. If the frame is Text then self.data is a unicode
        object. If the frame is Binary then self.data is a bytearray object.
        """
        pass

    def handleConnected(self):
        """client connection

        Called when a websocket client connects to the server.
        """
        pass

    def handleClose(self):
        """Websocket Close

        Called when a websocket server gets a Close frame from a client.
        """
        pass

    def _handleOPCClose(self):
        status = 1000
        reason = u''
        length = len(self.data)

        if length == 0:
            pass
        elif length >= 2:
            status = struct.unpack_from('!H', self.data[:2])[0]
            reason = self.data[2:]

            if status not in _VALID_STATUS_CODES:
                status = 1002

            if len(reason) > 0:
                try:
                    reason = reason.decode('utf8', errors='strict')
                except Exception:
                    status = 1002
        else:
            status = 1002

        self.close(status, reason)

    def _handleFinZero(self):
        if self.opcode != STREAM:
            if self.opcode == PING or self.opcode == PONG:
                raise exceptions.MessageFragmentFail()

            self.frag_type = self.opcode
            self.frag_start = True
            self.frag_decoder.reset()

            if self.frag_type == TEXT:
                self.frag_buffer = []
                utf_str = self.frag_decoder.decode(self.data, final=False)
                if utf_str:
                    self.frag_buffer.append(utf_str)
            else:
                self.frag_buffer = bytearray()
                self.frag_buffer.extend(self.data)
        else:
            if self.frag_start is False:
                raise exceptions.FragmentProtocolError()

            if self.frag_type == TEXT:
                utf_str = self.frag_decoder.decode(self.data, final=False)
                if utf_str:
                    self.frag_buffer.append(utf_str)
            else:
                self.frag_buffer.extend(self.data)

    def _handleValidInfo(self):
        if self.opcode == STREAM:
            if self.frag_start is False:
                raise exceptions.FragmentProtocolError()

            if self.frag_type == TEXT:
                utf_str = self.frag_decoder.decode(self.data, final=True)
                self.frag_buffer.append(utf_str)
                self.data = u''.join(self.frag_buffer)
            else:
                self.frag_buffer.extend(self.data)
                self.data = self.frag_buffer
            self.handleMessage()

            self.frag_decoder.reset()
            self.frag_type = BINARY
            self.frag_start = False
            self.frag_buffer = None

        elif self.opcode == PING:
            self._sendMessage(False, PONG, self.data)

        elif self.opcode == PONG:
            pass

        else:
            if self.frag_start is True:
                raise exceptions.FragmentProtocolError()

            if self.opcode == TEXT:
                try:
                    self.data = self.data.decode('utf8', errors='strict')
                except Exception:
                    raise exceptions.InvalidUtf8Payload()
            self.handleMessage()

    def _handlePacket(self):
        if self.opcode == CLOSE:
            pass
        elif self.opcode == STREAM:
            pass
        elif self.opcode == TEXT:
            pass
        elif self.opcode == BINARY:
            pass
        elif self.opcode == PONG or self.opcode == PING:
            if len(self.data) > 125:
                raise exceptions.ControlFrameOverLimit()
        else:
            raise exceptions.UnknownOPCCode(self.opcode)

        if self.opcode == CLOSE:
            self._handleOPCClose()
            return

        elif self.fin == 0:
            self._handleFinZero()
        else:
            self._handleValidInfo()

    def _handleData(self, proxy):
        # do normal data
        if self.handshaked is True:
            data = self.client.recv(16384)
            if not data:
                raise exceptions.RemoteSocketClose()
            for d in data:
                self._parseMessage(ord(d))

        # else do the HTTP header and handshake
        else:
            data = self.client.recv(self.headertoread)
            if not data:
                raise exceptions.RemoteSocketClose()
            else:
                # accumulate
                self.headerbuffer.extend(data)

                if len(self.headerbuffer) >= self.maxheader:
                    raise exceptions.ExcceedSize("Header length")

                # indicates end of HTTP header
                if b'\r\n\r\n' in self.headerbuffer:
                    self.request = HTTPRequest(self.headerbuffer)

                    # handshake rfc 6455
                    try:
                        key = self.request.headers['Sec-WebSocket-Key']
                        k = key.encode('ascii') + GUID_STR.encode('ascii')
                        k_s = base64.b64encode(
                            hashlib.sha1(k).digest()).decode('ascii')
                        hStr = HANDSHAKE_STR % {'acceptstr': k_s}
                        self.sendq.append((BINARY, hStr.encode('ascii')))
                        self.headerid = self.request.headers['User-Agent']
                        self.handshaked = True
                        self.handleConnected()
                        proxy.listeners.append(self.target.ws)
                    except Exception as e:
                        raise exceptions.HandshakeFailed(str(e))

    def close(self, status=1000, reason=u''):
        """Websocket close

        Send Close frame to the client. The underlying socket is only closed
        when the client acknowledges the Close frame.
        status is the closing identifier. reason is the reason for the close.
        """
        try:
            if self.closed is False:
                close_msg = bytearray()
                close_msg.extend(struct.pack("!H", status))
                if _check_unicode(reason):
                    close_msg.extend(reason.encode('utf-8'))
                else:
                    close_msg.extend(reason)

                self._sendMessage(False, CLOSE, close_msg)

        finally:
            self.closed = True

    def _sendBuffer(self, buff, send_all=False):
        size = len(buff)
        tosend = size
        already_sent = 0

        while tosend > 0:
            try:
                # i should be able to send a bytearray
                sent = self.client.send(buff[already_sent:])
                if sent == 0:
                    raise RuntimeError('socket connection broken')

                already_sent += sent
                tosend -= sent

            except socket.error as e:
                # if full buffers then wait for them to drain and try again
                if e.errno in [errno.EAGAIN, errno.EWOULDBLOCK]:
                    if send_all:
                        continue
                    return buff[already_sent:]
                else:
                    raise exceptions.sockerError(str(e))
        return None

    def sendFragmentStart(self, data):
        """Begin send data fragment

        Send the start of a data fragment stream to a websocket client.
        Subsequent data should be sent using sendFragment().
        A fragment stream is completed when sendFragmentEnd() is called.

        If data is a unicode object then the frame is sent as Text.
        If the data is a bytearray object then the frame is sent as Binary.
        """
        opcode = BINARY
        if _check_unicode(data):
            opcode = TEXT
        self._sendMessage(True, opcode, data)

    def sendFragment(self, data):
        """see sendFragmentStart()

        If data is a unicode object then the frame is sent as Text.
        If the data is a bytearray object then the frame is sent as Binary.
        """
        self._sendMessage(True, STREAM, data)

    def sendFragmentEnd(self, data):
        """see sendFragmentEnd()

        If data is a unicode object then the frame is sent as Text.
        If the data is a bytearray object then the frame is sent as Binary.
        """
        self._sendMessage(False, STREAM, data)

    def sendMessage(self, data):
        """Send websocket data frame to the client.

        If data is a unicode object then the frame is sent as Text.
        If the data is a bytearray object then the frame is sent as Binary.
        """
        opcode = BINARY
        if _check_unicode(data):
            opcode = TEXT
        if data:
            self._sendMessage(False, opcode, data)

    def _sendMessage(self, fin, opcode, data):

        payload = bytearray()

        b1 = 0
        b2 = 0
        if fin is False:
            b1 |= 0x80
        b1 |= opcode

        if _check_unicode(data):
            data = data.encode('utf-8')

        length = len(data)
        payload.append(b1)

        if length <= 125:
            b2 |= length
            payload.append(b2)

        elif length >= 126 and length <= 65535:
            b2 |= 126
            payload.append(b2)
            payload.extend(struct.pack("!H", length))

        else:
            b2 |= 127
            payload.append(b2)
            payload.extend(struct.pack("!Q", length))

        if length > 0:
            payload.extend(data)

        self.sendq.append((opcode, payload))

    def _parseHEADERB1(self, byte):
        self.fin = byte & 0x80
        self.opcode = byte & 0x0F
        self.state = HEADERB2

        self.index = 0
        self.length = 0
        self.lengtharray = bytearray()
        self.data = bytearray()

        rsv = byte & 0x70
        if rsv != 0:
            raise exceptions.RSVBitError()

    def _parseHEADERB2(self, byte):
        mask = byte & 0x80
        length = byte & 0x7F

        if self.opcode == PING and length > 125:
            raise exceptions.ExcceedSize("Ping Packet length")

        if mask == 128:
            self.hasmask = True
        else:
            self.hasmask = False

        if length <= 125:
            self.length = length

            # if we have a mask we must read it
            if self.hasmask is True:
                self.maskarray = bytearray()
                self.state = MASK
            else:
                # if there is no mask and no payload we are done
                if self.length <= 0:
                    try:
                        self._handlePacket()
                    finally:
                        self.state = self.HEADERB1
                        self.data = bytearray()

                # we have no mask and some payload
                else:
                    self.data = bytearray()
                    self.state = PAYLOAD

        elif length == 126:
            self.lengtharray = bytearray()
            self.state = LENGTHSHORT

        elif length == 127:
            self.lengtharray = bytearray()
            self.state = LENGTHLONG

    def _praseLengthShort(self, byte):
        self.lengtharray.append(byte)

        if len(self.lengtharray) > 2:
            raise exceptions.ExcceedSize('short length')

        if len(self.lengtharray) == 2:
            self.length = struct.unpack_from('!H', self.lengtharray)[0]

            if self.hasmask is True:
                self.maskarray = bytearray()
                self.state = MASK
            else:
                # if there is no mask and no payload we are done
                if self.length <= 0:
                    try:
                        self._handlePacket()
                    finally:
                        self.state = HEADERB1
                        self.data = bytearray()

                # we have no mask and some payload
                else:
                    self.data = bytearray()
                    self.state = PAYLOAD

    def _parseLengthLong(self, byte):
        self.lengtharray.append(byte)

        if len(self.lengtharray) > 8:
            raise exceptions.ExcceedSize('Long length')

        if len(self.lengtharray) == 8:
            self.length = struct.unpack_from('!Q', self.lengtharray)[0]

            if self.hasmask is True:
                self.maskarray = bytearray()
                self.state = MASK
            else:
                # if there is no mask and no payload we are done
                if self.length <= 0:
                    try:
                        self._handlePacket()
                    finally:
                        self.state = HEADERB1
                        self.data = bytearray()

                # we have no mask and some payload
                else:
                    self.data = bytearray()
                    self.state = PAYLOAD

    def _parseMask(self, byte):
        self.maskarray.append(byte)

        if len(self.maskarray) > 4:
            raise exceptions.ExcceedSize('mask length')

        if len(self.maskarray) == 4:
            # if there is no mask and no payload we are done
            if self.length <= 0:
                try:
                    self._handlePacket()
                finally:
                    self.state = HEADERB1
                    self.data = bytearray()

                    # we have no mask and some payload
            else:
                self.data = bytearray()
                self.state = PAYLOAD

    def _parsePayload(self, byte):
        if self.hasmask is True:
            self.data.append(byte ^ self.maskarray[self.index % 4])
        else:
            self.data.append(byte)

        # if length exceeds allowable size then remove the connection
        if len(self.data) >= self.maxpayload:
            raise exceptions.ExcceedSize('Payload')

        # check if we have processed length bytes; if so we are done
        if (self.index + 1) == self.length:
            try:
                self._handlePacket()
            finally:
                self.state = HEADERB1
                self.data = bytearray()
        else:
            self.index += 1

    def _parseMessage(self, byte):
        # read in the header
        if self.state == HEADERB1:
            self._parseHEADERB1(byte)
        elif self.state == HEADERB2:
            self._parseHEADERB2(byte)
        elif self.state == LENGTHSHORT:
            self._praseLengthShort()
        elif self.state == LENGTHLONG:
            self._parseLengthLong(byte)
        elif self.state == MASK:
            self._parseMask(byte)
        elif self.state == PAYLOAD:
            self._parsePayload(byte)
