# Reporting to the master

Read this file when the plan thread starts or resumes **as a subthread of a
master** (`coordinating-implementation-plans`, or a run assigned by it). A
standalone run reads only [the message definition](programme-messages.md) and
keeps its original commissioner.

Read both files at the normal entry point, after the resume reconciliation of
ledger, worktrees and Git state, before dispatching or redispatching any task
thread.

## Entry and address

- From the brief, take the master's reachable address, the mandate the run
  executes and the reserved decisions already granted.
- Publish that address, the mandate and the applicable stop criterion (what
  suspends which action, and the scope of any explicit owner stop) to every task
  thread you dispatch. A task thread sends its question to the plan
  thread, not to the master.
- On resume, reuse the addresses and mandates already recorded. Do not invent a
  missing address, and do not treat a stale brief as a new mandate.

## Resolve locally first

A doubt already answered by the mandate, the plan, the spec, an ordinary
project rule or a decision in force is resolved locally. Record the basis; do
not forward it. This holds for the steps the plan already covers, including a
dependent task whose next action follows the approved integration path.

Escalate only:

- a residual doubt about the programme flow that the sources leave open;
- a proposal that changes structure, contract, behaviour, perimeter or a
  reserved authorisation while the approved sources leave the choice open.

For a reserved choice, state the precise choice, the observable effect and the
dependent step, then route it to the owner through the master. Do not decide a
reserved choice yourself, and do not replace an approved gate with an
equivalent one unless an approved basis or the owner's decision authorises it.

## Questions, decisions and resumption

- A question follows the fields in [programme-messages.md](programme-messages.md):
  mandate, suspended action, proposed choice, consequence.
- A decision arrives with its question reference. Apply it inside its scope and
  revision; leave the rest of the run unchanged.
- Resume only the actions the decision unblocks, and make the next step cite
  the decision. A duplicated decision produces one step.
- An explicit stop suspends the actions inside its scope. Authorised
  independent work keeps running; a question suspends only its dependent
  action.
- A task that needs a contended shared resource waits for the master's grant
  notice. The plan requests it naming the resource and the suspended action,
  and instructs the task thread only after the notice, citing it.
- If delivery is uncertain, verify receipt before resending. A chat
  acknowledgement without an observed step is not resumption.
- Read the mandate document ([plan-mandate.md](plan-mandate.md)) at launch and
  after resume; a mandate change is a new committed revision, not a chat
  message. Out-of-perimeter or held paths become a question to the master.

## Deliveries and reports

- Every mandate you accept identifies its base, expected outcome and
  verifiable manifest. A change of delivery arrives as a distinct mandate
  citing the previous one; do not rewrite the old mandate or mint a new one
  yourself.
- A late report stays attributed to the mandate it was requested under, even
  after a later decision.
- Evidence for a technical operation and validity of the manifest are checked
  separately. Correct a manifest whose base is stale without repeating or
  re-counting an already verified operation.
- Report to the master keeping these apart: observed facts, requested
  perimeter, available evidence, readiness and merge authorisation. As the
  runtime protocol states for a map-master assignment, report readiness and wait
  for the merge go-ahead. Name any remaining verification instead of implying it
  passed.

## Boundaries

Dependency selection, workspace isolation, implementer/reviewer dispatch and
acceptance remain those of the [runtime protocol](runtime-protocol.md). The
dialogue never bypasses a dependency gate, a review stage or a commit boundary,
and a question or a decision is not a substitute for missing evidence.
