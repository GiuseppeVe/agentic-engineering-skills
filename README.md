# Agentic Engineering Skills

Audited 19-skill engineering workflow pack designed for Codex and Claude Code. Host-validation evidence is recorded in `docs/release-report.md` during release validation.

> **Windows UNC paths:** running bare `npm` from `\\\\wsl.localhost\\...` is unsupported. `cmd.exe` can silently change working directory and produce a false-green zero-test run. Use a WSL shell, clone to a native Windows path, or run `cmd /d /c "pushd \\\\wsl.localhost\\... && npm test"` so `pushd` maps the share to a drive. Repository test runner also rejects zero-test and missing-summary runs.

## Problem

Agent work often jumps from a vague request to code, skipping design, test-first execution, integrated review, or cleanup. This pack supplies focused skills spanning that whole path while keeping every distributed file traceable to a pinned source.

## Philosophy

Use the smallest skill set needed for current work. Skills guide judgment; they do not replace project instructions or make every workflow stage mandatory for every task. Vendor files stay byte-exact, adaptations remain auditable, and original files use this repository's MIT license.

## Workflow

Default lifecycle: **Understand -> Design -> Plan -> Implement -> Verify -> Review -> Clean**. See [workflow guide](docs/workflow.md) for phase-to-skill mapping.

## Install

Install complete bundle. This is supported path.

Codex:

```text
codex plugin marketplace add GiuseppeVe/agentic-engineering-skills
codex plugin add agentic-engineering-skills@agentic-engineering-skills
```

Claude Code:

```text
claude plugin marketplace add GiuseppeVe/agentic-engineering-skills
claude plugin install agentic-engineering-skills@agentic-engineering-skills
```

Confirm discovery with `codex plugin list --available --json` or `claude plugin list`. Then start a fresh host session and invoke one included skill, such as `brainstorming`; plugin listing alone does not prove fresh-session invocation.

Selective copying is advanced and can remove workflow stages. See [selective installation](docs/selective-install.md).

## Customize

Fork repository and edit source files, never generated plugin cache. Full workflow: [customization guide](docs/customization.md).

## Compatibility

Bundle targets exactly two verified hosts: Codex and Claude Code. Release-specific validation evidence belongs in `docs/release-report.md`. See [compatibility](docs/compatibility.md).

## Provenance

Every skill is classified as `vendor`, `adapted`, or `original`, with hashes and pinned revisions in lock. See [provenance inventory](docs/provenance.md).

## License

Repository-original material: [MIT](LICENSE), copyright GiuseppeVe. Third-party material remains under applicable retained licenses; see [Third-Party Notices](THIRD_PARTY_NOTICES.md). Forking, editing, removal, and redistribution remain subject to those licenses.
