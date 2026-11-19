"""JSON API for the settings page: server label and console port."""


class SettingsApiMixin:
    API_ROUTES_SETTINGS = {
        ("GET", "settings"): "api_settings",
        ("PUT", "settings/server-label"): "api_server_label",
        ("POST", "settings/console-port"): "api_console_port",
    }

    def _console_port_job(self):
        try:
            job = self.context.json.loads((self.context.DATA_DIR / "console-port-job.json").read_text())
        except (OSError, ValueError):
            return None
        if not isinstance(job, dict):
            return None
        return {"state": str(job.get("state", "")), "reason": str(job.get("reason", ""))}

    def api_settings(self):
        return self.api_ok({"serverLabel": self.context.server_label(),
                            "consolePort": self.context.CONSOLE_PORT,
                            "consolePortJob": self._console_port_job()})

    def api_server_label(self):
        body = self.read_json()
        if body is None or not isinstance(body.get("label"), str):
            return self.api_error(400, "invalid_request")
        try:
            self.context.save_server_label(body["label"])
        except ValueError:
            return self.api_error(400, "server_label_invalid")
        except OSError:
            return self.api_error(500, "server_label_error")
        return self.api_ok({"serverLabel": self.context.server_label()})

    def api_console_port(self):
        context = self.context
        body = self.read_json()
        port = body.get("port") if body else None
        if not isinstance(port, int) or isinstance(port, bool):
            return self.api_error(400, "invalid_request")
        host = context.urlsplit("https://" + self.headers.get("Host", "")).hostname
        if (not 1024 <= port <= 65535 or port == context.CONSOLE_PORT or not host or not host.isascii()
                or not all(c.isalnum() or c in ".:-" for c in host)):
            return self.api_error(400, "console_port_invalid")
        helper = context.WEB_CODE_DIR / "console_port.py"
        if not helper.is_file() or not context.shutil.which("systemd-run"):
            return self.api_error(500, "console_port_error")
        command = ["systemd-run", "--collect", "--unit=vps-server-console-port-job",
                   "/usr/bin/python3", str(helper), "change", str(context.BASE_DIR),
                   str(context.CONSOLE_PORT), str(port), str(context.CONSOLE_PORT_FILE)]
        try:
            result = context.subprocess.run(command, stdout=context.subprocess.DEVNULL,
                                            stderr=context.subprocess.DEVNULL, timeout=10, check=False)
            if result.returncode:
                raise OSError("could not start console port change")
        except (OSError, context.subprocess.TimeoutExpired):
            return self.api_error(500, "console_port_error")
        host = f"[{host}]" if ":" in host else host
        scheme = "https" if context.CONSOLE_TLS else "http"
        return self.api_ok({"url": f"{scheme}://{host}:{port}/settings",
                            "oldUrl": f"{scheme}://{host}:{context.CONSOLE_PORT}/settings"})
