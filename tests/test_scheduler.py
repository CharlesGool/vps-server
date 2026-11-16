"""Scheduled tasks: cron rules, running, history, overlap, backup job (no systemd)."""
import json
import os
import stat
import sys
import tempfile
import threading
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))
import scheduler as sc  # noqa: E402

D = datetime


class CronTest(unittest.TestCase):
    def nxt(self, text, after):
        return sc.next_run(text, after)

    def test_basic_fields(self):
        self.assertEqual(self.nxt("*/15 * * * *", D(2026, 11, 16, 10, 7)), D(2026, 11, 16, 10, 15))
        self.assertEqual(self.nxt("30 3 * * *", D(2026, 11, 16, 4, 0)), D(2026, 11, 17, 3, 30))
        self.assertEqual(self.nxt("0 0 1 * *", D(2026, 11, 16)), D(2026, 12, 1))
        self.assertEqual(self.nxt("0,30 9-10 * * *", D(2026, 11, 16, 9, 30)), D(2026, 11, 16, 10, 0))

    def test_weekday_and_sunday_seven(self):
        sunday = D(2026, 11, 22)  # a Sunday
        self.assertEqual(self.nxt("0 12 * * 0", D(2026, 11, 16)), D(2026, 11, 22, 12))
        self.assertEqual(self.nxt("0 12 * * 7", D(2026, 11, 16)), D(2026, 11, 22, 12))
        self.assertEqual(sunday.weekday(), 6)

    def test_day_and_weekday_both_restricted_is_or(self):
        # the 20th, or any Monday (Nov 16 2026 is a Monday): Monday comes first
        self.assertEqual(self.nxt("0 0 20 * 1", D(2026, 11, 15)), D(2026, 11, 16))
        self.assertEqual(self.nxt("0 0 20 * 1", D(2026, 11, 16, 1)), D(2026, 11, 20))

    def test_month_rollover_and_leap_day(self):
        self.assertEqual(self.nxt("0 0 29 2 *", D(2026, 11, 1)), D(2028, 2, 29))
        self.assertEqual(self.nxt("0 0 1 1 *", D(2026, 12, 31, 23, 59)), D(2027, 1, 1))

    def test_macros(self):
        self.assertEqual(self.nxt("@daily", D(2026, 11, 16, 5)), D(2026, 11, 17))
        self.assertEqual(self.nxt("@hourly", D(2026, 11, 16, 5, 10)), D(2026, 11, 16, 6))

    def test_invalid_schedules(self):
        for bad in ("", "* * * *", "60 * * * *", "* 24 * * *", "* * 0 * *", "* * * 13 *", "a b c d e",
                    "*/0 * * * *", "5-1 * * * *", "* * * * * *", None, "x" * 200):
            with self.assertRaises(sc.ScheduleError, msg=str(bad)):
                sc.parse_cron(bad)

    def test_never_matching_returns_none(self):
        self.assertIsNone(self.nxt("0 0 31 2 *", D(2026, 1, 1)))


class SchedulerTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.now = 1_800_000_000
        self.calls = []
        self.notes = []
        self.backups = []

        def run(command, timeout):
            self.calls.append((command, timeout))
            if "fail" in command:
                return 3, b"boom\n"
            return 0, b"fine\n"

        def backup(keep):
            self.backups.append(keep)
            return "config-x.tar.gz"

        self.s = sc.Scheduler(self.dir, backup_action=backup, run_command=run,
                              notify=lambda t, b: self.notes.append((t, b)), clock=lambda: self.now)

    def test_validation(self):
        for args in (("", "* * * * *", "echo"), ("n", "bad", "echo"), ("n", "* * * * *", ""),
                     ("n", "* * * * *", "echo\0"), ("n" * 61, "* * * * *", "echo")):
            with self.assertRaises(sc.ScheduleError):
                self.s.add_task(*args)
        with self.assertRaises(sc.ScheduleError):
            self.s.add_task("n", "* * * * *", "echo", timeout=0)
        with self.assertRaises(sc.ScheduleError):
            self.s.add_task("n", "* * * * *", "echo", timeout=86401)

    def test_files_are_private_and_task_limit(self):
        self.s.add_task("a", "* * * * *", "echo")
        self.assertEqual(stat.S_IMODE(os.stat(self.dir / "scheduled-tasks.json").st_mode), 0o600)
        for i in range(sc.MAX_TASKS - 1):
            self.s.add_task(f"t{i}", "* * * * *", "echo")
        with self.assertRaises(sc.ScheduleError):
            self.s.add_task("x", "* * * * *", "echo")

    def test_run_records_history_and_keeps_only_recent(self):
        tid = self.s.add_task("a", "* * * * *", "echo hi")
        for _ in range(sc.HISTORY_PER_TASK + 5):
            self.s.run_task(tid)
        self.assertEqual(len(self.s.runs(tid)), sc.HISTORY_PER_TASK)
        self.assertEqual(self.s.last_run(tid)["status"], "ok")
        self.assertEqual(self.calls[0], ("echo hi", 3600))

    def test_failure_notifies_only_when_enabled(self):
        loud = self.s.add_task("loud", "* * * * *", "fail", notify=True)
        quiet = self.s.add_task("quiet", "* * * * *", "fail", notify=False)
        self.assertEqual(self.s.run_task(loud)["status"], "failed")
        self.s.run_task(quiet)
        self.assertEqual([n[0] for n in self.notes], ["loud"])
        self.assertEqual(self.s.last_run(loud)["exit"], 3)

    def test_timeout_status(self):
        def slow(command, timeout):
            self.now += timeout
            return 1, b""
        self.s.run_command = slow
        tid = self.s.add_task("a", "* * * * *", "sleep 9", timeout=5)
        self.assertEqual(self.s.run_task(tid)["status"], "timeout")

    def test_output_is_truncated_to_tail(self):
        self.s.run_command = lambda c, t: (0, b"a" * 10000 + b"END")
        tid = self.s.add_task("a", "* * * * *", "x")
        out = self.s.run_task(tid)["output"]
        self.assertEqual(len(out), sc.OUTPUT_TAIL)
        self.assertTrue(out.endswith("END"))

    def test_overlap_is_skipped_and_recorded(self):
        gate, started = threading.Event(), threading.Event()

        def blocking(command, timeout):
            started.set()
            gate.wait(5)
            return 0, b""

        self.s.run_command = blocking
        tid = self.s.add_task("a", "* * * * *", "x")
        worker = threading.Thread(target=self.s.run_task, args=(tid,))
        worker.start()
        started.wait(5)
        self.assertEqual(self.s.run_task(tid)["status"], "skipped")
        gate.set()
        worker.join(5)
        self.assertEqual(sorted(r["status"] for r in self.s.runs(tid)), ["ok", "skipped"])

    def test_tick_starts_due_tasks_once_per_minute(self):
        started = []
        self.s.start_async = lambda target, *args: started.append((target.__name__, args))
        due = self.s.add_task("due", "* * * * *", "x")
        self.s.add_task("later", "0 0 1 1 *", "x")
        off = self.s.add_task("off", "* * * * *", "x", enabled=False)
        stamp = datetime(2026, 11, 16, 10, 30, 20).timestamp()
        self.assertEqual(self.s.tick(stamp), [due])
        self.assertEqual(self.s.tick(stamp + 10), [])        # same minute
        self.assertEqual(self.s.tick(stamp + 60), [due])     # next minute
        self.assertNotIn(off, [t for _, (t, *_) in [(n, a) for n, a in started]])

    def test_backup_job_scheduled_at_its_time_only(self):
        started = []
        self.s.start_async = lambda target, *args: started.append(target.__name__)
        self.s.save_backup_settings({"enabled": True, "time": "03:00", "keep": 4})
        self.assertEqual(self.s.tick(datetime(2026, 11, 16, 2, 59).timestamp()), [])
        self.assertEqual(self.s.tick(datetime(2026, 11, 16, 3, 0).timestamp()), ["backup"])
        self.s.save_backup_settings({"enabled": False, "time": "03:00", "keep": 4})
        self.assertEqual(self.s.tick(datetime(2026, 11, 17, 3, 0).timestamp()), [])

    def test_run_backup_passes_retention_and_records(self):
        self.s.save_backup_settings({"enabled": True, "time": "03:00", "keep": 4})
        entry = self.s.run_backup()
        self.assertEqual(self.backups, [4])
        self.assertEqual((entry["status"], entry["output"]), ("ok", "config-x.tar.gz"))
        self.assertEqual(self.s.last_run("backup")["status"], "ok")

    def test_failed_backup_notifies(self):
        def broken(keep):
            raise RuntimeError("no space left")
        self.s.backup_action = broken
        entry = self.s.run_backup()
        self.assertEqual(entry["status"], "failed")
        self.assertEqual(self.notes[0][0], "backup")

    def test_backup_settings_validation_and_defaults(self):
        self.assertEqual(self.s.backup_settings(), sc.BACKUP_DEFAULTS)
        for args in ((True, "3:00", "7"), (True, "24:00", "7"), (True, "03:00", "0"), (True, "03:00", "101"),
                     (True, "03:00", "x")):
            with self.assertRaises(sc.ScheduleError):
                sc.parse_backup_settings(*args)
        (self.dir / "backup-settings.json").write_text("garbage")
        self.assertEqual(self.s.backup_settings(), sc.BACKUP_DEFAULTS)

    def test_delete_removes_history_and_unknown_ids_fail(self):
        tid = self.s.add_task("a", "* * * * *", "x")
        self.s.run_task(tid)
        self.s.delete_task(tid)
        self.assertEqual(self.s.runs(tid), [])
        with self.assertRaises(sc.ScheduleError):
            self.s.delete_task(tid)
        with self.assertRaises(sc.ScheduleError):
            self.s.run_task("deadbeef")


if __name__ == "__main__":
    unittest.main()
