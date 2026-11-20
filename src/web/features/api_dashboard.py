"""JSON API for the home page: feature switches, module jobs and the host's total traffic."""

from features.modules import module_job_recent, module_job_text, public_listener_occupied
from features.traffic import TOTAL_LOCK
from field_errors import FieldError, details, schedule_error


def total_problem(error, body, name):
    """The field a total_meter.parse_* ValueError is about; ``name`` is the number's key in the request."""
    message = str(error)
    if message == "invalid reset schedule" and error.__cause__ is not None:
        return schedule_error(error.__cause__, body.get("resetSpec"), "resetSpec")
    if message.startswith("reset schedule must be"):
        return FieldError("resetSpec.mode", "format", message)
    if message == "invalid reset day":
        return FieldError("resetDay", "range" if str(body.get("resetDay")).strip().isdigit() else "format", message)
    if message in ("cap must be positive", "cap out of range", "usage must not be negative", "usage out of range"):
        return FieldError(name, "range", message)
    # float() refused the text.
    return FieldError(name, "format", message)

# Home page entries in display order: (key, page, switchable).
DASHBOARD_ITEMS = (
    ("web_public", "/public/http", True), ("speedtest", "/speedtest", True), ("iperf3", "/iperf", True),
    ("proxy_nodes", "/proxy", True), ("frps", "/frps", True), ("frpc", "/frpc", True),
    ("tailscale", "/tailscale", True), ("caddy", "/domains", True), ("ipcert", "/ipcert", True),
    ("portfwd", "/portfwd", True), ("files", "/files", True), ("visitors", "/visitors", True),
    ("terminal", "/terminal", True), ("monitor", "/monitor", True), ("system", "/system", True),
    ("updates", "/updates", True), ("processes", "/processes", True), ("services", "/services", True),
    ("ports", "/ports", True), ("filemanager", "/filemanager", True), ("fleet", "/fleet", True),
    ("changelog", "/changelog", False), ("backup", "/backup", True),
    ("tasks", "/tasks", True), ("logs", "/settings/logs", False),
)


class DashboardApiMixin:
    API_ROUTES_DASHBOARD = {
        ("GET", "dashboard"): "api_dashboard",
        ("POST", "modules/action"): "api_module_action",
        ("PUT", "traffic/total"): "api_total_settings",
        ("POST", "traffic/total/calibrate"): "api_total_calibrate",
    }

    def _module_job(self):
        try:
            job = self.context.json.loads(self.context.module_status_path(self.context.BASE_DIR).read_text())
        except (OSError, ValueError):
            return {}
        return job if isinstance(job, dict) else {}

    def _module_names(self, t):
        return {"web_public": t["module_web_public"], "speedtest": t["speedtest"], "iperf3": t["iperf"],
                "proxy_nodes": t["proxy"], "frps": "FRPS", "frpc": "FRPC", "tailscale": "Tailscale",
                "caddy": t["domains"], "ipcert": t["ipcert"], "portfwd": t["portfwd"], "files": t["files"],
                "visitors": t["visitors"], "terminal": t["terminal_title"], "changelog": t["changelog"],
                **{feature: t["feature_" + feature] for feature in self.context.SYSTEM_FEATURES}}

    def dashboard_modules(self):
        context = self.context
        installed = context.installed_modules(context.BASE_DIR)
        states = context.module_states(installed)
        job = self._module_job()
        now = context.time.time()
        busy = job.get("state") in ("queued", "running") and module_job_recent(job, now, 900)
        needs = {"web_public": "web", "iperf3": "iperf3", "proxy_nodes": "proxy", "frps": "frps",
                 "frpc": "frpc", "tailscale": "tailscale", "caddy": "caddy", "ipcert": "caddy"}
        modules = []
        for key, page, switchable in DASHBOARD_ITEMS:
            if key == "terminal" and not context.AUTH_ENABLED:
                continue
            enabled = True if not switchable else bool(states[key])
            available = (needs.get(key) is None or needs[key] in installed) and (
                key != "portfwd" or context.PORTFWD_ALLOWED)
            closed = switchable and not enabled and (
                key in context.MANAGED_FEATURES or key in needs and needs[key] in installed)
            item = {"key": key, "href": "/closed?module=" + key if closed or key == "web_public" and not enabled else page,
                    "switchable": switchable, "enabled": enabled, "available": available}
            if key == "web_public":
                item["occupiedPort"] = next((port for port in (public_listener_occupied(context, listener, job)
                                                               for listener in ("web_http", "web_https"))
                                             if port is not None), None)
                item["needsIpcert"] = bool(enabled and context.CADDY_HOLDS_PUBLIC_PORTS and not states["ipcert"])
            modules.append(item)
        lang, _ = self.resolve_lang(context.urlsplit(self.path))
        t = context.STRINGS[lang]
        recent = busy or job.get("state") in ("done", "failed") and module_job_recent(job, now, 30)
        return {"modules": modules, "busy": busy,
                "job": ({"module": job.get("module"), "action": job.get("action"), "state": job.get("state"),
                         "text": module_job_text(t, job, self._module_names(t))} if job and recent else None)}

    def dashboard_total(self):
        """The host's total traffic for this period, or None when it cannot be computed."""
        import total_meter
        try:
            state, info = self.total_state()
        except (OSError, ValueError, TypeError):
            return None
        measured, per_entry = total_meter.period_usage(state, total_meter.lifetimes(info))
        used = total_meter.calibrated_total(state, measured)
        spec = state.get("reset_spec")

        def when(stamp, with_time):
            # A calendar reset is in the host's local time; the older reset day is midnight UTC.
            if not stamp:
                return None
            if not spec:
                return stamp[:10]
            moment = self.context.datetime.fromisoformat(stamp).astimezone()
            return moment.strftime("%Y-%m-%d %H:%M" if with_time else "%Y-%m-%d")
        return {
            "used": used, "measured": measured, "cap": state["cap_bytes"], "resetDay": state["reset_day"],
            "resetSpec": spec, "timezone": self.context.time.tzname[0],
            "level": total_meter.level(state, used), "capAction": total_meter.cap_action(state),
            "enforced": total_meter.enforced(state, used), "since": when(state["period_start"], False),
            "nextReset": when(state["next_reset_at"], True),
            "offset": total_meter.calibration(state), "calibratedAt": (state.get("calibrated_at") or "")[:10] or None,
            # A deleted entry still counts what it used this period, under the name it had.
            "sources": [{"id": identifier, "name": total_meter.entry_name(state, info, identifier)[0], "value": value,
                         "multiplier": total_meter.entry_name(state, info, identifier)[1]}
                        for identifier, value in sorted(per_entry.items(), key=lambda item: -item[1]) if value],
        }

    def api_dashboard(self):
        resources = (self.dashboard_resources()
                     if self.context.module_feature_enabled(self.context.BASE_DIR, "monitor") else None)
        return self.api_ok({**self.dashboard_modules(), "total": self.dashboard_total(), "resources": resources})

    def dashboard_resources(self):
        """The four figures the home page shows above the modules, with hourly trend lines."""
        summary = self.monitor_summary()
        return {key: summary[key] for key in ("cpu", "memory", "disk", "load", "trend", "hourAgo", "gpus")}

    def start_module_job(self, module, action):
        """Start a module job; returns None once started or when there is nothing
        to do, otherwise (status, error code)."""
        context = self.context
        allowed = (("iperf3", "proxy_nodes", "frps", "frpc", "tailscale", "caddy") + (
            ("ipcert",) if action == "install" else ()) if action in ("install", "uninstall") else (
            "web_public", "iperf3", "proxy_nodes", "frps", "frpc", "tailscale", "caddy", "ipcert")
            + tuple(context.MANAGED_FEATURES))
        if module not in allowed or action not in ("install", "uninstall", "enable", "disable"):
            return 400, "invalid_request"
        installed = context.installed_modules(context.BASE_DIR)
        present = ("proxy" in installed if module == "proxy_nodes" else
                   "caddy" in installed if module == "ipcert" else module in installed)
        if action in ("install", "uninstall") and (action == "install") == present:
            return None
        install_source = (context.BASE_DIR / "installer-source" / "deploy" / "systemd" / "frpc@.service"
                          if module == "frpc" else context.BASE_DIR / "installer-source" / "deploy" / "install.sh")
        if action == "install" and module != "iperf3" and not install_source.is_file():
            return 503, "module_source_missing"
        # The archive name carries the version, which only config/dependencies.lock.json
        # records; installer-source holds the one archive its own release shipped.
        if action == "install" and module == "tailscale" and not (
                any(path.is_file() for path in (context.BASE_DIR / "installer-source" / "third_party" /
                                                "tailscale").glob("tailscale_*_amd64.tgz")) or
                (context.BASE_DIR / "installer-source" / "config" / "online-assets.json").is_file()):
            return 503, "module_tailscale_asset_missing"
        helper = context.WEB_CODE_DIR / "module_manager.py"
        if not helper.is_file() or not context.shutil.which("systemd-run"):
            return 503, "module_source_missing"
        command = ["systemd-run", "--collect", "--unit=vps-server-module-job",
                   "/usr/bin/python3", str(helper), action, module, str(context.BASE_DIR)]
        with (context.DATA_DIR / "module-request.lock").open("a+b") as request_lock:
            context.fcntl.flock(request_lock, context.fcntl.LOCK_EX)
            job = self._module_job()
            if job.get("state") in ("queued", "running") and context.time.time() - job.get("at", 0) < 900:
                return 409, "module_busy"
            if module in context.MANAGED_FEATURES and action in ("enable", "disable"):
                if context.module_feature_enabled(context.BASE_DIR, module) == (action == "enable"):
                    return None
            context.save_module_status(context.BASE_DIR, module, "queued", action=action)
            try:
                result = context.subprocess.run(command, stdout=context.subprocess.DEVNULL,
                                                stderr=context.subprocess.DEVNULL, timeout=10, check=False)
            except (OSError, context.subprocess.TimeoutExpired):
                result = None
            if result is None or result.returncode:
                context.save_module_status(context.BASE_DIR, module, "failed", action=action)
                return 503, "module_job_failed"
        return None

    def api_module_action(self):
        body = self.read_json() or {}
        failure = self.start_module_job(body.get("module"), body.get("action"))
        if failure:
            return self.api_error(*failure)
        return self.api_dashboard()

    def api_total_settings(self):
        import total_meter
        body = self.read_json()
        if body is None:
            return self.api_error(400, "invalid_request")
        cap, day, spec = body.get("capGib"), body.get("resetDay", 0), body.get("resetSpec")
        action = body.get("capAction")
        if action is not None and action not in total_meter.CAP_ACTIONS:
            return self.api_error(400, "invalid_request", field="capAction", reason="format")
        try:
            spec = total_meter.parse_spec(spec)
            cap, day = total_meter.parse_settings("" if cap is None else str(cap), "0" if spec else str(day))
        except ValueError as exc:
            return self.api_error(400, "invalid_request", **details(total_problem(exc, body, "capGib")))
        except TypeError:
            return self.api_error(400, "invalid_request")
        try:
            now = self.context.datetime.now(self.context.timezone.utc)
            with TOTAL_LOCK:
                state, info = self.total_state(now)
                total_meter.write_state(self.context.DATA_DIR / "total-traffic.json",
                                        total_meter.apply_settings(state, cap, day, now, info, spec, action))
        except (ValueError, TypeError):
            return self.api_error(400, "invalid_request")
        except OSError:
            return self.api_error(500, "failed")
        self.total_enforce_now()
        return self.api_dashboard()

    def total_enforce_now(self):
        """Apply a changed cap, action or calibration at once instead of on the next 30-second check."""
        try:
            self.total_enforce()
        except (OSError, ValueError, TypeError):
            pass

    def api_total_calibrate(self):
        import total_meter
        body = self.read_json()
        if body is None:
            return self.api_error(400, "invalid_request")
        actual = body.get("actualGib")
        try:
            actual = total_meter.parse_actual("" if actual is None else str(actual))
        except ValueError as exc:
            return self.api_error(400, "invalid_request", **details(total_problem(exc, body, "actualGib")))
        try:
            now = self.context.datetime.now(self.context.timezone.utc)
            with TOTAL_LOCK:
                state, info = self.total_state(now)
                measured, _per = total_meter.period_usage(state, total_meter.lifetimes(info))
                total_meter.write_state(self.context.DATA_DIR / "total-traffic.json",
                                        total_meter.apply_calibration(state, actual, measured, now))
        except (ValueError, TypeError):
            return self.api_error(400, "invalid_request")
        except OSError:
            return self.api_error(500, "failed")
        self.total_enforce_now()
        return self.api_dashboard()
