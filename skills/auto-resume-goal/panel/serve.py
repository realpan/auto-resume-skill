"""Serve a local, live AutoResumeGoal panel for one selected chat."""

import argparse
import json
import os
import secrets
import subprocess
import sys
import time
from datetime import datetime
from http.client import HTTPConnection, HTTPException
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

HELPER = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(HELPER))
import auto_resume_goal as monitor  # noqa: E402


def service_command(*args):
    return subprocess.run(args, capture_output=True, text=True, timeout=6, check=False)  # noqa: S603


def snapshot(thread, unit, socket_path):
    result = service_command("systemctl", "--user", "is-active", unit)
    service = result.stdout.strip() or "unknown"
    try:
        with monitor.connect(socket_path) as server:
            goal = monitor.read_goal(server.call, {"threadId": thread})
        native = goal["status"] if goal else "none"
    except monitor.APP_SERVER_ERRORS:
        native = "unknown"
    journal = service_command("journalctl", "--user", "-u", unit, "-n", "50",
                              "--no-pager", "-o", "json")
    next_check = None
    last_resume = None
    reason = None
    for line in journal.stdout.splitlines():
        entry = json.loads(line)
        message = entry.get("MESSAGE", "")
        if not isinstance(message, str):
            continue
        if message.startswith("Started "):
            next_check = last_resume = reason = None
        if message.startswith("Ordinary quota unavailable or unconfirmed; recheck at "):
            next_check = message.rsplit("recheck at ", 1)[1]
        if message == "Verified a new turn in the original chat":
            stamp = int(entry["__REALTIME_TIMESTAMP"]) / 1_000_000
            last_resume = datetime.fromtimestamp(stamp).astimezone().isoformat()
            next_check = None
        if message.startswith(("Stopped:", "Stopped during resume:")):
            reason = message
    return {
        "goal": native,
        "monitor": service,
        "nextCheck": next_check if native == "usageLimited" and service == "active" else None,
        "lastResume": last_resume,
        "reason": reason if service in {"inactive", "failed"} else None,
    }


def make_handler(thread, token, html_path, socket_path):
    unit = f"codex-auto-resume-goal-{thread}.service"
    base = "/" + token

    class Panel(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def send(self, status, kind, body):
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; script-src 'unsafe-inline'; "
                             "style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, status, body):
            self.send(status, "application/json", json.dumps(body).encode())

        def do_GET(self):
            if urlsplit(self.path).path == base + "/":
                try:
                    html = html_path.read_bytes()
                except OSError:
                    self.send_json(503, {"error": "Panel unavailable"})
                else:
                    self.send(200, "text/html; charset=utf-8", html)
            elif self.path == base + "/status":
                try:
                    self.send_json(200, snapshot(thread, unit, socket_path))
                except (OSError, ValueError, subprocess.TimeoutExpired):
                    self.send_json(503, {"error": "Status unavailable"})
            else:
                self.send_json(404, {"error": "Not found"})

        def do_POST(self):
            if self.path != base + "/stop" or self.headers.get("X-Panel-Action") != "stop":
                self.send_json(404, {"error": "Not found"})
                return
            try:
                result = service_command("systemctl", "--user", "stop", unit)
                state = service_command("systemctl", "--user", "is-active", unit)
                stopped = result.returncode == 0 and state.stdout.strip() == "inactive"
            except (OSError, subprocess.TimeoutExpired):
                stopped = False
            self.send_json(200 if stopped else 409, {"stopped": stopped})

    return Panel


def open_panel(thread, socket_path):
    runtime = f"codex-auto-resume-panel-{thread}"
    unit = f"{runtime}.service"
    address = Path("/run/user") / str(os.getuid()) / runtime / "url"
    state = service_command("systemctl", "--user", "is-active", unit)
    if state.stdout.strip() == "active" and address.is_file():
        # Older servers cached the HTML and rejected query strings.
        existing = urlsplit(address.read_text().strip())
        if existing.scheme != "http" or existing.hostname != "127.0.0.1" or existing.port is None:
            raise SystemExit("Existing panel address is not loopback HTTP")
        probe = HTTPConnection("127.0.0.1", existing.port, timeout=2)
        try:
            probe.request("GET", existing.path + "?lang=en")
            status = probe.getresponse().status
        except (OSError, HTTPException) as error:
            raise SystemExit("Could not reach the existing panel") from error
        finally:
            probe.close()
        if status == 404:
            restarted = service_command("systemctl", "--user", "restart", unit)
            if restarted.returncode:
                raise SystemExit(restarted.stderr.strip() or "Could not restart the panel")
        elif status != 200:
            raise SystemExit("Existing panel did not respond normally")
    if state.stdout.strip() != "active":
        result = service_command(
            "systemd-run", "--user", "--collect", f"--unit={unit}", "--service-type=exec",
            f"--property=RuntimeDirectory={runtime}", "--property=RuntimeDirectoryMode=0700",
            "--property=UMask=0077", "--property=NoNewPrivileges=yes",
            sys.executable, str(Path(__file__).resolve()), "--thread", thread,
            "--socket", str(socket_path), "--address-file", str(address),
        )
        if result.returncode and service_command(
            "systemctl", "--user", "is-active", unit
        ).stdout.strip() != "active":
            raise SystemExit(result.stderr.strip() or "Could not start the panel service")
    for _ in range(30):
        try:
            print(address.read_text().strip())
            return
        except FileNotFoundError:
            time.sleep(0.1)
    raise SystemExit("Panel service did not report an address")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--thread", type=UUID, required=True)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--socket", type=Path, default=monitor.DEFAULT_SOCKET)
    parser.add_argument("--open", action="store_true", help="Start or reuse the panel service")
    parser.add_argument("--address-file", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.open:
        open_panel(str(args.thread), args.socket.expanduser().absolute())
        return
    token = secrets.token_urlsafe(24)
    html_path = Path(__file__).with_name("index.html")
    handler = make_handler(str(args.thread), token, html_path, args.socket)
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        url = f"http://127.0.0.1:{server.server_port}/{token}/"
        if args.address_file:
            temporary = args.address_file.with_suffix(".tmp")
            temporary.write_text(url)
            temporary.replace(args.address_file)
        else:
            print(url, flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
