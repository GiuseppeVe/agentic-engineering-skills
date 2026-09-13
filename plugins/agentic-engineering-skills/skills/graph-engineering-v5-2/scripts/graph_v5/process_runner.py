"""Deny-by-default process execution for admitted real-system adapters."""

from __future__ import annotations

import base64
import ctypes
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import queue
import re
import signal
import subprocess
import threading
import time
from typing import Callable, Mapping

from .policy import (
    EvidencePolicy,
    EvidenceRedactionPolicy,
    PolicyError,
    RedactingEvidenceWriter,
    RedactionReceipt,
)


_ENVIRONMENT_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}")
_DEFAULT_REDACTION_POLICY_DIGEST = hashlib.sha256(
    b"graph-v5.default-evidence-redaction.v1"
).hexdigest()


if os.name == "nt":
    from ctypes import wintypes

    _KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _CREATE_JOB_OBJECT = _KERNEL32.CreateJobObjectW
    _CREATE_JOB_OBJECT.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
    _CREATE_JOB_OBJECT.restype = wintypes.HANDLE
    _SET_JOB_INFORMATION = _KERNEL32.SetInformationJobObject
    _SET_JOB_INFORMATION.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    )
    _SET_JOB_INFORMATION.restype = wintypes.BOOL
    _ASSIGN_PROCESS_TO_JOB = _KERNEL32.AssignProcessToJobObject
    _ASSIGN_PROCESS_TO_JOB.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    _ASSIGN_PROCESS_TO_JOB.restype = wintypes.BOOL
    _TERMINATE_JOB = _KERNEL32.TerminateJobObject
    _TERMINATE_JOB.argtypes = (wintypes.HANDLE, wintypes.UINT)
    _TERMINATE_JOB.restype = wintypes.BOOL
    _CLOSE_HANDLE = _KERNEL32.CloseHandle
    _CLOSE_HANDLE.argtypes = (wintypes.HANDLE,)
    _CLOSE_HANDLE.restype = wintypes.BOOL

    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000

    class _IoCounters(ctypes.Structure):
        _fields_ = (
            ("read_operation_count", ctypes.c_uint64),
            ("write_operation_count", ctypes.c_uint64),
            ("other_operation_count", ctypes.c_uint64),
            ("read_transfer_count", ctypes.c_uint64),
            ("write_transfer_count", ctypes.c_uint64),
            ("other_transfer_count", ctypes.c_uint64),
        )

    class _BasicLimitInformation(ctypes.Structure):
        _fields_ = (
            ("per_process_user_time_limit", ctypes.c_int64),
            ("per_job_user_time_limit", ctypes.c_int64),
            ("limit_flags", wintypes.DWORD),
            ("minimum_working_set_size", ctypes.c_size_t),
            ("maximum_working_set_size", ctypes.c_size_t),
            ("active_process_limit", wintypes.DWORD),
            ("affinity", ctypes.c_size_t),
            ("priority_class", wintypes.DWORD),
            ("scheduling_class", wintypes.DWORD),
        )

    class _ExtendedLimitInformation(ctypes.Structure):
        _fields_ = (
            ("basic_limit_information", _BasicLimitInformation),
            ("io_info", _IoCounters),
            ("process_memory_limit", ctypes.c_size_t),
            ("job_memory_limit", ctypes.c_size_t),
            ("peak_process_memory_used", ctypes.c_size_t),
            ("peak_job_memory_used", ctypes.c_size_t),
        )

    class _WindowsJob:
        """Own one process tree and terminate it without external commands."""

        def __init__(self) -> None:
            handle = _CREATE_JOB_OBJECT(None, None)
            if not handle:
                raise PolicyError("Windows Job Object creation failed before process spawn")
            self._handle: int | None = handle
            limits = _ExtendedLimitInformation()
            limits.basic_limit_information.limit_flags = (
                _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            )
            if not _SET_JOB_INFORMATION(
                handle,
                _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                ctypes.byref(limits),
                ctypes.sizeof(limits),
            ):
                error = ctypes.get_last_error()
                self.close()
                raise PolicyError(
                    "Windows Job Object configuration failed before process spawn"
                ) from OSError(error, "SetInformationJobObject failed")

        def assign(self, process: subprocess.Popen[bytes]) -> None:
            assert self._handle is not None
            process_handle = wintypes.HANDLE(int(process._handle))  # type: ignore[attr-defined]
            if not _ASSIGN_PROCESS_TO_JOB(self._handle, process_handle):
                error = ctypes.get_last_error()
                process.kill()
                process.wait()
                self.close()
                raise PolicyError(
                    "process could not enter its owned Windows Job Object"
                ) from OSError(error, "AssignProcessToJobObject failed")

        def terminate(self) -> bool:
            return self._handle is not None and bool(_TERMINATE_JOB(self._handle, 1))

        def close(self) -> None:
            if self._handle is not None:
                _CLOSE_HANDLE(self._handle)
                self._handle = None
else:
    _WindowsJob = None  # type: ignore[misc, assignment]


def _environment_name(value: str, *, field_name: str) -> str:
    if not isinstance(value, str) or _ENVIRONMENT_NAME.fullmatch(value) is None:
        raise ValueError(f"{field_name} must contain declared environment variable names")
    return value


def _distinct_names(values: tuple[str, ...], *, field_name: str) -> tuple[str, ...]:
    normalized = tuple(_environment_name(value, field_name=field_name) for value in values)
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{field_name} may not repeat environment variable names")
    return normalized


@dataclass(frozen=True, slots=True)
class EnvironmentPolicy:
    """Named ambient and secret values one admitted process may receive."""

    public_variables: tuple[str, ...] = ()
    secret_references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "public_variables",
            _distinct_names(self.public_variables, field_name="public_variables"),
        )
        object.__setattr__(
            self,
            "secret_references",
            _distinct_names(self.secret_references, field_name="secret_references"),
        )
        if set(self.public_variables) & set(self.secret_references):
            raise ValueError("environment variable may not be both public and secret")

    @classmethod
    def empty(cls) -> "EnvironmentPolicy":
        return cls()

    def child_environment(
        self,
        command: "ProcessCommand",
        *,
        parent_environment: Mapping[str, str],
        secret_resolver: Callable[[str], str] | None,
    ) -> tuple[dict[str, str], tuple[bytes, ...]]:
        path = parent_environment.get("PATH")
        if not isinstance(path, str) or not path:
            raise PolicyError("deny-by-default child environment requires PATH")

        public = set(command.public_environment)
        secrets = set(command.secret_references)
        if not public <= set(self.public_variables):
            raise PolicyError("command requested undeclared public environment")
        if not secrets <= set(self.secret_references):
            raise PolicyError("command requested undeclared secret reference")
        if secrets and secret_resolver is None:
            raise PolicyError("command secret references require a resolver at spawn")

        child = {"PATH": path}
        for name in command.public_environment:
            value = parent_environment.get(name)
            if not isinstance(value, str):
                raise PolicyError(f"declared public environment variable is unavailable: {name}")
            child[name] = value

        resolved_secrets: list[bytes] = []
        for name in command.secret_references:
            assert secret_resolver is not None  # Proven above; keeps resolver ephemeral.
            value = secret_resolver(name)
            if not isinstance(value, str) or not value:
                raise PolicyError(f"secret resolver returned no value for declared reference: {name}")
            child[name] = value
            resolved_secrets.append(value.encode("utf-8"))
        return child, tuple(resolved_secrets)


@dataclass(frozen=True, slots=True)
class ProcessCommand:
    """Validated argv and cwd; shell commands and implicit environment are absent."""

    argv: tuple[str, ...]
    cwd: Path
    public_environment: tuple[str, ...] = ()
    secret_references: tuple[str, ...] = ()
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not self.argv or any(not isinstance(value, str) or not value for value in self.argv):
            raise ValueError("argv must contain one or more non-empty arguments")
        object.__setattr__(
            self,
            "public_environment",
            _distinct_names(self.public_environment, field_name="public_environment"),
        )
        object.__setattr__(
            self,
            "secret_references",
            _distinct_names(self.secret_references, field_name="secret_references"),
        )
        if set(self.public_environment) & set(self.secret_references):
            raise ValueError("environment variable may not be both public and secret")
        if not isinstance(self.cwd, Path):
            raise TypeError("cwd must be a pathlib.Path")
        if not isinstance(self.timeout_seconds, (int, float)) or self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


@dataclass(frozen=True, slots=True)
class ProcessReceipt:
    """Secret-free result metadata; argv and values are intentionally omitted."""

    returncode: int
    redaction_policy_digest: str
    stdout_redaction: RedactionReceipt
    stderr_redaction: RedactionReceipt
    declared_public_environment: tuple[str, ...]
    declared_secret_references: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str
    receipt: ProcessReceipt


class ProcessRunner:
    """Runs only exact argv inside admitted roots with a sealed child environment."""

    def __init__(
        self,
        *,
        admitted_worktree: Path,
        admitted_fixture_root: Path | None = None,
        default_evidence_policy: EvidenceRedactionPolicy | None = None,
    ) -> None:
        self._admitted_roots = tuple(
            self._existing_directory(path, field_name="admitted root")
            for path in (admitted_worktree, admitted_fixture_root)
            if path is not None
        )
        if not self._admitted_roots:
            raise ValueError("at least one admitted cwd root is required")
        self._default_evidence_policy = (
            default_evidence_policy
            or EvidenceRedactionPolicy(
                redaction_policy_digest=_DEFAULT_REDACTION_POLICY_DIGEST
            )
        )

    @staticmethod
    def _existing_directory(path: Path, *, field_name: str) -> Path:
        if not isinstance(path, Path):
            raise TypeError(f"{field_name} must be a pathlib.Path")
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise PolicyError(f"{field_name} must resolve before process spawn") from exc
        if not resolved.is_dir():
            raise PolicyError(f"{field_name} must be a directory")
        return resolved

    def _admit_cwd(self, cwd: Path) -> Path:
        resolved = self._existing_directory(cwd, field_name="cwd")
        if not any(resolved == root or root in resolved.parents for root in self._admitted_roots):
            raise PolicyError("cwd is outside admitted worktree and fixture roots")
        return resolved

    def _redaction_policy(
        self,
        evidence_policy: EvidenceRedactionPolicy | EvidencePolicy | None,
    ) -> EvidenceRedactionPolicy:
        if evidence_policy is None:
            policy = self._default_evidence_policy
        elif isinstance(evidence_policy, EvidenceRedactionPolicy):
            policy = evidence_policy
        elif isinstance(evidence_policy, EvidencePolicy):
            policy = EvidenceRedactionPolicy(
                redaction_policy_digest=evidence_policy.redaction_policy_digest
            )
        else:
            raise TypeError("evidence_policy must be an admitted evidence policy")
        return policy

    @staticmethod
    def _secret_representations(secret: bytes) -> tuple[bytes, ...]:
        standard_base64 = base64.b64encode(secret)
        urlsafe_base64 = base64.urlsafe_b64encode(secret)
        return (
            secret,
            standard_base64,
            standard_base64.rstrip(b"="),
            urlsafe_base64,
            urlsafe_base64.rstrip(b"="),
            secret.hex().encode("ascii"),
            secret.hex().upper().encode("ascii"),
        )

    @staticmethod
    def _terminate(
        process: subprocess.Popen[bytes], windows_job: object | None = None
    ) -> None:
        """Stop only exact process tree created for this command."""

        if os.name == "nt":
            if windows_job is not None and windows_job.terminate():  # type: ignore[attr-defined]
                return
            if process.poll() is None:
                process.terminate()
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return

    @staticmethod
    def _kill(
        process: subprocess.Popen[bytes], windows_job: object | None = None
    ) -> None:
        if os.name == "nt":
            if windows_job is not None and windows_job.terminate():  # type: ignore[attr-defined]
                return
            if process.poll() is None:
                process.kill()
            return
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return

    @classmethod
    def _capture_output(
        cls,
        process: subprocess.Popen[bytes],
        *,
        max_output_bytes: int,
        timeout_seconds: float,
        windows_job: object | None = None,
    ) -> tuple[bytes, bytes]:
        """Bound both pipes while draining them so a noisy child cannot exhaust memory."""

        assert process.stdout is not None
        assert process.stderr is not None
        messages: queue.Queue[tuple[str, bytes | None]] = queue.Queue(maxsize=2)

        def drain(stream_name: str, stream: object) -> None:
            readable = stream
            try:
                while True:
                    chunk = readable.read1(8_192)  # type: ignore[union-attr]
                    if not chunk:
                        return
                    messages.put((stream_name, chunk))
            finally:
                try:
                    readable.close()  # type: ignore[union-attr]
                finally:
                    messages.put((stream_name, None))

        readers = tuple(
            threading.Thread(target=drain, args=(name, stream), daemon=True)
            for name, stream in (("stdout", process.stdout), ("stderr", process.stderr))
        )
        for reader in readers:
            reader.start()

        buffers = {"stdout": bytearray(), "stderr": bytearray()}
        completed_streams: set[str] = set()
        total = 0
        output_capped = False
        timed_out = False
        stopped_at: float | None = None
        deadline = time.monotonic() + timeout_seconds

        while len(completed_streams) != 2:
            now = time.monotonic()
            if not timed_out and now >= deadline:
                timed_out = True
                stopped_at = now
                cls._terminate(process, windows_job)
            if (output_capped or timed_out) and stopped_at is not None:
                if process.poll() is None and now - stopped_at >= 1.0:
                    cls._kill(process, windows_job)
            try:
                stream_name, chunk = messages.get(timeout=0.05)
            except queue.Empty:
                continue
            if chunk is None:
                completed_streams.add(stream_name)
                continue
            if output_capped or timed_out:
                continue
            if total + len(chunk) > max_output_bytes:
                output_capped = True
                stopped_at = time.monotonic()
                cls._terminate(process, windows_job)
                continue
            buffers[stream_name].extend(chunk)
            total += len(chunk)

        if not timed_out:
            try:
                process.wait(timeout=max(0.0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                timed_out = True
                cls._terminate(process, windows_job)
        if timed_out:
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                cls._kill(process, windows_job)
                process.wait()
        for reader in readers:
            reader.join(timeout=1.0)
        if output_capped:
            raise PolicyError("output cap exceeded before evidence receipt")
        if timed_out:
            raise PolicyError("process timed out before a receipt could be issued")
        return bytes(buffers["stdout"]), bytes(buffers["stderr"])

    def run(
        self,
        command: ProcessCommand,
        *,
        env_policy: EnvironmentPolicy,
        parent_environment: Mapping[str, str] | None = None,
        secret_resolver: Callable[[str], str] | None = None,
        evidence_policy: EvidenceRedactionPolicy | EvidencePolicy | None = None,
    ) -> ProcessResult:
        cwd = self._admit_cwd(command.cwd)
        parent = parent_environment if parent_environment is not None else os.environ
        child_environment, resolved_secrets = env_policy.child_environment(
            command,
            parent_environment=parent,
            secret_resolver=secret_resolver,
        )
        argv_bytes = b"".join(argument.encode("utf-8") for argument in command.argv)
        compact_argv_bytes = b"".join(argv_bytes.split())
        if any(
            representation in argv_bytes or representation in compact_argv_bytes
            for secret in resolved_secrets
            for representation in self._secret_representations(secret)
        ):
            raise PolicyError("resolved secret may not enter process argv")

        redaction_policy = self._redaction_policy(evidence_policy)
        windows_job = _WindowsJob() if os.name == "nt" else None
        try:
            process_options: dict[str, object] = {}
            if os.name == "nt":
                process_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                process_options["start_new_session"] = True
            process = subprocess.Popen(
                command.argv,
                cwd=cwd,
                env=child_environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                **process_options,
            )
            if windows_job is not None:
                windows_job.assign(process)
        except OSError as exc:
            if windows_job is not None:
                windows_job.close()
            raise PolicyError("process spawn failed before a receipt could be issued") from exc
        try:
            stdout_bytes, stderr_bytes = self._capture_output(
                process,
                max_output_bytes=redaction_policy.max_output_bytes,
                timeout_seconds=command.timeout_seconds,
                windows_job=windows_job,
            )
        finally:
            if windows_job is not None:
                windows_job.close()
        writer = RedactingEvidenceWriter(redaction_policy)
        stdout = writer.write(stdout_bytes, secret_values=resolved_secrets)
        stderr = writer.write(stderr_bytes, secret_values=resolved_secrets)
        receipt = ProcessReceipt(
            returncode=process.returncode,
            redaction_policy_digest=stdout.receipt.policy_digest,
            stdout_redaction=stdout.receipt,
            stderr_redaction=stderr.receipt,
            declared_public_environment=command.public_environment,
            declared_secret_references=command.secret_references,
        )
        return ProcessResult(
            returncode=process.returncode,
            stdout=stdout.payload.decode("utf-8", errors="backslashreplace"),
            stderr=stderr.payload.decode("utf-8", errors="backslashreplace"),
            receipt=receipt,
        )
