"""Whole-host traffic total: aggregation, periods and settings (pure, offline)."""
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))
import total_meter as tm  # noqa: E402

T0 = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


def entry(identifier, up, down, mult=None, name=None, cycle=None):
    """A metered entry; ``cycle`` is (upload, download) of its current billing cycle, as its own page shows."""
    item = {"id": identifier, "name": name or identifier, "total_upload_bytes": up, "total_download_bytes": down}
    if mult is not None:
        item["billable_multiplier"] = mult
    if cycle is not None:
        item["upload_bytes"], item["download_bytes"] = cycle
    return item


def full(entries):
    return tm.snapshot_full(entries)


class TotalMeterTest(unittest.TestCase):
    def test_lifetime_uses_each_entrys_multiplier(self):
        self.assertEqual(tm.lifetime_billable(entry("a", 10, 5)), 30)  # default x2, like nodes
        self.assertEqual(tm.lifetime_billable(entry("a", 10, 5, mult=1)), 15)
        with self.assertRaises(ValueError):
            tm.lifetime_billable(entry("a", -1, 0))

    def test_snapshot_skips_duplicates_and_keeps_names(self):
        usage, names = tm.snapshot([entry("a", 1, 1, name="Node A"), entry("a", 9, 9), entry("b", 2, 0, mult=1)])
        self.assertEqual(usage, {"a": 4, "b": 2})
        self.assertEqual(names["a"], "Node A")

    def test_first_period_without_cycle_counters_starts_at_zero_and_grows(self):
        info0 = full([entry("a", 100, 100), entry("b", 50, 0, mult=1)])
        state, changed = tm.advance(None, info0, T0)
        self.assertTrue(changed)
        self.assertEqual(tm.period_usage(state, tm.lifetimes(info0))[0], 0)
        info1 = full([entry("a", 150, 150), entry("b", 80, 0, mult=1), entry("c", 5, 5)])
        total, per = tm.period_usage(state, tm.lifetimes(info1))
        self.assertEqual(per, {"a": 200, "b": 30, "c": 20})  # a new entry counts from zero
        self.assertEqual(total, 250)

    def test_first_period_counts_what_each_current_cycle_already_holds(self):
        # lifetime 1000 up + 9000 down; this cycle's own page shows 300 up + 200 down (raw bytes)
        info = full([entry("node", 1000, 9000, cycle=(300, 200)), entry("plain", 10, 10, mult=1)])
        state, _ = tm.advance(None, info, T0)
        total, per = tm.period_usage(state, tm.lifetimes(info))
        self.assertEqual(per["node"], (300 + 200) * 2)        # billed: times the multiplier
        self.assertEqual(per["plain"], 0)                       # no cycle counters: counted from now
        self.assertEqual(total, 1000)
        grown = full([entry("node", 1100, 9000, cycle=(400, 200)), entry("plain", 10, 10, mult=1)])
        self.assertEqual(tm.period_usage(state, tm.lifetimes(grown))[1]["node"], (400 + 200) * 2)

    def test_a_cycle_larger_than_the_lifetime_counter_never_goes_negative(self):
        info = full([entry("odd", 10, 10, mult=1, cycle=(500, 500))])
        self.assertEqual(tm.backfilled_baselines(info), {"odd": 0})

    def test_period_starts_at_the_latest_boundary(self):
        self.assertEqual(tm.period_boundary(T0, 1), datetime(2026, 11, 1, tzinfo=timezone.utc))
        self.assertEqual(tm.period_boundary(T0, 20), datetime(2026, 10, 20, tzinfo=timezone.utc))
        self.assertEqual(tm.period_boundary(T0, 16), datetime(2026, 11, 16, tzinfo=timezone.utc))
        self.assertEqual(tm.period_boundary(datetime(2027, 1, 5, tzinfo=timezone.utc), 10), datetime(2026, 12, 10, tzinfo=timezone.utc))
        self.assertIsNone(tm.period_boundary(T0, 0))
        state = tm.new_state({}, T0)
        self.assertEqual(state["reset_day"], 1)
        self.assertEqual(state["period_start"], datetime(2026, 11, 1, tzinfo=timezone.utc).isoformat())
        self.assertEqual(state["next_reset_at"], datetime(2026, 12, 1, tzinfo=timezone.utc).isoformat())

    def test_removed_entry_never_makes_usage_negative(self):
        info0 = full([entry("a", 100, 0), entry("b", 100, 0)])
        state, _ = tm.advance(None, info0, T0)
        info1 = full([entry("a", 150, 0)])
        self.assertEqual(tm.period_usage(state, tm.lifetimes(info1))[0], 100)

    def test_next_reset_rolls_over_the_month_and_the_year(self):
        self.assertEqual(tm.next_reset(T0, 20), datetime(2026, 11, 20, tzinfo=timezone.utc))
        self.assertEqual(tm.next_reset(T0, 16), datetime(2026, 12, 16, tzinfo=timezone.utc))
        self.assertEqual(tm.next_reset(datetime(2026, 12, 30, tzinfo=timezone.utc), 1), datetime(2027, 1, 1, tzinfo=timezone.utc))
        self.assertIsNone(tm.next_reset(T0, 0))
        for bad in (29, -1, "1"):
            with self.assertRaises(ValueError):
                tm.next_reset(T0, bad)

    def test_period_rolls_when_due_and_resets_usage(self):
        info0 = full([entry("a", 100, 0)])
        state = tm.new_state(info0, T0, cap_bytes=1000, reset_day=20)
        later = datetime(2026, 11, 20, 0, 0, 1, tzinfo=timezone.utc)
        info1 = full([entry("a", 400, 0)])
        self.assertEqual(tm.period_usage(state, tm.lifetimes(info1))[0], 600)
        state, changed = tm.advance(state, info1, later)
        self.assertTrue(changed)
        self.assertEqual(tm.period_usage(state, tm.lifetimes(info1))[0], 0)
        self.assertEqual(state["next_reset_at"], datetime(2026, 12, 20, tzinfo=timezone.utc).isoformat())
        self.assertEqual(state["cap_bytes"], 1000)
        self.assertFalse(tm.advance(state, info1, later)[1])

    def test_an_old_state_is_rebuilt_from_the_cycles_keeping_cap_and_day(self):
        old = {"version": 1, "cap_bytes": 800 * 1024 ** 3, "reset_day": 1,
               "period_start": "2026-11-16T14:39:06+00:00", "next_reset_at": "2026-12-01T00:00:00+00:00",
               "baselines": {"node": 631_003_675_830}}
        info = full([entry("node", 39_364_668_614, 276_144_017_081, cycle=(27_663_103_405, 22_577_345_492))])
        state, changed = tm.advance(tm.validate(old), info, T0)
        self.assertTrue(changed)
        self.assertEqual((state["version"], state["cap_bytes"], state["reset_day"]), (3, 800 * 1024 ** 3, 1))
        self.assertEqual(state["period_start"], datetime(2026, 11, 1, tzinfo=timezone.utc).isoformat())
        self.assertEqual(tm.period_usage(state, tm.lifetimes(info))[0], (27_663_103_405 + 22_577_345_492) * 2)
        self.assertFalse(tm.advance(state, info, T0)[1])                    # and then it is stable

    def test_a_version_2_state_only_gains_the_calibration_fields(self):
        v2 = {"version": 2, "cap_bytes": None, "reset_day": 1, "period_start": "2026-11-01T00:00:00+00:00",
              "next_reset_at": "2026-12-01T00:00:00+00:00", "baselines": {"a": 5}}
        state, changed = tm.advance(tm.validate(v2), full([entry("a", 10, 0)]), T0)
        self.assertTrue(changed)
        self.assertEqual((state["version"], state["calibration_bytes"], state["baselines"]), (3, 0, {"a": 5}))

    def test_levels(self):
        state = tm.new_state({}, T0, cap_bytes=1000)
        self.assertEqual([tm.level(state, used) for used in (0, 799, 800, 999, 1000, 5000)],
                         ["ok", "ok", "warn", "warn", "over", "over"])
        self.assertEqual(tm.level(tm.new_state({}, T0), 10 ** 12), "none")

    def test_settings_parsing(self):
        self.assertEqual(tm.parse_settings("1", "0"), (1073741824, 0))
        self.assertEqual(tm.parse_settings("", ""), (None, 0))
        self.assertEqual(tm.parse_settings(" 0.5 ", "28"), (536870912, 28))
        for cap, day in (("0", "0"), ("-1", "0"), ("abc", "0"), ("nan", "0"), ("inf", "0"), ("1", "29"), ("1", "x"), ("1e30", "0")):
            with self.assertRaises(ValueError, msg=(cap, day)):
                tm.parse_settings(cap, day)

    def test_changing_the_day_without_counters_reschedules_but_keeps_the_period(self):
        state = tm.new_state(full([entry("a", 100, 0)]), T0, reset_day=20)
        updated = tm.apply_settings(state, 5, 25, T0)
        self.assertEqual(updated["next_reset_at"], datetime(2026, 11, 25, tzinfo=timezone.utc).isoformat())
        self.assertEqual(updated["baselines"], state["baselines"])
        self.assertEqual(updated["period_start"], state["period_start"])
        same = tm.apply_settings(state, 9, 20, T0)
        self.assertEqual(same["next_reset_at"], state["next_reset_at"])
        self.assertIsNone(tm.apply_settings(state, None, 0, T0)["next_reset_at"])

    def test_changing_the_day_with_counters_rebases_the_period(self):
        info = full([entry("a", 1000, 0, cycle=(100, 0))])
        state = tm.new_state(info, T0, reset_day=20)
        updated = tm.apply_settings(state, 7, 5, T0, info)
        self.assertEqual(updated["period_start"], datetime(2026, 11, 5, tzinfo=timezone.utc).isoformat())
        self.assertEqual(updated["cap_bytes"], 7)
        self.assertEqual(tm.period_usage(updated, tm.lifetimes(info))[0], 200)
        self.assertEqual(tm.apply_settings(state, 9, 20, T0, info)["period_start"], state["period_start"])

    # -- calibration ------------------------------------------------------------------

    def test_calibration_stores_the_signed_difference_and_totals_it(self):
        state = tm.new_state(full([entry("a", 100, 0, mult=1)]), T0)
        measured = 40
        up = tm.apply_calibration(state, 100, measured, T0)
        self.assertEqual((up["calibration_bytes"], up["calibrated_at"]), (60, T0.isoformat()))
        self.assertEqual(tm.calibrated_total(up, measured), 100)
        down = tm.apply_calibration(state, 25, measured, T0)
        self.assertEqual(down["calibration_bytes"], -15)
        self.assertEqual(tm.calibrated_total(down, measured), 25)
        self.assertEqual(tm.calibrated_total(down, 5), 0)                   # never below zero
        cleared = tm.apply_calibration(up, None, measured, T0)
        self.assertEqual((cleared["calibration_bytes"], cleared["calibrated_at"]), (0, None))
        self.assertEqual(tm.calibrated_total(cleared, measured), measured)

    def test_calibration_follows_the_count_as_it_grows(self):
        state = tm.apply_calibration(tm.new_state({}, T0), 1000, 400, T0)
        self.assertEqual(tm.calibrated_total(state, 400), 1000)
        self.assertEqual(tm.calibrated_total(state, 550), 1150)             # 150 more counted, 150 more shown

    def test_calibration_input_is_validated(self):
        self.assertIsNone(tm.parse_actual(""))
        self.assertIsNone(tm.parse_actual("   "))
        self.assertEqual(tm.parse_actual("1.5"), 1610612736)
        self.assertEqual(tm.parse_actual("0"), 0)
        for bad in ("-1", "abc", "nan", "inf", "1e30"):
            with self.assertRaises(ValueError, msg=bad):
                tm.parse_actual(bad)
        state = tm.new_state({}, T0)
        for bad in (-1, 1.5, "5", True and "x", tm.MAX_CAP_BYTES + 1):
            with self.assertRaises(ValueError, msg=str(bad)):
                tm.apply_calibration(state, bad, 0, T0)

    def test_calibration_clears_when_the_period_rolls(self):
        info = full([entry("a", 100, 0)])
        state = tm.apply_calibration(tm.new_state(info, T0, reset_day=20), 500, 0, T0)
        later = datetime(2026, 11, 20, 0, 0, 1, tzinfo=timezone.utc)
        rolled, changed = tm.advance(state, info, later)
        self.assertTrue(changed)
        self.assertEqual((rolled["calibration_bytes"], rolled["calibrated_at"]), (0, None))

    def test_calibration_survives_the_file_and_is_checked_on_read(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "total.json"
            state = tm.apply_calibration(tm.new_state({}, T0, cap_bytes=7), 30, 10, T0)
            tm.write_state(path, state)
            self.assertEqual(tm.read_state(path), state)
            self.assertEqual(tm.calibration(tm.read_state(path)), 20)
            for broken in ({**state, "calibration_bytes": "5"}, {**state, "calibration_bytes": 10 ** 19},
                           {**state, "calibrated_at": "yesterday"}):
                with self.assertRaises(ValueError):
                    tm.validate(broken)

    def test_state_file_round_trip_and_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sub" / "total.json"
            self.assertIsNone(tm.read_state(path))
            state = tm.new_state(full([entry("a", 1, 0, mult=1)]), T0, cap_bytes=7, reset_day=3)
            tm.write_state(path, state)
            self.assertEqual(tm.read_state(path), state)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            path.write_text("{not json")
            self.assertIsNone(tm.read_state(path))
            with self.assertRaises(ValueError):
                tm.write_state(path, {**state, "cap_bytes": 0})

    def test_format_bytes(self):
        self.assertEqual(tm.format_bytes(0), "0 B")
        self.assertEqual(tm.format_bytes(1536), "1.50 KiB")
        self.assertEqual(tm.format_bytes(5 * 1024 ** 4), "5.00 TiB")
        self.assertEqual(tm.format_bytes(2000 * 1024 ** 4), "2000.00 TiB")



class CalendarResetTest(unittest.TestCase):
    """A weekly, monthly or yearly reset in the host's local time (the scheduled-task rules)."""

    def setUp(self):
        import os
        import time
        self.old = os.environ.get("TZ")
        os.environ["TZ"] = "Asia/Shanghai"
        time.tzset()

    def tearDown(self):
        import os
        import time
        if self.old is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = self.old
        time.tzset()

    def test_monthly_spec_uses_local_time_and_rolls(self):
        spec = tm.parse_spec({"mode": "monthly", "day": 20, "time": "08:00"})
        state = tm.new_state(full([entry("a", 100, 0)]), T0, cap_bytes=None, spec=spec)
        self.assertEqual(state["reset_day"], 0)
        # 08:00 in UTC+8 is midnight UTC
        self.assertEqual(state["next_reset_at"], datetime(2026, 11, 20, tzinfo=timezone.utc).isoformat())
        self.assertEqual(state["period_start"], datetime(2026, 10, 20, tzinfo=timezone.utc).isoformat())
        tm.validate(state)
        info = full([entry("a", 500, 0)])
        state, changed = tm.advance(state, info, datetime(2026, 11, 20, 0, 0, 1, tzinfo=timezone.utc))
        self.assertTrue(changed)
        self.assertEqual(state["next_reset_at"], datetime(2026, 12, 20, tzinfo=timezone.utc).isoformat())

    def test_weekly_and_yearly_specs_and_switching_back_to_a_day(self):
        weekly = tm.parse_spec({"mode": "weekly", "days": [1], "time": "00:00"})        # Monday 00:00 local
        state = tm.apply_settings(tm.new_state(full([]), T0), None, 1, T0, full([]), weekly)
        self.assertEqual(state["reset_spec"], weekly)
        self.assertEqual(state["next_reset_at"], datetime(2026, 11, 22, 16, tzinfo=timezone.utc).isoformat())
        yearly = tm.parse_spec({"mode": "yearly", "month": 1, "day": 1, "time": "00:00"})
        state = tm.apply_settings(state, None, 0, T0, full([]), yearly)
        self.assertEqual(state["next_reset_at"], datetime(2026, 12, 31, 16, tzinfo=timezone.utc).isoformat())
        state = tm.apply_settings(state, None, 5, T0, full([]), None)
        self.assertNotIn("reset_spec", state)
        self.assertEqual(state["reset_day"], 5)

    def test_node_reset_modes_round_trip_and_advance_in_local_time(self):
        import node_inventory as ni
        for spec in ({"mode": "weekly", "days": [0, 3], "time": "03:00:00"},
                     {"mode": "monthly", "day": 31, "time": "00:30:00"},
                     {"mode": "yearly", "month": 2, "day": 29, "time": "12:00:00"}):
            mode = ni.schedule_reset_mode(spec)
            self.assertEqual(ni.reset_schedule(mode), spec, mode)
        for bad in ("at:weekly:7@03:00:00", "at:monthly:0@03:00:00", "at:yearly:02-30@03:00:00",
                    "at:weekly:3,1@03:00:00", "at:daily:1@03:00:00", "at:monthly:5@24:00:00"):
            self.assertIsNone(ni.reset_schedule(bad), bad)
        with self.assertRaises(ValueError):
            ni.schedule_reset_mode({"mode": "daily", "time": "03:00:00"})
        mode = ni.schedule_reset_mode({"mode": "monthly", "day": 31, "time": "08:00:00"})    # 00:00 UTC in UTC+8
        due = datetime(2026, 1, 31, tzinfo=timezone.utc)
        self.assertEqual(ni.advance_reset_interval(due, mode), datetime(2026, 2, 28, tzinfo=timezone.utc))
        self.assertEqual(ni.advance_reset_interval(datetime(2026, 2, 28, tzinfo=timezone.utc), mode),
                         datetime(2026, 3, 31, tzinfo=timezone.utc))

    def test_bad_specs_are_refused(self):
        for bad in ({"mode": "daily", "time": "01:00"}, {"mode": "once", "date": "2027-01-01", "time": "01:00"},
                    {"mode": "monthly", "day": 40, "time": "01:00"}, "0 0 * * *"):
            with self.assertRaises(ValueError, msg=str(bad)):
                tm.parse_spec(bad)
        state = tm.new_state(full([]), T0, spec=tm.parse_spec({"mode": "monthly", "day": 1, "time": "00:00"}))
        with self.assertRaises(ValueError):
            tm.validate({**state, "reset_day": 3})


if __name__ == "__main__":
    unittest.main()
