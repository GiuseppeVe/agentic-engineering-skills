# Customization

## Safe workflow

1. Fork repository.
2. Create branch in fork.
3. Edit source under `plugins/agentic-engineering-skills/skills/`.
4. Update provenance lock, patch, and change notice when adaptation ancestry changes.
5. Run `npm test` and pack verification.
6. Redistribute fork only with all applicable license and NOTICE files.

Direct edits, skill removal, and redistribution are allowed when applicable licenses are preserved. Third-party terms remain separate from root MIT license; consult [Third-Party Notices](../THIRD_PARTY_NOTICES.md) and [provenance](provenance.md).

Do not edit installed plugin cache. Host updates or reinstallations can overwrite cache contents, and cache edits bypass repository verification. Change source in fork, verify it, then reinstall.

For partial bundles, follow [selective installation](selective-install.md).
