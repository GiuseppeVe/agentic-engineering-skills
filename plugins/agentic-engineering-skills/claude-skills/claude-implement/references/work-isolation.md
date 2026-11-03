# Work isolation

Verify a clean base and freeze `base_sha` before any code dispatch. If user, repository, or host policy requires a verified remote base, fetch and verify the required ref (for example, `origin/main`) before creating a task branch or worktree, then record its exact SHA. If remote verification fails, return `BLOCKED`; never fall back to local `main`, current `HEAD`, or an unverified cached remote ref. Select the integration branch name and worktree root from explicit user instructions first, then repository and host policy. Do not impose this plugin's branch or path convention over those policies. If no convention applies, use the host's standard. Create the dedicated `integration/` worktree from exactly that frozen clean `base_sha`, never from a later integration or packet head. For project-local runs, verify the approved parent directory is ignored before creating worktrees.

Packet worktrees must be siblings of the integration worktree, never its children.

Independent worker packets start from the recorded `base_sha`. Dependent, corrective, or Opus-owned integration packets start from the current integration head after prerequisites are merged.

Only the controller may write to the integration branch. If isolated worktree creation is unavailable, do not dispatch code-writing worker or test-author packets, even serially. Read-only analysis and review may proceed; record blocked writing work and reduced isolation until required worktrees exist.
