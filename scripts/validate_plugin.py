#!/usr/bin/env python3
"""Deterministic Codex plugin validator used by CI.

Provenance: behavior adapted from installed Codex `plugin-creator` validator
(`skills/.system/plugin-creator/scripts/validate_plugin.py`), inspected 2026-07-12.
Kept repository-local so clean GitHub runners validate same contract.
"""

import json
import re
import sys
from pathlib import Path

import yaml

SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: validate_plugin.py PLUGIN_ROOT")
    root = Path(sys.argv[1]).resolve()
    manifest_path = root / ".codex-plugin" / "plugin.json"
    if not manifest_path.is_file():
        fail("missing .codex-plugin/plugin.json")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"invalid plugin manifest: {error}")
    for field in ("name", "version", "description", "skills", "interface"):
        if field not in manifest:
            fail(f"plugin.json missing {field}")
    if not isinstance(manifest["name"], str) or not manifest["name"].strip():
        fail("plugin.json name must be non-empty")
    if not isinstance(manifest["version"], str) or not SEMVER.fullmatch(manifest["version"]):
        fail("plugin.json version must be strict semver")
    if manifest["skills"].replace("\\", "/").rstrip("/") != "./skills":
        fail("plugin.json skills must resolve to ./skills/")
    skills_root = root / "skills"
    if not skills_root.is_dir():
        fail("missing skills directory")
    count = 0
    for skill_root in sorted(path for path in skills_root.iterdir() if path.is_dir()):
        skill_file = skill_root / "SKILL.md"
        if not skill_file.is_file():
            fail(f"skill {skill_root.name} missing SKILL.md")
        text = skill_file.read_text(encoding="utf-8").replace("\r\n", "\n")
        match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
        if not match:
            fail(f"skill {skill_root.name} has invalid frontmatter boundaries")
        try:
            frontmatter = yaml.safe_load(match.group(1))
        except yaml.YAMLError as error:
            fail(f"skill {skill_root.name} has invalid YAML: {error}")
        if not isinstance(frontmatter, dict):
            fail(f"skill {skill_root.name} frontmatter must be object")
        if frontmatter.get("name") != skill_root.name:
            fail(f"skill {skill_root.name} frontmatter name mismatch")
        if not isinstance(frontmatter.get("description"), str) or not frontmatter["description"].strip():
            fail(f"skill {skill_root.name} description must be non-empty")
        count += 1
    print(f"Valid Codex plugin: {manifest['name']} {manifest['version']} ({count} skills)")


if __name__ == "__main__":
    main()
