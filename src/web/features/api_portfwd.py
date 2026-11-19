"""JSON API for port forwarding. Ports stay masked: the page asks /api/private-value for them."""


class PortfwdApiMixin:
    API_ROUTES_PORTFWD = {
        ("GET", "portfwd"): "api_portfwd",
        ("POST", "portfwd/add"): "api_portfwd_add",
        ("POST", "portfwd/enable"): "api_portfwd_enable",
        ("POST", "portfwd/disable"): "api_portfwd_disable",
        ("POST", "portfwd/delete"): "api_portfwd_delete",
    }

    def portfwd_state(self, message=None):
        context = self.context
        rules = [{"id": rule["id"], "label": rule["label"], "protocol": rule["protocol"],
                  "targetHost": rule["target_host"], "enabled": bool(rule["enabled"]),
                  "applied": bool(rule["applied"])}
                 for rule in context.PORTFWD.list_rules()]
        return {"canAdd": bool(context.portfwd_enabled()), "max": context.PORTFWD_MAX_RULES,
                "rules": rules, "message": message}

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
        if protocol not in ("tcp", "udp", "both") or not isinstance(label, str) or len(label) > 80:
            return self.api_error(400, "invalid_request")
        public_port = context._valid_port(body.get("publicPort"))
        target_port = context._valid_port(body.get("targetPort"))
        target_host = body.get("targetHost")
        if public_port is None or target_port is None or not isinstance(target_host, str) or \
                not context._valid_target_host(target_host.strip()):
            return self.api_ok(self.portfwd_state("portfwd_invalid"))
        _, key = context.PORTFWD.add(protocol, public_port, target_host.strip(), target_port, label.strip())
        return self.api_ok(self.portfwd_state(key))

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
