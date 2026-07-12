# Distributable Skill and Agent Pack Design

## Goal

Make this repository a public, self-contained pack that users can clone or download to obtain runnable workflow skills, host-neutral agent profiles, clear installation guidance, and auditable third-party provenance.

## Package layout

```text
skills/
  <skill-name>/SKILL.md
  README.md
  sources.lock.json
agent-profiles/
  controller.md
  planner.md
  implementer.md
  reviewer.md
  test-runner.md
  researcher.md
  cleanup.md
THIRD_PARTY_NOTICES.md
licenses/
README.md
```

`skills/` contains the distributable content, not only a catalogue. `agent-profiles/` remains host-neutral: a user can adapt the profile to any agent host without hidden tools or repository assumptions.

## Provenance policy

Every skill has one manifest entry with source URL, immutable revision, license, status, and dependencies.

- `vendored`: exact upstream content copied only after source, commit, and license verification.
- `adapted`: derived content with explicit upstream notice and recorded modification status.
- `original`: independently written repository content; no proprietary prompt or unlicensed source text.

Unknown or incompatible licenses are never copied. The capability is documented or independently rewritten instead. Notices and full license texts are retained whenever source material requires them.

## Initial skill set

The pack includes practical skills for discovery, planning, implementation, testing, worktree isolation, swarm coordination, Knip-guided cleanup, architecture review, codebase learning, and concise communication. Each skill has routing metadata, actionable steps, validation, failure behavior, and host-neutral assumptions.

## Validation and release

Tests validate required headings for every skill and agent profile, manifest completeness, allowed provenance states, and documentation links. Public audit rejects secrets, private identifiers, URLs, personal data, and log artifacts. Final release runs lint, tests, build, evals, public audit, provenance verification, and Knip. Publication remains an explicit user-approved step.

## Scope boundary

The deterministic TypeScript harness remains the runnable reference implementation. This pack does not claim a specific host, provider, browser, Graphviz, GitHub CLI, or swarm runtime is installed. Each optional integration states its prerequisite and fallback.
