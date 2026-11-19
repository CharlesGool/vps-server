"""JSON API for the iperf3 page: the time-boxed server window and the outbound client test,
plus masked values (ports, commands, credentials) shared by every page."""


class IperfApiMixin:
    API_ROUTES_IPERF = {
        ("GET", "iperf"): "api_iperf",
        ("POST", "iperf/open"): "api_iperf_open",
        ("POST", "iperf/close"): "api_iperf_close",
        ("PUT", "iperf/port"): "api_iperf_port",
        ("POST", "iperf/client"): "api_iperf_client",
        ("GET", "private-value"): "api_private_value",
    }

    def iperf_state(self, message=None):
        context = self.context
        is_open, remaining = context.IPERF_WINDOW.state()
        installed = not (context.STATE_FILE.is_file() and "iperf3" not in context.installed_modules(context.BASE_DIR))
        return {"installed": installed, "enabled": bool(context.IPERF_ENABLED),
                "open": is_open, "remaining": remaining,
                "defaultMinutes": context.IPERF_DEFAULT_MINUTES, "maxMinutes": context.IPERF_MAX_MINUTES,
                "message": message}

    def _iperf_closed(self):
        if self.context.closed_page_module("/iperf"):
            self.api_error(403, "feature_closed", url="/closed?module=iperf3")
            return True
        return False

    def api_iperf(self):
        if not self._iperf_closed():
            self.api_ok(self.iperf_state())

    def api_iperf_open(self):
        if self._iperf_closed():
            return
        body = self.read_json()
        if body is None:
            return self.api_error(400, "invalid_request")
        ok, key = self.context.IPERF_WINDOW.open(body.get("minutes"))
        return self.api_ok(self.iperf_state(key))

    def api_iperf_close(self):
        if self._iperf_closed():
            return
        if self.read_json() is None:
            return self.api_error(400, "invalid_request")
        self.context.IPERF_WINDOW.close()
        return self.api_ok(self.iperf_state("iperf_shut"))

    def api_iperf_port(self):
        context = self.context
        if self._iperf_closed():
            return
        body = self.read_json()
        port = (body or {}).get("port")
        if not isinstance(port, int) or isinstance(port, bool):
            return self.api_error(400, "invalid_request")
        try:
            self.iperf_set_port(port)
        except ValueError:
            return self.api_error(400, "iperf_port_invalid")
        return self.api_ok(self.iperf_state("iperf_port_saved"))

    def api_iperf_client(self):
        context = self.context
        if self._iperf_closed():
            return
        body = self.read_json()
        fields = ("host", "port", "seconds", "mbps", "protocol", "direction")
        if body is None or any(not isinstance(body.get(name), (str, int)) or isinstance(body.get(name), bool)
                               for name in fields):
            return self.api_error(400, "invalid_request")
        values = {name: str(body[name]) for name in fields}
        result = ({"status": "disabled"} if not context.IPERF_ENABLED else
                  context.IPERF_CLIENT.run(values["host"], values["port"], values["protocol"],
                                           values["direction"], values["seconds"], values["mbps"]))
        return self.api_ok(result)

    def api_private_value(self):
        query = self.context.parse_qs(self.context.urlsplit(self.path).query)
        if len(query.get("id", [])) != 1 or len(query.get("field", [])) != 1:
            return self.api_error(400, "invalid_request")
        try:
            value = self.private_value(query["id"][0], query["field"][0])
        except ValueError:
            return self.api_error(404, "not_found")
        return self.api_ok({"value": value})
