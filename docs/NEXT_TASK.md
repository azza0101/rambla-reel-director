# Next Task — Technical specification review gate

Current phase: **technical specification review**.

Architecture decisions have been approved and recorded in `docs/DECISIONS.md`.

The draft MVP technical design now lives at:

`docs/superpowers/specs/2026-09-11-rambla-reel-director-mvp-design.md`

No product implementation, dependency installation, model installation, Resolve integration, or panel scaffolding is authorized yet.

## Required next action

Review the technical design for:

- contradictions with approved decisions
- missing invariants
- ambiguous interfaces
- unsafe Resolve mutation paths
- client-isolation/privacy gaps
- unrealistic local-AI assumptions
- schema/versioning weaknesses
- MVP scope creep
- missing test/acceptance criteria

If issues are found, revise the spec only. Do not implement product code.

If the spec is internally consistent and sufficiently concrete, report that it is ready for explicit human approval.

## After explicit spec approval

1. Invoke the Superpowers `writing-plans` workflow.
2. Produce a detailed implementation plan from the approved spec.
3. Request explicit review/approval of that plan.
4. Only after plan approval begin implementation on a separate branch using tests and pull requests.
