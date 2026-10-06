"""Unauthenticated reachability page, isolated from console routes."""


class PublicMixin:
    """The unauthenticated page on 80 and 443."""

    # No version string: whoever scans this port learns that something
    # answered, which is the entire point, and nothing more.
    server_version = "vps-server"
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        pass  # requests go to the visitor log instead

    def version_string(self):
        # Without this the base class appends sys_version and the page that
        # promises to disclose nothing about the host answers
        # "Server: vps-server Python/3.10.12" to any anonymous HEAD.
        return self.server_version

    def send_response(self, code, message=None):
        self._last_status = code
        super().send_response(code, message)

    def client_ip(self):
        if self.context.TRUST_PROXY:
            xff = self.headers.get("X-Forwarded-For")
            if xff:
                return xff.split(",")[0].strip()
        return self.client_address[0]

    def do_GET(self):
        self._dispatch(send_body=True)

    def do_HEAD(self):
        self._dispatch(send_body=False)

    def _dispatch(self, send_body):
        self._last_status = 200
        path = self.context.urlsplit(self.path).path
        try:
            if path == "/":
                self._send(200, self._text().encode("utf-8"), "text/plain; charset=utf-8", send_body)
            elif path == "/favicon.ico":
                self._send(200, (self.context.STATIC_DIR / "favicon.svg").read_bytes(), "image/svg+xml", send_body)
            else:
                self._send(404, b"not found\n", "text/plain; charset=utf-8", send_body)
        except (BrokenPipeError, ConnectionResetError):
            self._last_status = 0  # client hung up; not a real outcome
        finally:
            if self._last_status:
                # This listener is the one strangers reach, so it is the one
                # most likely to be hitting a full disk or a busy database.
                # Failing to record a visit is not a reason to drop the
                # connection that was successfully served.
                try:
                    self.context.log_visit(self.client_ip(), self.command, path, self._last_status)
                except Exception as exc:
                    print(self.context._log_text('log_visitor_write', error=exc), file=self.context.sys.stderr)

    def _send(self, status, body, content_type, send_body):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        if send_body and body:
            self.wfile.write(body)

    def _text(self):
        # Plain text, one line: the address the server sees. Accept-Language is
        # all there is to go on for a stranger who was handed an IP and nothing else.
        lang = self.context.pick_lang(None, None, self.headers.get("Accept-Language", ""))
        label = self.context.STRINGS[lang]["probe_your_ip"]
        return f"{label}{'：' if lang == 'zh_cn' else ': '}{self.client_ip()}\n"
