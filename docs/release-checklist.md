# Release Checklist

Release remains manual. CI success does not authorize publication or repository changes.

## Pack and source gates

- [ ] `npm ci` exits 0 on Node.js 22.
- [ ] From WSL, a native Windows clone, or a `cmd pushd` mapped drive, `npm test` exits 0 and prints a nonzero final test count. Never release from bare `npm` on a `\\wsl.localhost\\...` UNC working directory; it can false-green with zero tests.
- [ ] `npm run verify:pack` reports expected lock, directories, docs, both native receipt inventories, and payload hash.
- [ ] `npm run verify:upstream` verifies every included third-party skill at pinned revision.
- [ ] Every excluded skill has objective source or legal failure reason in release report.

## License and public-surface gates

- [ ] Root MIT license and all third-party license/NOTICE joins pass.
- [ ] Adapted Apache-2.0 files retain required prominent change notices.
- [ ] `npm run audit:public` exits 0 against Git-tracked release files.

## Native host gates

- [ ] Record Codex version, validator command, exit code, and discovered skill names.
- [ ] Record Claude Code version, validator command, exit code, and discovered skill names.
- [ ] Both native inventories match included lock inventory.
- [ ] CI fresh-installs both hosts and `verify:installed-native` matches each installed tree hash to source and schema-v2 receipt.
- [ ] Smoke tests use isolated temporary host homes/configuration.

## Owner approvals

- [ ] Review full diff and release report.
- [ ] Approve commit separately.
- [ ] Approve push separately.
- [ ] Approve pull request separately.
- [ ] Approve merge separately.
- [ ] Approve branch/worktree cleanup separately.
- [ ] Approve repository visibility change separately.
