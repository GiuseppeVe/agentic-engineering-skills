# Programme messages

Single definition of the logical correlation between a work mandate, a
question, a decision, an informational update and a delivery report in a
coordinated programme. The plan thread reaches this file from its normal entry
([SKILL.md](../SKILL.md)) and the master reaches the same file from its role
reference. This file fixes meaning and identity only: the host supplies
transport and the consumer project supplies its own evidence, gate and merge
format.

## Addresses

| Role | Receives an address from | Publishes |
| --- | --- | --- |
| Owner | The programme entry point | Reserved decisions only |
| Master | The programme brief | Its own reachable address, the mandate and the reserved decisions |
| Plan thread | The master brief or the run entry point | Its own reachable address to every task thread it dispatches |
| Task thread | The plan thread that dispatched it | Nothing outside its plan thread |

A plan thread that received no master address is not orphaned: its original
commissioner remains the addressee for questions and deliveries. Never invent a
master address, and never forward upward a question that the mandate, the
approved sources or a decision in force already answers. Only a residual doubt
those sources leave open travels to the addressee.

## Three identities

Keep these layers apart in every exchange:

- **Transport identity.** The host message, turn or thread identifier. It
  changes on each send, retry or resume.
- **Work identity.** The mandate the exchange serves. It stays stable for the
  life of that delivery and is what reports and manifests are verified
  against.
- **Question identity.** The reference of an open question. A decision and a
  resumed step name it.

A project may mint a UUID for every send while the correlation to the work
identity stays stable. A transport identifier alone never proves which
delivery a message belongs to, and an acknowledgement is never a work
identity.

## Message types

### Mandate or delivery change

A mandate carries its own identity, an addressable base (branch or commit),
the expected outcome and a verifiable manifest of the delivery. A change of
delivery creates a **distinct mandate** that cites the superseded one; it does
not overwrite the old mandate. Reaching the same delivery again after a resume
keeps the existing mandate identity.

### Question

A question cites the mandate it concerns, the action it suspends, the choice
it proposes and the consequence of each option. It is sent to the address the
questioning thread received. A question covered by the mandate, the approved
sources or a decision already in force is not sent: the thread resolves it
locally and records the basis.

### Decision

A decision identifies the question it answers, states the scope and the
revision it applies to, and names who decided. A decision that changes the
delivery explicitly creates the new mandate and cites the previous one. The
next authorised step of the questioning thread cites the decision, and a
duplicated decision produces a single step.

### Informational update

An update is associated with the mandate in force and carries no decision
authority. A receipt confirmation, if requested, preserves the work identity
of the technical delivery; it does not create or advance a step.

### Delivery report

A report is verified against the mandate it was requested under: base,
expected outcome and manifest. A late report stays attributed to its original
mandate even after a later decision. A later decision keeps precedence inside
its own scope only.

## Correlation rules

- **Order of operations.** Informational update, then its receipt
  confirmation, leave the delivery identity and the operation evidence intact.
- **Late and superseded deliveries.** Mandate A, update, question on A,
  decision that changes the base and creates mandate B, then a late report of
  A: the report remains A. B is a distinct mandate; A's report is never
  re-labelled as B.
- **Manifest correction.** Evidence for an operation and validity of the
  manifest are verified separately. When a push was already verified and the
  manifest lacks its base, the task thread corrects the delivery while the push
  evidence is preserved: the correction counts no new operation, does not
  re-run the push and does not create a new mandate.
- **Receipt uncertain.** A send whose result is not a confirmed `started` or
  `steered` delivery — for example `queued`, a timeout, an error or an
  ambiguous result — counts as uncertain. Verify arrival by reading the
  recipient thread for the message id or by observing the next step that cites
  the decision, log the verification result, and do not resend blindly. When
  the host offers no notification, a compact snapshot reconciles open
  questions, undelivered decisions and arrived results.
- **Standalone run.** Without an identified master the original commissioner
  receives questions and deliveries, and availability of a master is not
  assumed.

## Stop and resume

A question suspends only the action that depends on it; independent work
already authorised by the mandate continues. An explicit owner stop applies to
the actions inside its declared scope, not to the whole run. After a decision,
only the unblocked actions resume, and each resumed action names the decision
it follows. A receipt or a chat confirmation not followed by an observable
step does not prove resumption.

## Worked example

1. Master sends mandate `A` with base `main@c0ffee`, the expected outcome and
   the manifest to verify.
2. Plan sends an informational update on `A`; the master confirms receipt. Both
   keep `A` as the work identity.
3. Plan asks: mandate `A`, action suspended "synchronise the branch", proposed
   choice "sync now or after review", consequence "Gate X runs on a different
   revision".
4. Master decides: sync after review, scope `A`, cites the question reference.
   The decision changes the base, so the master issues mandate `B` and cites
   `A` as superseded.
5. A delivery report for `A` arrives late. It is verified against `A`'s base
   and manifest and stays attributed to `A`. The plan's next step cites the
   decision and proceeds under `B`.
