"""Authenticated WebSocket bridge to a short-lived local root PTY."""

import base64
import binascii
import fcntl
import hashlib
import json
import os
import pty
import select
import signal
import socket
import ssl
import struct
import termios
import threading
import time
from urllib.parse import urlsplit


MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MAX_FRAME = 65536
_SLOTS = threading.BoundedSemaphore(2)


def _exact(sock, size):
    data = bytearray()
    while len(data) < size:
        part = sock.recv(size - len(data))
        if not part:
            raise ConnectionError("terminal connection closed")
        data.extend(part)
    return bytes(data)


def _frame(sock):
    first, second = _exact(sock, 2)
    if first & 0x70 or not first & 0x80 or not second & 0x80:
        raise ValueError("unsupported WebSocket frame")
    length = second & 0x7f
    if length == 126:
        length = struct.unpack("!H", _exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", _exact(sock, 8))[0]
    if length > MAX_FRAME:
        raise ValueError("terminal frame too large")
    mask = _exact(sock, 4)
    payload = _exact(sock, length)
    return first & 0x0f, bytes(value ^ mask[index % 4] for index, value in enumerate(payload))


def _send(sock, opcode, payload=b""):
    header = bytes((0x80 | opcode,))
    size = len(payload)
    if size < 126:
        header += bytes((size,))
    elif size < 65536:
        header += bytes((126,)) + struct.pack("!H", size)
    else:
        header += bytes((127,)) + struct.pack("!Q", size)
    sock.sendall(header + payload)


def serve(handler, context, parsed):
    token = handler.get_cookie("session")
    query = context.parse_qs(parsed.query)
    origin = handler.headers.get("Origin", "")
    requested = urlsplit(origin)
    expected_scheme = "https" if isinstance(handler.connection, ssl.SSLSocket) else "http"
    key = handler.headers.get("Sec-WebSocket-Key", "")
    try:
        raw_key = base64.b64decode(key, validate=True)
    except (ValueError, binascii.Error):
        raw_key = b""
    if (not context.AUTH_ENABLED or not context.module_feature_enabled(context.BASE_DIR, "terminal")
            or not context.security_settings_valid(token)
            or query.get("token") != [context.access_csrf_token(token, "terminal")]
            or requested.scheme != expected_scheme or requested.netloc != handler.headers.get("Host")
            or len(raw_key) != 16 or handler.headers.get("Sec-WebSocket-Version") != "13"
            or handler.headers.get("Upgrade", "").lower() != "websocket"
            or "upgrade" not in handler.headers.get("Connection", "").lower()):
        return handler.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
    if not _SLOTS.acquire(blocking=False):
        return handler.send_html(429, "Terminal busy", {"Cache-Control": "no-store"})

    try:
        accept = base64.b64encode(hashlib.sha1((key + MAGIC).encode("ascii")).digest()).decode("ascii")
        handler.send_response(101, "Switching Protocols")
        handler.send_header("Upgrade", "websocket")
        handler.send_header("Connection", "Upgrade")
        handler.send_header("Sec-WebSocket-Accept", accept)
        handler.end_headers()
        handler._body_started = True
        handler.close_connection = True
        pid, master = pty.fork()
    except BaseException:
        _SLOTS.release()
        raise
    if pid == 0:
        os.chdir("/root")
        environment = {"HOME": "/root", "USER": "root", "LOGNAME": "root", "SHELL": "/bin/bash",
                       "TERM": "xterm-256color", "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                       "LANG": os.environ.get("LANG", "C.UTF-8")}
        os.execve("/bin/bash", ["/bin/bash", "-li"], environment)
    connection = handler.connection
    connection.settimeout(10)
    deadline = time.monotonic() + 1800
    try:
        while (time.monotonic() < deadline and context.security_settings_valid(token)
               and context.module_feature_enabled(context.BASE_DIR, "terminal")):
            readable, _, _ = select.select((connection, master), (), (), 0.5)
            if master in readable:
                try:
                    output = os.read(master, 16384)
                except OSError:
                    break
                if not output:
                    break
                _send(connection, 2, output)
            if connection in readable:
                opcode, payload = _frame(connection)
                deadline = time.monotonic() + 1800
                if opcode == 8:
                    break
                if opcode == 9:
                    _send(connection, 10, payload)
                elif opcode == 1:
                    message = json.loads(payload.decode("utf-8"))
                    if not isinstance(message, dict):
                        raise ValueError("invalid terminal message")
                    if message.get("type") == "input" and isinstance(message.get("data"), str):
                        data = message["data"].encode("utf-8")
                        if len(data) > 16384:
                            raise ValueError("terminal input too long")
                        os.write(master, data)
                    elif message.get("type") == "resize":
                        rows, cols = message.get("rows"), message.get("cols")
                        if type(rows) is not int or type(cols) is not int or not 10 <= rows <= 200 or not 20 <= cols <= 400:
                            raise ValueError("invalid terminal size")
                        fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
                        os.kill(pid, signal.SIGWINCH)
                    else:
                        raise ValueError("invalid terminal action")
                else:
                    raise ValueError("unsupported terminal frame")
    except (ConnectionError, OSError, ValueError, json.JSONDecodeError, socket.timeout):
        pass
    finally:
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        os.close(master)
        try:
            os.waitpid(pid, 0)
        except ChildProcessError:
            pass
        _SLOTS.release()
