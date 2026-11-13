# Bounded implementation worker

Run each scenario with task-implement and packet contract loaded. Record the assigned packet, exact owned paths, worker evidence, and pass/fail.

1. **Disjoint packets:** Two packets own disjoint files and no shared contract. Delegate only if each has objective, acceptance, allowed files, dependencies, checks, and result fields.
2. **Overlapping writer:** Packets edit same file or shared state. Assign one owner or serialize; never dispatch both concurrently.
3. **Out-of-scope dependency:** Packet discovers an excluded interface change is needed. Stop that packet and report exact dependency to parent; do not expand its allowlist.
4. **Packet routing:** Default Codex packet worker is `gpt-6.1-terra`/`high`; default Claude packet worker is `claude-sonnet-5-5`/`medium`. Owner/plan-selected available model and effort takes precedence. Record route and do not silently substitute unavailable required model.
5. **Result contract:** Worker reports outcome, satisfied/open requirements, checks and evidence class, changed files, base SHA/worktree for uncommitted state, assumptions, deviations, risks, and blockers.
