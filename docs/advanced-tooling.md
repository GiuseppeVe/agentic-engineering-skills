# Advanced tooling

Core commands (`npm test`, `npm run build`, `npm run demo`, and `npm run evals`) need only Node.js 20+. No provider key, network call, user data, or provider SDK is involved.

| Integration | Prerequisite | Workflow stage | Upgrade | Unavailable behavior |
| --- | --- | --- | --- | --- |
| Swarm orchestration | Agent host with workers | Parallel independent tasks | Independent review lanes | Run work serially. |
| Git worktrees | Git 2.20+ | Isolated implementation | Separate branch directories | Use a normal branch carefully. |
| `gh` | GitHub CLI login | Publish and CI inspection | PR and Actions automation | Push with Git or use web UI. |
| Browser capability | Browser tool | UI or docs inspection | Rendered-page verification | Review text and source only. |
| Graphviz | `dot` executable | Diagram rendering | SVG/PNG diagrams | Read Mermaid source. |
| Knip | `npm run maintenance:scan` | Maintenance | Unused-code findings | Skip scan; never auto-delete. |

Knip is advisory. Human review decides whether a reported dependency or export is safe to remove.
