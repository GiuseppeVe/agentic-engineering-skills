# Agent roles

Read this reference before delegating work or assigning review authority.

| Role | Profile | Authority |
|---|---|---|
| Opus invariants analyst | `agents/sol-invariants-analyst.md` | Read-only philosophy, invariants, boundaries. |
| Opus dependency analyst | `agents/sol-dependency-analyst.md` | Read-only DAG and contract risks. |
| Opus test strategist | `agents/sol-test-strategist.md` | Read-only test/evidence design. |
| Opus planner/synthesizer | `agents/planner.md` | Sole authoritative packet decisions. |
| worker | [`agents/worker.md`](../agents/worker.md) | One bounded implementation packet. |
| Opus test author | `agents/sol-test-author.md` | One bounded test packet. |
| Opus semantic tester | `agents/spec-aware-tester.md` | Semantic evidence and rework findings. |
| Opus audit reviewer | `agents/sol-audit-reviewer.md` | Read-only pre-final targeted findings. |
| Opus clean reviewer | `agents/clean-room-reviewer.md` | Fresh sole final gate. |

Planner, semantic tester and clean reviewer use neutral attachment names. Distinct analyst and audit names remain separate contracts; filenames alone do not register native agents.

Analysts, workers, tester, audit, and clean reviewer use separate contexts. Analysts advise; planner/synthesizer resolves disagreement against original spec and plan, never by voting. No role except clean reviewer approves final integration.

Opus analysis, worker implementation, and clean review run as distinct phases unless verified capacity permits safe overlap.
