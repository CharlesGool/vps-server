"""iperf3: the time-boxed server window and port changes (the page is the single-page UI).

Host dependencies are supplied by ``ConsoleHandler.context`` so the feature
can be reused with another application context.
"""


class IperfMixin:


    def iperf_set_port(self, port):
        """Move the iperf3 window to another port; raises ValueError when it cannot."""
        if not 1024 <= port <= 65535:
            raise ValueError("invalid port")
        if port != self.context.IPERF_WINDOW.port:
            if port in self.context.PORTFWD.reserved_ports():
                raise ValueError("reserved port")
            for family, address in ((self.context.socket.AF_INET, "0.0.0.0"), (self.context.socket.AF_INET6, "::")):
                try:
                    with self.context.socket.socket(family, self.context.socket.SOCK_STREAM) as probe:
                        # Closed connections linger in TIME_WAIT; like the servers, probe with SO_REUSEADDR.
                        probe.setsockopt(self.context.socket.SOL_SOCKET, self.context.socket.SO_REUSEADDR, 1)
                        probe.bind((address, port))
                except OSError as exc:
                    if family == self.context.socket.AF_INET6 and exc.errno in (97, 93):
                        continue
                    raise ValueError("busy port") from exc
        if not self.context.IPERF_WINDOW.set_port(
                port, commit=lambda old: self.context.node_control_apply(
                    {"action": "iperf-port", "old_port": old, "port": port})):
            raise ValueError("active window or persistence failure")


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
        if not self.context.IPERF_BINARY:
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
            owner = "vps-server-iperf3-window"
            try:
                self.context.reserve_owned_port(self.context.BASE_DIR, self._port, owner)
            except (OSError, ValueError):
                return False, "iperf_port_busy"
            try:
                proc = self.context.subprocess.Popen(
                    [self.context.IPERF_BINARY, "--server", "--port", str(self._port)],
                    stdin=self.context.subprocess.DEVNULL,
                    stdout=self.context.subprocess.DEVNULL,
                    stderr=self.context.subprocess.DEVNULL,
                )
            except OSError:
                self.context.release_owned_port(self.context.BASE_DIR, self._port, owner)
                return False, "iperf_missing"
            # iperf3 exits straight away if the port is taken. Without this
            # pause the console would report an open window that is not
            # listening to anything.
            self.context.time.sleep(0.3)
            if proc.poll() is not None:
                self.context.release_owned_port(self.context.BASE_DIR, self._port, owner)
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
            self.context.release_owned_port(self.context.BASE_DIR, self._port,
                                            "vps-server-iperf3-window")

    def _close(self):
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        proc, self._proc = self._proc, None
        self._deadline = 0.0
        if proc is None:
            self.context.release_owned_port(self.context.BASE_DIR, self._port,
                                            "vps-server-iperf3-window")
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
            self.context.release_owned_port(self.context.BASE_DIR, self._port,
                                            "vps-server-iperf3-window")
