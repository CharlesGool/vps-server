"""Forward the console's /lucky/ path to Lucky's loopback admin page.

Lucky refuses non-LAN clients while AllowInternetaccess is false. Requests
reach it from 127.0.0.1 here, after the console's own login, so the admin
port never has to be opened to the Internet. Lucky's page uses relative
URLs and hash routes, so stripping the prefix is enough.

Bodies are copied in chunks: the smallest supported hosts have about 460 MB
of memory, and Lucky can upload and download files.
"""

import http.client
import select
import socket
import ssl
import threading
import time
from urllib.parse import urlsplit

PREFIX = "/lucky"
CHUNK = 64 * 1024
CONNECT_SECONDS = 5
# Long enough for Lucky's slow API calls (update checks, certificate
# requests); an idle WebSocket ends after the same time without traffic.
IDLE_SECONDS = 300
TARGET_SECONDS = 15
MAX_TUNNELS = 8

# Hop-by-hop headers are per connection. Client address headers would let
# Lucky see the public IP and refuse the request; console cookies are none
# of Lucky's business.
_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "proxy-connection",
        "te", "trailer", "trailers", "transfer-encoding", "upgrade"}
_DROP_REQUEST = _HOP | {"host", "content-length", "cookie", "origin", "referer", "forwarded",
                        "x-forwarded-for", "x-forwarded-host", "x-forwarded-proto", "x-forwarded-port",
                        "x-real-ip", "x-client-ip", "true-client-ip", "cf-connecting-ip"}
_DROP_RESPONSE = _HOP | {"content-length", "server", "date"}
_CONSOLE_COOKIES = {"session", "lang"}
# Lucky's page checks its author's sites for updates and shows them in an
# iframe, as it does on its own port, and its status page decodes with
# protobufjs, which compiles code at run time. Scripts still come only from here.
LUCKY_CSP = ("default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; "
             "img-src 'self' data: blob: https:; font-src 'self' data:; connect-src 'self' https:; "
             "frame-src 'self' https:; worker-src 'self' blob:; object-src 'none'; base-uri 'self'; "
             "form-action 'self'; frame-ancestors 'none'")

_target = {"value": None, "at": 0.0}
_target_lock = threading.Lock()
_tunnels = threading.BoundedSemaphore(MAX_TUNNELS)


class Unavailable(Exception):
    """Lucky is not installed, not running, or not answering."""


def target(context):
    """(port, scheme) of Lucky's admin page, cached because finding it is slow."""
    now = time.monotonic()
    with _target_lock:
        if _target["value"] and now - _target["at"] < TARGET_SECONDS:
            return _target["value"]
    data = context.lucky_admin()
    if data is None or (context.STATE_FILE.is_file() and
                        "lucky" not in context.installed_modules(context.BASE_DIR)):
        raise Unavailable("Lucky is not installed")
    value = (data["AdminWebListenPort"], data.get("_scheme", "http"))
    with _target_lock:
        _target["value"], _target["at"] = value, now
    return value


def forget_target():
    with _target_lock:
        _target["value"] = None


def _upstream_path(handler):
    raw = handler.path
    if raw.startswith(("http://", "https://")):
        parts = urlsplit(raw)
        raw = parts.path + ("?" + parts.query if parts.query else "")
    rest = raw[len(PREFIX):]
    return rest if rest.startswith("/") else "/" + rest


def _request_headers(handler, port):
    headers = []
    for name, value in handler.headers.items():
        if name.lower() not in _DROP_REQUEST:
            headers.append((name, value))
    cookies = []
    for name, value in handler.headers.items():
        if name.lower() != "cookie":
            continue
        for item in value.split(";"):
            key = item.split("=", 1)[0].strip()
            if key and key not in _CONSOLE_COOKIES:
                cookies.append(item.strip())
    if cookies:
        headers.append(("Cookie", "; ".join(cookies)))
    headers.append(("Host", f"127.0.0.1:{port}"))
    return headers


def _same_origin(handler):
    """Browsers always send Origin on WebSocket handshakes; require ours."""
    origin = urlsplit(handler.headers.get("Origin", ""))
    expected = "https" if isinstance(handler.connection, ssl.SSLSocket) else "http"
    return origin.scheme == expected and origin.netloc == handler.headers.get("Host")


def _rewrite_location(value, port):
    parts = urlsplit(value)
    if parts.scheme in ("http", "https") and parts.hostname in ("127.0.0.1", "localhost") \
            and (parts.port or (443 if parts.scheme == "https" else 80)) == port:
        value = parts.path or "/"
        if parts.query:
            value += "?" + parts.query
        if parts.fragment:
            value += "#" + parts.fragment
    elif parts.scheme or parts.netloc:
        return value
    return PREFIX + value if value.startswith("/") else value


def _keep_cookie(value):
    name = value.split("=", 1)[0].strip()
    return name not in _CONSOLE_COOKIES


def _connection(port, scheme):
    if scheme == "https":
        # Lucky's own certificate is self-signed; this hop never leaves the host.
        tls = ssl._create_unverified_context()
        return http.client.HTTPSConnection("127.0.0.1", port, timeout=CONNECT_SECONDS, context=tls)
    return http.client.HTTPConnection("127.0.0.1", port, timeout=CONNECT_SECONDS)


def forward(handler, context, method):
    """Proxy one request. Raises Unavailable before anything is sent."""
    if handler.headers.get("Upgrade", "").lower() == "websocket":
        return _tunnel(handler, context)
    port, scheme = target(context)
    if handler.headers.get("Transfer-Encoding"):
        # Browsers send Content-Length for every body Lucky's page produces.
        handler.close_connection = True
        return handler.send_html(411, "Length Required", {"Cache-Control": "no-store"})
    try:
        length = int(handler.headers.get("Content-Length") or 0)
    except ValueError:
        length = -1
    if length < 0:
        handler.close_connection = True
        return handler.send_html(400, "Bad Request", {"Cache-Control": "no-store"})
    upstream = _connection(port, scheme)
    try:
        try:
            upstream.connect()
        except OSError as exc:
            forget_target()
            raise Unavailable("Lucky is not answering") from exc
        upstream.sock.settimeout(IDLE_SECONDS)
        upstream.putrequest(method, _upstream_path(handler), skip_host=True, skip_accept_encoding=True)
        for name, value in _request_headers(handler, port):
            upstream.putheader(name, value)
        if length or method in ("POST", "PUT", "PATCH"):
            upstream.putheader("Content-Length", str(length))
        upstream.endheaders()
        remaining = length
        while remaining:
            data = handler.rfile.read(min(CHUNK, remaining))
            if not data:
                raise ConnectionResetError("client closed the request body")
            upstream.send(data)
            remaining -= len(data)
        # The body is consumed, so the client connection can be reused.
        handler._close_after_response = False
        handler.close_connection = False
        response = upstream.getresponse()
        _relay(handler, response, method, port)
    finally:
        upstream.close()


def _relay(handler, response, method, port):
    handler.send_response(response.status, response.reason)
    for name, value in response.getheaders():
        lower = name.lower()
        if lower in _DROP_RESPONSE:
            continue
        if lower == "location":
            value = _rewrite_location(value, port)
        elif lower == "set-cookie" and not _keep_cookie(value):
            continue
        handler.send_header(name, value)
    if response.getheader("Content-Security-Policy") is None:
        handler.send_header("Content-Security-Policy", LUCKY_CSP)
    no_body = method == "HEAD" or response.status in (204, 304) or 100 <= response.status < 200
    length = response.getheader("Content-Length")
    if no_body:
        if length is not None:
            handler.send_header("Content-Length", length)
        handler.end_headers()
        return
    if length is not None and length.isdecimal():
        handler.send_header("Content-Length", length)
        handler.end_headers()
        remaining = int(length)
        while remaining > 0:
            data = response.read1(min(CHUNK, remaining))
            if not data:
                # Lucky stopped early; the client must not reuse a short response.
                handler.close_connection = True
                break
            handler.wfile.write(data)
            remaining -= len(data)
        return
    # Unknown length (streams, logs): re-chunk so the connection can stay open.
    handler.send_header("Transfer-Encoding", "chunked")
    handler.end_headers()
    while True:
        data = response.read1(CHUNK)
        if not data:
            break
        handler.wfile.write(b"%x\r\n%s\r\n" % (len(data), data))
        handler.wfile.flush()
    handler.wfile.write(b"0\r\n\r\n")


def _tunnel(handler, context):
    if not _same_origin(handler):
        return handler.send_html(403, "Forbidden", {"Cache-Control": "no-store"})
    port, scheme = target(context)
    if not _tunnels.acquire(blocking=False):
        return handler.send_html(429, "Too many Lucky connections", {"Cache-Control": "no-store"})
    try:
        try:
            upstream = socket.create_connection(("127.0.0.1", port), timeout=CONNECT_SECONDS)
            if scheme == "https":
                upstream = ssl._create_unverified_context().wrap_socket(upstream, server_hostname="127.0.0.1")
        except OSError as exc:
            forget_target()
            raise Unavailable("Lucky is not answering") from exc
        try:
            lines = [f"GET {_upstream_path(handler)} HTTP/1.1", f"Host: 127.0.0.1:{port}",
                     f"Origin: {scheme}://127.0.0.1:{port}", "Connection: Upgrade", "Upgrade: websocket"]
            for name, value in _request_headers(handler, port):
                if name.lower() != "host":
                    lines.append(f"{name}: {value}")
            upstream.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("latin-1"))
            upstream.settimeout(IDLE_SECONDS)
            head = b""
            while b"\r\n\r\n" not in head:
                data = upstream.recv(CHUNK)
                if not data or len(head) > 65536:
                    raise ConnectionResetError("Lucky closed the WebSocket handshake")
                head += data
            head, rest = head.split(b"\r\n\r\n", 1)
            status = head.split(b"\r\n", 1)[0].split()
            handler._last_status = int(status[1]) if len(status) > 1 and status[1].isdigit() else 502
            # Lucky's handshake reply goes back unchanged; it has no console headers to keep.
            handler._body_started = True
            handler.close_connection = True
            handler.wfile.write(head + b"\r\n\r\n" + rest)
            handler.wfile.flush()
            if handler._last_status == 101:
                _pump(handler.connection, upstream)
        finally:
            upstream.close()
    finally:
        _tunnels.release()


def _readable(sockets):
    ready = [sock for sock in sockets if isinstance(sock, ssl.SSLSocket) and sock.pending()]
    if ready:
        return ready
    readable, _, _ = select.select(sockets, (), (), IDLE_SECONDS)
    return readable


def _pump(client, upstream):
    client.settimeout(IDLE_SECONDS)
    peers = {client: upstream, upstream: client}
    while True:
        readable = _readable([client, upstream])
        if not readable:
            return
        for sock in readable:
            try:
                data = sock.recv(CHUNK)
            except ssl.SSLWantReadError:
                continue
            if not data:
                return
            peers[sock].sendall(data)
