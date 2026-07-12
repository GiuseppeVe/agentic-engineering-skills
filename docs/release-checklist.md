# Release Checklist

Release remains manual. CI success does not authorize publication or repository changes.

## Pack and source gates

- [ ] `npm ci` exits 0 on Node.js 22.
- [ ] `npm test` exits 0.
- [ ] `npm run verify:pack` reports expected included inventory.
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
- [ ] Smoke tests use isolated temporary host homes/configuration.

## Owner approvals

- [ ] Review full diff and release report.
- [ ] Approve commit separately.
- [ ] Approve push separately.
- [ ] Approve pull request separately.
- [ ] Approve merge separately.
- [ ] Approve branch/worktree cleanup separately.
- [ ] Approve repository visibility change separately.
