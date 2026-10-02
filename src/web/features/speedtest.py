"""Speedtest pages and actions for the operator console.

Host dependencies are supplied by ``ConsoleHandler.context`` so the feature
can be reused with another application context.
"""


class SpeedtestMixin:
    def page_speedtest(self, lang, query_lang):
        t = self.context.STRINGS[lang]
        ip = self.context.html.escape(self.client_ip())
        config = {
            # Maps onto LibreSpeed's own Settings keys — see vps-webserver
            # DECISIONS.md (2026-08-25, "Vendor LibreSpeed's official test engine").
            "urlDl": "/speedtest/garbage",
            "urlUl": "/speedtest/empty",
            "urlPing": "/speedtest/empty",
            "urlGetIp": "/speedtest/getip",
            # "P_D_U": ping+jitter, download, upload. No "I" (IP lookup) —
            # the IP is already server-rendered above, so skip the extra
            # round trip.
            "testOrder": "P_D_U",
            "timeDlMax": self.context.TEST_SECONDS,
            "timeUlMax": self.context.TEST_SECONDS,
            "warmup": self.context.WARMUP_SECONDS,
            "pingSamples": self.context.PING_SAMPLES,
            "downloadStreams": self.context.DOWNLOAD_STREAMS,
            "uploadStreams": self.context.UPLOAD_STREAMS,
            "overhead": self.context.OVERHEAD_FACTOR,
            "chunkSizeMiB": min(100, self.context.MAX_TEST_MB),
        }
        i18n = {k: t[k] for k in ("run_test", "running", "download", "upload",
                                  "latency", "jitter", "waiting", "warmup",
                                  "measuring", "done", "idle")}
        body = f"""
        <div class="card">
          <h1>{self.context.html.escape(t['speedtest'])}</h1>
          <p class="muted">{self.context.html.escape(t['your_ip'])}: <strong>{ip}</strong></p>
          <div class="gauges latency-row">
            <div class="gauge small-gauge">
              <div class="gauge-label">⏱ {self.context.html.escape(t['latency'])}</div>
              <div class="gauge-value" id="latency-value">{self.context.html.escape(t['idle'])}</div>
              <div class="gauge-unit">ms</div>
              <div class="gauge-state muted" id="latency-state">{self.context.html.escape(t['waiting'])}</div>
            </div>
            <div class="gauge small-gauge">
              <div class="gauge-label">〜 {self.context.html.escape(t['jitter'])}</div>
              <div class="gauge-value" id="jitter-value">{self.context.html.escape(t['idle'])}</div>
              <div class="gauge-unit">ms</div>
              <div class="gauge-state muted" id="jitter-state">&nbsp;</div>
            </div>
          </div>
          <div class="gauges">
            <div class="gauge">
              <div class="gauge-label">⬇ {self.context.html.escape(t['download'])}</div>
              <div class="gauge-value" id="download-value">{self.context.html.escape(t['idle'])}</div>
              <div class="gauge-unit">Mbps</div>
              <div class="bar"><span id="download-bar"></span></div>
              <div class="gauge-state muted" id="download-state">{self.context.html.escape(t['waiting'])}</div>
            </div>
            <div class="gauge">
              <div class="gauge-label">⬆ {self.context.html.escape(t['upload'])}</div>
              <div class="gauge-value" id="upload-value">{self.context.html.escape(t['idle'])}</div>
              <div class="gauge-unit">Mbps</div>
              <div class="bar"><span id="upload-bar"></span></div>
              <div class="gauge-state muted" id="upload-state">{self.context.html.escape(t['waiting'])}</div>
            </div>
          </div>
          <button id="run">{self.context.html.escape(t['run_test'])}</button>
        </div>
        <script id="speedtest-config" type="application/json">{self.context.json.dumps(config)}</script>
        <script id="speedtest-i18n" type="application/json">{self.context.json.dumps(i18n)}</script>
        <script src="/static/speedtest.js"></script>
        <script src="/static/speedtest-ui.js"></script>
        """
        self.send_html(200, self.render_page(t['speedtest'], body, lang, active="speedtest"),
                       self.maybe_lang_cookie(query_lang))

    def handle_speedtest_garbage(self, parsed):
        q = self.context.parse_qs(parsed.query)
        try:
            chunks = int(q.get("ckSize", ["4"])[0])
        except ValueError:
            chunks = 4
        if chunks <= 0:
            chunks = 4
        # Upstream clamps at 1024 (1 GiB); MAX_TEST_MB is our own additional
        # ceiling on top of that.
        chunks = min(chunks, 1024, self.context.MAX_TEST_MB)

        self.send_response(200)
        self.send_header("Content-Description", "File Transfer")
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", "attachment; filename=random.dat")
        self.send_header("Content-Transfer-Encoding", "binary")
        self.send_header("Content-Length", str(chunks * self.context.DOWNLOAD_CHUNK))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0, s-maxage=0")
        self.send_header("Cache-Control", "post-check=0, pre-check=0")
        self.send_header("Pragma", "no-cache")
        self.end_headers()
        for _ in range(chunks):
            self.wfile.write(self.context.FILL_BUFFER)

    def handle_speedtest_ping(self):
        """GET on the same endpoint upload POSTs to — LibreSpeed times the
        round trip of downloading this empty response itself; there is no
        separate ping protocol. See doc.md in the upstream repo.
        """
        self.send_response(200)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0, s-maxage=0")
        self.send_header("Cache-Control", "post-check=0, pre-check=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def handle_speedtest_upload(self):
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            length = 0
        length = max(0, min(length, self.context.MAX_TEST_MB * 1024 * 1024 + 1024))

        remaining = length
        buf = bytearray(self.context.DOWNLOAD_CHUNK)
        view = memoryview(buf)
        while remaining > 0:
            n = self.rfile.readinto(view[: min(len(buf), remaining)])
            if not n:
                break
            remaining -= n

        # The client only checks the HTTP status, never the response body.
        self.send_response(200)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0, s-maxage=0")
        self.send_header("Cache-Control", "post-check=0, pre-check=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def handle_speedtest_getip(self):
        # No ISP/geolocation lookup — that would need an outbound call to a
        # third party, which conflicts with the zero-dependency design (see
        # vps-webserver DECISIONS.md, "Zero third-party runtime dependencies").
        self.send_json(200, {"processedString": self.client_ip(), "rawIspInfo": ""})

    def route_speedtest(self, method, path, parsed, lang, query_lang):
        if path == "/speedtest" and method == "GET":
            self.page_speedtest(lang, query_lang)
        elif path == "/speedtest/garbage" and method == "GET":
            self.handle_speedtest_garbage(parsed)
        elif path == "/speedtest/empty" and method == "GET":
            self.handle_speedtest_ping()
        elif path == "/speedtest/empty" and method == "POST":
            self.handle_speedtest_upload()
        elif path == "/speedtest/getip" and method == "GET":
            self.handle_speedtest_getip()
        else:
            return False
        return True
