from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _git(repository: Path, *args: str) -> None:
    environment = os.environ.copy()
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    for key in tuple(environment):
        if key == "GIT_CONFIG_COUNT" or key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")):
            environment.pop(key)

    command = ["git"]
    git_directory = repository / ".git"
    if git_directory.is_dir():
        hooks_path = git_directory / "fixture-empty-hooks"
        hooks_path.mkdir(exist_ok=True)
        command.extend(("-c", f"core.hooksPath={hooks_path}"))

    subprocess.run(
        [*command, *args],
        cwd=repository,
        env=environment,
        text=True,
        capture_output=True,
        check=True,
    )


def create_git_repository(repository: Path) -> Path:
    """Create a committed Git repository without shipping a static .git directory."""
    repository.mkdir(parents=True)
    _git(repository, "init", "--initial-branch=main")
    _git(repository, "config", "user.name", "Graph V5 Fixture")
    _git(repository, "config", "user.email", "graph-v5-fixture@example.invalid")
    (repository / "README.md").write_text("fixture base\n", encoding="utf-8")
    _git(repository, "add", "README.md")
    _git(repository, "commit", "--no-gpg-sign", "-m", "fixture base")
    return repository


def create_node22_repository(repository: Path) -> Path:
    """Create deterministic disposable Node 22 repository for V5 worktree tests."""
    create_git_repository(repository)
    (repository / ".nvmrc").write_text("22\n", encoding="utf-8")
    (repository / "package.json").write_text(
        '{"engines":{"node":">=22 <23"},"packageManager":"npm@10.9.0"}\n',
        encoding="utf-8",
    )
    (repository / "package-lock.json").write_text(
        '{"lockfileVersion":3}\n', encoding="utf-8"
    )
    fixture = repository / ".graph-v5-fixture"
    validator = repository / ".graph-v5-validator"
    fixture.mkdir()
    validator.mkdir()
    (fixture / ".graph-v5-disposable-fixture").write_text("fixture\n", encoding="utf-8")
    (validator / ".graph-v5-disposable-validator").write_text(
        "validator\n", encoding="utf-8"
    )
    binary = repository / "node_modules" / ".bin" / "fixture-validator.CMD"
    binary.parent.mkdir(parents=True)
    binary.write_text("@echo off\r\necho fixture-validator 1.0.0\r\n", encoding="ascii")
    _git(
        repository,
        "add",
        ".nvmrc",
        "package.json",
        "package-lock.json",
        ".graph-v5-fixture",
        ".graph-v5-validator",
        "node_modules/.bin/fixture-validator.CMD",
    )
    _git(repository, "commit", "--no-gpg-sign", "-m", "fixture node 22")
    return repository


def git_revision(repository: Path, revision: str = "HEAD") -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", f"{revision}^{{commit}}"],
        cwd=repository,
        text=True,
        encoding="utf-8",
        errors="strict",
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()
