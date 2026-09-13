"""Disposable loopback service for supervisor lifecycle and Task 8 journey tests."""

from __future__ import annotations

import argparse
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - HTTP handler API.
        if self.path == "/health":
            self.send_response(200)
            challenge = self.headers.get("X-Graph-Readiness-Challenge")
            if challenge is not None:
                self.send_header("X-Graph-Readiness-Response", challenge)
            self.end_headers()
            self.wfile.write(b"ok")
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        del format, args


class NotReadyHandler(HealthHandler):
    def do_GET(self) -> None:  # noqa: N802 - HTTP handler API.
        self.send_response(503)
        challenge = self.headers.get("X-Graph-Readiness-Challenge")
        if challenge is not None:
            self.send_header("X-Graph-Readiness-Response", challenge)
        self.end_headers()


class LocalJourneyHandler(BaseHTTPRequestHandler):
    """Loopback-only disposable UI/worker/data fixture for Task 8."""

    namespace: Path
    lease_token_digest: str

    def do_GET(self) -> None:  # noqa: N802 - HTTP handler API.
        if self.path == "/health":
            self._send_json(
                200,
                {"status": "ok"},
                readiness_challenge=self.headers.get("X-Graph-Readiness-Challenge"),
            )
            return
        if self.path == "/ui":
            self._send_json(200, {"ui": "local-system-ready"})
            return
        self._send_json(404, {"error": "not-found"})

    def do_POST(self) -> None:  # noqa: N802 - HTTP handler API.
        if self.path != "/action":
            self._send_json(404, {"error": "not-found"})
            return
        supplied = self.headers.get("X-Graph-Lease-Token", "")
        supplied_digest = hashlib.sha256(supplied.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(supplied_digest, self.lease_token_digest):
            self._send_json(403, {"error": "lease-ownership-unproven"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            action_id = payload["action_id"]
        except (KeyError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(400, {"error": "invalid-action"})
            return
        if not isinstance(action_id, str) or not action_id:
            self._send_json(400, {"error": "invalid-action"})
            return
        self.namespace.mkdir(parents=True, exist_ok=True)
        trace = self.namespace / "worker.trace.jsonl"
        with trace.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"action_id": action_id, "event": "accepted"}) + "\n")
        (self.namespace / "state.json").write_text(
            json.dumps({"last_action_id": action_id, "status": "synthetic"}),
            encoding="utf-8",
        )
        self._send_json(200, {"worker": "accepted"})

    def _send_json(
        self,
        status: int,
        payload: dict[str, str],
        *,
        readiness_challenge: str | None = None,
    ) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if readiness_challenge is not None:
            self.send_header("X-Graph-Readiness-Response", readiness_challenge)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        del format, args


def serve_malformed_response(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind(("127.0.0.1", port))
        listener.listen()
        connection, _ = listener.accept()
        with connection:
            connection.recv(4096)
            connection.sendall(b"not-http\r\n\r\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument(
        "--mode",
        choices=(
            "healthy",
            "unhealthy",
            "child_healthy",
            "broad",
            "not_ready",
            "malformed",
            "local_journey",
        ),
        required=True,
    )
    parser.add_argument("--child-pid-file", type=Path)
    parser.add_argument("--environment-file", type=Path)
    parser.add_argument("--namespace", type=Path)
    parser.add_argument("--lease-token-digest")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.environment_file is not None:
        args.environment_file.write_text(
            os.environ.get("PARENT_SECRET", "missing"),
            encoding="utf-8",
        )
    if args.mode == "healthy":
        server = ThreadingHTTPServer(("127.0.0.1", args.port), HealthHandler)
        server.serve_forever()
        return 0

    if args.mode == "local_journey":
        if args.namespace is None or args.lease_token_digest is None:
            raise SystemExit("local_journey requires namespace and lease token digest")
        if re.fullmatch(r"[0-9a-f]{64}", args.lease_token_digest) is None:
            raise SystemExit("local_journey requires lowercase SHA-256 lease token digest")
        handler = type(
            "BoundLocalJourneyHandler",
            (LocalJourneyHandler,),
            {
                "namespace": args.namespace.resolve(),
                "lease_token_digest": args.lease_token_digest,
            },
        )
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
        server.serve_forever()
        return 0

    if args.mode == "broad":
        server = ThreadingHTTPServer(("0.0.0.0", args.port), HealthHandler)
        server.serve_forever()
        return 0

    if args.mode == "not_ready":
        server = ThreadingHTTPServer(("127.0.0.1", args.port), NotReadyHandler)
        server.serve_forever()
        return 0

    if args.mode == "malformed":
        serve_malformed_response(args.port)
        return 0

    if args.mode == "child_healthy":
        child = subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__)),
                "--port",
                str(args.port),
                "--mode",
                "healthy",
            ]
        )
        if args.child_pid_file is not None:
            args.child_pid_file.write_text(str(child.pid), encoding="ascii")
        while True:
            time.sleep(1)

    if args.child_pid_file is not None:
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        args.child_pid_file.write_text(str(child.pid), encoding="ascii")
    while True:
        time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main())
