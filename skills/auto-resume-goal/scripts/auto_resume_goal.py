#!/usr/bin/env python3
"""Monitor one native Codex Goal using the local App Server."""

import argparse
import hashlib
import itertools
import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

from websockets.exceptions import WebSocketException
from websockets.sync.client import unix_connect

DEFAULT_SOCKET = (
    Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    / "app-server-control/app-server-control.sock"
)
CHECK_SECONDS = 60
TERMINAL_TURNS = {"completed", "failed", "interrupted"}


class RpcError(RuntimeError):
    pass


class ResumeUnconfirmed(RuntimeError):
    pass


APP_SERVER_ERRORS = (RpcError, OSError, WebSocketException, ValueError, KeyError)
COMMAND_ERRORS = (*APP_SERVER_ERRORS, subprocess.CalledProcessError)


class AppServer:
    def __init__(self, socket):
        self.socket = socket
        self.ids = itertools.count(1)
        self.started = set()

    def receive(self, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("App Server response timed out")
        message = json.loads(self.socket.recv(timeout=remaining))
        if message.get("method") == "turn/started":
            self.started.add(message["params"]["threadId"])
        return message

    def call(self, method, params):
        request_id = next(self.ids)
        self.socket.send(json.dumps({"id": request_id, "method": method, "params": params}))
        deadline = time.monotonic() + (35 if method == "thread/resume" else 12)
        try:
            while True:
                message = self.receive(deadline)
                if message.get("id") == request_id:
                    if "error" in message:
                        raise RpcError(f"{method} failed (RPC {message['error'].get('code')})")
                    return message["result"]
        except TimeoutError as error:
            raise TimeoutError(f"{method} timed out") from error


@contextmanager
def connect(socket_path):
    with unix_connect(str(socket_path), open_timeout=3, close_timeout=1) as socket:
        server = AppServer(socket)
        server.call("initialize", {
            "clientInfo": {"name": "auto-resume-goal", "version": "1.0"},
            "capabilities": {"experimentalApi": True},
        })
        socket.send('{"method":"initialized"}')
        yield server


def fingerprint(goal):
    objective = hashlib.sha256(goal["objective"].encode()).hexdigest()
    return f"{goal['createdAt']}:{objective}"


def read_goal(call, ref):
    goal = call("thread/goal/get", ref)["goal"]
    if goal is not None and goal["threadId"] != ref["threadId"]:
        raise RpcError("Unexpected Goal chat identity")
    return goal


def quota(call, now):
    result = call("account/rateLimits/read", {"excludeResetCreditDetails": True})
    limits = result["rateLimits"]
    windows = [limits.get("primary"), limits.get("secondary")]
    available = (
        result.get("ordinaryUsageAllowed") is True
        and limits.get("limitId") == "codex"
        and limits.get("spendControlReached") is False
        and limits.get("rateLimitReachedType") is None
        and any(windows)
        and all(
            window is None or (
                type(window.get("usedPercent")) in (float, int)
                and 0 <= window["usedPercent"] < 100
            )
            for window in windows
        )
    )
    if available:
        return True, now
    resets = [
        window["resetsAt"]
        for window in windows if window
        and type(window.get("usedPercent")) in (float, int)
        and window["usedPercent"] >= 100
        and type(window.get("resetsAt")) is int
        and window["resetsAt"] > now
    ]
    return False, max(resets) + 5 if resets else now + 600


def thread_status(call, ref):
    thread = call("thread/read", {**ref, "includeTurns": False})["thread"]
    if thread["id"] != ref["threadId"]:
        raise RpcError("Unexpected chat identity")
    return thread["status"]["type"]


def latest_turn(call, ref):
    turns = call("thread/turns/list", {**ref, "limit": 1})["data"]
    return turns[0] if turns else {}


def resume(server, ref, expected):
    call = server.call
    thread_id = ref["threadId"]
    status = thread_status(call, ref)
    before = latest_turn(call, ref) if status in {"idle", "notLoaded"} else {}
    if status == "notLoaded" and before.get("status") in TERMINAL_TURNS:
        goal = read_goal(call, ref)
        if goal is None or fingerprint(goal) != expected or goal["status"] != "usageLimited":
            return False
        loaded = call("thread/resume", {**ref, "excludeTurns": True})["thread"]
        if loaded["id"] != thread_id:
            raise RpcError("Unexpected chat identity after loading")
        status = thread_status(call, ref)
    if status != "idle" or (before and before.get("status") not in TERMINAL_TURNS):
        return False
    goal = read_goal(call, ref)
    if goal is None or fingerprint(goal) != expected or goal["status"] != "usageLimited":
        return False

    # The protocol has no compare-and-set operation. Check identity and status immediately before writing.
    server.started.discard(thread_id)
    try:
        accepted = call("thread/goal/set", {
            **ref, "status": "active", "origin": "automatic",
        })["goal"]
        if (accepted["threadId"] != thread_id or fingerprint(accepted) != expected
                or accepted["status"] != "active"):
            raise RpcError("Native App Server did not confirm activation of the selected Goal")

        deadline = time.monotonic() + 8
        while thread_id not in server.started:
            try:
                server.receive(deadline)
            except TimeoutError:
                break
        if thread_id not in server.started:
            latest = latest_turn(call, ref)
            if not latest or latest["id"] == before.get("id"):
                raise RpcError("No new turn observed")
    except APP_SERVER_ERRORS as error:
        raise ResumeUnconfirmed(
            f"{error}. Check the original chat before restarting the monitor."
        ) from error
    print("Verified a new turn in the original chat", flush=True)
    return True


def watch(ref, expected, socket_path):
    next_quota = 0
    read_failures = 0
    while True:
        try:
            with connect(socket_path) as server:
                goal = read_goal(server.call, ref)
                if goal is None or fingerprint(goal) != expected:
                    print("Stopped: Goal removed or replaced", flush=True)
                    return
                status = goal["status"]
                if status not in {"active", "usageLimited"}:
                    print(f"Stopped: native Goal is {status}", flush=True)
                    return
                now = time.time()
                if status == "active":
                    next_quota = 0
                elif now >= next_quota:
                    available, next_quota = quota(server.call, now)
                    if available:
                        resumed = resume(server, ref, expected)
                        next_quota = now + (600 if resumed else CHECK_SECONDS)
                    else:
                        check_at = time.strftime("%Y-%m-%d %H:%M:%S %z", time.localtime(next_quota))
                        print(f"Ordinary quota unavailable or unconfirmed; recheck at {check_at}", flush=True)
                read_failures = 0
        except ResumeUnconfirmed as error:
            raise SystemExit(f"Stopped: continuation unconfirmed. {error}") from error
        except APP_SERVER_ERRORS as error:
            read_failures += 1
            print(f"Read check failed ({read_failures}/5): {type(error).__name__}", flush=True)
            if read_failures >= 5:
                raise SystemExit("Stopped: App Server state could not be verified") from error
        time.sleep(CHECK_SECONDS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "status", "stop", "watch"))
    parser.add_argument("--thread", default=os.environ.get("CODEX_THREAD_ID"))
    parser.add_argument("--socket", type=Path, default=DEFAULT_SOCKET,
                        help="Path to the owning Codex App Server control socket")
    parser.add_argument("--expected", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        thread_id = str(UUID(args.thread or ""))
    except ValueError:
        parser.error("A valid Codex chat UUID is required via --thread or CODEX_THREAD_ID")
    ref = {"threadId": thread_id}
    unit = f"codex-auto-resume-goal-{thread_id}.service"
    socket_path = args.socket.expanduser().absolute()
    if args.action == "stop":
        return subprocess.call(["systemctl", "--user", "stop", unit])  # noqa: S603, S607
    if args.action == "watch":
        if not args.expected:
            parser.error("watch requires a captured Goal fingerprint")
        watch(ref, args.expected, socket_path)
        return 0

    if args.action == "status":
        result = subprocess.run(["systemctl", "--user", "is-active", unit],  # noqa: S603, S607
                                capture_output=True, text=True, check=False)
        print(f"Background monitor: {result.stdout.strip() or 'unknown'}", flush=True)
    with connect(socket_path) as server:
        goal = read_goal(server.call, ref)
    if args.action == "status":
        print(f"Native Goal: {goal['status'] if goal else 'none'}")
        return 0
    if goal is None or goal["status"] not in {"active", "usageLimited"}:
        parser.error("start requires an existing active or usage-limited Goal")
    # A unique unit per chat prevents a second monitor from racing the first.
    subprocess.run([  # noqa: S603, S607
        "systemd-run", "--user", "--collect", f"--unit={unit}", "--service-type=exec",
        "--property=UMask=0077", "--property=NoNewPrivileges=yes",
        sys.executable, str(Path(__file__).resolve()), "watch", "--thread", thread_id,
        "--expected", fingerprint(goal), "--socket", str(socket_path),
    ], check=True)
    print(f"Monitoring the existing Goal in {thread_id}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except COMMAND_ERRORS as error:
        raise SystemExit(str(error)) from error
