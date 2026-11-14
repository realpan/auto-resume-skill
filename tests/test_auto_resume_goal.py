import importlib.util
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, patch

SCRIPT = (Path(__file__).resolve().parents[1]
          / "skills/auto-resume-goal/scripts/auto_resume_goal.py")
spec = importlib.util.spec_from_file_location("auto_resume_goal", SCRIPT)
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)

REF = {"threadId": "00000000-0000-0000-0000-000000000001"}
GOAL = {**REF, "createdAt": 2, "objective": "Verify the result", "status": "usageLimited"}
EXPECTED = monitor.fingerprint(GOAL)


def limits(allowed, primary=100, secondary=100):
    return {
        "ordinaryUsageAllowed": allowed,
        "rateLimits": {
            "limitId": "codex", "spendControlReached": False, "rateLimitReachedType": None,
            "primary": {"usedPercent": primary, "resetsAt": 1200},
            "secondary": {"usedPercent": secondary, "resetsAt": 1500},
        },
    }


class Server:
    def __init__(self, *, status="idle", goal=GOAL, signal_turn=True, preflight_failure=False):
        self.started = set()
        self.writes = []
        self.status = status
        self.goal = goal
        self.signal_turn = signal_turn
        self.preflight_failure = preflight_failure
        self.reads = 0

    def call(self, method, params):
        if method == "thread/goal/get":
            self.reads += 1
            return {"goal": self.goal}
        if method == "account/rateLimits/read":
            return limits(True, 10, 20)
        if method == "thread/read":
            if self.preflight_failure:
                self.preflight_failure = False
                raise TimeoutError("preflight")
            return {"thread": {"id": REF["threadId"], "status": {"type": self.status}}}
        if method == "thread/turns/list":
            return {"data": [{"id": "old-turn", "status": "failed"}]}
        if method == "thread/goal/set":
            self.writes.append(params)
            self.goal = {**self.goal, "status": "active"}
            if self.signal_turn:
                self.started.add(REF["threadId"])
            return {"goal": self.goal}
        raise AssertionError(method)

    def receive(self, deadline):
        raise TimeoutError("no event")


class AutoResumeTests(unittest.TestCase):
    def test_waits_for_last_exhausted_window_and_requires_explicit_recovery(self):
        for result, expected in [
            (limits(False), (False, 1505)),
            (limits(False, 10, 20), (False, 1600)),
            (limits(None, 10, 20), (False, 1600)),
            (limits(True, 10, 20), (True, 1000)),
        ]:
            self.assertEqual(monitor.quota(Mock(return_value=result), 1000), expected)

    def test_only_activates_existing_matching_goal_in_idle_chat(self):
        for server in (Server(status="active"), Server(goal={**GOAL, "objective": "Changed"})):
            self.assertFalse(monitor.resume(server, REF, EXPECTED))
            self.assertEqual(server.writes, [])
        server = Server()
        self.assertTrue(monitor.resume(server, REF, EXPECTED))
        self.assertEqual(server.writes, [{**REF, "status": "active", "origin": "automatic"}])

    def test_does_not_repeat_an_unconfirmed_activation(self):
        server = Server(signal_turn=False)
        with patch.object(monitor, "connect", self.connection(server)), self.assertRaisesRegex(
            SystemExit, "continuation unconfirmed"
        ):
            monitor.watch(REF, EXPECTED, Path("/unused"))
        self.assertEqual(len(server.writes), 1)

    def test_preflight_read_failure_retries_before_first_activation(self):
        server = Server(preflight_failure=True)

        def advance(_seconds):
            if server.writes:
                server.goal = {**GOAL, "status": "complete"}

        with patch.object(monitor, "connect", self.connection(server)), patch.object(
            monitor.time, "sleep", side_effect=advance
        ):
            monitor.watch(REF, EXPECTED, Path("/unused"))
        self.assertEqual(len(server.writes), 1)

    def test_terminal_goal_states_exit_without_writing_or_sleeping(self):
        for status in ("complete", "paused", "blocked", "budgetLimited", None):
            with self.subTest(status=status):
                server = Server(goal={**GOAL, "status": status} if status else None)
                with patch.object(monitor, "connect", self.connection(server)), patch.object(
                    monitor.time, "sleep", side_effect=AssertionError("unexpected retry")
                ):
                    monitor.watch(REF, EXPECTED, Path("/unused"))
                self.assertEqual(server.reads, 1)
                self.assertEqual(server.writes, [])

    @staticmethod
    def connection(server):
        @contextmanager
        def connect(_socket):
            yield server

        return connect
