"""JSON API for port forwarding. Ports stay masked: the page asks /api/private-value for them.

A refused rule comes back as the page state with a message (``portfwd_invalid``,
``portfwd_port_taken``) and, when one input is at fault, its ``field`` and ``reason``.
"""

from field_errors import FieldError, details


class PortfwdApiMixin:
    API_ROUTES_PORTFWD = {
        ("GET", "portfwd"): "api_portfwd",
        ("POST", "portfwd/add"): "api_portfwd_add",
        ("POST", "portfwd/enable"): "api_portfwd_enable",
        ("POST", "portfwd/disable"): "api_portfwd_disable",
        ("POST", "portfwd/delete"): "api_portfwd_delete",
    }

    def portfwd_state(self, message=None, problem=None):
        """The page state; ``problem`` is the FieldError behind a refused rule."""
        context = self.context
        rules = [{"id": rule["id"], "label": rule["label"], "protocol": rule["protocol"],
                  "targetHost": rule["target_host"], "enabled": bool(rule["enabled"]),
                  "applied": bool(rule["applied"])}
                 for rule in context.PORTFWD.list_rules()]
        return {"canAdd": bool(context.portfwd_enabled()), "max": context.PORTFWD_MAX_RULES,
                "rules": rules, "message": message, **details(problem)}

    def _portfwd_closed(self):
        if self.context.closed_page_module("/portfwd"):
            self.api_error(403, "feature_closed", url="/closed?module=portfwd")
            return True
        return False

    def api_portfwd(self):
        if not self._portfwd_closed():
            self.api_ok(self.portfwd_state())

    def api_portfwd_add(self):
        context = self.context
        if self._portfwd_closed():
            return
        body = self.read_json()
        if body is None:
            return self.api_error(400, "invalid_request")
        protocol = body.get("protocol")
        label = body.get("label", "")
        if protocol not in ("tcp", "udp", "both"):
            return self.api_error(400, "invalid_request", field="protocol", reason="format" if protocol else "required")
        if not isinstance(label, str) or len(label) > 80:
            return self.api_error(400, "invalid_request", field="label",
                                  reason="type" if not isinstance(label, str) else "too_long")
        try:
            public_port = self._portfwd_port(body, "publicPort")
            target_host = body.get("targetHost")
            if not isinstance(target_host, str) or not target_host.strip():
                raise FieldError("targetHost", "required" if not target_host else "type")
            if not context._valid_target_host(target_host.strip()):
                raise FieldError("targetHost", "format")
            target_port = self._portfwd_port(body, "targetPort")
        except FieldError as exc:
            return self.api_ok(self.portfwd_state("portfwd_invalid", exc))
        _, key = context.PORTFWD.add(protocol, public_port, target_host.strip(), target_port, label.strip())
        problem = FieldError("publicPort", "port_in_use") if key == "portfwd_port_taken" else None
        return self.api_ok(self.portfwd_state(key, problem))

    def _portfwd_port(self, body, name):
        """A port the way _valid_port reads it; FieldError when it is not one."""
        value = body.get(name)
        port = self.context._valid_port(value)
        if port is not None:
            return port
        if value is None or value == "":
            raise FieldError(name, "required")
        try:
            int(value)
        except (TypeError, ValueError):
            raise FieldError(name, "type" if not isinstance(value, str) else "format") from None
        raise FieldError(name, "range")

    def _portfwd_rule_action(self, action):
        if self._portfwd_closed():
            return
        body = self.read_json()
        identifier = (body or {}).get("id")
        if not isinstance(identifier, str):
            return self.api_error(400, "invalid_request")
        key = action(identifier)
        return self.api_ok(self.portfwd_state(key))

    def api_portfwd_enable(self):
        return self._portfwd_rule_action(lambda identifier: self.context.PORTFWD.set_enabled(identifier, True))

    def api_portfwd_disable(self):
        return self._portfwd_rule_action(lambda identifier: self.context.PORTFWD.set_enabled(identifier, False))

    def api_portfwd_delete(self):
        return self._portfwd_rule_action(self.context.PORTFWD.remove)
