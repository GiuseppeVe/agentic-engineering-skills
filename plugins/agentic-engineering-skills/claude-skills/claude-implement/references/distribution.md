# Distribution and runtime verification

The reviewed project-local skill tree is the source for that project. After integration and required tests pass, verify the reviewed files and runtime; report the results.

Copy to another project, user-level directory, or WSL installation only when the user requests that distribution. For each requested target, compare the relative file set and SHA-256 hashes with the reviewed tree. Run `claude --model opus --effort high --help` and `claude --model opus --effort medium --help`; record exit status and output.

Any required copy, hash, or model-command mismatch blocks final clean approval. Create a narrow corrective packet and repeat verification. Give the clean reviewer only objective verification output, never worker or reviewer reasoning.

## Forward validation

Run `tests/forward-tests.md` after every change. Distribution is blocked until it prevents out-of-packet interface changes, clean-room bias, green-but-invariant-breaking diffs, nested worktrees, overlapping packets, test-author scope escape, and worker integration-conflict resolution.
