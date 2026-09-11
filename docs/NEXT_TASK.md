# Next Task — Explicit technical specification approval gate

Current phase: **technical specification approval**.

Architecture decisions are approved and recorded in `docs/DECISIONS.md`.

The MVP technical specification consists of:

- `docs/superpowers/specs/2026-09-11-rambla-reel-director-mvp-design.md`
- `docs/superpowers/specs/2026-09-11-rambla-reel-director-mvp-contracts-v1.md`

The contracts supplement is normative where it is more specific and closes all seven technical blockers previously listed in section 25 of the design document.

No product implementation, dependency installation, model installation, Resolve integration, or panel scaffolding is authorized yet.

## Current disposition

The specification is ready for explicit human approval.

All previously open technical-contract decisions are now frozen:

1. complete v1 persisted schemas and typed errors;
2. HTTP/SSE contracts, idempotency, status codes, replay, and reconnect behavior;
3. typed MVP port contracts;
4. semantics, validation, layering/collision policy, and postconditions for all five MVP editorial actions;
5. one deterministic Dry Run meaning;
6. retention, deletion, cleanup, and audit policy v1;
7. benchmark protocol, hard safety gates, and authority for the editorial quality gate.

Resolve-version-specific facts may remain `TBD_BY_SPIKE` only where D-018/D-019 permit capability discovery in Slice 0. They are capability facts, not unresolved product-contract decisions.

## Required next action

Request explicit human approval of the complete technical specification.

If approval is granted:

1. record the approval in `docs/DECISIONS.md` or an equivalent approval record;
2. invoke the Superpowers `writing-plans` workflow;
3. produce a detailed implementation plan from the approved specification;
4. request explicit review and approval of that implementation plan;
5. only after plan approval begin implementation on a separate branch using tests and pull requests.

If approval is not granted, revise documentation/specification only and remain at this gate.

Do not implement product code before explicit specification approval.
