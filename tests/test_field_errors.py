"""Refused requests say which input and why: ``field`` and ``reason`` next to the unchanged error code.

Also checks that the limits dialog, now parsed from its JSON object directly, gives the same
entry fields as the form-shaped parser it replaced (kept below as the reference).
"""
import decimal
import itertools
import json
import os
import re
import sys
import tempfile
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
sys.path.insert(0, str(TESTS.parent / "src" / "web"))
import _isolation  # noqa: E402,F401
import field_errors as fe  # noqa: E402
import node_inventory as ni  # noqa: E402
import scheduler  # noqa: E402
import sysadmin  # noqa: E402
from features.proxy import ProxyMixin  # noqa: E402
from test_spa_api import PASSWORD, Exchange, load_app  # noqa: E402

UTC = timezone.utc


# -- the limits dialog ------------------------------------------------------------------------

def old_limits_form(body):
    """The browser's limits object as the old parser read it (features/api_traffic.py before 7.5)."""
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
    form = {name: [text(key)] for name, key in fields.items()}
    spec = body.get("resetSpec")
    if spec is not None and not isinstance(spec, dict):
        raise ValueError("invalid field resetSpec")
    form["reset_spec"] = [json.dumps(spec) if spec is not None else ""]
    return form


def old_limits_request(context, form, existing):
    """The form-shaped parser the JSON one replaced (features/proxy.py node_limits_request before 7.5)."""
    request = {}
    cap = form["cap_gib"][0].strip()
    if cap:
        amount = context.Decimal(cap)
        if not amount.is_finite() or not 0 < amount <= 100000000:
            raise ValueError("invalid cap")
        request["cap_bytes"] = int(amount * 1073741824)
    else:
        request["cap_bytes"] = None

    def speed(value):
        if not value.strip():
            return None
        amount = context.Decimal(value)
        if not amount.is_finite() or not context.Decimal("0.001") <= amount <= 10000000:
            raise ValueError("invalid speed")
        result = int(amount * 1000000)
        if result < 1000:
            raise ValueError("invalid speed")
        return result
    request["upload_limit_bps"] = speed(form["upload_mbps"][0])
    request["download_limit_bps"] = speed(form["download_mbps"][0])
    if form["cap_action"][0] not in ("throttle", "block"):
        raise ValueError("invalid cap action")
    request["cap_action"] = form["cap_action"][0]
    now = context.datetime.now(context.timezone.utc)

    def duration(count_value, unit_value):
        count = int(count_value)
        if not 1 <= count <= 9999 or unit_value not in ("days", "months", "years"):
            raise ValueError("invalid duration")
        anchor = "-" if unit_value == "days" else "1" if unit_value == "months" else now.strftime("%m-%d")
        mode = f"every:{count}:{unit_value}:{anchor}"
        return count, unit_value, mode, context.advance_reset_interval(now, mode).isoformat()

    def date_value(value):
        if not value:
            return None
        if not context.re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", value):
            raise ValueError("invalid date")
        return context.datetime.fromisoformat(value).replace(tzinfo=context.timezone.utc).isoformat()
    expiry_mode = form["expiry_mode"][0]
    if expiry_mode == "set":
        count, unit, _, _ = duration(form["expiry_count"][0], form["expiry_unit"][0])
        if (existing["expiry_count"], existing["expiry_unit"]) != (count, unit):
            request.update(expiry_count=count, expiry_unit=unit,
                           expires_at=ni.add_period(now, count, unit).isoformat())
    elif expiry_mode == "none":
        if existing["expiry_count"] is not None:
            request.update(expiry_count=None, expiry_unit=None, expires_at=None)
    else:
        raise ValueError("invalid expiry mode")
    mode = form["reset_mode"][0]
    if mode not in ("none", "repeat", "once", "schedule"):
        raise ValueError("invalid reset mode")
    if mode == "repeat":
        _, _, request["reset_mode"], request["next_reset_at"] = duration(form["reset_count"][0], form["reset_unit"][0])
    elif mode == "schedule":
        try:
            spec = scheduler.normalize_spec(context.json.loads(form.get("reset_spec", [""])[0] or "null"))
        except (scheduler.ScheduleError, ValueError) as exc:
            raise ValueError("invalid reset schedule") from exc
        if spec["mode"] == "once":
            moment = context.datetime.strptime(f"{spec['date']} {spec['time']}", "%Y-%m-%d %H:%M:%S")
            due = moment.astimezone(context.timezone.utc)
            if due <= now:
                raise ValueError("reset must be future")
            request["reset_mode"], request["next_reset_at"] = "once", due.isoformat()
        else:
            request["reset_mode"] = context.schedule_reset_mode(spec)
            request["next_reset_at"] = context.next_scheduled_reset(now, spec).isoformat()
    elif mode == "once":
        request["reset_mode"] = "once"
        request["next_reset_at"] = date_value(form["next_reset_at"][0])
        if request["next_reset_at"] is None or context.datetime.fromisoformat(request["next_reset_at"]) <= now:
            raise ValueError("reset must be future")
    else:
        request["reset_mode"] = "none"
        request["next_reset_at"] = None
    return request


class Limits(ProxyMixin):
    def __init__(self, now):
        fixed = now

        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed
        self.context = types.SimpleNamespace(
            Decimal=decimal.Decimal, datetime=Clock, timezone=timezone, re=re, json=json,
            advance_reset_interval=ni.advance_reset_interval, schedule_reset_mode=ni.schedule_reset_mode,
            next_scheduled_reset=ni.next_scheduled_reset)


NOW = datetime(2026, 11, 20, 9, 30, tzinfo=UTC)
NO_EXPIRY = {"expiry_count": None, "expiry_unit": None, "expires_at": None}
ONE_MONTH = {"expiry_count": 1, "expiry_unit": "months", "expires_at": "2026-12-20T09:30:00+00:00"}
BASE = {"capGib": "", "uploadMbps": "", "downloadMbps": "", "capAction": "throttle", "resetMode": "none",
        "resetCount": 1, "resetUnit": "months", "nextResetAt": "", "expiryMode": "none", "expiryCount": 1,
        "expiryUnit": "months"}


def valid_bodies():
    """A spread of inputs the limits dialog (and older pages) send, all of them accepted."""
    caps = ("", "1.5", 2, 0.25, "100000000", " 7 ", None)
    speeds = (("", ""), ("20", ""), (0.001, 10000000), ("1e2", " 3.5 "))
    resets = ({"resetMode": "none"},
              {"resetMode": "repeat", "resetCount": 3, "resetUnit": "days"},
              {"resetMode": "repeat", "resetCount": "2", "resetUnit": "months"},
              {"resetMode": "repeat", "resetCount": 1, "resetUnit": "years"},
              {"resetMode": "schedule", "resetSpec": {"mode": "monthly", "day": 1, "time": "00:00:00"}},
              {"resetMode": "schedule", "resetSpec": {"mode": "weekly", "days": [0, 3], "time": "08:15"}},
              {"resetMode": "schedule", "resetSpec": {"mode": "yearly", "month": 2, "day": 29, "time": "23:59:59"}},
              {"resetMode": "schedule", "resetSpec": {"mode": "once", "date": "2027-01-02", "time": "03:04:05"}},
              {"resetMode": "once", "nextResetAt": "2027-03-01T00:00"})
    expiries = ({"expiryMode": "none"}, {"expiryMode": "set", "expiryCount": 1, "expiryUnit": "months"},
                {"expiryMode": "set", "expiryCount": "12", "expiryUnit": "days"},
                {"expiryMode": "set", "expiryCount": 2, "expiryUnit": "years"})
    for cap, (up, down), reset, expiry, action in itertools.product(
            caps, speeds, resets, expiries, ("throttle", "block")):
        yield {**BASE, "capGib": cap, "uploadMbps": up, "downloadMbps": down, "capAction": action, **reset, **expiry}


class LimitsParserTest(unittest.TestCase):
    def test_valid_input_gives_what_the_form_parser_gave(self):
        limits = Limits(NOW)
        count = 0
        for body in valid_bodies():
            for existing in (NO_EXPIRY, ONE_MONTH):
                expected = old_limits_request(limits.context, old_limits_form(body), existing)
                self.assertEqual(limits.limits_request(body, existing), expected, body)
                count += 1
        self.assertGreater(count, 1000)

    def test_form_shape_still_parses(self):
        form = {"cap_gib": ["3"], "upload_mbps": [""], "download_mbps": ["5"], "cap_action": ["block"],
                "expiry_mode": ["set"], "expiry_count": ["1"], "expiry_unit": ["months"], "reset_mode": ["schedule"],
                "reset_count": ["1"], "reset_unit": ["months"], "next_reset_at": [""],
                "reset_spec": [json.dumps({"mode": "monthly", "day": 5, "time": "06:00:00"})]}
        limits = Limits(NOW)
        self.assertEqual(limits.node_limits_request(form, NO_EXPIRY), old_limits_request(limits.context, form, NO_EXPIRY))

    def test_invalid_input_names_the_field(self):
        limits = Limits(NOW)
        cases = (
            ({"capGib": "-1"}, "capGib", "range"), ({"capGib": "0"}, "capGib", "range"),
            ({"capGib": "abc"}, "capGib", "format"), ({"capGib": "NaN"}, "capGib", "format"),
            ({"capGib": [1]}, "capGib", "type"), ({"capGib": True}, "capGib", "type"),
            ({"uploadMbps": "0.0001"}, "uploadMbps", "range"), ({"downloadMbps": "x"}, "downloadMbps", "format"),
            ({"capAction": "slow"}, "capAction", "format"), ({"capAction": None}, "capAction", "required"),
            ({"expiryMode": "set", "expiryCount": 0}, "expiryCount", "range"),
            ({"expiryMode": "set", "expiryCount": "1.5"}, "expiryCount", "format"),
            ({"expiryMode": "set", "expiryCount": ""}, "expiryCount", "required"),
            ({"expiryMode": "set", "expiryUnit": "weeks"}, "expiryUnit", "format"),
            ({"expiryMode": "set", "expiryCount": 9999, "expiryUnit": "years"}, "expiryCount", "range"),
            ({"expiryMode": "maybe"}, "expiryMode", "format"),
            ({"resetMode": "repeat", "resetCount": 10000}, "resetCount", "range"),
            ({"resetMode": "repeat", "resetUnit": ""}, "resetUnit", "required"),
            ({"resetMode": "weekly"}, "resetMode", "format"),
            ({"resetMode": "schedule"}, "resetSpec", "required"),
            ({"resetMode": "none", "resetSpec": "monthly"}, "resetSpec", "type"),
            ({"resetMode": "schedule", "resetSpec": {"mode": "monthly", "day": 32, "time": "00:00"}}, "resetSpec.day", "range"),
            ({"resetMode": "schedule", "resetSpec": {"mode": "weekly", "days": [], "time": "00:00"}}, "resetSpec.days", "required"),
            ({"resetMode": "schedule", "resetSpec": {"mode": "monthly", "day": 1, "time": "25:00"}}, "resetSpec.time", "format"),
            ({"resetMode": "schedule", "resetSpec": {"mode": "yearly", "month": 2, "day": 30, "time": "00:00"}}, "resetSpec.day", "range"),
            ({"resetMode": "schedule", "resetSpec": {"mode": "once", "date": "2026-11-19", "time": "00:00"}}, "resetSpec.date", "past"),
            ({"resetMode": "schedule", "resetSpec": {"mode": "once", "date": "2026-13-01", "time": "00:00"}}, "resetSpec.date", "format"),
            ({"resetMode": "once", "nextResetAt": ""}, "nextResetAt", "required"),
            ({"resetMode": "once", "nextResetAt": "2027-03-01"}, "nextResetAt", "format"),
            ({"resetMode": "once", "nextResetAt": "2027-02-30T00:00"}, "nextResetAt", "format"),
            ({"resetMode": "once", "nextResetAt": "2026-01-01T00:00"}, "nextResetAt", "past"),
            # A value the chosen settings do not use is still checked for its type, as before.
            ({"resetMode": "none", "resetCount": [2]}, "resetCount", "type"),
        )
        for change, field, reason in cases:
            body = {**BASE, **change}
            with self.assertRaises(fe.FieldError, msg=change) as caught:
                limits.limits_request(body, NO_EXPIRY)
            self.assertEqual((caught.exception.field, caught.exception.reason), (field, reason), change)
            # The old parser refused the same input.
            with self.assertRaises((ValueError, ArithmeticError, ni.InvalidInventory), msg=change):
                old_limits_request(limits.context, old_limits_form(body), NO_EXPIRY)


class ScheduleErrorTest(unittest.TestCase):
    def field(self, spec):
        try:
            scheduler.normalize_spec(spec)
            scheduler.require_future(scheduler.normalize_spec(spec), datetime(2030, 1, 1).timestamp())
        except scheduler.ScheduleError as exc:
            problem = fe.schedule_error(exc, spec)
            return problem.field, problem.reason
        return None

    def test_each_schedule_refusal_names_its_key(self):
        self.assertEqual(self.field(None), ("spec", "required"))
        self.assertEqual(self.field({"mode": "hourly"}), ("spec.mode", "format"))
        self.assertEqual(self.field({"mode": "interval", "n": 0, "unit": "hours"}), ("spec.n", "range"))
        self.assertEqual(self.field({"mode": "interval", "n": "x", "unit": "hours"}), ("spec.n", "format"))
        self.assertEqual(self.field({"mode": "interval", "n": 1, "unit": "weeks"}), ("spec.unit", "format"))
        self.assertEqual(self.field({"mode": "cron", "expr": ""}), ("spec.expr", "required"))
        self.assertEqual(self.field({"mode": "cron", "expr": "* * *"}), ("spec.expr", "format"))
        self.assertEqual(self.field({"mode": "cron", "expr": "61 * * * *"}), ("spec.expr", "range"))
        self.assertEqual(self.field("not a cron"), ("spec", "format"))
        self.assertEqual(self.field({"mode": "daily"}), ("spec.time", "required"))
        self.assertEqual(self.field({"mode": "yearly", "month": 13, "day": 1, "time": "00:00"}), ("spec.month", "range"))
        self.assertEqual(self.field({"mode": "once", "date": "2029-01-01", "time": "00:00"}), ("spec.date", "past"))


# -- the JSON API -----------------------------------------------------------------------------

class FieldApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = load_app()
        cls.token = Exchange(cls.app, "POST", "/api/login", body={"password": PASSWORD}).cookie()

    def call(self, method, path, body):
        return Exchange(self.app, method, path, body=body, cookie=self.token)

    def assertRefused(self, reply, status, code, field, reason=None):
        self.assertEqual((reply.status, reply.json["error"]), (status, code), reply.json)
        self.assertEqual(reply.json.get("field"), field, reply.json)
        self.assertEqual(reply.json.get("reason"), reason, reply.json)

    def test_traffic_limits(self):
        limits = {"key": "speedtest", **BASE, "capGib": "1.5"}
        self.assertEqual(self.call("PUT", "/api/traffic/limits", limits).json["entry"]["capBytes"], int(1.5 * 2 ** 30))
        self.assertRefused(self.call("PUT", "/api/traffic/limits", {**limits, "capGib": "-1"}),
                           400, "invalid_limits", "capGib", "range")
        self.assertRefused(self.call("PUT", "/api/traffic/limits", {**limits, "resetMode": "schedule",
                                                                    "resetSpec": {"mode": "weekly", "time": "00:00"}}),
                           400, "invalid_limits", "resetSpec.days", "required")
        self.assertRefused(self.call("PUT", "/api/traffic/limits", {**limits, "key": "../x"}),
                           400, "invalid_request", "key", "format")

    def test_node_create_and_edit(self):
        create = {"protocol": "trojan", "name": "n1", "port": None, "credential": "", "sni": "www.bing.com"}
        self.assertRefused(self.call("POST", "/api/proxy/create", {**create, "name": ""}),
                           400, "invalid_request", "name", "required")
        self.assertRefused(self.call("POST", "/api/proxy/create", {**create, "name": "a/b"}),
                           400, "invalid_request", "name", "format")
        self.assertRefused(self.call("POST", "/api/proxy/create", {**create, "name": "x" * 65}),
                           400, "invalid_request", "name", "too_long")
        self.assertRefused(self.call("POST", "/api/proxy/create", {**create, "port": 70000}),
                           400, "invalid_request", "port", "range")
        self.assertRefused(self.call("POST", "/api/proxy/create", {**create, "port": "443"}),
                           400, "invalid_request", "port", "type")
        self.assertRefused(self.call("POST", "/api/proxy/create", {**create, "port": self.app.CONSOLE_PORT}),
                           400, "invalid_request", "port", "port_in_use")
        self.assertRefused(self.call("POST", "/api/proxy/create", {**create, "credential": "short"}),
                           400, "invalid_request", "credential", "format")
        self.assertRefused(self.call("POST", "/api/proxy/create", {**create, "protocol": "vmess", "credential": "nope"}),
                           400, "invalid_request", "credential", "format")
        self.assertRefused(self.call("POST", "/api/proxy/create", {**create, "sni": "bad host"}),
                           400, "invalid_request", "sni", "format")
        self.assertRefused(self.call("POST", "/api/proxy/create", {**create, "protocol": "wireguard"}),
                           400, "invalid_request", "protocol", "format")
        # Valid input still goes to the root helper, which is missing here.
        with mock.patch.object(self.app, "node_control_apply", return_value=False) as apply:
            reply = self.call("POST", "/api/proxy/create", {**create, "port": 24567, "credential": "a" * 12})
        self.assertRefused(reply, 500, "node_settings_failed", None)
        apply.assert_called_once()
        node = {"id": "n-1", "protocol": "shadowsocks", "port": 30000, "inbound": {}}
        with mock.patch.object(self.app.ConsoleHandler, "proxy_node", return_value=node), \
                mock.patch.object(self.app, "node_control_apply", return_value=False):
            self.assertRefused(self.call("PUT", "/api/proxy/edit", {"id": "n-1", "name": "n", "port": 0, "credential": "x"}),
                               400, "invalid_request", "credential", "format")
            # 0 keeps the current port, as it always did.
            self.assertRefused(self.call("PUT", "/api/proxy/edit", {"id": "n-1", "name": "n", "port": 0}),
                               500, "node_settings_failed", None)

    def test_port_forwarding(self):
        rule = {"protocol": "tcp", "label": "", "publicPort": 20001, "targetHost": "100.64.0.2", "targetPort": 80}
        self.assertRefused(self.call("POST", "/api/portfwd/add", {**rule, "protocol": "icmp"}),
                           400, "invalid_request", "protocol", "format")
        self.assertRefused(self.call("POST", "/api/portfwd/add", {**rule, "label": "x" * 81}),
                           400, "invalid_request", "label", "too_long")
        # Refused rules come back as the page state with a message, as before, now naming the input.
        for change, field, reason in (({"publicPort": 0}, "publicPort", "range"), ({"publicPort": None}, "publicPort", "required"),
                                      ({"publicPort": "x"}, "publicPort", "format"), ({"targetHost": "x"}, "targetHost", "format"),
                                      ({"targetHost": ""}, "targetHost", "required"), ({"targetPort": 65536}, "targetPort", "range")):
            reply = self.call("POST", "/api/portfwd/add", {**rule, **change})
            self.assertEqual((reply.status, reply.json["message"]), (200, "portfwd_invalid"))
            self.assertEqual((reply.json["field"], reply.json["reason"]), (field, reason), change)
        with mock.patch.object(self.app.PORTFWD, "add", return_value=(None, "portfwd_port_taken")):
            reply = self.call("POST", "/api/portfwd/add", rule).json
        self.assertEqual((reply["message"], reply["field"], reply["reason"]), ("portfwd_port_taken", "publicPort", "port_in_use"))
        self.assertNotIn("field", self.call("GET", "/api/portfwd", None).json)

    def test_scheduled_tasks_and_backup_settings(self):
        task = {"name": "t", "command": "true", "timeout": 60, "notify": False, "enabled": True,
                "spec": {"mode": "daily", "time": "04:00:00"}}
        self.assertRefused(self.call("PUT", "/api/tasks/save", {**task, "name": "  "}), 400, "invalid", "name", "required")
        self.assertRefused(self.call("PUT", "/api/tasks/save", {**task, "name": "x" * 61}), 400, "invalid", "name", "too_long")
        self.assertRefused(self.call("PUT", "/api/tasks/save", {**task, "command": ""}), 400, "invalid", "command", "required")
        self.assertRefused(self.call("PUT", "/api/tasks/save", {**task, "timeout": 0}), 400, "invalid", "timeout", "range")
        self.assertRefused(self.call("PUT", "/api/tasks/save", {**task, "timeout": "60"}), 400, "invalid", "timeout", "type")
        self.assertRefused(self.call("PUT", "/api/tasks/save", {**task, "spec": {"mode": "daily", "time": "4pm"}}),
                           400, "invalid", "spec.time", "format")
        self.assertRefused(self.call("PUT", "/api/tasks/save", {**task, "spec": {"mode": "once", "date": "2001-01-01",
                                                                                   "time": "00:00"}}),
                           400, "past", "spec.date", "past")
        self.assertRefused(self.call("PUT", "/api/backup/settings", {"enabled": True, "keep": 0,
                                                                     "spec": {"mode": "daily", "time": "03:00"}}),
                           400, "invalid", "keep", "range")
        self.assertRefused(self.call("PUT", "/api/backup/settings", {"enabled": True, "keep": 3,
                                                                     "spec": {"mode": "weekly", "days": [], "time": "03:00"}}),
                           400, "invalid", "spec.days", "required")
        self.assertRefused(self.call("PUT", "/api/backup/key", {"public": "abc"}), 400, "invalid", "public", "format")

    def test_file_manager_rename(self):
        root = tempfile.mkdtemp()
        for name in ("a.txt", "b.txt"):
            Path(root, name).write_text("x")
        staging = tempfile.mkdtemp()

        def helper(context, request, timeout=120):
            try:
                return {"ok": True, **sysadmin.handle(request, staging)}
            except sysadmin.Refused as refused:
                return {"ok": False, "error": str(refused)}
            except FileExistsError:
                return {"ok": False, "error": "exists"}
        with mock.patch("features.api_filemanager.run_helper", helper):
            source = os.path.join(root, "a.txt")
            self.assertRefused(self.call("POST", "/api/fm/op", {"action": "rename", "path": source, "name": "b.txt"}),
                               400, "exists", "name", "exists")
            self.assertRefused(self.call("POST", "/api/fm/op", {"action": "rename", "path": source, "name": "../c"}),
                               400, "name_invalid", "name", "format")
            self.assertRefused(self.call("POST", "/api/fm/op", {"action": "mkdir", "path": os.path.join(root, "b.txt")}),
                               400, "exists", "path", "exists")
            self.assertRefused(self.call("POST", "/api/fm/op", {"action": "chmod", "path": source, "mode": "999"}),
                               400, "mode_invalid", "mode", "format")
            self.assertRefused(self.call("POST", "/api/fm/op", {"action": "chown", "path": source, "user": "root",
                                                                "group": "no-such-group-x"}),
                               400, "owner_invalid", "group", "not_found")
            self.assertRefused(self.call("POST", "/api/fm/op", {"action": "explode", "path": source}),
                               400, "invalid_request", "action", "format")
            renamed = self.call("POST", "/api/fm/op", {"action": "rename", "path": source, "name": "c.txt"})
            self.assertEqual(renamed.status, 200)

    def test_other_forms(self):
        self.assertRefused(self.call("PUT", "/api/iperf/port", {"port": 80}), 400, "iperf_port_invalid", "port", "range")
        self.assertRefused(self.call("PUT", "/api/iperf/port", {"port": "5201"}), 400, "invalid_request", "port", "type")
        self.assertRefused(self.call("POST", "/api/settings/console-port", {"port": 80}),
                           400, "console_port_invalid", "port", "range")
        self.assertRefused(self.call("PUT", "/api/monitor/alerts", {"alerts": {"disk": 10}}),
                           400, "invalid_request", "alerts.disk", "range")
        self.assertRefused(self.call("PUT", "/api/traffic/total", {"capGib": "-5"}),
                           400, "invalid_request", "capGib", "range")
        self.assertRefused(self.call("PUT", "/api/traffic/total", {"capGib": "", "resetSpec": {"mode": "daily", "time": "00:00"}}),
                           400, "invalid_request", "resetSpec.mode", "format")
        self.assertRefused(self.call("POST", "/api/security/allowlist", {"address": "nope"}),
                           400, "invalid_address", "address", "format")
        self.assertRefused(self.call("PUT", "/api/security/password", {"password": "short", "confirm": "short"}),
                           400, "weak_password", "password", "too_short")
        self.assertRefused(self.call("POST", "/api/frpc/change", {"name": "../x", "section": "create", "server": "a",
                                                                  "port": 1, "token": "t"}),
                           400, "invalid_request", "name", "format")
        self.assertRefused(self.call("POST", "/api/frpc/change", {"name": "c1", "section": "create", "server": "a",
                                                                  "port": 1, "token": "t"}),
                           400, "invalid_request", "server", "format")
        self.assertRefused(self.call("POST", "/api/frpc/change", {"name": "c1", "section": "create", "server": "192.0.2.1",
                                                                  "port": 0, "token": "t"}),
                           400, "invalid_request", "port", "range")

    def test_mini_drive(self):
        flag = self.app.DATA_DIR / "files-enabled"
        flag.write_text("1\n")
        self.addCleanup(flag.unlink)
        self.assertRefused(self.call("POST", "/api/files/link", {"file": "f", "minutes": 7, "max": None}),
                           400, "link_invalid", "minutes", "format")
        self.assertRefused(self.call("POST", "/api/files/link", {"file": "f", "minutes": "60", "max": None}),
                           400, "link_invalid", "minutes", "type")
        self.assertRefused(self.call("PUT", "/api/files/limits", {"quotaGib": 0}), 400, "quota_invalid", "quotaGib", "range")
        self.assertRefused(self.call("POST", "/api/files/fetch", {"url": "ftp://example.com/x"}),
                           400, "url_invalid", "url", "format")


class SiteProblemTest(unittest.TestCase):
    """caddy_sites.py reports a code only; the console tells the inputs apart with the same rules."""

    def test_codes_name_their_input(self):
        from features import api_domains
        problem = api_domains.site_problem
        self.assertEqual(problem({"host": "bad host"}, "host_invalid"), {"field": "host", "reason": "format"})
        self.assertEqual(problem({"host": ""}, "host_invalid"), {"field": "host", "reason": "required"})
        self.assertEqual(problem({"zone": "example.com", "name": "a b"}, "host_invalid"), {"field": "name", "reason": "format"})
        self.assertEqual(problem({"host": "ok.example.com", "aliases": ["x y"]}, "host_invalid"),
                         {"field": "aliases", "reason": "format"})
        with mock.patch.object(api_domains, "read_sites", return_value=[{"host": "ok.example.com"}]):
            self.assertEqual(problem({"host": "ok.example.com"}, "host_exists"), {"field": "host", "reason": "exists"})
            self.assertEqual(problem({"host": "new.example.com", "aliases": ["ok.example.com"]}, "host_exists"),
                             {"field": "aliases", "reason": "exists"})
        self.assertEqual(problem({"port": 443}, "port_invalid"), {"field": "port", "reason": "port_in_use"})
        self.assertEqual(problem({"port": 70000}, "port_invalid"), {"field": "port", "reason": "range"})
        self.assertEqual(problem({"allowIps": ["10.0.0.0/8", "nope"]}, "allow_invalid"), {"field": "allowIps", "reason": "format"})
        self.assertEqual(problem({"authUser": "a b"}, "auth_invalid"), {"field": "authUser", "reason": "format"})
        self.assertEqual(problem({"authUser": "admin", "authPassword": "short"}, "auth_invalid"),
                         {"field": "authPassword", "reason": "too_short"})
        self.assertEqual(problem({"token": "x"}, "token_invalid"), {"field": "token", "reason": "format"})
        self.assertEqual(problem({}, "caddy_rejected"), {})


class ReasonsTest(unittest.TestCase):
    def test_reasons_have_texts_in_every_language(self):
        root = TESTS.parent / "lang" / "ui"
        for name in ("zh-CN.json", "en.json", "es.json"):
            texts = json.loads((root / name).read_text(encoding="utf-8"))["vps"]["error"]["reason"]
            self.assertEqual(set(texts), set(fe.REASONS), name)

    def test_unknown_reason_is_a_bug(self):
        with self.assertRaises(AssertionError):
            fe.FieldError("x", "wrong")


if __name__ == "__main__":
    unittest.main()
