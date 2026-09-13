from __future__ import annotations

import ctypes
import hashlib
import http.client
import os
from pathlib import Path
import socket
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from scripts.graph_v5.models import ResourceLease
from scripts.graph_v5.policy import PolicyError
from scripts.graph_v5.process_runner import ProcessRunner
from scripts.graph_v5.service_supervisor import (
    DeclaredService,
    LeaseError,
    ServiceSupervisor,
    _ManagedService,
)


class ServiceSupervisorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary_directory.name)
        self.worktree = self.root / "worktree"
        self.fixtures = self.root / "fixtures"
        self.worktree.mkdir()
        self.fixtures.mkdir()
        worker_source = (
            Path(__file__).resolve().parents[2]
            / "fixtures"
            / "processes"
            / "local_system_worker.py"
        )
        self.worker = self.fixtures / "local_system_worker.py"
        shutil.copyfile(worker_source, self.worker)
        self.run_id = "run-a"
        self.supervisor = ServiceSupervisor(
            admitted_worktree=self.worktree,
            admitted_fixture_root=self.fixtures,
            run_id=self.run_id,
        )

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    def _available_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            return int(probe.getsockname()[1])

    def _service(
        self,
        *,
        port: int,
        mode: str,
        child_pid_file: Path | None = None,
        environment_file: Path | None = None,
        executable_root: Path | None = None,
    ) -> DeclaredService:
        arguments = (
            sys.executable,
            str(self.worker),
            "--port",
            str(port),
            "--mode",
            mode,
        )
        if child_pid_file is not None:
            arguments += ("--child-pid-file", str(child_pid_file))
        if environment_file is not None:
            arguments += ("--environment-file", str(environment_file))
        return DeclaredService(
            service_id="local-system-worker",
            command_kind="python_script",
            argv=arguments,
            cwd=self.worktree,
            port=port,
            readiness_path="/health",
            readiness_timeout_seconds=2.0,
            executable_digest=self._digest_file(Path(sys.executable)),
            executable_root=executable_root or Path(sys.executable).parent,
            script_digest=self._digest_file(self.worker),
        )

    @staticmethod
    def _digest_file(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _lease(self, *, port: int, run_id: str | None = None) -> ResourceLease:
        if run_id is None:
            run_id = self.run_id
        return ResourceLease.issue(run_id=run_id, resource=f"port:{port}")

    @staticmethod
    def _process_exists(pid: int) -> bool:
        if os.name == "nt":
            process_query_limited_information = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(  # type: ignore[attr-defined]
                process_query_limited_information,
                False,
                pid,
            )
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[attr-defined]
            return True
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        return True

    def _assert_process_exits(self, pid: int) -> None:
        deadline = time.monotonic() + 2.0
        while self._process_exists(pid) and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertFalse(self._process_exists(pid), f"owned descendant {pid} still running")

    def test_teardown_refuses_foreign_lease_token(self) -> None:
        port = self._available_port()
        lease = self._lease(port=port)
        receipt = self.supervisor.start(self._service(port=port, mode="healthy"), lease=lease)
        self.assertEqual(receipt.status, "ready")

        with self.assertRaisesRegex(LeaseError, "ownership"):
            self.supervisor.teardown(lease, ownership_token="wrong")

        teardown = self.supervisor.teardown(
            lease,
            ownership_token=lease.issued_ownership_token,
        )
        self.assertEqual(teardown.status, "terminated")
        self.assertTrue(teardown.process_tree_terminated)

    def test_readiness_failure_terminates_owned_process_tree(self) -> None:
        port = self._available_port()
        child_pid_file = self.worktree / "child.pid"
        lease = self._lease(port=port)

        receipt = self.supervisor.start(
            self._service(port=port, mode="unhealthy", child_pid_file=child_pid_file),
            lease=lease,
        )

        self.assertEqual(receipt.status, "readiness_failed")
        self.assertTrue(receipt.process_tree_terminated)
        child_pid = int(child_pid_file.read_text(encoding="ascii"))
        self._assert_process_exits(child_pid)

    def test_unproven_readiness_failure_remains_managed_for_recovery(self) -> None:
        port = self._available_port()
        lease = self._lease(port=port)
        captured: list[_ManagedService] = []
        terminate_tree = ServiceSupervisor._terminate_tree

        def leave_unproven(managed: _ManagedService) -> bool:
            captured.append(managed)
            return False

        with patch.object(ServiceSupervisor, "_terminate_tree", side_effect=leave_unproven):
            receipt = self.supervisor.start(
                self._service(port=port, mode="unhealthy"),
                lease=lease,
            )

        try:
            self.assertEqual(receipt.status, "readiness_failed")
            self.assertFalse(receipt.process_tree_terminated)
            self.assertIn(lease.lease_id, self.supervisor._managed)
        finally:
            if lease.lease_id in self.supervisor._managed:
                self.supervisor.teardown(
                    lease,
                    ownership_token=lease.issued_ownership_token,
                )
            elif captured:
                terminate_tree(captured[0])

    def test_wildcard_listener_cannot_satisfy_loopback_ownership(self) -> None:
        port = self._available_port()
        lease = self._lease(port=port)
        receipt = self.supervisor.start(
            self._service(port=port, mode="broad"),
            lease=lease,
        )

        try:
            self.assertEqual(receipt.status, "readiness_failed")
            self.assertTrue(receipt.process_tree_terminated)
        finally:
            if receipt.status == "ready":
                self.supervisor.teardown(
                    lease,
                    ownership_token=lease.issued_ownership_token,
                )

    def test_malformed_readiness_response_returns_failure_receipt(self) -> None:
        port = self._available_port()
        lease = self._lease(port=port)

        receipt = self.supervisor.start(
            self._service(port=port, mode="malformed"),
            lease=lease,
        )

        self.assertEqual(receipt.status, "readiness_failed")
        self.assertIsNotNone(receipt.health)
        assert receipt.health is not None
        self.assertIsNone(receipt.health.status_code)

    def test_readiness_failure_preserves_last_http_status(self) -> None:
        port = self._available_port()
        lease = self._lease(port=port)

        receipt = self.supervisor.start(
            self._service(port=port, mode="not_ready"),
            lease=lease,
        )

        self.assertEqual(receipt.status, "readiness_failed")
        self.assertTrue(receipt.process_tree_terminated)
        self.assertIsNotNone(receipt.health)
        assert receipt.health is not None
        self.assertEqual(receipt.health.status_code, 503)

    def test_readiness_refuses_substituted_receipt_identity(self) -> None:
        port = self._available_port()
        lease = self._lease(port=port)
        receipt = self.supervisor.start(self._service(port=port, mode="healthy"), lease=lease)
        self.assertEqual(receipt.status, "ready")

        substituted = receipt.model_copy(update={"run_id": "run-foreign"})
        try:
            with self.assertRaisesRegex(LeaseError, "exact owned service receipt"):
                self.supervisor.readiness(substituted)
        finally:
            teardown = self.supervisor.teardown(
                lease,
                ownership_token=lease.issued_ownership_token,
            )
        self.assertEqual(teardown.status, "terminated")

    def test_start_refuses_port_already_owned_by_foreign_process(self) -> None:
        port = self._available_port()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as foreign_listener:
            foreign_listener.bind(("127.0.0.1", port))
            foreign_listener.listen()

            receipt = self.supervisor.start(
                self._service(port=port, mode="healthy"),
                lease=self._lease(port=port),
            )

        self.assertEqual(receipt.status, "port_collision")
        self.assertFalse(receipt.process_tree_terminated)

    def test_foreign_lease_cannot_stop_owned_process_even_with_its_own_token(self) -> None:
        port = self._available_port()
        lease = self._lease(port=port, run_id="run-a")
        receipt = self.supervisor.start(self._service(port=port, mode="healthy"), lease=lease)
        self.assertEqual(receipt.status, "ready")
        foreign = self._lease(port=port, run_id="run-b")

        with self.assertRaisesRegex(LeaseError, "exact lease"):
            self.supervisor.teardown(
                foreign,
                ownership_token=foreign.issued_ownership_token,
            )

        self.supervisor.teardown(lease, ownership_token=lease.issued_ownership_token)

    def test_windows_network_bootstrap_does_not_restore_ambient_environment(self) -> None:
        port = self._available_port()
        environment_file = self.worktree / "environment.txt"
        lease = self._lease(port=port)

        with patch.dict(os.environ, {"PARENT_SECRET": "must-not-reach-child"}):
            receipt = self.supervisor.start(
                self._service(
                    port=port,
                    mode="healthy",
                    environment_file=environment_file,
                ),
                lease=lease,
            )

        self.assertEqual(receipt.status, "ready")
        self.assertEqual(environment_file.read_text(encoding="utf-8"), "missing")
        self.supervisor.teardown(lease, ownership_token=lease.issued_ownership_token)

    def test_repeat_teardown_keeps_service_identity(self) -> None:
        port = self._available_port()
        lease = self._lease(port=port)
        receipt = self.supervisor.start(self._service(port=port, mode="healthy"), lease=lease)
        self.assertEqual(receipt.status, "ready")

        self.supervisor.teardown(lease, ownership_token=lease.issued_ownership_token)
        repeat = self.supervisor.teardown(lease, ownership_token=lease.issued_ownership_token)

        self.assertEqual(repeat.status, "not_running")
        self.assertEqual(repeat.service_id, "local-system-worker")

    def test_service_rejects_foreign_run_lease_before_spawn(self) -> None:
        port = self._available_port()

        with self.assertRaisesRegex(LeaseError, "run_id"):
            self.supervisor.start(
                self._service(port=port, mode="healthy"),
                lease=self._lease(port=port, run_id="run-b"),
            )

    def test_start_records_distinct_owned_process_lease(self) -> None:
        port = self._available_port()
        lease = self._lease(port=port)

        receipt = self.supervisor.start(self._service(port=port, mode="healthy"), lease=lease)

        self.assertEqual(receipt.status, "ready")
        self.assertEqual(receipt.port_lease_id, lease.lease_id)
        self.assertIsNotNone(receipt.process_lease)
        assert receipt.process_lease is not None
        self.assertEqual(receipt.process_lease.resource, f"process:{receipt.process_id}")
        self.assertNotEqual(receipt.process_lease.lease_id, lease.lease_id)
        self.supervisor.teardown(lease, ownership_token=lease.issued_ownership_token)

    def test_start_rejects_unbound_tool_digest_and_outside_script(self) -> None:
        port = self._available_port()
        bad_digest = DeclaredService(
            service_id="local-system-worker",
            command_kind="python_script",
            argv=(sys.executable, str(self.worker), "--port", str(port), "--mode", "healthy"),
            cwd=self.worktree,
            port=port,
            readiness_path="/health",
            readiness_timeout_seconds=2.0,
            executable_digest="0" * 64,
            executable_root=Path(sys.executable).parent,
            script_digest=self._digest_file(self.worker),
        )
        with self.assertRaisesRegex(PolicyError, "digest"):
            self.supervisor.start(bad_digest, lease=self._lease(port=port))

        outside_script = self.root / "outside.py"
        outside_script.write_text("raise SystemExit(0)\n", encoding="utf-8")
        outside = DeclaredService(
            service_id="outside-script",
            command_kind="python_script",
            argv=(sys.executable, str(outside_script), "--port", str(port), "--mode", "healthy"),
            cwd=self.worktree,
            port=port,
            readiness_path="/health",
            readiness_timeout_seconds=2.0,
            executable_digest=self._digest_file(Path(sys.executable)),
            executable_root=Path(sys.executable).parent,
            script_digest=self._digest_file(outside_script),
        )
        with self.assertRaisesRegex(PolicyError, "script"):
            self.supervisor.start(outside, lease=self._lease(port=port))

    def test_service_rejects_interpreter_shell_string(self) -> None:
        with self.assertRaisesRegex(ValueError, "interpreter"):
            DeclaredService(
                service_id="shell-string",
                command_kind="python_script",
                argv=(sys.executable, "-c", "print('not admitted')"),
                cwd=self.worktree,
                port=4317,
                readiness_path="/health",
                executable_digest=self._digest_file(Path(sys.executable)),
                executable_root=Path(sys.executable).parent,
                script_digest=self._digest_file(self.worker),
            )

    def test_service_rejects_compact_interpreter_payload_and_tool_outside_root(self) -> None:
        with self.assertRaisesRegex(ValueError, "interpreter"):
            DeclaredService(
                service_id="compact-shell-string",
                command_kind="python_script",
                argv=(sys.executable, "-cprint('not admitted')"),
                cwd=self.worktree,
                port=4317,
                readiness_path="/health",
                executable_digest=self._digest_file(Path(sys.executable)),
                executable_root=Path(sys.executable).parent,
                script_digest=self._digest_file(self.worker),
            )

        port = self._available_port()
        with self.assertRaisesRegex(PolicyError, "tool root"):
            self.supervisor.start(
                self._service(
                    port=port,
                    mode="healthy",
                    executable_root=self.worktree,
                ),
                lease=self._lease(port=port),
            )

    def test_service_rejects_versioned_and_dispatcher_inline_payloads(self) -> None:
        common = dict(
            command_kind="python_script",
            cwd=self.worktree,
            port=4317,
            readiness_path="/health",
            executable_digest="0" * 64,
            executable_root=Path(sys.executable).parent,
            script_digest=self._digest_file(self.worker),
        )
        for executable, arguments in (
            ("C:/admitted/python3.12.exe", ("-c", "print('not admitted')")),
            ("C:/admitted/pwsh.exe", ("-Command", "Write-Output nope")),
            ("C:/admitted/env.exe", ("python", "-c", "print('not admitted')")),
            ("C:/admitted/perl.exe", ("-e", "print 'not admitted'")),
            ("C:/admitted/php.exe", ("-r", "echo 'not admitted';")),
            ("C:/admitted/lua.exe", ("-e", "print('not admitted')")),
            ("C:/admitted/bash.exe", ("-c", "echo not-admitted")),
            ("C:/admitted/busybox.exe", ("sh", "-c", "echo not-admitted")),
        ):
            with self.subTest(executable=executable), self.assertRaisesRegex(
                ValueError,
                "python",
            ):
                DeclaredService(
                    service_id="inline-payload",
                    argv=(executable, *arguments),
                    **common,
                )

    def test_service_requires_explicit_supported_command_kind(self) -> None:
        with self.assertRaisesRegex(ValueError, "command kind"):
            DeclaredService(
                service_id="direct-binary",
                command_kind="direct_binary",
                argv=("C:/admitted/perl.exe", "-e", "print 'not admitted'"),
                cwd=self.worktree,
                port=4317,
                readiness_path="/health",
                executable_digest="0" * 64,
                executable_root=Path(sys.executable).parent,
                script_digest=self._digest_file(self.worker),
            )

    def test_posix_root_exit_refuses_ambiguous_process_group_cleanup(self) -> None:
        port = self._available_port()
        lease = self._lease(port=port)
        process = MagicMock()
        process.poll.return_value = 0
        managed = _ManagedService(
            service=self._service(port=port, mode="healthy"),
            port_lease=lease,
            process_lease=ResourceLease.issue(run_id=self.run_id, resource="process:99"),
            process=process,
            windows_job=None,
        )

        with (
            patch("scripts.graph_v5.service_supervisor.os.name", "posix"),
            patch.object(ProcessRunner, "_terminate") as terminate,
        ):
            self.assertFalse(ServiceSupervisor._terminate_tree(managed))

        terminate.assert_not_called()

    def test_posix_ownership_unproven_teardown_remains_non_green(self) -> None:
        port = self._available_port()
        lease = self._lease(port=port)
        process = MagicMock()
        process.poll.return_value = 0
        managed = _ManagedService(
            service=self._service(port=port, mode="healthy"),
            port_lease=lease,
            process_lease=ResourceLease.issue(run_id=self.run_id, resource="process:99"),
            process=process,
            windows_job=None,
        )
        self.supervisor._managed[lease.lease_id] = managed
        self.supervisor._known_leases[lease.lease_id] = lease
        self.supervisor._known_service_ids[lease.lease_id] = managed.service.service_id

        with patch("scripts.graph_v5.service_supervisor.os.name", "posix"):
            first = self.supervisor.teardown(
                lease,
                ownership_token=lease.issued_ownership_token,
            )
            second = self.supervisor.teardown(
                lease,
                ownership_token=lease.issued_ownership_token,
            )

        self.assertEqual(first.status, "ownership_unproven")
        self.assertEqual(second.status, "ownership_unproven")
        self.assertIn(lease.lease_id, self.supervisor._managed)

    def test_readiness_accepts_owned_child_listener_and_teardown_owns_its_tree(self) -> None:
        port = self._available_port()
        child_pid_file = self.worktree / "child-healthy.pid"
        lease = self._lease(port=port)

        receipt = self.supervisor.start(
            self._service(
                port=port,
                mode="child_healthy",
                child_pid_file=child_pid_file,
            ),
            lease=lease,
        )

        self.assertEqual(receipt.status, "ready")
        assert receipt.process_lease is not None
        self.assertEqual(receipt.process_lease.resource, f"process:{receipt.process_id}")
        child_pid = int(child_pid_file.read_text(encoding="ascii"))
        teardown = self.supervisor.teardown(
            lease,
            ownership_token=lease.issued_ownership_token,
        )
        self.assertTrue(teardown.process_tree_terminated)
        self._assert_process_exits(child_pid)

    def test_foreign_listener_started_after_port_probe_cannot_become_ready(self) -> None:
        port = self._available_port()
        foreign_code = (
            "from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer\n"
            "import socket\n"
            "class Server(ThreadingHTTPServer):\n"
            "    allow_reuse_address = False\n"
            "    def server_bind(self):\n"
            "        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)\n"
            "        super().server_bind()\n"
            "class Handler(BaseHTTPRequestHandler):\n"
            "    def do_GET(self):\n"
            "        self.send_response(200)\n"
            "        challenge = self.headers.get('X-Graph-Readiness-Challenge')\n"
            "        if challenge is not None:\n"
            "            self.send_header('X-Graph-Readiness-Response', challenge)\n"
            "        self.end_headers()\n"
            "    def log_message(self, *args):\n"
            "        pass\n"
            f"Server(('127.0.0.1', {port}), Handler).serve_forever()\n"
        )
        foreign = subprocess.Popen(
            (sys.executable, "-c", foreign_code),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        receipt = None
        lease = self._lease(port=port)
        try:
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                connection = http.client.HTTPConnection("127.0.0.1", port, timeout=0.1)
                try:
                    connection.request("GET", "/health")
                    if connection.getresponse().status == 200:
                        break
                except OSError:
                    pass
                finally:
                    connection.close()
                time.sleep(0.02)
            else:
                self.fail("foreign listener never became ready")

            with patch.object(ServiceSupervisor, "_port_is_available", return_value=True):
                receipt = self.supervisor.start(
                    self._service(port=port, mode="healthy"),
                    lease=lease,
                )
            self.assertEqual(receipt.status, "readiness_failed")
        finally:
            if receipt is not None and receipt.status == "ready":
                self.supervisor.teardown(
                    lease,
                    ownership_token=lease.issued_ownership_token,
                )
            foreign.terminate()
            foreign.wait(timeout=2.0)


if __name__ == "__main__":
    unittest.main()
