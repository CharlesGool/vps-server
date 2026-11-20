"""JSON API for FRPS (the server on this host) and FRPC instances (clients to other servers).

Every change still goes through the root helper frp_control.py. Saving an FRPC
instance can restart the tunnel carrying this very request, so those changes
are queued as a job and the page polls ``frpc/job`` for the outcome.
"""

import ipaddress
import re

from field_errors import FieldError, details
from frp_control import MIN_SECRET, valid_client_name

SECRET_FIELD = re.compile(r"(proxy|visitor)-secret:([0-9]{1,2})")
JOB_ID = re.compile(r"[0-9a-f]{32}")


def _port(value, field):
    if type(value) is not int:
        raise FieldError(field, "required" if value is None else "type")
    if not 1 <= value <= 65535:
        raise FieldError(field, "range")


def _name(value, field, limit=64):
    if not value:
        raise FieldError(field, "required")
    if len(value) > limit:
        raise FieldError(field, "too_long")


def _address(value, field):
    if not value:
        raise FieldError(field, "required")
    try:
        ipaddress.ip_address(value)
    except ValueError:
        raise FieldError(field, "format") from None


def _secret(value, field):
    """A supplied secret key as frp_control._normalize_proxy and _normalize_visitor take it."""
    if len(value) > 128:
        raise FieldError(field, "too_long")
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise FieldError(field, "format")
    if len(value) < MIN_SECRET:
        raise FieldError(field, "too_short")


def frpc_problem(section, values):
    """FieldError for a value the FRPC helper refuses for certain (frp_control.build_client and its
    normalizers). The job still checks everything, duplicate names and taken ports included."""
    if section in ("server", "create"):
        _address(values["server"], "server")
        _port(values["port"], "port")
        if section == "create" and not values["token"]:
            raise FieldError("token", "required")
        if len(values["token"]) > 128:
            raise FieldError("token", "too_long")
    elif section in ("add", "edit"):
        proxy = values["proxy"]
        _name(proxy["name"], "proxy.name")
        _address(proxy["localIP"], "proxy.localIP")
        _port(proxy["localPort"], "proxy.localPort")
        if proxy["type"] == "stcp":
            if proxy["secretKey"]:
                _secret(proxy["secretKey"], "proxy.secretKey")
        else:
            _port(proxy["remotePort"], "proxy.remotePort")
    elif section in ("visitor-add", "visitor-edit"):
        visitor = values["proxy"]
        _name(visitor["name"], "visitor.name")
        _name(visitor["serverName"], "visitor.serverName")
        _port(visitor["bindPort"], "visitor.bindPort")
        if visitor["secretKey"]:
            _secret(visitor["secretKey"], "visitor.secretKey")
        elif section == "visitor-add":
            raise FieldError("visitor.secretKey", "required")


class FrpApiMixin:
    API_ROUTES_FRP = {
        ("GET", "frps"): "api_frps",
        ("POST", "frps/toggle"): "api_frps_toggle",
        ("PUT", "frps/save"): "api_frps_save",
        ("GET", "frpc"): "api_frpc",
        ("POST", "frpc/test"): "api_frpc_test",
        ("POST", "frpc/toggle"): "api_frpc_toggle",
        ("POST", "frpc/delete"): "api_frpc_delete",
        ("GET", "frpc/client"): "api_frpc_client",
        ("POST", "frpc/change"): "api_frpc_change",
        ("GET", "frpc/job"): "api_frpc_job",
    }

    # -- running the helper ---------------------------------------------------------

    def _frp_systemd(self):
        """(available, systemd-run path); unavailable when the helper is missing."""
        context = self.context
        if not context.FRP_CONTROL_HELPER.is_file():
            return False, None
        systemd_run = context.shutil.which("systemd-run")
        if not systemd_run and context.Path("/run/systemd/system").exists():
            return False, None
        return True, systemd_run

    def frp_run(self, request):
        """Run one request through the helper and wait; True on success."""
        context = self.context
        available, systemd_run = self._frp_systemd()
        if not available:
            return False
        direct = ["/usr/bin/python3", str(context.FRP_CONTROL_HELPER)]
        command = (["systemd-run", "--pipe", "--wait", "--collect", "--unit=vps-server-frp-control.service", *direct]
                   if systemd_run else direct)
        try:
            result = context.subprocess.run(command, input=context.json.dumps(request).encode(),
                                            stdout=context.subprocess.DEVNULL, stderr=context.subprocess.DEVNULL,
                                            timeout=180, check=False)
        except context.subprocess.TimeoutExpired:
            if systemd_run:
                context._run_quiet(["systemctl", "stop", "vps-server-frp-control.service"])
            return False
        except OSError:
            return False
        return result.returncode == 0

    def frp_queue(self, request):
        """Queue an FRPC change and return its job id, or None when it cannot start.

        Without systemd the change runs at once and the job is written finished.
        """
        context = self.context
        available, systemd_run = self._frp_systemd()
        if not available:
            return None
        jobs = context.DATA_DIR / "frp-jobs"
        jobs.mkdir(mode=0o700, exist_ok=True)
        ident = context.secrets.token_hex(16)
        job_path = jobs / (ident + ".json")
        if not systemd_run:
            done = self.frp_run(request)
            context._atomic_private_text(job_path, context.json.dumps(
                {"state": "done" if done else "failed", "at": context.time.time(), "success": "", "failure": ""}))
            return ident
        context._atomic_private_text(job_path, context.json.dumps(
            {"state": "queued", "at": context.time.time(), "request": request, "success": "", "failure": ""}))
        command = ["systemd-run", "--collect", "--unit=vps-server-frp-control", "--property=RuntimeMaxSec=240",
                   "/usr/bin/python3", str(context.FRP_CONTROL_HELPER), "--job", str(job_path)]
        try:
            result = context.subprocess.run(command, stdout=context.subprocess.DEVNULL,
                                            stderr=context.subprocess.DEVNULL, timeout=10, check=False)
            if result.returncode:
                raise OSError("FRP job unavailable")
        except (OSError, context.subprocess.TimeoutExpired):
            job_path.unlink(missing_ok=True)
            return None
        return ident

    def _frp_auth(self):
        if not self.context.AUTH_ENABLED:
            self.api_error(404, "not_found")
            return False
        return True

    # -- FRPS -----------------------------------------------------------------------

    def frps_state(self):
        context = self.context
        installed = not (context.STATE_FILE.is_file() and "frps" not in context.installed_modules(context.BASE_DIR))
        node = context.frps_node() if installed else None
        if node is None:
            return {"installed": installed, "node": None}
        lang, _ = self.resolve_lang(context.urlsplit(self.path))
        return {"installed": True, "node": {
            "running": context._run_quiet(["systemctl", "is-active", "--quiet", context.FRPS_SERVICE]),
            "bind": node["address"],
            "addresses": [{"index": index, "label": label}
                          for index, (label, _) in enumerate(context.address_entries(context.STRINGS[lang]))],
        }}

    def api_frps(self):
        if self._frp_auth():
            self.api_ok(self.frps_state())

    def api_frps_toggle(self):
        if not self._frp_auth():
            return
        body = self.read_json() or {}
        if not isinstance(body.get("enable"), bool) or self.context.frps_node() is None:
            return self.api_error(400, "invalid_request")
        if not self.frp_run({"action": "server-enable" if body["enable"] else "server-disable"}):
            return self.api_error(500, "frp_failed")
        return self.api_ok(self.frps_state())

    def api_frps_save(self):
        """Port and token; an empty value keeps the current one."""
        if not self._frp_auth():
            return
        body = self.read_json() or {}
        node = self.context.frps_node()
        port, token = body.get("port"), body.get("token") or ""
        if node is None:
            return self.api_error(400, "invalid_request")
        try:
            if port is not None and not (type(port) is int and port == 0):  # 0 keeps the port, like null
                _port(port, "port")
            if not isinstance(token, str):
                raise FieldError("token", "type")
            if len(token) > 128 or "\n" in token or "\r" in token:
                raise FieldError("token", "too_long" if len(token) > 128 else "format")
        except FieldError as exc:
            return self.api_error(400, "invalid_request", **details(exc))
        if not self.frp_run({"action": "server", "port": port or node["port"], "token": token or node["token"]}):
            return self.api_error(500, "frp_failed")
        return self.api_ok(self.frps_state())

    # -- FRPC -----------------------------------------------------------------------

    def _frpc_existing(self, name):
        """The instance's config path when ``name`` is a real, non-link instance; else None."""
        try:
            path = self.context.frpc_path(name)
            return path if path.is_file() and not path.is_symlink() else None
        except (OSError, ValueError, TypeError):
            return None

    def frpc_state(self):
        context = self.context
        installed = "frpc" in context.installed_modules(context.BASE_DIR)
        clients = []
        for name in context.frpc_names():
            try:
                item = context.frpc_summary(name)
            except (OSError, ValueError):
                continue
            try:
                config = context.frpc_structured(name) or {}
            except (OSError, ValueError, KeyError, TypeError):
                config = {}
            clients.append({
                "name": name,
                "running": context._run_quiet(["systemctl", "is-active", "--quiet", context.frpc_unit(name)]),
                "connected": context.frpc_connected(name, item["server"], item["port"]),
                "count": item["proxies"],
                "proxies": [{"name": proxy["name"], "type": proxy["type"], "localIP": proxy["localIP"],
                             "localPort": proxy["localPort"], "remotePort": proxy.get("remotePort")}
                            for proxy in config.get("proxies", [])],
                "visitors": [{"name": visitor["name"], "serverName": visitor["serverName"],
                              "bindAddr": visitor["bindAddr"], "bindPort": visitor["bindPort"]}
                             for visitor in config.get("visitors", [])],
            })
        return {"installed": installed or bool(clients), "binaryMissing": not installed, "clients": clients}

    def api_frpc(self):
        if self._frp_auth():
            self.api_ok(self.frpc_state())

    def _frpc_name(self):
        body = self.read_json() or {}
        name = body.get("name")
        if not isinstance(name, str) or self._frpc_existing(name) is None:
            self.api_error(404, "not_found")
            return None, body
        return name, body

    def api_frpc_test(self):
        if not self._frp_auth():
            return
        name, _body = self._frpc_name()
        if name is None:
            return
        connected = self.context.frpc_test_connection(name)
        if connected is None:
            return self.api_error(429, "frp_busy")
        return self.api_ok({"connected": connected})

    def api_frpc_toggle(self):
        if not self._frp_auth():
            return
        name, body = self._frpc_name()
        if name is None:
            return
        if not isinstance(body.get("enable"), bool):
            return self.api_error(400, "invalid_request")
        if not self.frp_run({"action": "enable" if body["enable"] else "disable", "name": name}):
            return self.api_error(500, "frp_failed")
        return self.api_ok(self.frpc_state())

    def api_frpc_delete(self):
        if not self._frp_auth():
            return
        name, _body = self._frpc_name()
        if name is None:
            return
        if not self.frp_run({"action": "delete-client", "name": name}):
            return self.api_error(500, "frp_failed")
        return self.api_ok(self.frpc_state())

    def api_frpc_client(self):
        """One instance for the editor; secrets and the server stay masked (see frpc_masked_value)."""
        if not self._frp_auth():
            return
        name = self.context.parse_qs(self.context.urlsplit(self.path).query).get("name", [""])[0]
        if self._frpc_existing(name) is None:
            return self.api_error(404, "not_found")
        try:
            config = self.context.frpc_structured(name)
        except (OSError, ValueError, KeyError, TypeError):
            config = None
        if config is None:
            return self.api_ok({"name": name, "supported": False})
        return self.api_ok({"name": name, "supported": True,
                            "proxies": [{"name": proxy["name"], "type": proxy["type"], "localIP": proxy["localIP"],
                                         "localPort": proxy["localPort"], "remotePort": proxy.get("remotePort")}
                                        for proxy in config.get("proxies", [])],
                            "visitors": [{"name": visitor["name"], "serverName": visitor["serverName"],
                                          "bindAddr": visitor["bindAddr"], "bindPort": visitor["bindPort"]}
                                         for visitor in config.get("visitors", [])]})

    def frpc_masked_value(self, name, field):
        """A masked FRPC value: server address, port, token or one proxy's or visitor's secret key."""
        secret = SECRET_FIELD.fullmatch(field)
        if field not in ("server", "port", "token") and not secret:
            raise ValueError("unsupported value")
        if self._frpc_existing(name) is None:
            raise ValueError("no such instance")
        try:
            config = self.context.frpc_structured(name)
            if config is None:
                raise ValueError("unsupported config")
            if secret:
                return config["proxies" if secret[1] == "proxy" else "visitors"][int(secret[2])]["secretKey"]
            return (config["serverAddr"] if field == "server" else
                    str(config["serverPort"]) if field == "port" else config["auth"]["token"])
        except (OSError, KeyError, TypeError, IndexError) as exc:
            raise ValueError("no such value") from exc

    def api_frpc_change(self):
        """One change to an instance (or a new one), queued as a job: create, server, rename,
        add/edit/delete a proxy, add/edit/delete a visitor."""
        if not self._frp_auth():
            return
        body = self.read_json() or {}
        name, section = body.get("name"), body.get("section")
        sections = ("create", "server", "rename", "add", "edit", "delete", "visitor-add", "visitor-edit", "visitor-delete")
        if section not in sections:
            return self.api_error(400, "invalid_request", field="section", reason="format" if section else "required")
        if not isinstance(name, str):
            return self.api_error(400, "invalid_request", field="name", reason="required" if name is None else "type")
        try:
            if section == "create":
                if not valid_client_name(name):
                    raise FieldError("name", "required" if not name else "too_long" if len(name) > 32 else "format")
                self.context.frpc_path(name)  # validates the name
                if self._frpc_existing(name) is not None:
                    raise FieldError("name", "exists")
            elif self._frpc_existing(name) is None:
                return self.api_error(404, "not_found")
            if section == "rename":
                new_name = body.get("newName")
                if not isinstance(new_name, str):
                    raise FieldError("newName", "required" if new_name is None else "type")
                if not valid_client_name(new_name):
                    raise FieldError("newName", "required" if not new_name else
                                     "too_long" if len(new_name) > 32 else "format")
                self.context.frpc_path(new_name)
                request = {"action": "rename-client", "name": name, "new_name": new_name}
            else:
                values = {}
                if section in ("edit", "delete", "visitor-edit", "visitor-delete"):
                    if type(body.get("index")) is not int:
                        raise FieldError("index", "type")
                    values["index"] = body["index"]
                if section in ("server", "create"):
                    server, port, token = body.get("server"), body.get("port"), body.get("token")
                    for key, value in (("server", server), ("token", token)):
                        if not isinstance(value, str):
                            raise FieldError(key, "required" if value is None else "type")
                    if type(port) is not int:
                        raise FieldError("port", "required" if port is None else "type")
                    values.update(server=server.strip(), port=port, token=token)
                elif section in ("visitor-add", "visitor-edit"):
                    item = body.get("visitor") or {}
                    if type(item.get("bindPort")) is not int:
                        raise FieldError("visitor.bindPort", "required" if item.get("bindPort") is None else "type")
                    values["proxy"] = {"name": str(item.get("name") or ""), "serverName": str(item.get("serverName") or ""),
                                       "bindPort": item["bindPort"], "secretKey": str(item.get("secretKey") or "")}
                elif section in ("add", "edit"):
                    item = body.get("proxy") or {}
                    if item.get("type") not in ("tcp", "udp", "stcp"):
                        raise FieldError("proxy.type", "format" if item.get("type") else "required")
                    if type(item.get("localPort")) is not int:
                        raise FieldError("proxy.localPort", "required" if item.get("localPort") is None else "type")
                    proxy = {"name": str(item.get("name") or ""), "type": item["type"],
                             "localIP": str(item.get("localIP") or ""), "localPort": item["localPort"]}
                    if proxy["type"] == "stcp":
                        proxy["secretKey"] = str(item.get("secretKey") or "")
                    else:
                        if type(item.get("remotePort")) is not int:
                            raise FieldError("proxy.remotePort", "required" if item.get("remotePort") is None else "type")
                        proxy["remotePort"] = item["remotePort"]
                    values["proxy"] = proxy
                frpc_problem(section, values)
                request = {"action": "create-structured-client" if section == "create" else "structured-client",
                           "name": name, "section": section, "values": values}
        except FieldError as exc:
            return self.api_error(400, "invalid_request", **details(exc))
        except (ValueError, OSError, TypeError):
            return self.api_error(400, "invalid_request")
        ident = self.frp_queue(request)
        if ident is None:
            return self.api_error(503, "frp_failed")
        return self.api_ok({"job": ident, "name": request.get("new_name", name)})

    def api_frpc_job(self):
        context = self.context
        ident = context.parse_qs(context.urlsplit(self.path).query).get("job", [""])[0]
        if not JOB_ID.fullmatch(ident):
            return self.api_error(400, "invalid_request")
        try:
            job = context.json.loads((context.DATA_DIR / "frp-jobs" / (ident + ".json")).read_text())
        except (OSError, ValueError):
            return self.api_error(404, "not_found")
        state = job.get("state")
        if state in ("queued", "running") and context.time.time() - job.get("at", 0) > 250:
            state = "failed"
        return self.api_ok({"state": state})
