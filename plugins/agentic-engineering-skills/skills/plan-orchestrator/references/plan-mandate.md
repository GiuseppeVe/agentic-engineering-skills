# Plan mandate document

The master commits this document in the plan branch before the first message
to the plan thread. The consumer fixes the directory (Alfe:
`docs/work/mandates/<plan>.md`). It is the written perimeter: a thread that has
lost its context recovers it from here, not from memory or chat.

## Who reads it

- The plan thread reads it at launch and after every resume, and passes its
  path to every task thread together with the plan's own address.
- Every task thread reads it at launch and after every resume, cites its path
  and `revision` before its first step, and cites the `revision` again in its
  first report.
- A change of mandate is a new commit of this document with `revision`
  incremented and `supersedes` set to the previous revision. A chat message
  alone does not change the mandate: ask for the updated document, through the
  plan thread when you are a task thread, up to the master.
- The consumer's check reads the mandate from the base of a task PR: editing
  or deleting it inside the task PR does not change the perimeter that PR is
  checked against.

## Overlap rule

If a step needs a path outside `paths`, or a path listed under `shared` with a
holder other than this plan, stop that step and send a question that names the
file, the holder and the blocked step, with the fields of
[programme messages](programme-messages.md). A task thread sends it to its plan
thread; the plan thread sends it to the master (or to its original commissioner
when it received no master address). Do not edit the file. Continue only
independent authorised work.

## Gates

Never choose which gates run, and never drop or substitute one. The project's
versioned map selects them, and selects the full suite when a path is
unmapped, a shared file changes, or the diff or the map cannot be read. A PR to
`main` runs the full suite unless the consumer's diff-exception label (Alfe:
`gate:diff`) was applied by an owner account after the current head was
pushed. A new push voids the label; a chat reply never replaces it.

## Required sections

1. **Perimeter** — links to the plan and spec sections with their revisions.
2. **Paths** — the machine-readable block below.
3. **Parallel plans** — active plans, their paths and shared files with holders.
4. **Overlap rule** — as above, plus any project-specific contact.
5. **Contended resources** — resource, holder, who assigns it. Gate machines behind a self-queuing gate runner are not listed.
6. **Reserved decisions** — what only the owner decides.
7. **Stop criteria** — when the plan stops and reports.

## Machine-readable block

Exactly one fenced `json` block; consumers check diffs against it.

```json
{
  "plan": "K4-A",
  "branch": "codex/k4-a-sources",
  "base": "pkg/k4-sources",
  "revision": 1,
  "supersedes": null,
  "paths": ["backend/src/sources/**", "backend/test/sources/**"],
  "shared": [{ "path": "backend/package.json", "holder": "K4-B" }]
}
```
