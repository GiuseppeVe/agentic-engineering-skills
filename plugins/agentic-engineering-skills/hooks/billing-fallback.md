# Billing fallback preflight

Use only when the project's policy permits equivalent local/cloud CI after a confirmed GitHub billing block. This guide does not authorize a merge or make hosted checks green.

1. Read `billing-policies.json` next to this file. Select exactly the repository and PR base branch; follow every gate's commands, tool versions, services and coverage. An empty inventory or missing policy cannot certify a fallback. The manifest is trusted configuration: update it only after independently reviewing the actual CI workflow inventory and both base/head revisions.
2. On the exact, clean PR head, collect genuine billing evidence from GitHub and execute all equivalent gates. Keep logs outside the worktree. For every blocked gate record the current GitHub Actions `run_id`, `job_id`, `check_run_id`, and `attempt`; the checker retrieves and verifies those GitHub objects itself. All policy gates, including any hosted successes, need local results under this fallback.
3. Have an independent reviewer assess the full gate evidence, versions, services, coverage and billing proof. Record the normal independent code review in `review.json` as described by the hook, then add the following fields. Replace all placeholders with real values; copy the arrays and coverage exactly from the matching policy gates.

```json
{
  "billing_fallback": {
    "kind": "github_billing",
    "head_sha": "<40-character SHA>",
    "pr_url": "https://github.com/OWNER/REPO/pull/123",
    "billing_block_confirmed": true,
    "confirmed_by": "<reviewer or run>",
    "billing_blocked_checks": ["<blocked gate name>"],
    "block_evidence": "billing.txt",
    "block_evidence_sha256": "<SHA-256 of billing.txt>",
    "billing_proofs": [{"run_id": 123, "job_id": 456, "check_run_id": 456, "attempt": 1}],
    "gates": [{
      "name": "<policy gate name>",
      "head_sha": "<40-character SHA>",
      "outcome": "passed",
      "exit_code": 0,
      "equivalent": true,
      "commands": ["<every exact command from the policy>"],
      "tool_versions": ["<every exact tool entry from the policy>"],
      "services": [],
      "coverage": "<exact policy coverage>",
      "evidence": "gate.log",
      "evidence_sha256": "<SHA-256 of gate.log>"
    }]
  },
  "billing_review": {
    "head_sha": "<40-character SHA>",
    "outcome": "passed",
    "independent": true,
    "reviewer": "<independent reviewer>",
    "verified_fallback_sha256": "<SHA-256 of compact JSON.stringify(billing_fallback)>",
    "evidence": "billing-review.txt",
    "evidence_sha256": "<SHA-256 of billing-review.txt>"
  }
}
```

Merge these fields into the normal review record, including `required_checks` exactly matching the policy's gate names. Compute hashes from actual bytes. Compute `verified_fallback_sha256` from UTF-8 `JSON.stringify(record.billing_fallback)` without a trailing newline. The independent billing review must cover the exact resulting dossier and all local logs.

When a policy gate has `runtime_reference_required: true`, its gate record also needs `runtime_reference` with `runner_image`, matching concrete `hosted_node_version` and `local_node_version` in `major.minor.patch` format, a `reference_url` to the official `actions/runner-images` release or repository file, plus `evidence` and `evidence_sha256`. The reviewer must establish that this is the hosted runner image and that the local runtime is equivalent. If the unpinned hosted version cannot be established, stop.

Run `node <checker> preflight <PR-URL> <review.json>`. `READY LOCAL BILLING FALLBACK (hosted CI is not green)` permits the post-PR skill sequence only under the project's policy. Unknown billing messages, forks, missing/skipped/pending checks, stale attempts, changed workflows, incomplete logs or an unverifiable runtime remain `NOT READY`. The checker verifies hashes and GitHub metadata, not whether an independent reviewer truly acted independently or whether local commands actually ran; the reviewer must verify that evidence.
