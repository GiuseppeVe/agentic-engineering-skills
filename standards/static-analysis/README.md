# Shared static analysis presets

Canonical, noise-filtered static analysis presets for consumer repositories.

## Two-speed model

1. **Fast feedback circuit (edit hook and `pre-commit`):** syntactic Oxlint (`--quiet`, no `--type-aware`) on modified files only. Typical latency is under 200 ms per file and 1–3 s per repository.
2. **Deep verification circuit (`pre-push` and CI):** type-aware Oxlint (`--type-aware`, backed by `oxlint-tsgolint`) on TypeScript packages and syntactic Oxlint on plain JS/MJS packages, alongside `tsc` (kept authoritative for compilation and type checking) and `knip` for dead code.

## Presets

- [`base-ts-js.oxlintrc.json`](base-ts-js.oxlintrc.json): correctness and high-signal type-aware rules for TypeScript and JavaScript (`no-floating-promises`, `no-misused-promises`, `await-thenable`, `no-base-to-string`, `no-misused-spread`, `require-array-sort-compare`, `eqeqeq`, `no-empty`, `no-unsafe-finally`, `no-unsafe-optional-chaining`, `import/no-duplicates`). Noisy style rules and empirically verified false positives are explicitly disabled.
- [`react-web.oxlintrc.json`](react-web.oxlintrc.json): extends the base preset with React 19 hooks rules (`rules-of-hooks`, `set-state-in-effect`, `refs`, `immutability`, `jsx-key`) and keyboard accessibility checks (`click-events-have-key-events`, `no-static-element-interactions`, `interactive-supports-focus`).
- [`ruff.toml`](ruff.toml): minimal correctness preset for Python helper scripts, runnable zero-install via `uvx ruff check --config ruff.toml`.

## Ratchet adoption in existing repositories

When enabling these presets in an existing codebase with pre-existing violations:

- Block with exit code 1 on **any error in files touched by the diff** (against the merge-base with the remote default branch, or staged files in `pre-commit`).
- Never suppress valid rules globally to hide legacy debt; track and remediate high-risk pre-existing findings in dedicated cleanup batches.
- Keep `oxlint` and `oxlint-tsgolint` pinned in the consumer repository's lockfile so Windows, Linux and CI runners execute identical versions. The `.oxlintrc.json` format remains portable across Oxlint and future stable Bun linter releases.
