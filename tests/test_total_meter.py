"""Whole-host traffic total: aggregation, periods and settings (pure, offline)."""
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))
import total_meter as tm  # noqa: E402

T0 = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


def entry(identifier, up, down, mult=None, name=None):
    item = {"id": identifier, "name": name or identifier, "total_upload_bytes": up, "total_download_bytes": down}
    if mult is not None:
        item["billable_multiplier"] = mult
    return item


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

    def test_first_period_starts_at_zero_and_grows(self):
        snap0, _ = tm.snapshot([entry("a", 100, 100), entry("b", 50, 0, mult=1)])
        state, changed = tm.advance(None, snap0, T0)
        self.assertTrue(changed)
        self.assertEqual(tm.period_usage(state, snap0)[0], 0)
        snap1, _ = tm.snapshot([entry("a", 150, 150), entry("b", 80, 0, mult=1), entry("c", 5, 5)])
        total, per = tm.period_usage(state, snap1)
        self.assertEqual(per, {"a": 200, "b": 30, "c": 20})  # a new entry counts from zero
        self.assertEqual(total, 250)

    def test_removed_entry_never_makes_usage_negative(self):
        snap0, _ = tm.snapshot([entry("a", 100, 0), entry("b", 100, 0)])
        state, _ = tm.advance(None, snap0, T0)
        snap1, _ = tm.snapshot([entry("a", 150, 0)])
        self.assertEqual(tm.period_usage(state, snap1)[0], 100)

    def test_next_reset_rolls_over_the_month_and_the_year(self):
        self.assertEqual(tm.next_reset(T0, 20), datetime(2026, 11, 20, tzinfo=timezone.utc))
        self.assertEqual(tm.next_reset(T0, 16), datetime(2026, 12, 16, tzinfo=timezone.utc))
        self.assertEqual(tm.next_reset(datetime(2026, 12, 30, tzinfo=timezone.utc), 1), datetime(2027, 1, 1, tzinfo=timezone.utc))
        self.assertIsNone(tm.next_reset(T0, 0))
        for bad in (29, -1, "1"):
            with self.assertRaises(ValueError):
                tm.next_reset(T0, bad)

    def test_period_rolls_when_due_and_resets_usage(self):
        snap0, _ = tm.snapshot([entry("a", 100, 0)])
        state = tm.new_state(snap0, T0, cap_bytes=1000, reset_day=20)
        later = datetime(2026, 11, 20, 0, 0, 1, tzinfo=timezone.utc)
        snap1, _ = tm.snapshot([entry("a", 400, 0)])
        self.assertEqual(tm.period_usage(state, snap1)[0], 600)
        state, changed = tm.advance(state, snap1, later)
        self.assertTrue(changed)
        self.assertEqual(tm.period_usage(state, snap1)[0], 0)
        self.assertEqual(state["next_reset_at"], datetime(2026, 12, 20, tzinfo=timezone.utc).isoformat())
        self.assertEqual(state["cap_bytes"], 1000)
        self.assertFalse(tm.advance(state, snap1, later)[1])

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

    def test_changing_the_day_reschedules_but_keeps_the_period(self):
        snap, _ = tm.snapshot([entry("a", 100, 0)])
        state = tm.new_state(snap, T0, reset_day=20)
        updated = tm.apply_settings(state, 5, 25, T0)
        self.assertEqual(updated["next_reset_at"], datetime(2026, 11, 25, tzinfo=timezone.utc).isoformat())
        self.assertEqual(updated["baselines"], state["baselines"])
        self.assertEqual(updated["period_start"], state["period_start"])
        same = tm.apply_settings(state, 9, 20, T0)
        self.assertEqual(same["next_reset_at"], state["next_reset_at"])
        self.assertIsNone(tm.apply_settings(state, None, 0, T0)["next_reset_at"])

    def test_state_file_round_trip_and_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sub" / "total.json"
            self.assertIsNone(tm.read_state(path))
            state = tm.new_state({"a": 1}, T0, cap_bytes=7, reset_day=3)
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


if __name__ == "__main__":
    unittest.main()
