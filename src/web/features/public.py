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
                body = self._page().encode("utf-8")
                self._send(200, body, "text/html; charset=utf-8", send_body)
            elif path == "/favicon.ico":
                self._send(200, (self.context.BASE_DIR / "static" / "favicon.svg").read_bytes(), "image/svg+xml", send_body)
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

    def _page(self):
        # No cookie and no ?lang= here — the page has no navigation and sets
        # nothing. Accept-Language is all there is to go on, which is right for
        # a stranger who was handed an IP and nothing else.
        lang = self.context.pick_lang(None, None, self.headers.get("Accept-Language", ""))
        t = self.context.STRINGS[lang]
        # self.server is the listener this request actually arrived on, so the
        # port is the real one even with several running.
        arrived_port = self.server.server_address[1]
        scheme = "HTTPS" if getattr(self.server, "is_tls", False) else "HTTP"
        now = self.context.datetime.now(self.context.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        iperf_html = ""
        if self.context.IPERF_ENABLED:
            is_open, remaining = self.context.IPERF_WINDOW.state()
            if is_open:
                # Advertised on purpose: a tester who cannot see that the
                # window is open has no way to know when to connect, and the
                # window is deliberately open anyway.
                text = t["probe_iperf"].format(
                    port=self.context.IPERF_WINDOW.port, mins=remaining // 60, secs=remaining % 60
                )
                iperf_html = f'<p class="iperf">{self.context.html.escape(text)}</p>'

        label = self.context.server_label()
        page_title = f"{label} — {t['probe_title']}" if label else t['probe_title']
        return f"""<!doctype html>
<html lang="{self.context.HTML_LANG_TAGS.get(lang, lang)}"{self.context.RTL_ATTR.get(lang, "")}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{self.context.html.escape(page_title)}</title>
<link rel="icon" type="image/svg+xml" href="/favicon.ico">
<style>{self.context.PROBE_CSS}</style>
</head>
<body>
<main>
<h1><span class="ok">&#10003;</span> {self.context.html.escape(t['probe_title'])}</h1>
<p>{self.context.html.escape(t['probe_ok'])}</p>
{iperf_html}
<dl>
  <dt>{self.context.html.escape(t['probe_your_ip'])}</dt><dd>{self.context.html.escape(self.client_ip())}</dd>
  <dt>{self.context.html.escape(t['probe_arrived_on'])}</dt><dd>{scheme} :{arrived_port}</dd>
  <dt>{self.context.html.escape(t['probe_server_time'])}</dt><dd>{now}</dd>
</dl>
<p class="note">{self.context.html.escape(t['probe_note'])}</p>
</main>
</body>
</html>"""
