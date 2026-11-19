"""JSON API for one metered feature's traffic: usage and the limits dialog.

The same entry shape is used for sing-box nodes and FRPS, so the browser has
one traffic card for all of them.
"""

import re

# Metered features with a traffic card; FRPC instances and forwarding rules carry their own name.
TRAFFIC_KEYS = ("files", "speedtest", "iperf3", "caddy", "tailscale")
INSTANCE_KEY = re.compile(r"(frpc|portfwd):[A-Za-z0-9_.-]{1,64}")


def usage_json(context, node, meter_nodes):
    """Usage, limits and state of one metered entry for the browser."""
    used = context.billable_bytes(node)
    cap = node["cap_bytes"]
    entry = meter_nodes.get(node["id"]) if isinstance(meter_nodes, dict) else None
    if isinstance(entry, dict) and type(entry.get("suspect")) is bool and "samples" in entry:
        suspect = entry["suspect"] or entry["samples"] is None
    else:
        suspect = None
    now = context.datetime.now(context.timezone.utc)
    remaining = ((context.datetime.fromisoformat(node["expires_at"]) - now).total_seconds()
                 if node["expires_at"] else None)
    expired = remaining is not None and remaining <= 0
    capped = cap is not None and used >= cap
    state = ("blocked" if expired or (capped and node["cap_action"] == "block") else
             "limited" if capped else "unknown" if suspect is None else "normal")
    interval = context.reset_interval(node["reset_mode"])
    reset = "none" if node["reset_mode"] == "none" else "once" if node["reset_mode"] == "once" else "repeat"
    return {
        "id": node["id"], "state": state,
        "upload": node["upload_bytes"], "download": node["download_bytes"],
        "uploadLimitBps": node["upload_limit_bps"], "downloadLimitBps": node["download_limit_bps"],
        "capBytes": cap, "billed": used, "multiplier": node.get("billable_multiplier", 2),
        "capAction": node["cap_action"],
        "resetMode": reset, "resetCount": interval[0] if interval else 1,
        "resetUnit": interval[1] if interval else "months",
        "nextResetAt": node["next_reset_at"],
        "expiryCount": node["expiry_count"], "expiryUnit": node["expiry_unit"],
        "remainingSeconds": None if remaining is None else int(remaining),
    }


def limits_form(body):
    """The browser's limits object as the form node_limits_request() reads."""
    def text(name, default=""):
        value = body.get(name, default)
        if value is None:
            return ""
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise ValueError("invalid field " + name)
        return str(value)
    fields = {"cap_gib": "capGib", "upload_mbps": "uploadMbps", "download_mbps": "downloadMbps",
              "cap_action": "capAction", "expiry_mode": "expiryMode", "expiry_count": "expiryCount",
              "expiry_unit": "expiryUnit", "reset_mode": "resetMode", "reset_count": "resetCount",
              "reset_unit": "resetUnit", "next_reset_at": "nextResetAt"}
    return {name: [text(key)] for name, key in fields.items()}


class TrafficApiMixin:
    API_ROUTES_TRAFFIC = {
        ("GET", "traffic"): "api_traffic",
        ("PUT", "traffic/limits"): "api_traffic_limits",
    }

    def _traffic_key(self, key):
        if not isinstance(key, str):
            return None
        return key if key in TRAFFIC_KEYS or INSTANCE_KEY.fullmatch(key) else None

    def traffic_json(self, key):
        found = self.traffic_entry(key)
        if found is None:
            return {"entry": None}
        entry, ledger = found
        names = entry["name"] if str(entry.get("key", "")).startswith("frpcsrv:") and ", " in entry["name"] else None
        return {"entry": usage_json(self.context, entry, ledger),
                "help": ("tailscale" if key == "tailscale" else
                         "twice" if entry.get("billable_multiplier", 2) == 2 else "once"),
                "sharedWith": names}

    def api_traffic(self):
        query = self.context.parse_qs(self.context.urlsplit(self.path).query)
        key = self._traffic_key(query.get("key", [""])[0])
        if key is None:
            return self.api_error(404, "not_found")
        return self.api_ok(self.traffic_json(key))

    def api_traffic_limits(self):
        context = self.context
        body = self.read_json()
        key = self._traffic_key((body or {}).get("key"))
        if key is None:
            return self.api_error(400, "invalid_request")
        if key in ("files", "speedtest"):
            # Before the console's first flush the file does not exist yet and every
            # read makes new entry ids; write it once so the id below is the stored one.
            try:
                context.APP_METER.flush()
            except (OSError, ValueError, context.InvalidInventory):
                return self.api_error(500, "limits_failed")
        found = self.traffic_entry(key)
        if found is None:
            return self.api_error(404, "not_found")
        entry = found[0]
        try:
            request = self.node_limits_request(limits_form(body), entry)
            if key in ("files", "speedtest"):
                context.APP_METER.edit(entry["id"], request)
                done = True
            else:
                done = self.traffic_meter_apply({"action": "edit", "id": entry["id"], **request})
        except (ValueError, context.InvalidOperation, OverflowError, KeyError,
                context.InvalidInventory, TypeError):
            return self.api_error(400, "invalid_limits")
        except OSError:
            done = False
        if not done:
            return self.api_error(500, "limits_failed")
        return self.api_ok(self.traffic_json(key))
