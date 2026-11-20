"""Traffic meters: validity periods, daylight saving, the host total and recovery (offline, no root or nft)."""
import copy
import decimal
import fcntl
import json
import os
import re
import sys
import tempfile
import threading
import time
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))
import app_meter  # noqa: E402
import config_backup as cb  # noqa: E402
import node_accounting as na  # noqa: E402
import node_inventory as ni  # noqa: E402
import node_meter as nm  # noqa: E402
import sysmon  # noqa: E402
import total_meter as tm  # noqa: E402
import traffic_meter  # noqa: E402
from features import traffic as traffic_feature  # noqa: E402
from features.proxy import ProxyMixin  # noqa: E402

UTC = timezone.utc
GIB = 1 << 30


class LocalTime:
    """Run with the host's local time zone set to ``name``."""

    def __init__(self, name):
        self.name = name

    def __enter__(self):
        self.saved = os.environ.get("TZ")
        os.environ["TZ"] = self.name
        time.tzset()

    def __exit__(self, *exc):
        if self.saved is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = self.saved
        time.tzset()


def returns_within(test, seconds, function, *args, **kwargs):
    """Call ``function`` on a thread; fail instead of hanging when it never returns."""
    outcome = {}

    def run():
        try:
            outcome["value"] = function(*args, **kwargs)
        except BaseException as exc:  # noqa: BLE001 - handed back to the test
            outcome["error"] = exc
    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(seconds)
    test.assertFalse(worker.is_alive(), "did not return")
    if "error" in outcome:
        raise outcome["error"]
    return outcome["value"]


def ledger_for(inventory):
    return {"version": 1, "nodes": {node["id"]: {"samples": None, "suspect": False} for node in inventory["nodes"]}}


# -- validity periods --------------------------------------------------------------

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


def form(count, unit, mode="set"):
    return {"cap_gib": [""], "upload_mbps": [""], "download_mbps": [""], "cap_action": ["throttle"],
            "expiry_mode": [mode], "expiry_count": [str(count)], "expiry_unit": [unit],
            "reset_mode": ["none"], "reset_count": ["1"], "reset_unit": ["months"], "next_reset_at": [""]}


NO_EXPIRY = {"expiry_count": None, "expiry_unit": None, "expires_at": None}


class ValidityTest(unittest.TestCase):
    def test_months_keep_the_day_and_time(self):
        start = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)
        self.assertEqual(ni.add_period(start, 1, "months"), datetime(2026, 12, 20, 9, 0, tzinfo=UTC))
        self.assertEqual(ni.add_period(start, 2, "months"), datetime(2027, 1, 20, 9, 0, tzinfo=UTC))
        end_of_january = datetime(2027, 1, 31, 23, 0, tzinfo=UTC)
        self.assertEqual(ni.add_period(end_of_january, 1, "months"), datetime(2027, 2, 28, 23, 0, tzinfo=UTC))
        self.assertEqual(ni.add_period(end_of_january, 13, "months"), datetime(2028, 2, 29, 23, 0, tzinfo=UTC))
        self.assertEqual(ni.add_period(datetime(2028, 2, 29, tzinfo=UTC), 1, "years"), datetime(2029, 2, 28, tzinfo=UTC))
        self.assertEqual(ni.add_period(start, 10, "days"), datetime(2026, 11, 30, 9, 0, tzinfo=UTC))
        for count, unit in ((0, "days"), (1, "weeks"), ("1", "days")):
            with self.assertRaises(ni.InvalidInventory):
                ni.add_period(start, count, unit)
        with self.assertRaises(ni.InvalidInventory):
            ni.add_period(start, 9999, "years")

    def test_limits_form_sets_months_from_now_not_from_the_first(self):
        for now, expected in ((datetime(2026, 11, 20, 9, 0, tzinfo=UTC), datetime(2026, 12, 20, 9, 0, tzinfo=UTC)),
                              (datetime(2027, 1, 31, 23, 0, tzinfo=UTC), datetime(2027, 2, 28, 23, 0, tzinfo=UTC))):
            request = Limits(now).node_limits_request(form(1, "months"), NO_EXPIRY)
            self.assertEqual(request["expires_at"], expected.isoformat())
            self.assertEqual((request["expiry_count"], request["expiry_unit"]), (1, "months"))
        now = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)
        for unit, expected in (("days", datetime(2026, 11, 23, 9, 0, tzinfo=UTC)),
                               ("years", datetime(2029, 11, 20, 9, 0, tzinfo=UTC))):
            self.assertEqual(Limits(now).node_limits_request(form(3, unit), NO_EXPIRY)["expires_at"], expected.isoformat())

    def test_saving_the_same_length_again_keeps_the_end(self):
        existing = {"expiry_count": 1, "expiry_unit": "months", "expires_at": "2026-12-20T09:00:00+00:00"}
        request = Limits(datetime(2026, 12, 1, tzinfo=UTC)).node_limits_request(form(1, "months"), existing)
        self.assertNotIn("expires_at", request)

    def test_a_monthly_reset_interval_still_starts_on_the_first(self):
        due = ni.advance_reset_interval(datetime(2026, 11, 20, 9, 0, tzinfo=UTC), "every:1:months:1")
        self.assertEqual(due, datetime(2026, 12, 1, tzinfo=UTC))


# -- daylight saving -----------------------------------------------------------------

def entry_due(mode, due):
    entry = traffic_meter.new_entry("caddy", "Caddy", 1)
    entry.update(reset_mode=mode, next_reset_at=due.isoformat(), upload_bytes=5, total_upload_bytes=5)
    return {"version": 1, "nodes": [entry]}


@unittest.skipUnless(Path("/usr/share/zoneinfo/America/New_York").is_file(), "needs the tz database")
class DaylightSavingTest(unittest.TestCase):
    def test_a_reset_in_the_skipped_hour_moves_on_and_returns(self):
        with LocalTime("America/New_York"):
            inventory = entry_due("at:weekly:0@02:30:00", datetime(2027, 3, 14, 6, 30, tzinfo=UTC))
            now = datetime(2027, 3, 14, 6, 31, tzinfo=UTC)
            result, _ = returns_within(self, 5, na.advance_cycles, inventory, ledger_for(inventory),
                                       now=now, validate=traffic_meter.validate)
            node = result["nodes"][0]
            # 02:30 does not exist that night: it falls at 03:30 EDT (07:30 UTC).
            self.assertEqual(node["next_reset_at"], datetime(2027, 3, 14, 7, 30, tzinfo=UTC).isoformat())
            self.assertEqual(node["upload_bytes"], 0)

    def test_next_and_previous_are_strictly_after_and_at_or_before(self):
        spec = {"mode": "weekly", "days": [0], "time": "02:30:00"}
        with LocalTime("America/New_York"):
            for after in (datetime(2027, 3, 14, 6, 30, tzinfo=UTC), datetime(2027, 3, 14, 7, 0, tzinfo=UTC)):
                self.assertEqual(ni.next_scheduled_reset(after, spec), datetime(2027, 3, 14, 7, 30, tzinfo=UTC))
            # At 03:10 EDT the moved-on 02:30 (03:30) is still ahead: the boundary is a week earlier.
            self.assertEqual(ni.previous_scheduled_reset(datetime(2027, 3, 14, 7, 10, tzinfo=UTC), spec),
                             datetime(2027, 3, 7, 7, 30, tzinfo=UTC))
            self.assertEqual(ni.previous_scheduled_reset(datetime(2027, 3, 14, 7, 40, tzinfo=UTC), spec),
                             datetime(2027, 3, 14, 7, 30, tzinfo=UTC))

    def test_a_repeated_hour_falls_once(self):
        spec = {"mode": "weekly", "days": [0], "time": "01:30:00"}
        with LocalTime("America/New_York"):
            first = datetime(2027, 11, 7, 5, 30, tzinfo=UTC)   # 01:30 EDT; 06:30 UTC is 01:30 EST
            self.assertEqual(ni.next_scheduled_reset(datetime(2027, 11, 7, 5, 0, tzinfo=UTC), spec), first)
            following = datetime(2027, 11, 14, 6, 30, tzinfo=UTC)
            for after in (first, datetime(2027, 11, 7, 6, 15, tzinfo=UTC), datetime(2027, 11, 7, 6, 30, tzinfo=UTC)):
                self.assertEqual(ni.next_scheduled_reset(after, spec), following)
            inventory = entry_due("at:weekly:0@01:30:00", first)
            result, _ = na.advance_cycles(inventory, ledger_for(inventory), now=datetime(2027, 11, 7, 6, 31, tzinfo=UTC),
                                          validate=traffic_meter.validate)
            self.assertEqual(result["nodes"][0]["next_reset_at"], following.isoformat())

    def test_a_schedule_that_does_not_advance_is_an_error_not_a_spin(self):
        due = datetime(2026, 11, 1, tzinfo=UTC)
        inventory = entry_due("every:1:days:-", due)
        with mock.patch.object(na, "advance_reset_interval", lambda value, mode: value):
            with self.assertRaises(ni.InvalidInventory):
                returns_within(self, 5, na.advance_cycles, inventory, ledger_for(inventory),
                               now=datetime(2026, 11, 2, tzinfo=UTC), validate=traffic_meter.validate)


# -- the host total --------------------------------------------------------------------

T0 = datetime(2026, 11, 16, 12, tzinfo=UTC)


def counted(identifier, gib, name=None):
    """A metered entry that has used ``gib`` GiB in total (billed twice)."""
    half = gib * GIB // 4
    return {"id": identifier, "name": name or identifier, "billable_multiplier": 2,
            "total_upload_bytes": half, "total_download_bytes": half, "upload_bytes": half, "download_bytes": half}


class TotalAbsentTest(unittest.TestCase):
    def setUp(self):
        state, _ = tm.advance(None, tm.snapshot_full([counted("node", 0), counted("rule", 0)]), T0)
        self.state = tm.apply_settings(state, 100 * GIB, 1, T0, None, None, "block")

    def usage(self, state, entries):
        return tm.period_usage(state, tm.lifetimes(tm.snapshot_full(entries)))

    def test_a_deleted_entry_keeps_counting_and_the_limit_stays(self):
        info = tm.snapshot_full([counted("node", 0), counted("rule", 120, "portfwd")])
        state, changed = tm.observe(self.state, info)
        self.assertTrue(changed)
        self.assertEqual(tm.enforced(state, self.usage(state, [counted("node", 0), counted("rule", 120)])[0]), "block")
        used, per = self.usage(state, [counted("node", 0)])               # the rule is deleted
        self.assertEqual(used, 120 * GIB)
        self.assertEqual(tm.enforced(state, used), "block")
        self.assertEqual(tm.entry_name(state, {}, "rule"), ("portfwd", 2))
        self.assertEqual(self.usage(state, [])[0], 120 * GIB)             # nothing readable at all
        state = tm.validate(json.loads(json.dumps(state)))                # survives the file
        self.assertFalse(tm.observe(state, info)[1])

    def test_usage_never_drops_within_a_period(self):
        state, _ = tm.observe(self.state, tm.snapshot_full([counted("node", 40)]))
        state, _ = tm.observe(state, tm.snapshot_full([counted("node", 10)]))   # counters went back (restore)
        self.assertEqual(self.usage(state, [counted("node", 10)])[0], 40 * GIB)

    def test_a_new_period_forgets_and_keeps_absent_baselines(self):
        state, _ = tm.observe(self.state, tm.snapshot_full([counted("node", 30), counted("rule", 10)]))
        later = datetime(2026, 12, 1, 0, 0, 1, tzinfo=UTC)
        # The rule's meter cannot be read at the turn of the period.
        rolled, changed = tm.advance(state, tm.snapshot_full([counted("node", 30)]), later)
        self.assertTrue(changed)
        self.assertEqual(rolled["seen"], {})
        self.assertEqual(self.usage(rolled, [counted("node", 30)])[0], 0)
        # Back again, it counts only what it used since, not its whole history.
        self.assertEqual(self.usage(rolled, [counted("node", 30), counted("rule", 12)])[0], 2 * GIB)
        # Gone for a whole period, its baseline is dropped at the next turn.
        again, _ = tm.advance(rolled, tm.snapshot_full([counted("node", 30)]), datetime(2027, 1, 1, 0, 0, 1, tzinfo=UTC))
        self.assertNotIn("rule", again["baselines"])

    def test_bad_records_are_refused(self):
        for seen in ([], {"a": {"bytes": -1, "name": "a", "multiplier": 2}}, {"a": {"bytes": 1, "name": "a"}}):
            with self.assertRaises(ValueError):
                tm.validate({**self.state, "seen": seen})


class Context(types.SimpleNamespace):
    pass


class TotalFeatureTest(unittest.TestCase):
    """features/traffic.py: an unreadable or deleted entry does not lift the total's limit."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.entries = [counted("node", 0)]
        self.failing = False
        notices = self.notices = []

        def read_inventory(**_):
            if self.failing:
                raise ValueError("unreadable")
            return {"nodes": copy.deepcopy(self.entries)}
        self.context = Context(
            DATA_DIR=self.tmp, NODE_STATE_PATH=self.tmp / "none", PROXY_CONFIG=self.tmp / "none",
            read_inventory=read_inventory, frps_traffic_state=lambda: None,
            APP_METER=types.SimpleNamespace(state=lambda: {"nodes": []}),
            datetime=datetime, timezone=timezone, _log_text=lambda key, **values: key,
            ALERTS=types.SimpleNamespace(notify_task=lambda title, body: notices.append(title)))
        self.feature = traffic_feature.TrafficMixin()
        self.feature.context = self.context
        patcher = mock.patch.object(traffic_feature, "TRAFFIC_DIR", self.tmp / "no-kernel-meter")
        patcher.start()
        self.addCleanup(patcher.stop)
        now = datetime.now(UTC)
        state, info = self.feature.total_state(now)
        tm.write_state(self.tmp / "total-traffic.json", tm.apply_settings(state, 100 * GIB, 1, now, info, None, "block"))

    def limit(self):
        return tm.host_limit(datetime.now(UTC), self.tmp)

    def test_limit_holds_through_a_failed_read_and_a_deletion(self):
        self.entries = [counted("node", 120)]
        self.assertEqual(self.feature.total_enforce(), "block")
        self.assertEqual(self.limit(), "block")
        self.failing = True
        self.assertEqual(self.feature.total_enforce(), "block")
        self.failing = False
        self.entries = []
        self.assertEqual(self.feature.total_enforce(), "block")
        self.assertEqual(self.limit(), "block")
        saved = tm.read_state(self.tmp / "total-traffic.json")
        self.assertEqual(saved["seen"]["node"]["bytes"], 120 * GIB)


# -- meters that stopped a service start it again ------------------------------------------

class Systemctl:
    def __init__(self, active=(), enabled=()):
        self.active, self.enabled, self.calls = set(active), set(enabled), []

    def __call__(self, args, **_):
        self.calls.append(args[1:])
        verb, unit = args[1], args[-1]
        code = 0
        if verb == "is-active":
            code = 0 if unit in self.active else 3
        elif verb == "is-enabled":
            code = 0 if unit in self.enabled else 1
        elif verb == "stop":
            self.active.discard(unit)
        elif verb == "start":
            self.active.add(unit)
        return types.SimpleNamespace(returncode=code)


class StopMarkerTest(unittest.TestCase):
    def setUp(self):
        self.marker = Path(tempfile.mkdtemp()) / "meter-stopped.json"
        self.unit = "vps-server-proxy.service"

    def test_a_service_the_meter_stopped_comes_back(self):
        systemctl = Systemctl(active={self.unit}, enabled={self.unit})
        self.assertEqual(nm.stop_services((self.unit,), self.marker, run=systemctl), [self.unit])
        self.assertNotIn(self.unit, systemctl.active)
        self.assertEqual(json.loads(self.marker.read_text())["services"], [self.unit])
        # The restarted meter fails again before its first good tick: the note stays.
        nm.stop_services((self.unit,), self.marker, run=systemctl)
        self.assertTrue(self.marker.exists())
        self.assertEqual(nm.resume_services(self.marker, run=systemctl), [self.unit])
        self.assertIn(["start", "--no-block", self.unit], systemctl.calls)
        self.assertFalse(self.marker.exists())
        self.assertEqual(nm.resume_services(self.marker, run=systemctl), [])

    def test_a_service_the_operator_stopped_or_disabled_stays_stopped(self):
        systemctl = Systemctl(active=(), enabled={self.unit})
        self.assertEqual(nm.stop_services((self.unit,), self.marker, run=systemctl), [])
        self.assertFalse(self.marker.exists())
        self.assertEqual(nm.resume_services(self.marker, run=systemctl), [])
        systemctl = Systemctl(active={self.unit}, enabled=())
        nm.stop_services((self.unit,), self.marker, run=systemctl)
        self.assertEqual(nm.resume_services(self.marker, run=systemctl), [])   # disabled meanwhile
        self.assertNotIn(self.unit, systemctl.active)
        self.assertFalse(self.marker.exists())


# -- restoring a backup -------------------------------------------------------------------

class FakeNft:
    def __init__(self):
        self.table = None

    def exists(self):
        return self.table is not None

    def counters(self):
        return {"nftables": [{"counter": {"family": "inet", "table": "t", "name": name, "bytes": value}}
                             for name, value in self.table.items()]}

    def apply(self, batch):
        names = [line.split()[-1] for line in batch.splitlines() if line.startswith("add counter")]
        self.table = {name: 0 for name in names}


class RestoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.state = self.tmp / "state"
        (self.state / "data").mkdir(parents=True)
        self.etc = self.tmp / "etc" / "vps-server-nodes"
        self.etc.mkdir(parents=True)
        os.environ["VPSSRV_STATE_DIR"] = str(self.state)
        self.saved = (cb.SYSTEM_DIRS, cb.SYSTEM_GLOBS)
        cb.SYSTEM_DIRS, cb.SYSTEM_GLOBS = (str(self.etc),), ()
        self.lock = self.tmp / "node.lock"
        self.out = self.tmp / "out"

    def tearDown(self):
        cb.SYSTEM_DIRS, cb.SYSTEM_GLOBS = self.saved
        os.environ.pop("VPSSRV_STATE_DIR", None)

    def test_restore_holds_the_meter_lock_and_drops_the_restored_table(self):
        (self.etc / "state.json").write_text("{}")
        (self.etc / "meter-stopped.json").write_text('{"services": ["vps-server-proxy.service"]}')
        other_dir = self.tmp / "etc" / "vps-server-frps"   # installed, but the backup holds none of its files
        other_dir.mkdir()
        outside = self.tmp / "outside"                      # installed, but no restore may write there
        outside.mkdir()
        cb.SYSTEM_DIRS = (str(self.etc), str(other_dir))
        name = cb.create_backup("manual", self.out)
        with __import__("tarfile").open(self.out / name) as archive:
            self.assertFalse([n for n in archive.getnames() if n.endswith("meter-stopped.json")])
        dropped = []

        def delete(table):
            with open(self.lock, "a+b") as other:      # a meter's tick would wait here
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
            dropped.append(table)
        meters = [(self.lock, self.etc, "vps_server_nodes"), (self.tmp / "frps.lock", other_dir, "vps_server_frps"),
                  (self.tmp / "gone.lock", self.tmp / "not-installed", "vps_server_traffic"),
                  (self.tmp / "outside.lock", outside, "vps_server_other")]
        with mock.patch.object(cb, "meters", lambda: meters), mock.patch.object(cb, "delete_table", delete):
            cb.restore(self.out / name, self.out)
        self.assertEqual(dropped, ["vps_server_nodes"])     # only the meter whose state came back
        self.assertTrue((self.tmp / "frps.lock").exists())  # held, though its table stays
        self.assertFalse((self.tmp / "gone.lock").exists())
        self.assertFalse((self.tmp / "outside.lock").exists())
        with open(self.lock, "a+b") as other:               # and released afterwards
            fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_an_older_ledger_rebuilds_from_a_missing_table(self):
        a = traffic_meter.new_entry("caddy", "Caddy", 1)
        b = traffic_meter.new_entry("iperf3", "iPerf3", 1)
        a["matches"] = b["matches"] = []
        store = {"inventory": {"version": 1, "nodes": [a, b]}}
        nft = FakeNft()
        meter = self.tmp / "meter.json"
        options = dict(state_path=self.tmp / "s", config_paths={}, meter_path=meter, lock_path=self.lock,
                       backend=nft, table="t", reader=lambda **_: copy.deepcopy(store["inventory"]),
                       writer=lambda inventory, **_: store.update(inventory=copy.deepcopy(inventory)),
                       validate=lambda inventory: None, limit=lambda now: None)
        now = datetime(2026, 11, 20, tzinfo=UTC)
        nm.tick(now=now, **options)
        backup = (copy.deepcopy(store["inventory"]), meter.read_text())
        store["inventory"]["nodes"] = [a]
        nm.tick(now=now, **options)                         # b is deleted later
        store["inventory"] = backup[0]
        meter.write_text(backup[1])                         # the older backup comes back...
        nft.table = None                                    # ...and the restore drops the table
        policy = nm.tick(now=now, **options)
        self.assertEqual(set(policy), {a["id"], b["id"]})
        self.assertTrue(all(entry["suspect"] for entry in json.loads(meter.read_text())["ledger"]["nodes"].values()))
        # A node with usage the ledger never saw (a backup taken between two writes) is suspect, not an error.
        node = store["inventory"]["nodes"][1]
        node.update(upload_bytes=7, total_upload_bytes=7)
        document = json.loads(meter.read_text())
        del document["ledger"]["nodes"][node["id"]]
        meter.write_text(json.dumps(document))
        nft.table = None
        nm.tick(now=now, **options)
        self.assertTrue(json.loads(meter.read_text())["ledger"]["nodes"][node["id"]]["suspect"])


# -- the host total's stop leaves a way into the console ------------------------------------

class ConsolePathTest(unittest.TestCase):
    def policy(self, entry, host):
        inventory = {"version": 1, "nodes": [entry]}
        return na.desired_policy(inventory, ledger_for(inventory), now=T0, validate=traffic_meter.validate,
                                 host=host)[entry["id"]]

    def test_a_console_path_is_throttled_not_stopped(self):
        entry = {**traffic_meter.new_entry("tailscale", "Tailscale", 1), "matches": [], "console_path": True}
        decision = self.policy(entry, "block")
        self.assertFalse(decision["blocked"])
        self.assertEqual((decision["upload_bps"], decision["host"]), (na.LIMIT_BPS, "throttle"))
        self.assertTrue(self.policy({**entry, "console_path": False}, "block")["blocked"])
        own = {**entry, "cap_bytes": 1, "cap_action": "block", "upload_bytes": 5, "total_upload_bytes": 5}
        self.assertTrue(self.policy(own, "block")["blocked"])        # its own cap still stops it

    def test_which_entries_carry_the_console(self):
        sites = Path(tempfile.mkdtemp()) / "sites.json"
        with mock.patch.object(traffic_meter, "CADDY_SITES", sites):
            self.assertTrue(traffic_meter.console_path("tailscale"))
            self.assertTrue(traffic_meter.console_path("frpcsrv:frp.example.com:7000"))
            self.assertFalse(traffic_meter.console_path("iperf3"))
            self.assertFalse(traffic_meter.console_path("portfwd:ab12"))
            self.assertFalse(traffic_meter.console_path("caddy"))            # no sites at all
            sites.write_text(json.dumps({"sites": [{"host": "a.example.com", "port": 8080}]}))
            self.assertFalse(traffic_meter.console_path("caddy"))
            sites.write_text(json.dumps({"sites": [{"host": "1.2.3.4", "ip": True, "console": True}]}))
            self.assertFalse(traffic_meter.console_path("caddy"))            # an IP certificate only
            sites.write_text(json.dumps({"sites": [{"host": "vps.example.com", "console": True}]}))
            self.assertTrue(traffic_meter.console_path("caddy"))
            sites.write_text("not json")
            self.assertTrue(traffic_meter.console_path("caddy"))             # unsure: keep the way in

    def test_the_mark_is_never_stored(self):
        folder = Path(tempfile.mkdtemp())
        entry = {**traffic_meter.new_entry("tailscale", "Tailscale", 1), "matches": [], "console_path": True}
        traffic_meter.validate({"version": 1, "nodes": [entry]})
        with mock.patch.object(traffic_meter, "STATE_DIR", folder), \
                mock.patch.object(traffic_meter, "STATE_PATH", folder / "traffic.json"):
            traffic_meter.write_state({"version": 1, "nodes": [entry]})
        stored = json.loads((folder / "traffic.json").read_text())["nodes"][0]
        self.assertNotIn("console_path", stored)
        self.assertNotIn("matches", stored)


# -- smaller fixes ------------------------------------------------------------------------------

class SmallFixesTest(unittest.TestCase):
    def test_app_meter_saves_atomically(self):
        folder = Path(tempfile.mkdtemp())
        meter = app_meter.AppMeter(folder / "app-traffic.json")
        meter.flush(datetime(2026, 11, 20, tzinfo=UTC))
        path = folder / "app-traffic.json"
        app_meter.validate(json.loads(path.read_text()))
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(sorted(p.name for p in folder.iterdir()), ["app-traffic.json", "app-traffic.lock"])

    def test_an_alert_does_not_write_back_old_thresholds(self):
        folder = Path(tempfile.mkdtemp())
        holder = {}

        def notify(title, body):
            # Thresholds saved from the page while the alert is going out.
            holder["monitor"].save_alerts({**sysmon.DEFAULT_ALERTS, "disk": 70})
        monitor = holder["monitor"] = sysmon.Monitor(folder, notify=notify)
        snapshot = {"disks": [{"mount": "/", "percent": 99}], "memory": {"used": 1, "total": 100},
                    "cpu": {"percent": 1}, "gpus": []}
        self.assertEqual(monitor.check_alerts(snapshot), ["disk:/"])
        settings = monitor.settings()
        self.assertEqual(settings["alerts"]["disk"], 70)
        self.assertIn("disk:/", settings["sent"])


if __name__ == "__main__":
    unittest.main()
