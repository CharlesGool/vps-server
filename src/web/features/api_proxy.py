"""JSON API for Singbox nodes, identified by stable ID. Every change goes through the
transactional root helper (``node_control_apply``); ports and credentials stay masked."""

from field_errors import FieldError, details, integer, text
from node_inventory import _NAME as NODE_NAME, InvalidInventory


def credential_valid(protocol, value):
    """Whether the root helper takes ``value`` as a credential for ``protocol``: the same check it runs."""
    from node_operations import check_credential
    try:
        check_credential(protocol, value)
    except InvalidInventory:
        return False
    return True


def sni_valid(value):
    """Whether the root helper takes ``value`` as an SNI: the same check it runs."""
    from node_control import NodeControlError, _sni
    try:
        _sni(value)
    except NodeControlError:
        return False
    return True


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

    def _proxy_ports_taken(self, current=None):
        """Ports a node cannot listen on, as far as the console can tell: fixed and registered ports,
        forwarding rules and the other nodes. The root helper checks again, and also tries the port."""
        context = self.context
        taken = {80, 443, context.CONSOLE_PORT}
        for read in (lambda: [context.IPERF_WINDOW.port],
                     lambda: [rule["public_port"] for rule in context.PORTFWD.list_rules()],
                     lambda: [row[0] for row in context.console_port_rows(context.BASE_DIR.parent / "PORTS.md")[0]]):
            try:
                taken.update(port for port in read() if type(port) is int)
            except (OSError, ValueError, TypeError, KeyError, AttributeError):
                pass
        found = self.proxy_inventory()
        if found is not None:
            taken.update(node["port"] for node in found[0]["nodes"] if current is None or node["id"] != current["id"])
        return taken

    def _proxy_fields(self, body, protocol, current=None):
        """(name, port, credential, sni) of a create or edit request. FieldError for input the root
        helper refuses for certain; it still checks everything itself."""
        name = text(body, "name", 64, required=True)
        if name != name.strip() or not NODE_NAME.fullmatch(name):
            raise FieldError("name", "format")
        if current is not None and body.get("port") == 0:
            port = None  # 0 keeps the current port, as an empty value does
        else:
            port = integer(body, "port", 1, 65535, required=False)
        if port is not None and (current is None or port != current["port"]) and port in self._proxy_ports_taken(current):
            raise FieldError("port", "port_in_use")
        credential = text(body, "credential", 256)
        if credential and not credential_valid(protocol, credential):
            raise FieldError("credential", "format")
        sni = text(body, "sni", 253).strip() if protocol != "shadowsocks" else ""
        if sni and not sni_valid(sni):
            raise FieldError("sni", "format")
        return name, port, credential, sni

    def api_proxy_create(self):
        context = self.context
        body = self.read_json() or {}
        protocol = body.get("protocol")
        try:
            if protocol not in context.NODE_PROTOCOLS:
                raise FieldError("protocol", "format" if protocol else "required")
            name, port, credential, sni = self._proxy_fields(body, protocol)
        except FieldError as exc:
            return self.api_error(400, "invalid_request", **details(exc))
        request = {"action": "create", "protocol": protocol, "name": name, "port": port}
        if credential:
            request["credential"] = credential
        if protocol != "shadowsocks":
            request["sni"] = sni or "www.bing.com"
        return self._proxy_apply(request, "node_created")

    def api_proxy_edit(self):
        body, node = self._proxy_body()
        if node is None:
            return
        try:
            name, port, credential, sni = self._proxy_fields(body, node["protocol"], node)
            request = {"action": "edit", "id": node["id"], "name": name, "port": port or node["port"]}
            if credential:
                request["credential"] = credential
            if sni and sni != self.context._cert_common_name(node["inbound"]["tls"]["certificate_path"]):
                request["sni"] = sni
        except FieldError as exc:
            return self.api_error(400, "invalid_request", **details(exc))
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
