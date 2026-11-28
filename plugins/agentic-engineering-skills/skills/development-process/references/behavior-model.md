# Behavior Model

Applies when behavior depends on state or on the order of events, so that what happened before, an error, a cancellation, a retry, or a concurrent action changes the outcome for the user. A change with no such transition goes straight to the plan: state that in one line in the spec, or in the plan when there is no spec.

## Design

1. Derive the model from the conversation, in product terms. Existing code shows current behavior, not agreed behavior. Include every transition that changes the outcome for the user, with errors, cancellations, and retries where pertinent.
2. Keep it next to the spec in `<spec-name>.model/`: the TLA+ module, its config, the view module, and the generated `chart.mmd`. Write the spec first if none exists.
3. Draw it with `/statechart`. Its automatic invocation is off: read [the statechart skill](../../statechart/SKILL.md) and follow it; this procedure is the explicit request. Run it on a copy in a scratch folder, then bring the sources and `chart.mmd` back. If it cannot run, report the error and keep the behavior unapproved; never hand-draw a substitute. Every transition that changes the outcome is a visible labelled arrow: split labels instead of hiding it, even past the skill's arrow budget.
4. Record in the spec the assumptions and what the model leaves out. A choice the conversation did not settle goes to Open Questions, even when the model needs a provisional value for it.

## Approval

Show the owner the diagram, the assumptions, and each open choice, and ask them to approve the behavior. Choices that change a transition are settled before approval. Writing the plan waits for that approval. Record in the spec who approved, when, and the `git hash-object` of `chart.mmd`. The approval holds while a chart regenerated from the current sources has that hash: after any model change, including one the owner asks for while approving, show the new diagram and record approval again.

## Plan

Each critical transition (a wrong one loses or duplicates data or an effect, grants access, or leaves the user stuck or misinformed) becomes an acceptance criterion checked on the real code: starting state, event, resulting state, and what the user sees. A transition the model forbids gets a criterion that shows the code refuses it. A TLC run checks only the model and satisfies none of these.

## Code review

Before `gh pr ready` and the CI gates, the reviewer reads the model and checks both directions with code and tests:

- **Missing:** a model transition that the code does not perform.
- **Forbidden:** a path the code allows that the model does not, such as a late, repeated, or out-of-order event.

Report each as a finding with `file:line` and the event sequence. Repeat the check on fixes that touch a modelled transition.

## Behavior changes

When planning, implementation, or review calls for different behavior, show the owner the difference (transition now, transition proposed, effect on the user) and wait for approval before editing the model. Then update the model, diagram, spec, and criteria together. A defect where the code departs from the approved model is fixed in the code.
