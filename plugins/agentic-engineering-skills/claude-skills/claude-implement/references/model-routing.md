# Model routing

Host-specific selection stays in this calling layer. Independent sessions receive the complete role attachment and only its permitted inputs; preserve original unabridged specification and plan.

| Role | Model | Effort |
|---|---|---|
| Planner | `claude-opus-5-5` | `medium` |
| Semantic tester, clean reviewer, audit reviewer and read-only analysts | `claude-opus-5-5` | `high` |
| Test author | `claude-sonnet-5-5` | `medium` |
| Bounded packet worker | `claude-sonnet-5-5` | `high` |

Start each role and retry in a fresh generic session; named global agent profiles are not required. Put the complete role attachment in the session's system prompt and provide only its allowed inputs. For worker use the worker contract identified in the role map. For read-only tester and reviewer sessions, restrict built-in tools to `Read,Grep,Glob` and disable unlisted MCP servers; supply the diff and test evidence as inputs.

The worker contract must require this return block, in this order: `Status: DONE | BLOCKED`, `Change summary:`, `Tests and results:`, `Assumptions:`, `Deviations:`, `Integration risks:`, `Files changed:`. A return without `Status:` is treated as BLOCKED.

```powershell
claude -p --model claude-opus-5-5 --effort medium --append-system-prompt "<planner attachment>" "<allowed inputs>"
claude -p --model claude-opus-5-5 --effort high --tools "Read,Grep,Glob" --strict-mcp-config --append-system-prompt "<tester attachment>" "<allowed inputs>"
claude -p --model claude-opus-5-5 --effort high --tools "Read,Grep,Glob" --strict-mcp-config --append-system-prompt "<reviewer attachment>" "<allowed inputs>"
claude -p --model claude-sonnet-5-5 --effort high --append-system-prompt "<bounded worker contract>" "<one packet>"
```

Distinct analyst, audit and test-author attachments keep their names. Launch each in a fresh session with its full attachment and explicit table selection; do not invent registration from a skill directory. Parsing help does not prove discovery or routing. Capture actual host model/effort telemetry; if unavailable, preserve role isolation and record reduced assurance.
