# Agent Profiles

Seven host-neutral role contracts give workflow skills a shared vocabulary for bounded delegation. Use exact profile names; aliases such as “builder,” “tester,” or “orchestrator” are descriptions, not profile identifiers.

## Role contracts

| Profile | Responsibility | Use when | Role-specific evidence |
| --- | --- | --- | --- |
| `cleanup` | Remove explicitly scoped temporary artifacts. | Delivery leaves known disposable paths. | `resolvedScope`, `deletedPaths`, `retainedPaths` |
| `controller` | Route work and own state, budget, retries, escalation, and trace assembly. | Multiple bounded roles need coordination. | `route`, `budget`, `attempt`, `trace` |
| `implementer` | Apply one owned task with test-first discipline. | A plan has a bounded implementation unit. | `taskId`, `changedFiles`, `redEvidence`, `greenEvidence` |
| `planner` | Produce a bounded structured plan. | Requirements need tasks, dependencies, and acceptance criteria. | `tasks`, `dependencies`, `acceptanceCriteria`, `unresolvedDecisions` |
| `researcher` | Gather read-only evidence and separate observation from inference. | Decisions require verified codebase findings. | `observations`, `inferences`, `verifiedFindings` |
| `reviewer` | Review through spec, quality, security, and fidelity lenses. | Independent judgment is needed before acceptance. | `lenses`, `verdict`, `findings` |
| `test-runner` | Execute and interpret named verification commands without fixing failures. | Work needs reproducible verification evidence. | `commands`, `results`, `failedCommands` |

Canonical payloads live under `plugins/agentic-engineering-skills/agent-profiles/`. Repository manifest `manifests/agent-profiles.json` is canonical inventory and integrity source of truth. Installed plugin manifest `plugins/agentic-engineering-skills/manifests/agent-profiles.json` mirrors same seven profiles, provenance, and hashes while using paths relative to installed plugin root (`agent-profiles/<role>.md`).

## Common result envelope

Every role returns these fields:

| Field | Meaning |
| --- | --- |
| `role` | Exact declared profile name. |
| `status` | `completed`, `blocked`, or `failed`. |
| `summary` | Concise outcome. |
| `evidence` | Verifiable commands, paths, observations, or findings. |
| `risks` | Remaining uncertainty or hazards. |
| `nextAction` | One concrete continuation, or `none`. |

Role-specific fields supplement this envelope; they do not replace it.

## Workflow boundaries

These role contracts are consumed by workflow skills. They are not an executable harness and do not guarantee automatic native registration by either host. Workflow owners choose profiles, supply bounded inputs, enforce permissions, interpret results, and retain final accountability. Profiles contain no host-specific commands.

## Phase mapping

| Workflow phase | Profiles |
| --- | --- |
| Understand | `researcher`, optionally coordinated by `controller` |
| Design | `researcher`, `planner`, `reviewer` |
| Plan | `planner`, `reviewer` |
| Implement | `implementer`, optionally coordinated by `controller` |
| Verify | `test-runner` |
| Review | `reviewer` |
| Clean | `cleanup` |

## Codex

Use Codex native delegation capabilities to assign a complete profile payload plus bounded task context. Keep host-specific commands in calling workflow or project instructions, not inside profiles. Confirm available native delegation behavior in current Codex environment; profile distribution alone does not register agents automatically.

## Claude Code

Use Claude Code native delegation capabilities to assign a complete profile payload plus bounded task context. Keep host-specific commands in calling workflow or project instructions, not inside profiles. Confirm available native delegation behavior in current Claude Code environment; profile distribution alone does not register agents automatically.

Return to [README](../README.md).
