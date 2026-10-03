# Operational residue

Removing code leaves residue outside the source tree: configuration, environment
variables, stored data, deployed artifacts and the deployments themselves. Plan
this phase explicitly; discovering it after a failed deploy is too late.

## Proposing operational actions

Actions outside files have no file row in a batch proposal: removing variables,
deleting or migrating data, revoking grants, webhooks or secrets, moving artifacts,
repointing consumers, deploying or restarting units. Each one gets a row in the
[operational action proposals](run-report.md#operational-action-proposals) and its
own owner approval; a cleanup mandate covers none of them by implication.
Repointing a consumer is new wiring, so it is a functional change. When the
environment reserves the action, hand the owner the commands.

## Configuration and environment variables

- Work on names only; never read or print values. Get the names from the owner,
  from example env files and blueprints, or from a platform command that extracts
  keys inside the same pipeline so values never reach the output (for example
  `... | jq -r '.[].envVar.key'`, adapted to the platform). Tracked templates
  (check with `git ls-files`, for example `.env.example`) may be read; never open
  untracked or ignored env files.
- For each deployable unit (web service, worker, job), list the variables the code
  **reachable from that unit's entrypoint** actually reads. A variable read
  anywhere in the repository is not read by every service.
- Compare with the variables configured on each unit. Classify: needed, unused
  now, unused after this release. Remove unused ones only after the code that read
  them is gone from every unit, including suspended or pinned units that may
  restart on an old build; save without redeploy when the platform allows it.
- A rollback to an older build needs the removed variables back: keep the list of
  removed names, and the owner keeps their values, until the rollback window closes.
- Update example env files and checklists in the same change as the code. Update
  deploy blueprints there too, unless syncing a blueprint removes variables from
  running units: then update it when the variables are actually removed.

## Stored data

- Data cleanup comes **after** the code that stops writing it is deployed.
- Deleting data closes the rollback to the previous version. Wait an observation
  period after the deploy, or record the owner's explicit acceptance that
  rollback becomes impossible.
- Remove the data models first: some ORMs recreate dropped collections or
  indexes on first use, and orphan writes keep recreating removed fields.
- Keep privacy obligations covered: if a deletion cascade (GDPR) referenced a
  removed model, keep deleting that data by collection name until it is gone.
- Use a one-shot script with this contract:
  - default is a dry run that prints only names and counts, never documents;
  - applying requires an explicit flag, an explicit list of named groups and a
    backup reference; reject placeholders and empty or unknown groups. When the
    owner declares the data disposable, they pass a dedicated waiver value (for
    example `NO-BACKUP-OWNER-ACCEPTED`) that the script accepts and prints;
  - idempotent (absent collection or index = skipped), never touching protected
    collections;
  - tested with a fake database that records the exact filters and updates.
- Run it where the deployed code and credentials already live (for example a
  platform shell), not on a laptop with copied secrets. Verify with a second dry
  run. Record a backup waiver and the owner's words in the report.

## Work in flight and scheduled

- Queued jobs may carry an old payload shape or target a removed handler: drain
  or migrate the queue before removing the handler.
- Inventory cron and scheduled jobs, webhooks registered at providers, remote
  feature flags, service accounts and IAM grants, and secrets in a secret manager
  (names only) that only the removed code used. Propose their removal after the
  deploy, like environment variables.

## External artifacts

- Bundles, buckets, images and indexes may be shared: a cleanup-era artifact can
  also feed other services (for example a planner job and a chat worker using the
  same bundle). Inventory every consumer before changing or deleting one.
- Check storage lifecycle rules, retention and versioning. An age-based delete
  rule can silently remove an artifact still in use. Keep in-use artifacts under a
  protected, versioned path and propose pointing consumers at it (a functional
  change with its own approval); verify checksums.
- Verify content, not names: compare sizes and hashes with what consumers expect.

## Deployments

- Know which services redeploy on merge and which are suspended or pinned to an
  old version. A suspended service must restart from a fresh deploy of the current
  base, never by resuming an old build that still knows removed data or code.
- After each deploy, verify health, the protective gate (maintenance mode or
  flags) and the expected responses; read deploy status from the platform.
- Record per service: version live, variables changed, checks run, open issues.
  Unresolved residue becomes a ticket with owner, trigger and steps.
