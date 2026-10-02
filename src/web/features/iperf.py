"""Iperf pages and actions for the operator console.

Host dependencies are supplied by ``ConsoleHandler.context`` so the feature
can be reused with another application context.
"""


class IperfMixin:
    def iperf_client_result_key(self):
        return self.get_cookie('session') or ('peer', self.client_address[0])

    def page_iperf(self, lang, query_lang, client_result=None, client_values=None):
        t = self.context.STRINGS[lang]
        if (self.context.BASE_DIR / ".install-state").is_file() and "iperf3" not in self.context.installed_modules(self.context.BASE_DIR):
            return self.page_module_not_installed(lang, query_lang, "iperf3", "iperf3", active="iperf")
        if client_result is None and self.context.parse_qs(
                self.context.urlsplit(self.path).query).get('client') == ['done']:
            client_result, client_values = self.context.IPERF_CLIENT.take_result(
                self.iperf_client_result_key())
        port = self.context.IPERF_WINDOW.port
        is_open, remaining = self.context.IPERF_WINDOW.state()

        notice = ""
        key = self.context.parse_qs(self.context.urlsplit(self.path).query).get("msg", [""])[0]
        if key in self.context.IPERF_MESSAGE_KEYS:
            cls = "error" if key == "iperf_port_invalid" else "notice"
            notice = f'<p class="{cls}">{self.context.html.escape(t[key].format(port="••••••"))}</p>'

        countdown_script = ""
        if is_open:
            # The countdown used to be a static string baked in at render
            # time — an operator reported it never moving, only a manual
            # reload showed a new value. deadline is an absolute Unix
            # timestamp so /static/iperf-countdown.js can tick the visible
            # minutes/seconds down every second without another request,
            # and reload once it reaches zero (the window has actually
            # closed itself server-side by then). None of the interpolated
            # values are attacker-controlled — port is server config, mins/
            # secs are ints — so building this without html.escape is safe;
            # escaping it would also escape the <span> tags the script needs.
            deadline = int(self.context.time.time()) + remaining
            state = t["iperf_state_open"].format(
                port='••••••',
                mins=f'<span id="iperf-mins">{remaining // 60}</span>',
                secs=f'<span id="iperf-secs">{remaining % 60}</span>',
            )
            state_attr = f' data-iperf-deadline="{deadline}"'
            countdown_script = '<script src="/static/iperf-countdown.js"></script>'
            # While a window is open, submitting the same form pushes the
            # deadline out rather than starting a second server. Labelling it
            # "open" then leaves two buttons that look like they compete; the
            # pair only reads correctly as extend / close.
            open_label = t["iperf_extend"]
            close_form = f"""
            <form method="post" action="/iperf/close">
              <button type="submit" class="danger">{self.context.html.escape(t['iperf_close'])}</button>
            </form>
            """
        else:
            state = self.context.html.escape(t["iperf_state_closed"].format(port='••••••'))
            state_attr = ""
            open_label = t["iperf_open"]
            close_form = ""

        commands = ''.join(
            f'<div class="copyrow"><div class="copyhead">{self.context.html.escape(t[label])}</div>'
            f'{self.private_value_control("iperf", field, t, copy=True)}</div>'
            for label, field in (("iperf_cmd_speed", "cmd-speed"),
                                 ("iperf_cmd_single", "cmd-single"),
                                 ("iperf_cmd_multi", "cmd-multi")))

        client_values = client_values or {}
        client_host = self.context.html.escape(client_values.get('host', ''), quote=True)
        client_port = self.context.html.escape(client_values.get('port', '5201'), quote=True)
        client_seconds = self.context.html.escape(client_values.get('seconds', '10'), quote=True)
        client_mbps = self.context.html.escape(client_values.get('mbps', '100'), quote=True)

        def options(name, choices):
            selected = client_values.get(name, choices[0][0])
            return ''.join(
                f'<option value="{value}" {"selected" if value == selected else ""}>'
                f'{self.context.html.escape(t[key])}</option>'
                for value, key in choices)

        client_notice = ''
        if client_result:
            status = client_result['status']
            if status == 'done':
                metrics = [f"{self.context.html.escape(t['iperf_client_speed'])}: "
                           f"{client_result['mbps']:.2f} Mbit/s"]
                for field, key, unit in (('jitter_ms', 'iperf_client_jitter', 'ms'),
                                         ('loss_percent', 'iperf_client_loss', '%'),
                                         ('retransmits', 'iperf_client_retransmits', '')):
                    if field in client_result:
                        metrics.append(f"{self.context.html.escape(t[key])}: "
                                       f"{client_result[field]}{unit}")
                client_notice = (f'<div class="notice" role="status"><strong>'
                                 f'{self.context.html.escape(t["iperf_client_done"])}</strong>'
                                 f'<p>{" · ".join(metrics)}</p></div>')
            else:
                detail = client_result.get('detail', '')
                message = self.context.html.escape(t['iperf_client_' + status])
                if detail:
                    message += f' {self.context.html.escape(detail)}'
                client_notice = f'<p class="error" role="alert">{message}</p>'

        csrf = self.context.access_csrf_token(self.get_cookie('session'), 'iperf-client')
        client_form = f"""
        <div class="card">
          <h2>{self.context.html.escape(t['iperf_client_heading'])}</h2>
          <p class="muted">{self.context.html.escape(t['iperf_client_hint'])}</p>
          {client_notice}
          <form method="post" action="/iperf/client" class="iperf-client-form">
            <input type="hidden" name="csrf" value="{csrf}">
            <label>{self.context.html.escape(t['iperf_client_host'])}<input name="host" inputmode="decimal" value="{client_host}" required></label>
            <label>{self.context.html.escape(t['iperf_client_port'])}<input type="number" name="port" min="1" max="65535" value="{client_port}" required></label>
            <label>{self.context.html.escape(t['iperf_client_seconds'])}<input type="number" name="seconds" min="1" max="30" value="{client_seconds}" required></label>
            <label>{self.context.html.escape(t['iperf_client_mbps'])}<input type="number" name="mbps" min="1" max="1000" value="{client_mbps}" required></label>
            <label>{self.context.html.escape(t['iperf_client_protocol'])}<select name="protocol">{options('protocol', [('tcp', 'iperf_client_tcp'), ('udp', 'iperf_client_udp')])}</select></label>
            <label>{self.context.html.escape(t['iperf_client_direction'])}<select name="direction">{options('direction', [('upload', 'iperf_client_upload'), ('download', 'iperf_client_download')])}</select></label>
            <button type="submit">{self.context.html.escape(t['iperf_client_start'])}</button>
          </form>
        </div>
        """

        body = f"""
        <div class="iperf-panels">
        <div class="card">
          <h1>{self.context.html.escape(t['iperf_heading'])}</h1>
          {notice}
          <div class="iperf-facts">
            <div class="iperf-fact"><span>{self.context.html.escape(t['iperf_status'])}</span><strong class="iperf-state {'is-open' if is_open else 'is-closed'}"{state_attr}>{state}</strong></div>
            <div class="iperf-fact"><span>{self.context.html.escape(t['iperf_port'])}</span><strong>{self.private_value_control('iperf', 'port', t)}</strong></div>
          </div>
          <form method="post" action="/iperf/port" class="iperf-port-form">
            <label>{self.context.html.escape(t['iperf_change_port'])}<input type="number" name="port" min="1024" max="65535" placeholder="••••••" required {'disabled' if is_open else ''}></label>
            <button type="submit" {'disabled' if is_open else ''}>{self.context.html.escape(t['iperf_save_port'])}</button>
          </form>
          <div class="iperf-actions">
            <form method="post" action="/iperf/open" class="inline-form">
              <label>{self.context.html.escape(t['iperf_minutes'])}
                <input type="number" name="minutes" min="1" max="{self.context.IPERF_MAX_MINUTES}"
                       value="{self.context.IPERF_DEFAULT_MINUTES}" required>
              </label>
              <button type="submit">{self.context.html.escape(open_label)}</button>
            </form>
            {close_form}
          </div>
          <p class="muted">{self.context.html.escape(t['iperf_howto'])}</p>
          {commands}
        </div>
        {client_form}
        </div>
        <script src="/static/copy.js"></script>
        <script src="/static/private-values.js"></script>
        {countdown_script}
        """
        self.send_html(200, self.render_page(t['iperf_heading'], body, lang, active="iperf"),
                       {**self.maybe_lang_cookie(query_lang), 'Cache-Control': 'no-store'})

    def handle_iperf_client(self, lang, query_lang):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 1024 or self.headers.get('Content-Type', '').split(';', 1)[0] != 'application/x-www-form-urlencoded':
                raise ValueError('invalid form')
            form = self.context.parse_qs(self.read_body(1024).decode('utf-8'),
                                         strict_parsing=True, keep_blank_values=True)
            expected = {'csrf', 'host', 'port', 'seconds', 'mbps', 'protocol', 'direction'}
            if set(form) != expected or any(len(values) != 1 for values in form.values()):
                raise ValueError('invalid form')
        except (ValueError, UnicodeError):
            return self.send_html(400, 'Invalid request', {'Cache-Control': 'no-store'})
        values = {key: value[0] for key, value in form.items()}
        csrf = self.context.access_csrf_token(self.get_cookie('session'), 'iperf-client')
        if not self.context.hmac.compare_digest(values.pop('csrf'), csrf):
            return self.send_html(403, 'Forbidden', {'Cache-Control': 'no-store'})
        result = ({'status': 'disabled'} if not self.context.IPERF_ENABLED else
                  self.context.IPERF_CLIENT.run(values['host'], values['port'],
                                                values['protocol'], values['direction'],
                                                values['seconds'], values['mbps']))
        self.context.IPERF_CLIENT.remember_result(self.iperf_client_result_key(), result, values)
        self.redirect('/iperf?client=done', {'Cache-Control': 'no-store'})

    def handle_iperf_open(self):
        raw = self.read_body(self.context.LOGIN_BODY_LIMIT)
        form = self.context.parse_qs(raw.decode("utf-8", errors="replace"))
        minutes = form.get("minutes", [str(self.context.IPERF_DEFAULT_MINUTES)])[0]
        _, key = self.context.IPERF_WINDOW.open(minutes)
        self.redirect(f"/iperf?msg={key}")

    def handle_iperf_close(self):
        self.read_body(self.context.LOGIN_BODY_LIMIT)  # drain: keep-alive needs the body gone
        self.context.IPERF_WINDOW.close()
        self.redirect("/iperf?msg=iperf_shut")

    def handle_iperf_port(self):
        raw = self.read_body(self.context.LOGIN_BODY_LIMIT)
        try:
            form = self.context.parse_qs(raw.decode("utf-8"), strict_parsing=True)
            if set(form) != {"port"} or len(form["port"]) != 1:
                raise ValueError("invalid form")
            port = int(form["port"][0])
            if not 1024 <= port <= 65535:
                raise ValueError("invalid port")
            if port != self.context.IPERF_WINDOW.port:
                if port in self.context.PORTFWD.reserved_ports():
                    raise ValueError("reserved port")
                for family, address in ((self.context.socket.AF_INET, "0.0.0.0"), (self.context.socket.AF_INET6, "::")):
                    try:
                        with self.context.socket.socket(family, self.context.socket.SOCK_STREAM) as probe:
                            probe.bind((address, port))
                    except OSError as exc:
                        if family == self.context.socket.AF_INET6 and exc.errno in (97, 93):
                            continue
                        raise ValueError("busy port") from exc
            if not self.context.IPERF_WINDOW.set_port(
                    port, commit=lambda old: self.context.node_control_apply(
                        {"action": "iperf-port", "old_port": old, "port": port})):
                raise ValueError("active window or persistence failure")
        except (UnicodeError, ValueError):
            return self.redirect("/iperf?msg=iperf_port_invalid")
        return self.redirect("/iperf?msg=iperf_port_saved")

    def route_iperf(self, method, path, parsed, lang, query_lang):
        if method == "GET" and path == "/iperf":
            self.page_iperf(lang, query_lang)
        elif method == "POST" and path == "/iperf/open":
            self.handle_iperf_open()
        elif method == "POST" and path == "/iperf/close":
            self.handle_iperf_close()
        elif method == "POST" and path == "/iperf/port":
            self.handle_iperf_port()
        elif method == "POST" and path == "/iperf/client":
            self.handle_iperf_client(lang, query_lang)
        else:
            return False
        return True


class IperfWindow:
    """A time-boxed `iperf3 -s`, opened from the console and self-closing.

    The state lives in memory and nowhere else. If the service dies, the
    window dies with it — the safe direction to fail. A restart never
    resurrects a window somebody opened and forgot about.
    """

    def __init__(self, port, max_minutes, port_file=None):
        self._port_file = self.context.Path(port_file) if port_file else None
        self._port = port
        if self._port_file and self._port_file.exists():
            try:
                saved = int(self._port_file.read_text().strip())
                if 1 <= saved <= 65535:
                    self._port = saved
            except (OSError, ValueError):
                pass
        self._max_minutes = max_minutes
        self._lock = self.context.threading.RLock()
        self._proc = None
        self._deadline = 0.0
        self._timer = None

    @property
    def port(self):
        with self._lock:
            return self._port

    def set_port(self, port, commit=None):
        """Change the port while closed; persist it for the next restart."""
        if type(port) is not int or not 1 <= port <= 65535:
            return False
        with self._lock:
            self._reap()
            if self._proc is not None:
                return False
            if commit is not None:
                if not commit(self._port):
                    return False
            elif self._port_file:
                stage = self._port_file.with_suffix(".tmp")
                try:
                    stage.write_text(str(port) + "\n")
                    self.context.os.chmod(stage, 0o600)
                    stage.replace(self._port_file)
                except OSError:
                    stage.unlink(missing_ok=True)
                    return False
            self._port = port
            return True

    def state(self):
        """(is_open, remaining_seconds), reaping an iperf3 that died on its own."""
        with self._lock:
            self._reap()
            if self._proc is None:
                return False, 0
            return True, max(0, int(self._deadline - self.context.time.time()))

    def open(self, minutes):
        """Open or extend a window. Returns (ok, key) where key is a STRINGS key."""
        if not self.context.IPERF_ENABLED:
            return False, "iperf_disabled"
        if not self.context.shutil.which("iperf3"):
            return False, "iperf_missing"
        try:
            minutes = int(minutes)
        except (TypeError, ValueError):
            minutes = self.context.IPERF_DEFAULT_MINUTES
        minutes = max(1, min(minutes, self._max_minutes))

        with self._lock:
            self._reap()
            if self._proc is not None:
                # Already open. Extend it instead of spawning a second server
                # on the same port, which would only fail to bind.
                self._deadline = self.context.time.time() + minutes * 60
                self._arm()
                return True, "iperf_extended"
            try:
                proc = self.context.subprocess.Popen(
                    ["iperf3", "--server", "--port", str(self._port)],
                    stdin=self.context.subprocess.DEVNULL,
                    stdout=self.context.subprocess.DEVNULL,
                    stderr=self.context.subprocess.DEVNULL,
                )
            except OSError:
                return False, "iperf_missing"
            # iperf3 exits straight away if the port is taken. Without this
            # pause the console would report an open window that is not
            # listening to anything.
            self.context.time.sleep(0.3)
            if proc.poll() is not None:
                return False, "iperf_port_busy"
            self._proc = proc
            self._deadline = self.context.time.time() + minutes * 60
            self.context.firewall_port(self._port, opening=True)
            self._arm()
            return True, "iperf_opened"

    def close(self):
        with self._lock:
            self._close()

    # -- internals; every one of these runs under self._lock ---------------

    def _arm(self):
        if self._timer is not None:
            self._timer.cancel()
        self._timer = self.context.threading.Timer(
            max(0.0, self._deadline - self.context.time.time()), self._expire
        )
        self._timer.daemon = True
        self._timer.start()

    def _expire(self):
        with self._lock:
            # An open() between this timer firing and acquiring the lock may
            # have pushed the deadline out. Only close if time really is up.
            if self._proc is not None and self.context.time.time() >= self._deadline - 0.5:
                self._close()

    def _reap(self):
        if self._proc is not None and self._proc.poll() is not None:
            self._proc = None
            self._deadline = 0.0
            self.context.firewall_port(self._port, opening=False)

    def _close(self):
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        proc, self._proc = self._proc, None
        self._deadline = 0.0
        if proc is None:
            return
        # Withdraw the rule whatever happens to the process. A child that will
        # not die within ten seconds is a problem; a firewall left open for a
        # window this object already reports as closed is a worse one, and
        # letting TimeoutExpired escape here produced exactly that — the state
        # said shut, the port stayed open.
        try:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except self.context.subprocess.TimeoutExpired:
                proc.kill()
                try:
                    proc.wait(timeout=5)
                except self.context.subprocess.TimeoutExpired:
                    print(self.context._log_text('log_iperf_stuck', pid=proc.pid), file=self.context.sys.stderr)
        finally:
            self.context.firewall_port(self._port, opening=False)
