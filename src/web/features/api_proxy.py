"""JSON API for Singbox nodes, identified by stable ID. Every change goes through the
transactional root helper (``node_control_apply``); ports and credentials stay masked."""


class ProxyApiMixin:
    API_ROUTES_PROXY = {
        ("GET", "proxy"): "api_proxy",
        ("POST", "proxy/create"): "api_proxy_create",
        ("PUT", "proxy/edit"): "api_proxy_edit",
        ("POST", "proxy/toggle"): "api_proxy_toggle",
        ("POST", "proxy/reset"): "api_proxy_reset",
        ("POST", "proxy/delete"): "api_proxy_delete",
        ("PUT", "proxy/access"): "api_proxy_access",
    }

    def proxy_inventory(self):
        """(inventory, meter ledger nodes), or None when the node state cannot be read."""
        context = self.context
        try:
            inventory = context.read_inventory(state_path=context.NODE_STATE_PATH,
                                               config_paths={"proxy": context.PROXY_CONFIG})
            if not isinstance(inventory, dict) or not isinstance(inventory.get("nodes"), list):
                return None
            meter = context._read_json(context.NODE_METER_PATH) or {}
            return inventory, meter.get("ledger", {}).get("nodes", {})
        except (OSError, ValueError, TypeError, AttributeError):
            return None

    def proxy_node(self, identifier):
        found = self.proxy_inventory()
        if found is None:
            return None
        return next((node for node in found[0]["nodes"] if node["id"] == identifier), None)

    def proxy_state(self, message=None):
        context = self.context
        if "proxy" not in context.installed_modules(context.BASE_DIR):
            return {"installed": False}
        found = self.proxy_inventory()
        if found is None:
            return {"installed": True, "available": False}
        inventory, _meter = found
        lang, _ = self.resolve_lang(context.urlsplit(self.path))
        t = context.STRINGS[lang]
        running = context.proxy_running()
        host = (self.headers.get("Host") or "").split(":")[0]
        nodes = []
        for node in sorted(inventory["nodes"], key=lambda item: item["number"]):
            protocol = node["protocol"]
            sni = (context._cert_common_name(node["inbound"]["tls"]["certificate_path"]) or ""
                   if protocol != "shadowsocks" else None)
            access = node.get("access") or {}
            nodes.append({"id": node["id"], "number": node["number"], "name": node["name"], "protocol": protocol,
                          "enabled": bool(node["enabled"]), "active": bool(node["enabled"] and running),
                          "sni": sni, "route": self.node_route_summary(node, t),
                          "access": {"mode": access.get("mode", "all"), "destinations": list(access.get("destinations", []))}})
        return {"installed": True, "available": True, "running": running,
                "protocols": ["anytls", "vmess", "vless", "trojan", "shadowsocks"] if context.PROXY_CONFIG.is_file() else [],
                "share": bool(context.AUTH_ENABLED and context.clash_lan_host(host)),
                "addresses": [{"index": index, "label": label} for index, (label, _) in enumerate(context.address_entries(t))],
                "nodes": nodes, "message": message}

    def api_proxy(self):
        if self.context.closed_page_module("/proxy"):
            return self.api_error(403, "feature_closed", url="/closed?module=proxy_nodes")
        return self.api_ok(self.proxy_state())

    def _proxy_apply(self, request, success="node_settings_done"):
        if not self.context.node_control_apply(request):
            return self.api_error(500, "node_settings_failed")
        return self.api_ok(self.proxy_state(success))

    def _proxy_body(self):
        """The request body with the node it names, or None after an error."""
        body = self.read_json() or {}
        node = self.proxy_node(body.get("id")) if isinstance(body.get("id"), str) else None
        if node is None:
            self.api_error(404, "not_found")
            return None, None
        return body, node

    @staticmethod
    def _proxy_text(body, name, limit):
        value = body.get(name) or ""
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError(name)
        return value

    def api_proxy_create(self):
        context = self.context
        body = self.read_json() or {}
        protocol, port = body.get("protocol"), body.get("port")
        try:
            if protocol not in context.NODE_PROTOCOLS or not (port is None or type(port) is int):
                raise ValueError("protocol")
            request = {"action": "create", "protocol": protocol, "name": self._proxy_text(body, "name", 64), "port": port}
            credential = self._proxy_text(body, "credential", 256)
            if credential:
                request["credential"] = credential
            if protocol != "shadowsocks":
                request["sni"] = self._proxy_text(body, "sni", 253).strip() or "www.bing.com"
        except ValueError:
            return self.api_error(400, "invalid_request")
        return self._proxy_apply(request, "node_created")

    def api_proxy_edit(self):
        body, node = self._proxy_body()
        if node is None:
            return
        port = body.get("port")
        try:
            if not (port is None or type(port) is int):
                raise ValueError("port")
            request = {"action": "edit", "id": node["id"], "name": self._proxy_text(body, "name", 64),
                       "port": port or node["port"]}
            credential = self._proxy_text(body, "credential", 256)
            if credential:
                request["credential"] = credential
            if node["protocol"] != "shadowsocks":
                sni = self._proxy_text(body, "sni", 253).strip()
                if sni and sni != self.context._cert_common_name(node["inbound"]["tls"]["certificate_path"]):
                    request["sni"] = sni
        except (ValueError, KeyError):
            return self.api_error(400, "invalid_request")
        return self._proxy_apply(request)

    def api_proxy_toggle(self):
        body, node = self._proxy_body()
        if node is None:
            return
        if not isinstance(body.get("enabled"), bool):
            return self.api_error(400, "invalid_request")
        return self._proxy_apply({"action": "toggle", "id": node["id"], "enabled": body["enabled"]})

    def api_proxy_reset(self):
        body, node = self._proxy_body()
        if node is None:
            return
        if body.get("confirm") is not True:
            return self.api_error(400, "invalid_request")
        return self._proxy_apply({"action": "reset", "id": node["id"]}, "node_reset_done")

    def api_proxy_delete(self):
        body, node = self._proxy_body()
        if node is None:
            return
        if body.get("confirm") is not True:
            return self.api_error(400, "invalid_request")
        return self._proxy_apply({"action": "delete", "id": node["id"]}, "node_deleted")

    def api_proxy_access(self):
        """Which destinations a node may reach: anything, public Internet only, or a list."""
        context = self.context
        body, node = self._proxy_body()
        if node is None:
            return
        mode = body.get("mode")
        try:
            if mode == "all":
                access = None
            elif mode == "internet":
                access = {"mode": "internet"}
            elif mode == "custom":
                text = self._proxy_text(body, "destinations", 8000)
                entries = [item for item in context.re.split(r"[\s,;]+", text) if item]
                access = {"mode": "custom", "destinations": context.normalize_destinations(entries)}
            else:
                raise ValueError("mode")
        except (ValueError, context.InvalidInventory):
            return self.api_error(400, "invalid_destinations")
        return self._proxy_apply({"action": "edit", "id": node["id"], "access": access})
