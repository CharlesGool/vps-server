"""The meters ride out short nft failures instead of stopping FRPS/proxy at once."""
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "web"))
import node_meter  # noqa: E402
from node_inventory import InvalidInventory  # noqa: E402


class Clock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = 0

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds
        self.sleeps += 1


def make(grace=60.0):
    clock = Clock()
    return node_meter.Tolerance(grace=grace, interval=1.0, clock=clock.clock, sleep=clock.sleep), clock


class ToleranceTest(unittest.TestCase):
    def test_success_needs_no_retry(self):
        tolerance, clock = make()
        self.assertEqual(tolerance.retrying(lambda: "ok"), "ok")
        self.assertEqual(clock.sleeps, 0)

    def test_transient_failure_is_retried_then_succeeds(self):
        tolerance, clock = make()
        calls = []

        def step():
            calls.append(1)
            if len(calls) < 4:
                raise RuntimeError("cannot list nftables tables: segfault")
            return "ok"

        self.assertEqual(tolerance.retrying(step), "ok")
        self.assertEqual(len(calls), 4)

    def test_other_host_failures_are_transient_too(self):
        for error in (OSError("busy"), subprocess.TimeoutExpired("nft", 20)):
            tolerance, _ = make()
            state = {"n": 0}

            def step():
                state["n"] += 1
                if state["n"] == 1:
                    raise error
                return state["n"]

            self.assertEqual(tolerance.retrying(step), 2)

    def test_persistent_failure_gives_up_after_grace(self):
        tolerance, clock = make(grace=60.0)

        def step():
            raise RuntimeError("nft is gone")

        with self.assertRaises(RuntimeError):
            tolerance.retrying(step)
        self.assertGreaterEqual(clock.now, 60.0)
        self.assertLess(clock.now, 62.0)

    def test_invalid_state_fails_at_once(self):
        for error in (InvalidInventory("bad"), ValueError("bad json")):
            tolerance, clock = make()

            def step():
                raise error

            with self.assertRaises(type(error)):
                tolerance.retrying(step)
            self.assertEqual(clock.sleeps, 0)

    def test_each_call_gets_its_own_window(self):
        tolerance, clock = make(grace=5.0)
        for _ in range(3):  # three outages of 3s each never add up to a stop
            state = {"n": 0}

            def step():
                state["n"] += 1
                if state["n"] <= 3:
                    raise RuntimeError("blip")
                return "ok"

            self.assertEqual(tolerance.retrying(step), "ok")


if __name__ == "__main__":
    unittest.main()
