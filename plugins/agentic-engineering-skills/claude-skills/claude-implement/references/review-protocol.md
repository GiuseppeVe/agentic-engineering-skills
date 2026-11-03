# Review protocol

Integrate only `DONE` packets with a verified commit SHA and complete pre-integration evidence; partial or `BLOCKED` states never integrate. Integrate serially in dependency order and run the declared combined integration tests after each meaningful group of changes, capturing objective output: command, exit code, stdout/stderr, and test identifiers.

Any failed test or material finding blocks further integration, semantic testing, audit review, and clean review until corrected and reverified through a narrow corrective packet created from the current integration head.

A conflict, ownership breach, or shared-contract decision aborts integration and creates an Opus-owned `INTEGRATION` packet; never ask worker to force-resolve it.

Use fresh, independent review contexts. Reviewers evaluate the original specification, acceptance criteria, integrated diff, repository architecture, and objective test evidence without relying on implementer conclusions.

Classify findings as `BLOCKER`, `MAJOR`, `MINOR`, or `NOTE`. Material findings require targeted correction and repeated verification. Audit reviewers return `NO_MATERIAL_FINDING` or `TARGETED_REWORK`; they never approve integration.

Start the clean reviewer with only the original spec, original plan, acceptance criteria, final diff (`base_sha..integration_head`), and objective test output. Exclude worker notes, assumptions, planner/tester/audit reasoning, and prior verdicts; rebuild any contaminated bundle.

Only a fresh clean reviewer may grant final approval, returning `APPROVE`, `TARGETED_REWORK`, or `BLOCK` with cited requirement and code/test evidence. Approval requires passing required tests, full traceability of every requirement to code or test evidence or explicit non-applicability, and no unresolved material divergence.
