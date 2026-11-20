"""JSON API for the fleet overview: other consoles watched through their token API."""

from fleet import FleetError, probe

# FleetError codes that name one input of adding a host: code -> (request key, reason).
ADD_FIELDS = {"name_invalid": ("name", "format"), "url_invalid": ("url", "format"),
              "token_invalid": ("token", "format"), "token_rejected": ("token", None), "exists": ("url", "exists")}


def add_problem(code, body):
    field, reason = ADD_FIELDS.get(code, (None, None))
    if field == "name" and not str(body.get("name") or "").strip():
        reason = "required"
    elif field == "name" and len(str(body.get("name")).strip()) > 40:
        reason = "too_long"
    elif field == "token" and reason and not body.get("token"):
        reason = "required"
    if field is None:
        return {}
    return {"field": field, "reason": reason} if reason else {"field": field}


class FleetApiMixin:
    API_ROUTES_FLEET = {
        ("GET", "fleet"): "api_fleet",
        ("POST", "fleet/probe"): "api_fleet_probe",
        ("POST", "fleet/add"): "api_fleet_add",
        ("POST", "fleet/delete"): "api_fleet_delete",
        ("POST", "fleet/action"): "api_fleet_action",
    }

    def api_fleet(self):
        if not self._security_allowed():
            return
        refresh = (self.query_params().get("refresh") or [""])[0] == "1"
        return self.api_ok({"hosts": self.context.FLEET.statuses(refresh=refresh)})

    def api_fleet_probe(self):
        if not self._security_allowed():
            return
        body = self.read_json()
        try:
            return self.api_ok(probe(body.get("url") if body else None))
        except FleetError as error:
            return self.api_error(400, str(error), **({"field": "url", "reason": "format"}
                                                      if str(error) == "url_invalid" else {}))

    def api_fleet_add(self):
        if not self._security_allowed():
            return
        body = self.read_json()
        if body is None:
            return self.api_error(400, "invalid_request")
        try:
            row = self.context.FLEET.add(body.get("name"), body.get("url"), body.get("token"), body.get("mode"),
                                         body.get("fingerprint"))
        except FleetError as error:
            return self.api_error(400, str(error), **add_problem(str(error), body))
        self.audit("fleet_host_added", f'{row["name"]} {row["url"]}')
        return self.api_ok({"hosts": self.context.FLEET.statuses()})

    def api_fleet_delete(self):
        if not self._security_allowed():
            return
        body = self.read_json()
        try:
            self.context.FLEET.remove(body.get("id") if body else None)
        except FleetError as error:
            return self.api_error(404, str(error))
        self.audit("fleet_host_removed")
        return self.api_ok({"hosts": self.context.FLEET.statuses()})

    def api_fleet_action(self):
        if not self._security_allowed():
            return
        body = self.read_json()
        ids = body.get("ids") if body else None
        version = body.get("version") if body else None
        if not isinstance(ids, list) or not ids or not all(isinstance(item, str) for item in ids):
            return self.api_error(400, "invalid_request")
        if version is not None and not isinstance(version, str):
            return self.api_error(400, "invalid_request")
        try:
            results = self.context.FLEET.action(set(ids), body.get("action"), version or None)
        except FleetError as error:
            return self.api_error(400, str(error))
        self.audit("fleet_" + body.get("action", ""), f"{len(results)}")
        return self.api_ok({"results": results})
