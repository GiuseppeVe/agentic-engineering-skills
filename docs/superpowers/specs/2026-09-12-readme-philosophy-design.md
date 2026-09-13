# README Philosophy and Usage Design

**Date:** 2026-09-12

**Status:** Approved direction; implementation pending

**Scope:** Public README narrative and GitHub repository description. Skill payloads, manifests, hero asset, and technical behavior remain unchanged.

## Intent

Make the README explain the author's practical engineering philosophy instead of repeating the hero graphic. The page should let a technically experienced reader understand what each workflow element is for, when it is useful, and how the execution paths differ. It should share a working practice, not teach a universal method.

## Voice and positioning

- Keep the README in English for the public repository.
- Use first-person ownership where it adds authenticity: “I use this workflow…”
- Describe choices and observed benefits, not commandments.
- Invite inspection, adaptation, and reuse.
- Avoid tutorial/course language and claims that this is the “correct” workflow.
- Let the hero carry the visual summary; prose carries philosophy and concrete usage.

## README structure

Keep the approved hero immediately below the title, followed by one short non-repetitive framing sentence. Replace the current generic introduction and duplicated philosophy paragraph with these sections:

### What this repository shares

Explain that the repository is an experience-shaped collection of composable skills and agent profiles for Codex and Claude Code. State that its purpose is to make reasoning, sequencing, verification, and ownership inspectable and adaptable.

### My working philosophy

Explain five concrete principles:

1. start from evidence rather than an implementation guess;
2. turn decisions into durable specifications and traceable plans;
3. isolate implementation and separate worker output from independent evidence;
4. test both plan fidelity and implementation correctness;
5. keep publication and other external actions under explicit human control.

### How I use the workflow

Use a compact table with columns `Situation`, `Path`, and `Purpose`:

- large, uncertain initiative → `Wayfinder` → map scope beyond one session;
- bounded or creative design → `Brainstorming` → clarify intent before changes;
- consequential or disputed design → `Grill-me` → pressure-test assumptions;
- agreed design → `To Spec` → create standalone specification;
- multi-step implementation → `Writing Plans` → create traceable implementation plan;
- large implementation → `Sequential Task Orchestrator` → run one bounded task at a time with review;
- small implementation → `Codex Implement` → execute the focused change with relevant verification;
- Claude Code implementation → `Claude Implement` → use the host-equivalent bounded workflow.

State that these are composable choices, not mandatory stages for every task.

### The quality loop

Explain the orchestrator's two review dimensions explicitly:

- `Test Gaps` compares delivered work with the plan and finds missing or incomplete implementation coverage;
- `Test-Driven Development` checks behavior correctness through failing tests, implementation, passing tests, and fixes;
- findings return through the TDD cycle before acceptance.

### Supporting skills

Describe `Impeccable` and `UI UX Pro Max` as frontend craft/design support, `Caveman` as communication compression, and `How to Use Codex` as current official guidance for model-aware prompting, settings, and delegation. Clarify that `Graph Engineering V5.2` is not included because it is not yet validated.

### Example: from request to reviewed change

Add one short concrete sequence showing conditional selection rather than a mandatory recipe:

```text
large/uncertain request
→ Wayfinder
→ Brainstorming or Grill-me
→ To Spec
→ Writing Plans
→ Codex Implement or Sequential Task Orchestrator
→ Test Gaps + TDD
→ independent review
→ owner-approved publication
```

Explain in one sentence that a small, clear change can start directly at implementation and still retain the relevant verification and owner gates.

## GitHub repository description

Set the public repository description to this exact text:

> An experience-shaped workflow of composable skills for Codex and Claude Code: evidence, design, planning, implementation, verification, and review.

Do not change homepage, topics, visibility, branch protection, or other repository settings in this pass.

## Preservation rules

- Keep the hero image and Mermaid workflow diagram.
- Keep installation, customization, compatibility, provenance, and license sections, improving only links or wording needed for consistency.
- Do not duplicate the hero's full workflow labels in the opening paragraph.
- Do not modify files under `plugins/` or any skill payload.
- Keep Graph Engineering V5.2 explicitly outside the shipped inventory.
- Keep work isolated from `main` until explicit merge approval.

## Acceptance criteria

- README has the approved section structure and no generic introduction repeated from the hero.
- Every named workflow element above has a concrete purpose and usage condition in README prose or table form.
- README remains understandable without loading the hero image.
- Existing Mermaid, installation, provenance, compatibility, and license content remains present.
- GitHub description exactly matches the quoted description.
- `npm run verify:pack`, `npm run audit:public`, and `git diff --check` pass.
- No plugin payload or manifest changes are present in the branch diff.
