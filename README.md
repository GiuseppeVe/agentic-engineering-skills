# Agentic Engineering Skills

Audited 19-skill engineering workflow pack for Codex and Claude Code.

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
codex plugin install agentic-engineering-skills
```

Claude Code:

```text
/plugin marketplace add agentic-engineering-skills
/plugin install agentic-engineering-skills@agentic-engineering-skills
```

Selective copying is advanced and can remove workflow stages. See [selective installation](docs/selective-install.md).

## Customize

Fork repository and edit source files, never generated plugin cache. Full workflow: [customization guide](docs/customization.md).

## Compatibility

Bundle is verified for exactly two hosts: Codex and Claude Code. See [compatibility](docs/compatibility.md).

## Provenance

Every skill is classified as `vendor`, `adapted`, or `original`, with hashes and pinned revisions in lock. See [provenance inventory](docs/provenance.md).

## License

Repository-original material: [MIT](LICENSE), copyright GiuseppeVe. Third-party material remains under applicable retained licenses; see [Third-Party Notices](THIRD_PARTY_NOTICES.md). Forking, editing, removal, and redistribution remain subject to those licenses.
