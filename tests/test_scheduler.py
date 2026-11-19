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


def ts(*parts):
    """Unix time of a local date and time."""
    return D(*parts).timestamp()


class SpecTest(unittest.TestCase):
    def test_times_take_seconds_and_default_them(self):
        n = sc.normalize_spec
        self.assertEqual(n({"mode": "daily", "time": "03:30"}), {"mode": "daily", "time": "03:30:00"})
        self.assertEqual(n({"mode": "daily", "time": "12:30:10"}), {"mode": "daily", "time": "12:30:10"})
        self.assertEqual(n({"mode": "weekly", "days": [3, 1, 1], "time": "22:05:59"}),
                         {"mode": "weekly", "days": [1, 3], "time": "22:05:59"})
        self.assertEqual(n({"mode": "monthly", "day": 15, "time": "00:00"}), {"mode": "monthly", "day": 15, "time": "00:00:00"})
        self.assertEqual(n({"mode": "once", "date": "2026-12-01", "time": "08:00:30"}),
                         {"mode": "once", "date": "2026-12-01", "time": "08:00:30"})
        self.assertEqual(n("*/5 * * * *"), {"mode": "cron", "expr": "*/5 * * * *"})
        self.assertEqual(n({"mode": "interval", "n": "30", "unit": "minutes"}), {"mode": "interval", "n": 30, "unit": "minutes"})

    def test_invalid_specs_are_refused(self):
        bad = ({"mode": "interval", "n": 0, "unit": "minutes"}, {"mode": "interval", "n": 5, "unit": "weeks"},
               {"mode": "interval", "n": "x", "unit": "hours"}, {"mode": "interval", "n": 400, "unit": "days"},
               {"mode": "interval", "n": -3, "unit": "hours"}, {"mode": "daily", "time": "24:00"}, {"mode": "daily"},
               {"mode": "daily", "time": "12:30:60"}, {"mode": "daily", "time": "12:30:1"}, {"mode": "daily", "time": "1:30"},
               {"mode": "weekly", "days": [], "time": "01:00"}, {"mode": "weekly", "days": [7], "time": "01:00"},
               {"mode": "weekly", "days": "1", "time": "01:00"}, {"mode": "weekly", "days": [True], "time": "01:00"},
               {"mode": "monthly", "day": 32, "time": "01:00"}, {"mode": "monthly", "day": 0, "time": "01:00"},
               {"mode": "yearly", "month": 2, "day": 30, "time": "01:00"}, {"mode": "yearly", "month": 13, "day": 1, "time": "01:00"},
               {"mode": "yearly", "day": 1, "time": "01:00"},
               {"mode": "once", "time": "01:00"}, {"mode": "once", "date": "2026-02-30", "time": "01:00"},
               {"mode": "once", "date": "2026-1-5", "time": "01:00"}, {"mode": "once", "date": "tomorrow", "time": "01:00"},
               {"mode": "once", "date": "2026-12-01"}, {"mode": "once", "date": None, "time": "01:00"},
               {"mode": "cron", "expr": "bad"}, {"mode": "hourly"}, None, 5, [])
        for spec in bad:
            with self.assertRaises(sc.ScheduleError, msg=str(spec)):
                sc.normalize_spec(spec)

    def test_old_tasks_without_a_spec_still_load_as_cron(self):
        self.assertEqual(sc.task_spec({"schedule": "0 3 * * *"}), {"mode": "cron", "expr": "0 3 * * *"})
        self.assertIsNone(sc.task_spec({"schedule": "nonsense"}))
        self.assertEqual(sc.task_spec({"spec": {"mode": "daily", "time": "03:00"}}), {"mode": "daily", "time": "03:00:00"})

    def test_occurrences_down_to_the_second(self):
        daily = sc.normalize_spec({"mode": "daily", "time": "12:30:10"})
        self.assertEqual(sc.previous_occurrence(daily, D(2026, 11, 16, 12, 30, 10)), D(2026, 11, 16, 12, 30, 10))
        self.assertEqual(sc.previous_occurrence(daily, D(2026, 11, 16, 12, 30, 9)), D(2026, 11, 15, 12, 30, 10))
        self.assertEqual(sc.next_occurrence(daily, D(2026, 11, 16, 12, 30, 10)), D(2026, 11, 17, 12, 30, 10))
        weekly = sc.normalize_spec({"mode": "weekly", "days": [3], "time": "12:30:10"})            # Wednesday
        self.assertEqual(sc.previous_occurrence(weekly, D(2026, 11, 16, 9)), D(2026, 11, 11, 12, 30, 10))   # Monday -> last Wed
        self.assertEqual(sc.next_occurrence(weekly, D(2026, 11, 16, 9)), D(2026, 11, 18, 12, 30, 10))
        sunday = sc.normalize_spec({"mode": "weekly", "days": [0], "time": "00:00:05"})
        self.assertEqual(sc.next_occurrence(sunday, D(2026, 11, 16, 9)), D(2026, 11, 22, 0, 0, 5))
        monthly = sc.normalize_spec({"mode": "monthly", "day": 15, "time": "06:07:08"})
        self.assertEqual(sc.previous_occurrence(monthly, D(2026, 11, 16, 9)), D(2026, 11, 15, 6, 7, 8))
        self.assertEqual(sc.next_occurrence(monthly, D(2026, 12, 20)), D(2027, 1, 15, 6, 7, 8))

    def test_month_ends_and_yearly_dates(self):
        # Day 31 falls on each month's last day; a yearly Feb 29 falls on Feb 28 in other years.
        end = sc.normalize_spec({"mode": "monthly", "day": 31, "time": "03:00"})
        self.assertEqual(sc.next_occurrence(end, D(2026, 2, 1)), D(2026, 2, 28, 3))
        self.assertEqual(sc.next_occurrence(end, D(2026, 2, 28, 3)), D(2026, 3, 31, 3))
        self.assertEqual(sc.previous_occurrence(end, D(2026, 5, 1)), D(2026, 4, 30, 3))
        yearly = sc.normalize_spec({"mode": "yearly", "month": 11, "day": 1, "time": "00:00"})
        self.assertEqual(yearly, {"mode": "yearly", "month": 11, "day": 1, "time": "00:00:00"})
        self.assertEqual(sc.next_occurrence(yearly, D(2026, 11, 1)), D(2027, 11, 1))
        self.assertEqual(sc.previous_occurrence(yearly, D(2026, 10, 31)), D(2025, 11, 1))
        leap = sc.normalize_spec({"mode": "yearly", "month": 2, "day": 29, "time": "12:00"})
        self.assertEqual(sc.next_occurrence(leap, D(2026, 1, 1)), D(2026, 2, 28, 12))
        self.assertEqual(sc.next_occurrence(leap, D(2027, 3, 1)), D(2028, 2, 29, 12))

    def test_check_due_for_a_weekly_time_with_seconds(self):
        spec = sc.normalize_spec({"mode": "weekly", "days": [3], "time": "12:30:10"})
        marker = ts(2026, 11, 11, 12, 30, 10)                         # last Wednesday already ran
        wednesday = lambda sec: ts(2026, 11, 18, 12, 30, sec)
        self.assertEqual(sc.check_due(spec, wednesday(9), marker)[0], None)
        self.assertEqual(sc.check_due(spec, wednesday(10), marker), ("run", int(wednesday(10))))
        self.assertEqual(sc.check_due(spec, wednesday(10) + 119, marker)[0], "run")      # a little late: still runs
        self.assertIsNone(sc.check_due(spec, wednesday(10) + 121, marker)[0])               # too late: not made up
        self.assertIsNone(sc.check_due(spec, wednesday(10), wednesday(10))[0])              # already ran this one
        self.assertIsNone(sc.check_due(spec, ts(2026, 11, 19, 12, 30, 10), wednesday(10))[0])   # Thursday

    def test_check_due_for_once(self):
        spec = sc.normalize_spec({"mode": "once", "date": "2026-11-20", "time": "08:00:30"})
        at, created = ts(2026, 11, 20, 8, 0, 30), ts(2026, 11, 16)
        self.assertIsNone(sc.check_due(spec, at - 1, created)[0])
        self.assertEqual(sc.check_due(spec, at, created), ("run", int(at)))
        self.assertEqual(sc.check_due(spec, at + 100, created)[0], "run")
        self.assertEqual(sc.check_due(spec, at + 500, created)[0], "missed")                 # the console was down
        self.assertIsNone(sc.check_due(spec, at + 5, int(at))[0])                           # never twice

    def test_a_one_time_schedule_must_lie_ahead(self):
        spec = sc.normalize_spec({"mode": "once", "date": "2026-11-20", "time": "08:00:30"})
        sc.require_future(spec, ts(2026, 11, 20, 8, 0, 29))
        for now in (ts(2026, 11, 20, 8, 0, 30), ts(2026, 11, 21)):
            with self.assertRaises(sc.ScheduleError) as caught:
                sc.require_future(spec, now)
            self.assertIn("passed", str(caught.exception))
        sc.require_future(sc.normalize_spec({"mode": "daily", "time": "00:00"}), ts(2030, 1, 1))     # only "once" is checked

    def test_next_time_for_every_mode(self):
        now = ts(2026, 11, 16, 9)
        self.assertEqual(sc.next_time(sc.normalize_spec({"mode": "interval", "n": 10, "unit": "minutes"}), int(now), now), int(now) + 600)
        self.assertEqual(sc.next_time(sc.normalize_spec({"mode": "daily", "time": "12:30:10"}), None, now), int(ts(2026, 11, 16, 12, 30, 10)))
        self.assertEqual(sc.next_time(sc.normalize_spec("30 3 * * *"), None, now), int(ts(2026, 11, 17, 3, 30)))
        once = sc.normalize_spec({"mode": "once", "date": "2026-11-20", "time": "08:00"})
        self.assertEqual(sc.next_time(once, int(now), now), int(ts(2026, 11, 20, 8)))
        self.assertIsNone(sc.next_time(once, int(ts(2026, 11, 20, 8)), now))                        # already ran
        self.assertIsNone(sc.next_time(once, None, ts(2026, 11, 21)))                                 # in the past


class SchedulerTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.now = ts(2026, 11, 16, 12, 0, 0)
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
        self.started = []
        self.s.start_async = lambda target, *args: self.started.append((target.__name__, args))

    def reopen(self):
        """A new Scheduler over the same files, as after a restart."""
        other = sc.Scheduler(self.dir, backup_action=lambda keep: "x", run_command=self.s.run_command,
                             notify=self.s.notify, clock=lambda: self.now)
        other.start_async = self.s.start_async
        return other

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

    def test_home_switch_pauses_tasks(self):
        tid = self.s.add_task("c", "* * * * *", "x")
        self.now = ts(2026, 11, 16, 12, 30, 5)
        switches = {"tasks": False, "backup": True}
        self.s.active = lambda feature: switches[feature]
        self.assertEqual(self.s.tick(self.now), [])
        switches["tasks"] = True
        self.assertEqual(self.s.tick(self.now + 1), [tid])

    def test_cron_task_runs_once_per_minute_even_across_a_restart(self):
        tid = self.s.add_task("c", "* * * * *", "x")
        self.now = ts(2026, 11, 16, 12, 30, 5)
        self.assertEqual(self.s.tick(self.now), [tid])
        self.assertEqual(self.s.tick(self.now + 10), [])                              # same minute
        self.assertEqual(self.reopen().tick(self.now + 20), [])                       # restarted inside it
        self.assertEqual(self.s.tick(self.now + 60), [tid])

    def test_daily_task_fires_at_the_second_and_only_once(self):
        tid = self.s.add_task("d", {"mode": "daily", "time": "12:30:10"}, "x")
        self.assertEqual(self.s.tick(ts(2026, 11, 16, 12, 30, 9)), [])
        self.assertEqual(self.s.tick(ts(2026, 11, 16, 12, 30, 10)), [tid])
        self.assertEqual(self.s.tick(ts(2026, 11, 16, 12, 30, 11)), [])
        self.assertEqual(self.reopen().tick(ts(2026, 11, 16, 12, 30, 12)), [])
        self.assertEqual(self.s.tick(ts(2026, 11, 17, 12, 30, 10)), [tid])

    def test_a_task_created_after_todays_time_waits_for_the_next_one(self):
        self.now = ts(2026, 11, 16, 12, 31, 0)
        tid = self.s.add_task("d", {"mode": "daily", "time": "12:30:10"}, "x")
        self.assertEqual(self.s.tick(self.now + 1), [])                                # not run for a time already past
        self.assertEqual(self.s.tick(ts(2026, 11, 17, 12, 30, 10)), [tid])

    def test_weekly_task_fires_on_chosen_days_only(self):
        tid = self.s.add_task("w", {"mode": "weekly", "days": [3], "time": "12:30:10"}, "x")   # Wednesday
        self.assertEqual(self.s.tick(ts(2026, 11, 17, 12, 30, 10)), [])                # Tuesday
        self.assertEqual(self.s.tick(ts(2026, 11, 18, 12, 30, 10)), [tid])              # Wednesday
        self.assertEqual(self.s.tick(ts(2026, 11, 18, 12, 30, 40)), [])

    def test_interval_task_runs_every_interval_counted_from_the_last_start(self):
        tid = self.s.add_task("every", {"mode": "interval", "n": 10, "unit": "minutes"}, "x")
        self.assertEqual(self.s.next_for(self.s.tasks()[0]), int(self.now) + 600)
        self.assertEqual(self.s.tick(self.now + 599), [])
        self.assertEqual(self.s.tick(self.now + 600), [tid])
        self.assertEqual(self.s.tick(self.now + 601), [])
        self.assertEqual(self.s.tick(self.now + 1200), [tid])
        self.assertEqual(self.s.tick(self.now + 1200 + 600 * 50), [tid])                # an outage: one run, not a burst
        self.assertEqual(self.s.tick(self.now + 1200 + 600 * 50 + 1), [])

    def test_disabled_tasks_never_run_and_editing_restarts_the_clock(self):
        tid = self.s.add_task("x", {"mode": "interval", "n": 1, "unit": "hours"}, "x", enabled=False)
        self.assertEqual(self.s.tick(self.now + 99999), [])
        self.now += 5000
        self.s.edit_task(tid, "x", {"mode": "interval", "n": 1, "unit": "hours"}, "x", 60, True, True)
        self.assertEqual(self.s.next_for(self.s.tasks()[0]), int(self.now) + 3600)

    # -- one-time tasks -------------------------------------------------------------

    def once(self, date="2026-11-16", at="13:00:00", **extra):
        return self.s.add_task("once", {"mode": "once", "date": date, "time": at}, "x", **extra)

    def test_a_one_time_task_in_the_past_is_refused(self):
        for date, at in (("2026-11-16", "11:59:59"), ("2026-11-15", "23:00:00"), ("2026-11-16", "12:00:00")):
            with self.assertRaises(sc.ScheduleError) as caught:
                self.once(date, at)
            self.assertIn("passed", str(caught.exception))
        self.once(date="2026-11-16", at="12:00:01")                                    # one second ahead is fine
        self.once(enabled=False, date="2020-01-01")                                    # a disabled one may keep any date

    def test_a_one_time_task_runs_once_then_is_finished(self):
        tid = self.once(at="13:00:30")
        self.assertEqual(self.s.tick(ts(2026, 11, 16, 13, 0, 29)), [])
        self.assertEqual(self.s.next_for(self.s.tasks()[0]), int(ts(2026, 11, 16, 13, 0, 30)))
        self.assertEqual(self.s.tick(ts(2026, 11, 16, 13, 0, 30)), [tid])
        task = self.s.tasks()[0]
        self.assertEqual((task["enabled"], task["done"]), (False, "ran"))
        self.assertIsNone(self.s.next_for(task))
        self.assertEqual(self.s.tick(ts(2026, 11, 16, 13, 0, 31)), [])
        self.assertEqual(self.reopen().tick(ts(2026, 11, 17, 13, 0, 30)), [])
        self.assertEqual(self.s.tasks()[0]["name"], "once")                            # still listed

    def test_a_one_time_task_missed_during_downtime_is_recorded_not_run(self):
        tid = self.once(at="13:00:00")
        self.assertEqual(self.s.tick(ts(2026, 11, 16, 15, 0, 0)), [])                  # the console was down until 15:00
        task = self.s.tasks()[0]
        self.assertEqual((task["enabled"], task["done"]), (False, "missed"))
        last = self.s.last_run(tid)
        self.assertEqual((last["status"], last["output"], last["trigger"]), ("skipped", "missed", "schedule"))
        self.assertEqual(self.started, [])

    def test_a_finished_one_time_task_cannot_be_switched_back_on_but_can_be_rescheduled(self):
        tid = self.once(at="13:00:00")
        self.s.tick(ts(2026, 11, 16, 13, 0, 0))
        self.now = ts(2026, 11, 16, 14, 0, 0)
        with self.assertRaises(sc.ScheduleError):
            self.s.set_enabled(tid, True)                                               # its time has passed
        self.s.edit_task(tid, "once", {"mode": "once", "date": "2026-11-18", "time": "09:00:00"}, "x", 60, True, True)
        task = self.s.tasks()[0]
        self.assertEqual((task["enabled"], task["done"]), (True, None))
        self.assertEqual(self.s.tick(ts(2026, 11, 18, 9, 0, 0)), [tid])

    def test_run_now_works_on_a_one_time_task_without_finishing_it(self):
        tid = self.once(at="13:00:00")
        self.s.run_task(tid, "manual")
        task = self.s.tasks()[0]
        self.assertEqual((task["enabled"], task["done"]), (True, None))

    # -- the scheduled backup uses the same schedules ---------------------------------

    def test_backup_settings_validation_defaults_and_the_old_format(self):
        self.assertEqual({k: v for k, v in self.s.backup_settings().items() if k != "anchor"}, sc.BACKUP_DEFAULTS)
        for args in ((True, {"mode": "daily", "time": "24:00"}, "7"), (True, {"mode": "daily", "time": "03:00"}, "0"),
                     (True, {"mode": "daily", "time": "03:00"}, "101"), (True, {"mode": "daily", "time": "03:00"}, "x"),
                     (True, {"mode": "hourly"}, "7")):
            with self.assertRaises(sc.ScheduleError):
                sc.parse_backup_settings(*args)
        (self.dir / "backup-settings.json").write_text("garbage")
        self.assertEqual({k: v for k, v in self.s.backup_settings().items() if k != "anchor"}, sc.BACKUP_DEFAULTS)
        (self.dir / "backup-settings.json").write_text(json.dumps({"enabled": True, "time": "04:15", "keep": 3}))
        old = self.s.backup_settings()
        self.assertEqual((old["spec"], old["keep"]), ({"mode": "daily", "time": "04:15:00"}, 3))

    def test_backup_runs_on_any_kind_of_schedule_with_seconds(self):
        self.s.save_backup_settings(sc.parse_backup_settings(True, {"mode": "weekly", "days": [3], "time": "12:30:10"}, 4))
        self.assertEqual(self.s.tick(ts(2026, 11, 17, 12, 30, 10)), [])                  # Tuesday
        self.assertEqual(self.s.tick(ts(2026, 11, 18, 12, 30, 9)), [])
        self.assertEqual(self.s.tick(ts(2026, 11, 18, 12, 30, 10)), ["backup"])
        self.assertEqual(self.s.tick(ts(2026, 11, 18, 12, 30, 11)), [])
        self.assertEqual(self.reopen().tick(ts(2026, 11, 18, 12, 30, 12)), [])
        self.s.save_backup_settings(sc.parse_backup_settings(True, {"mode": "interval", "n": 6, "unit": "hours"}, 4))
        self.assertEqual(self.s.tick(self.now + 6 * 3600), ["backup"])

    def test_saving_backup_settings_does_not_fire_for_a_time_already_past_today(self):
        self.s.save_backup_settings(sc.parse_backup_settings(True, {"mode": "daily", "time": "11:00:00"}, 7))
        self.assertEqual(self.s.tick(self.now + 5), [])
        self.assertEqual(self.s.tick(ts(2026, 11, 17, 11, 0, 0)), ["backup"])

    def test_a_one_time_backup_runs_once_and_turns_itself_off(self):
        spec = {"mode": "once", "date": "2026-11-16", "time": "13:00:00"}
        self.s.save_backup_settings(sc.parse_backup_settings(True, spec, 2, self.now))
        self.assertEqual(self.s.tick(ts(2026, 11, 16, 12, 59, 59)), [])
        self.assertEqual(self.s.tick(ts(2026, 11, 16, 13, 0, 0)), ["backup"])
        settings = self.s.backup_settings()
        self.assertFalse(settings["enabled"])
        self.assertIsNone(self.s.next_backup())
        self.assertEqual(self.s.tick(ts(2026, 11, 17, 13, 0, 0)), [])

    def test_a_one_time_backup_in_the_past_is_refused_unless_switched_off(self):
        spec = {"mode": "once", "date": "2026-11-15", "time": "13:00:00"}
        with self.assertRaises(sc.ScheduleError) as caught:
            sc.parse_backup_settings(True, spec, 2, self.now)
        self.assertIn("passed", str(caught.exception))
        sc.parse_backup_settings(False, spec, 2, self.now)

    def test_a_missed_one_time_backup_is_recorded_not_run(self):
        spec = {"mode": "once", "date": "2026-11-16", "time": "13:00:00"}
        self.s.save_backup_settings(sc.parse_backup_settings(True, spec, 2, self.now))
        self.assertEqual(self.s.tick(ts(2026, 11, 16, 18, 0, 0)), [])
        last = self.s.last_run("backup")
        self.assertEqual((last["status"], last["output"]), ("skipped", "missed"))
        self.assertFalse(self.s.backup_settings()["enabled"])

    def test_run_backup_passes_retention_and_records(self):
        self.s.save_backup_settings(sc.parse_backup_settings(True, {"mode": "daily", "time": "03:00"}, 4))
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
