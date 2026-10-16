"""Just enough of a WebSocket client (RFC 6455) to talk to the Stream Deck app.

Standard library only, so plugins can run on the system Python. Text frames
in and out, pings answered, no fragmentation (the Stream Deck app sends none).
"""

from __future__ import annotations

import base64
import itertools
import os
import socket
import struct


def _mask(data: bytes, mask: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(data, itertools.cycle(mask)))


class WebSocket:
    def __init__(self, host: str, port: int, path: str = "/") -> None:
        self.sock = socket.create_connection((host, port))
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(request.encode())
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("websocket handshake: connection closed")
            response += chunk
        head, _, self.buf = response.partition(b"\r\n\r\n")
        status = head.split(b"\r\n", 1)[0]
        if b" 101 " not in status:
            raise ConnectionError(f"websocket handshake failed: {status!r}")

    def send(self, text: str) -> None:
        self._frame(0x1, text.encode())

    def _frame(self, opcode: int, data: bytes) -> None:
        n = len(data)
        header = bytes([0x80 | opcode])
        if n < 126:
            header += bytes([0x80 | n])
        elif n < 65536:
            header += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            header += bytes([0x80 | 127]) + struct.pack(">Q", n)
        mask = os.urandom(4)
        self.sock.sendall(header + mask + _mask(data, mask))

    def _read(self, n: int) -> bytes:
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("websocket closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def recv(self) -> str:
        """Next text message. Answers pings; raises ConnectionError on close."""
        while True:
            b0, b1 = self._read(2)
            opcode, masked, n = b0 & 0x0F, b1 & 0x80, b1 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            mask = self._read(4) if masked else None
            payload = self._read(n)
            if mask:
                payload = _mask(payload, mask)
            if opcode == 0x1:
                return payload.decode()
            if opcode == 0x9:
                self._frame(0xA, payload)
            elif opcode == 0x8:
                raise ConnectionError("websocket closed by peer")
            # binary / continuation / pong: not used by the Stream Deck app
