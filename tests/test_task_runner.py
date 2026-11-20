"""Scheduled tasks through the built-in runner: output tail, fixed unit names, timeouts, loop logging.

A stand-in ``systemd-run`` on PATH runs the command with bash, or refuses like systemd
when a marker says the unit still exists, so no systemd or root is needed.
"""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))

import scheduler as sc  # noqa: E402

FAKE_SYSTEMD_RUN = """#!/bin/bash
unit=""
for arg in "$@"; do case "$arg" in --unit=*) unit="${arg#--unit=}";; esac; done
echo "$unit" >> "$FAKE_RUN_DIR/units"
if [ -e "$FAKE_RUN_DIR/busy-$unit" ]; then
  echo "Failed to start transient service unit: Unit $unit.service already exists." >&2
  exit 1
fi
while [ "$#" -gt 0 ] && [ "$1" != /bin/bash ]; do shift; done
exec "$@"
"""


class TaskRunnerTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        bin_dir = self.dir / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "systemd-run"
        fake.write_text(FAKE_SYSTEMD_RUN)
        fake.chmod(0o755)
        environment = mock.patch.dict(os.environ, {"PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
                                                   "FAKE_RUN_DIR": str(self.dir)})
        environment.start()
        self.addCleanup(environment.stop)
        self.notes = []
        self.s = sc.Scheduler(self.dir / "state", backup_action=lambda keep: "x",
                              notify=lambda title, body: self.notes.append(title))
        (self.dir / "state").mkdir()

    def units(self):
        return (self.dir / "units").read_text().split()

    def test_a_flood_of_output_keeps_only_the_tail(self):
        tid = self.s.add_task("chatty", "* * * * *", "head -c 3000000 /dev/zero | tr '\\0' x; echo; echo END")
        entry = self.s.run_task(tid)
        self.assertEqual(entry["status"], "ok")
        self.assertEqual(len(entry["output"]), sc.OUTPUT_TAIL)
        self.assertTrue(entry["output"].endswith("x\nEND\n"))
        code, raw = sc.Scheduler._systemd_run("head -c 3000000 /dev/zero; echo END", 60)
        self.assertEqual(code, 0)
        self.assertLessEqual(len(raw), sc.OUTPUT_TAIL * 4)
        self.assertTrue(raw.endswith(b"END\n"))

    def test_each_task_runs_as_its_own_fixed_unit(self):
        first = self.s.add_task("a", "* * * * *", "exit 3")
        second = self.s.add_task("b", "* * * * *", "true")
        self.assertEqual(self.s.run_task(first)["exit"], 3)
        self.s.run_task(second)
        self.s.run_task(first)
        self.assertEqual(self.units(), [f"vps-server-task-{first}", f"vps-server-task-{second}",
                                        f"vps-server-task-{first}"])
        self.assertEqual(sc.task_unit(first), f"vps-server-task-{first}")

    def test_a_unit_still_running_from_before_a_restart_is_a_skip(self):
        tid = self.s.add_task("long", "* * * * *", "true", notify=True)
        (self.dir / f"busy-vps-server-task-{tid}").touch()
        entry = self.s.run_task(tid)
        self.assertEqual((entry["status"], entry["exit"], entry["output"]), ("skipped", None, "still running"))
        self.assertEqual(self.notes, [])
        # A command that fails on its own, even one that prints "already", is still a failure.
        other = self.s.add_task("other", "* * * * *", "echo already; exit 1", notify=True)
        self.assertEqual(self.s.run_task(other)["status"], "failed")
        self.assertEqual(self.notes, ["other"])

    def test_a_timeout_keeps_the_output_so_far(self):
        ticks = iter(range(0, 10 ** 6, 5))
        tid = self.s.add_task("slow", "* * * * *", "echo partial; exec sleep 30", timeout=1)
        with mock.patch.object(sc.time, "monotonic", lambda: next(ticks)):
            entry = self.s.run_task(tid)
        self.assertEqual(entry["status"], "timeout")
        self.assertEqual(entry["output"], "partial\n")

    def test_a_failing_check_is_logged_once_while_it_repeats(self):
        calls = []

        def broken():
            calls.append(1)
            if len(calls) != 3:
                raise ValueError("bad file")

        self.s.tick = broken
        log = io.StringIO()
        with contextlib.redirect_stderr(log):
            for _ in range(5):
                self.s._safe_tick()
        self.assertEqual(len(calls), 5)
        lines = log.getvalue().splitlines()
        self.assertEqual(len(lines), 2)  # once, then again after a good check
        self.assertIn("ValueError: bad file", lines[0])



@unittest.skipUnless(Path("/usr/share/zoneinfo/America/New_York").exists(), "needs tzdata")
class CronClockBackTest(unittest.TestCase):
    """The hour repeated when the clock goes back runs a fixed-hour cron job once, a "*" one twice."""

    def setUp(self):
        old = os.environ.get("TZ")
        os.environ["TZ"] = "America/New_York"
        time.tzset()

        def restore():
            if old is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = old
            time.tzset()
        self.addCleanup(restore)

    def runs(self, expr):
        from datetime import datetime, timezone
        marker = int(datetime(2027, 11, 6, 12, tzinfo=timezone.utc).timestamp())
        start = int(datetime(2027, 11, 7, 4, 0, tzinfo=timezone.utc).timestamp())   # 00:00 EDT
        fired = []
        for now in range(start, start + 4 * 3600, 30):
            action, marker = sc.check_due({"mode": "cron", "expr": expr}, now, marker)
            if action:
                fired.append(datetime.fromtimestamp(now, timezone.utc).strftime("%H:%M"))
        return fired

    def test_fixed_hour_runs_once(self):
        self.assertEqual(self.runs("30 1 * * *"), ["05:30"])        # 01:30 EDT only

    def test_every_hour_runs_in_both_passes(self):
        self.assertEqual(self.runs("30 * * * *"), ["04:30", "05:30", "06:30", "07:30"])


if __name__ == "__main__":
    unittest.main()
