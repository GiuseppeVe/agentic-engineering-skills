# Package Manifest

The master commits this file on the `pkg/*` branch when creating a package and
updates it in the same step that adds a plan to the contracts map. The consumer
sets the directory and filename, derived from the branch name without `pkg/`. A
CI check reads it on the `pkg/*` → `main` PR and blocks until every listed plan
is integrated: each plan's PR must be merged into the package branch with its
merge commit in the head's history. Recreating the branch from a pre-merge
commit reopens the plan.

A plan leaves a package only by owner decision, expressed via the
`exclude:<plan>` label on the PR to `main`: the check accepts the exclusion
only when the latest labeling event comes from an owner account. Never delete a
plan from this file to make the check pass.

Exactly one fenced `json` block:

```json
{
  "package": "K4",
  "branch": "pkg/k4-sources",
  "plans": [
    { "id": "K4-A", "pr": 576 },
    { "id": "K4-B" }
  ]
}
```

Add `pr` when the plan's PR opens; a plan without `pr` is pending.
