"""JSON API for the iperf3 page: the time-boxed server window and the outbound client test,
plus masked values (ports, commands, credentials) shared by every page."""

import ipaddress

from field_errors import FieldError, details

# How the outbound test checks its settings (iperf_client.IperfClient.run): (low, high) per number.
CLIENT_RANGES = {"port": (1, 65535), "seconds": (1, 30), "mbps": (1, 1000)}
CLIENT_CHOICES = {"protocol": ("tcp", "udp"), "direction": ("upload", "download")}
# iperf_set_port's refusals that are about the port itself.
PORT_REASONS = {"invalid port": "range", "reserved port": "port_in_use", "busy port": "port_in_use"}


def client_problem(values):
    """The FieldError for test settings the client refuses (status "invalid"), or None."""
    host = values["host"]
    try:
        address = ipaddress.ip_address(host)
        if address.is_unspecified or address.is_multicast or "%" in host:
            raise ValueError(host)
    except ValueError:
        return FieldError("host", "format" if host else "required")
    for name, (low, high) in CLIENT_RANGES.items():
        try:
            number = int(values[name])
        except ValueError:
            return FieldError(name, "format" if values[name] else "required")
        if not low <= number <= high:
            return FieldError(name, "range")
    for name, allowed in CLIENT_CHOICES.items():
        if values[name] not in allowed:
            return FieldError(name, "format")
    return None


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
            return self.api_error(400, "invalid_request", field="port", reason="required" if port is None else "type")
        try:
            self.iperf_set_port(port)
        except ValueError as exc:
            reason = PORT_REASONS.get(str(exc))
            return self.api_error(400, "iperf_port_invalid", **({"field": "port", "reason": reason} if reason else {}))
        return self.api_ok(self.iperf_state("iperf_port_saved"))

    def api_iperf_client(self):
        context = self.context
        if self._iperf_closed():
            return
        body = self.read_json()
        fields = ("host", "port", "seconds", "mbps", "protocol", "direction")
        if body is None:
            return self.api_error(400, "invalid_request")
        for name in fields:
            if not isinstance(body.get(name), (str, int)) or isinstance(body.get(name), bool):
                return self.api_error(400, "invalid_request", field=name,
                                      reason="required" if body.get(name) is None else "type")
        values = {name: str(body[name]) for name in fields}
        result = ({"status": "disabled"} if not context.IPERF_ENABLED else
                  context.IPERF_CLIENT.run(values["host"], values["port"], values["protocol"],
                                           values["direction"], values["seconds"], values["mbps"]))
        if isinstance(result, dict) and result.get("status") == "invalid":
            # The test was refused for its settings: say which one.
            result = {**result, **details(client_problem(values))}
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
