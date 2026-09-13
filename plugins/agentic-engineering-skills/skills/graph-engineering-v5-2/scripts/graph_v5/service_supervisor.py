"""Own declared local services with exact leases and loopback-only readiness."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import http.client
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import time
from typing import Literal

from .models import HealthReceipt, ResourceLease, ServiceReceipt, TeardownReceipt
from .policy import PolicyError
from .process_runner import ProcessRunner, _WindowsJob


class LeaseError(ValueError):
    """A resource action lacks proof of exact current ownership."""


def _rfc3339_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


_SHA256 = re.compile(r"[0-9a-f]{64}")
_PYTHON_EXECUTABLE = re.compile(r"(?:python|pypy)(?:\d+(?:\.\d+)*)?(?:\.exe)?\Z")


def _validate_python_script_argv(argv: tuple[str, ...]) -> None:
    """Admit only Python interpreter followed by one explicit script path."""

    executable = Path(argv[0]).name.casefold()
    if _PYTHON_EXECUTABLE.fullmatch(executable) is None:
        raise ValueError("python_script command kind requires a Python interpreter")
    if len(argv) == 1 or argv[1].startswith("-"):
        raise ValueError(
            "python interpreter requires one explicit script path before arguments"
        )


if os.name == "nt":
    from ctypes import wintypes

    _ERROR_INSUFFICIENT_BUFFER = 122
    _TCP_TABLE_OWNER_PID_LISTENER = 3
    _MIB_TCP_STATE_LISTEN = 2

    class _MibTcpRowOwnerPid(ctypes.Structure):
        _fields_ = (
            ("state", wintypes.DWORD),
            ("local_address", wintypes.DWORD),
            ("local_port", wintypes.DWORD),
            ("remote_address", wintypes.DWORD),
            ("remote_port", wintypes.DWORD),
            ("owning_pid", wintypes.DWORD),
        )

    _GET_EXTENDED_TCP_TABLE = ctypes.WinDLL("iphlpapi", use_last_error=True).GetExtendedTcpTable
    _GET_EXTENDED_TCP_TABLE.argtypes = (
        wintypes.LPVOID,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.BOOL,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
    )
    _GET_EXTENDED_TCP_TABLE.restype = wintypes.DWORD
    _QUERY_INFORMATION_JOB_OBJECT = ctypes.WinDLL(
        "kernel32", use_last_error=True
    ).QueryInformationJobObject
    _QUERY_INFORMATION_JOB_OBJECT.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    )
    _QUERY_INFORMATION_JOB_OBJECT.restype = wintypes.BOOL
    _JOB_OBJECT_BASIC_PROCESS_ID_LIST = 3


@dataclass(frozen=True, slots=True)
class DeclaredService:
    """Exact local process and health contract; shell command strings are absent."""

    service_id: str
    command_kind: Literal["python_script"]
    argv: tuple[str, ...]
    cwd: Path
    port: int
    readiness_path: str
    executable_digest: str
    executable_root: Path
    script_digest: str
    readiness_timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        if not isinstance(self.service_id, str) or not self.service_id.strip():
            raise ValueError("service_id must be a non-empty string")
        if (
            not self.argv
            or any(not isinstance(argument, str) or not argument for argument in self.argv)
        ):
            raise ValueError("argv must contain one or more non-empty arguments")
        if self.command_kind != "python_script":
            raise ValueError("declared service command kind is not supported")
        _validate_python_script_argv(self.argv)
        if not isinstance(self.cwd, Path):
            raise TypeError("cwd must be a pathlib.Path")
        if isinstance(self.port, bool) or not isinstance(self.port, int) or not 1 <= self.port <= 65535:
            raise ValueError("port must be an integer between 1 and 65535")
        if (
            not isinstance(self.readiness_path, str)
            or not self.readiness_path.startswith("/")
            or "?" in self.readiness_path
            or "#" in self.readiness_path
        ):
            raise ValueError("readiness_path must be an exact loopback HTTP path")
        if (
            isinstance(self.readiness_timeout_seconds, bool)
            or not isinstance(self.readiness_timeout_seconds, (int, float))
            or not 0 < self.readiness_timeout_seconds <= 120
        ):
            raise ValueError("readiness_timeout_seconds must be between zero and 120")
        if _SHA256.fullmatch(self.executable_digest) is None:
            raise ValueError("executable_digest must be lowercase SHA-256 hexadecimal")
        if not isinstance(self.executable_root, Path):
            raise TypeError("executable_root must be a pathlib.Path")
        if _SHA256.fullmatch(self.script_digest) is None:
            raise ValueError("script_digest must be lowercase SHA-256 hexadecimal")

    @property
    def readiness_endpoint(self) -> str:
        return f"http://127.0.0.1:{self.port}{self.readiness_path}"


@dataclass(slots=True)
class _ManagedService:
    service: DeclaredService
    port_lease: ResourceLease
    process_lease: ResourceLease
    process: subprocess.Popen[bytes]
    windows_job: object | None


class ServiceSupervisor:
    """Starts and stops only service process trees proven to belong to a lease."""

    def __init__(
        self,
        *,
        admitted_worktree: Path,
        admitted_fixture_root: Path | None = None,
        run_id: str,
    ) -> None:
        self._admitted_roots = tuple(
            self._existing_directory(path, field_name="admitted root")
            for path in (admitted_worktree, admitted_fixture_root)
            if path is not None
        )
        if not self._admitted_roots:
            raise ValueError("at least one admitted cwd root is required")
        if not isinstance(run_id, str) or not run_id.strip():
            raise ValueError("run_id must be a non-empty string")
        self._run_id = run_id
        self._managed: dict[str, _ManagedService] = {}
        self._known_leases: dict[str, ResourceLease] = {}
        self._known_service_ids: dict[str, str] = {}

    @staticmethod
    def _existing_directory(path: Path, *, field_name: str) -> Path:
        if not isinstance(path, Path):
            raise TypeError(f"{field_name} must be a pathlib.Path")
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise PolicyError(f"{field_name} must resolve before service spawn") from exc
        if not resolved.is_dir():
            raise PolicyError(f"{field_name} must be a directory")
        return resolved

    def _admit_cwd(self, cwd: Path) -> Path:
        resolved = self._existing_directory(cwd, field_name="cwd")
        if not any(resolved == root or root in resolved.parents for root in self._admitted_roots):
            raise PolicyError("cwd is outside admitted worktree and fixture roots")
        return resolved

    def _admit_lease(self, service: DeclaredService, lease: ResourceLease) -> None:
        if lease.run_id != self._run_id:
            raise LeaseError("lease run_id does not match supervisor run")
        if lease.is_expired():
            raise LeaseError("lease has expired")
        if lease.resource_kind != "port" or lease.resource_ref != str(service.port):
            raise LeaseError("service requires an exact port lease")

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1_048_576), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _is_admitted_path(self, path: Path) -> bool:
        resolved = path.resolve(strict=False)
        return any(resolved == root or root in resolved.parents for root in self._admitted_roots)

    def _admit_argv(self, service: DeclaredService, cwd: Path) -> tuple[str, ...]:
        executable = Path(service.argv[0])
        if not executable.is_absolute():
            raise PolicyError("service executable must be an absolute digest-bound path")
        try:
            executable = executable.resolve(strict=True)
        except OSError as exc:
            raise PolicyError("service executable must resolve before process spawn") from exc
        if not executable.is_file():
            raise PolicyError("service executable must be a file")
        _validate_python_script_argv((str(executable), *service.argv[1:]))
        tool_root = self._existing_directory(
            service.executable_root,
            field_name="admitted tool root",
        )
        if executable != tool_root and tool_root not in executable.parents:
            raise PolicyError("service executable is outside declared admitted tool root")
        if self._sha256_file(executable) != service.executable_digest:
            raise PolicyError("service executable digest does not match declared authority")
        script = Path(service.argv[1])
        if not script.is_absolute():
            script = cwd / script
        try:
            script = script.resolve(strict=True)
        except OSError as exc:
            raise PolicyError("service script must resolve before process spawn") from exc
        if not script.is_file() or not self._is_admitted_path(script):
            raise PolicyError("service script is outside admitted worktree and fixture roots")
        if self._sha256_file(script) != service.script_digest:
            raise PolicyError("service script digest does not match declared authority")
        for argument in service.argv[2:]:
            candidate = Path(argument)
            if candidate.is_absolute():
                if not self._is_admitted_path(candidate):
                    raise PolicyError("service argv path is outside admitted worktree and fixture roots")
            elif "/" in argument or "\\" in argument:
                if not self._is_admitted_path(cwd / candidate):
                    raise PolicyError("service argv path is outside admitted worktree and fixture roots")
            if "://" in argument:
                raise PolicyError("service argv may not contain an undeclared network endpoint")
        return (str(executable), str(script), *service.argv[2:])

    @staticmethod
    def _port_is_available(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            if os.name == "nt":
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                return False
        return True

    @staticmethod
    def _listener_owned_by_process(
        *,
        port: int,
        process_id: int,
        windows_job: object | None,
    ) -> bool:
        """Prove loopback listener belongs to root process or its owned tree."""

        if os.name == "nt":
            size = wintypes.DWORD(0)
            result = _GET_EXTENDED_TCP_TABLE(
                None,
                ctypes.byref(size),
                False,
                socket.AF_INET,
                _TCP_TABLE_OWNER_PID_LISTENER,
                0,
            )
            if result not in (0, _ERROR_INSUFFICIENT_BUFFER) or not size.value:
                return False
            table = ctypes.create_string_buffer(size.value)
            if _GET_EXTENDED_TCP_TABLE(
                table,
                ctypes.byref(size),
                False,
                socket.AF_INET,
                _TCP_TABLE_OWNER_PID_LISTENER,
                0,
            ) != 0:
                return False
            count = ctypes.cast(table, ctypes.POINTER(wintypes.DWORD)).contents.value
            first_row = ctypes.addressof(table) + ctypes.sizeof(wintypes.DWORD)
            row_size = ctypes.sizeof(_MibTcpRowOwnerPid)
            listener_pids: set[int] = set()
            for index in range(count):
                row = _MibTcpRowOwnerPid.from_address(first_row + index * row_size)
                if (
                    row.state == _MIB_TCP_STATE_LISTEN
                    and socket.ntohl(row.local_address) == 0x7F000001
                    and socket.ntohs(row.local_port & 0xFFFF) == port
                ):
                    listener_pids.add(int(row.owning_pid))
            if process_id in listener_pids:
                return True
            handle = getattr(windows_job, "_handle", None)
            if handle is None:
                return False
            pointer_size = ctypes.sizeof(ctypes.c_size_t)
            buffer = ctypes.create_string_buffer(8 + pointer_size * 256)
            returned = wintypes.DWORD(0)
            if not _QUERY_INFORMATION_JOB_OBJECT(
                handle,
                _JOB_OBJECT_BASIC_PROCESS_ID_LIST,
                buffer,
                ctypes.sizeof(buffer),
                ctypes.byref(returned),
            ):
                return False
            count = wintypes.DWORD.from_buffer(buffer, 4).value
            job_pids = {
                ctypes.c_size_t.from_buffer(buffer, 8 + pointer_size * index).value
                for index in range(count)
            }
            return bool(listener_pids & job_pids)

        inodes: set[str] = set()
        loopback_addresses = {
            Path("/proc/net/tcp"): {"0100007F"},
            Path("/proc/net/tcp6"): {"0000000000000000FFFF00000100007F"},
        }
        for table_path, allowed_addresses in loopback_addresses.items():
            try:
                rows = table_path.read_text(encoding="ascii").splitlines()[1:]
            except OSError:
                continue
            for row in rows:
                fields = row.split()
                if len(fields) < 10 or fields[3] != "0A":
                    continue
                local_address, local_port = fields[1].rsplit(":", 1)
                if (
                    local_address in allowed_addresses
                    and int(local_port, 16) == port
                ):
                    inodes.add(fields[9])
        if not inodes:
            return False
        try:
            process_group = os.getpgid(process_id)
        except ProcessLookupError:
            return False
        try:
            for entry in Path("/proc").iterdir():
                if not entry.name.isdigit():
                    continue
                listener_pid = int(entry.name)
                try:
                    if os.getpgid(listener_pid) != process_group:
                        continue
                    for descriptor in (entry / "fd").iterdir():
                        target = os.readlink(descriptor)
                        if target.startswith("socket:[") and target[8:-1] in inodes:
                            return True
                except OSError:
                    continue
        except OSError:
            return False
        return False

    @staticmethod
    def _child_environment() -> dict[str, str]:
        """Minimal process environment plus Windows socket-provider bootstrap."""

        path = os.environ.get("PATH")
        if not isinstance(path, str) or not path:
            raise PolicyError("deny-by-default child environment requires PATH")
        environment = {"PATH": path}
        if os.name == "nt":
            system_root = os.environ.get("SYSTEMROOT")
            if not isinstance(system_root, str) or not system_root:
                raise PolicyError("Windows service child requires SYSTEMROOT")
            environment["SYSTEMROOT"] = system_root
        return environment

    @staticmethod
    def _same_lease(left: ResourceLease, right: ResourceLease) -> bool:
        return left.model_dump(mode="python") == right.model_dump(mode="python")

    @staticmethod
    def _terminate_tree(managed: _ManagedService) -> bool:
        process = managed.process
        if os.name != "nt" and process.poll() is not None:
            return False
        ProcessRunner._terminate(process, managed.windows_job)
        if process.poll() is None:
            try:
                process.wait(timeout=0.75)
            except subprocess.TimeoutExpired:
                ProcessRunner._kill(process, managed.windows_job)
                process.wait(timeout=0.75)
        if managed.windows_job is not None:
            managed.windows_job.close()  # type: ignore[attr-defined]
        return True

    @staticmethod
    def _readiness(service: DeclaredService, *, challenge: str) -> tuple[int | None, str | None]:
        connection = http.client.HTTPConnection(
            "127.0.0.1",
            service.port,
            timeout=min(0.2, service.readiness_timeout_seconds),
        )
        try:
            connection.request(
                "GET",
                service.readiness_path,
                headers={
                    "Host": "localhost",
                    "X-Graph-Readiness-Challenge": challenge,
                },
            )
            response = connection.getresponse()
            response.read()
            return response.status, response.getheader("X-Graph-Readiness-Response")
        except (OSError, http.client.HTTPException):
            return None, None
        finally:
            connection.close()

    def _failed_start(
        self,
        service: DeclaredService,
        lease: ResourceLease,
        *,
        status: Literal["readiness_failed", "port_collision", "spawn_failed"],
        process_id: int | None = None,
        process_tree_terminated: bool = False,
        health: HealthReceipt | None = None,
        process_lease: ResourceLease | None = None,
    ) -> ServiceReceipt:
        return ServiceReceipt(
            service_id=service.service_id,
            run_id=lease.run_id,
            lease_id=lease.lease_id,
            port_lease_id=lease.lease_id,
            process_lease=process_lease,
            port=service.port,
            process_id=process_id,
            status=status,
            process_tree_terminated=process_tree_terminated,
            started_at=_rfc3339_now(),
            health=health,
        )

    def start(self, service: DeclaredService, *, lease: ResourceLease) -> ServiceReceipt:
        """Start one declared service; failed readiness always tears down owned tree."""

        self._admit_lease(service, lease)
        if lease.lease_id in self._managed:
            raise LeaseError("exact lease already owns a running service")
        cwd = self._admit_cwd(service.cwd)
        argv = self._admit_argv(service, cwd)
        if not self._port_is_available(service.port):
            return self._failed_start(service, lease, status="port_collision")
        windows_job = _WindowsJob() if os.name == "nt" else None
        try:
            process_options: dict[str, object] = {}
            if os.name == "nt":
                process_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                process_options["start_new_session"] = True
            process = subprocess.Popen(
                argv,
                cwd=cwd,
                env=self._child_environment(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
                **process_options,
            )
            if windows_job is not None:
                windows_job.assign(process)
        except (OSError, PolicyError):
            if windows_job is not None:
                windows_job.close()
            return self._failed_start(
                service,
                lease,
                status="spawn_failed",
            )
        process_lease = ResourceLease.issue(
            run_id=lease.run_id,
            resource=f"process:{process.pid}",
        )

        managed = _ManagedService(
            service=service,
            port_lease=lease,
            process_lease=process_lease,
            process=process,
            windows_job=windows_job,
        )
        last_health = HealthReceipt(
            service_id=service.service_id,
            lease_id=lease.lease_id,
            endpoint=service.readiness_endpoint,
            status_code=None,
            checked_at=_rfc3339_now(),
        )
        deadline = time.monotonic() + service.readiness_timeout_seconds
        while time.monotonic() < deadline:
            challenge = secrets.token_urlsafe(32)
            status_code, response_challenge = self._readiness(service, challenge=challenge)
            last_health = HealthReceipt(
                service_id=service.service_id,
                lease_id=lease.lease_id,
                endpoint=service.readiness_endpoint,
                status_code=status_code,
                checked_at=_rfc3339_now(),
            )
            if (
                process.poll() is None
                and status_code is not None
                and 200 <= status_code < 300
                and response_challenge == challenge
                and self._listener_owned_by_process(
                    port=service.port,
                    process_id=process.pid,
                    windows_job=windows_job,
                )
            ):
                self._managed[lease.lease_id] = managed
                self._known_leases[lease.lease_id] = lease
                self._known_service_ids[lease.lease_id] = service.service_id
                return ServiceReceipt(
                    service_id=service.service_id,
                    run_id=lease.run_id,
                    lease_id=lease.lease_id,
                    port_lease_id=lease.lease_id,
                    process_lease=process_lease,
                    port=service.port,
                    process_id=process.pid,
                    status="ready",
                    process_tree_terminated=False,
                    started_at=_rfc3339_now(),
                    health=last_health,
                )
            if process.poll() is not None:
                break
            time.sleep(0.025)

        terminated = self._terminate_tree(managed)
        if not terminated:
            # Preserve exact ownership evidence for an explicit later recovery;
            # do not claim a teardown when tree containment is unproven.
            self._managed[lease.lease_id] = managed
            self._known_leases[lease.lease_id] = lease
            self._known_service_ids[lease.lease_id] = service.service_id
        return self._failed_start(
            service,
            lease,
            status="readiness_failed",
            process_id=process.pid,
            process_tree_terminated=terminated,
            health=last_health,
            process_lease=process_lease,
        )

    def teardown(self, lease: ResourceLease, ownership_token: str) -> TeardownReceipt:
        """Terminate only running process tree mapped to matching current lease and token."""

        if not lease.ownership_matches(ownership_token):
            raise LeaseError("lease ownership token does not match durable ownership proof")
        known = self._known_leases.get(lease.lease_id)
        if known is None or not self._same_lease(known, lease):
            raise LeaseError("exact lease does not own a managed service")
        managed = self._managed.get(lease.lease_id)
        if managed is None:
            return TeardownReceipt(
                service_id=self._known_service_ids[known.lease_id],
                run_id=known.run_id,
                lease_id=known.lease_id,
                status="not_running",
                process_tree_terminated=False,
                completed_at=_rfc3339_now(),
            )
        try:
            process_token = managed.process_lease.issued_ownership_token
        except ValueError as exc:
            raise LeaseError("process lease ownership proof is unavailable") from exc
        if not managed.process_lease.ownership_matches(process_token):
            raise LeaseError("process lease ownership proof does not match")
        terminated = self._terminate_tree(managed)
        if not terminated:
            return TeardownReceipt(
                service_id=managed.service.service_id,
                run_id=lease.run_id,
                lease_id=lease.lease_id,
                status="ownership_unproven",
                process_tree_terminated=False,
                completed_at=_rfc3339_now(),
            )
        self._managed.pop(lease.lease_id, None)
        return TeardownReceipt(
            service_id=managed.service.service_id,
            run_id=lease.run_id,
            lease_id=lease.lease_id,
            status="terminated",
            process_tree_terminated=terminated,
            completed_at=_rfc3339_now(),
        )

    def readiness(self, receipt: ServiceReceipt) -> HealthReceipt:
        """Recheck only a currently owned process using a fresh loopback challenge."""

        managed = self._managed.get(receipt.port_lease_id)
        if (
            managed is None
            or managed.service.service_id != receipt.service_id
            or managed.port_lease.run_id != receipt.run_id
            or managed.port_lease.lease_id != receipt.lease_id
            or managed.process.pid != receipt.process_id
            or managed.port_lease.lease_id != receipt.port_lease_id
            or managed.service.port != receipt.port
            or receipt.status != "ready"
            or receipt.process_tree_terminated
            or receipt.process_lease is None
            or receipt.process_lease.model_dump(mode="json")
            != managed.process_lease.model_dump(mode="json")
        ):
            raise LeaseError("exact owned service receipt is required for readiness")
        challenge = secrets.token_urlsafe(32)
        status_code, response_challenge = self._readiness(managed.service, challenge=challenge)
        return HealthReceipt(
            service_id=managed.service.service_id,
            lease_id=managed.port_lease.lease_id,
            endpoint=managed.service.readiness_endpoint,
            status_code=(
                status_code
                if (
                    managed.process.poll() is None
                    and status_code is not None
                    and 200 <= status_code < 300
                    and response_challenge == challenge
                    and self._listener_owned_by_process(
                        port=managed.service.port,
                        process_id=managed.process.pid,
                        windows_job=managed.windows_job,
                    )
                )
                else None
            ),
            checked_at=_rfc3339_now(),
        )
