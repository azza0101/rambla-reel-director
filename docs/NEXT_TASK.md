# Next Task — Complete technical specification blockers

Current phase: **technical specification completion and review**.

Architecture decisions are approved and recorded in `docs/DECISIONS.md`.

The reviewed MVP technical design is:

`docs/superpowers/specs/2026-09-11-rambla-reel-director-mvp-design.md`

No product implementation, dependency installation, model installation, Resolve integration, or panel scaffolding is authorized yet.

## Required next action

Resolve every open decision in section 25 of the technical design before asking for final specification approval.

The seven blockers are:

1. Freeze complete v1 JSON schemas for all persisted core entities and typed errors.
2. Freeze MVP HTTP/SSE contracts, including status codes, idempotency, concurrency, replay, and reconnect behavior.
3. Freeze exact typed contracts for every MVP port.
4. Freeze semantics, validation, layering/collision policy, parameters, and verification postconditions for all five MVP editorial actions.
5. Give Dry Run one deterministic meaning, terminal state, and artifact set.
6. Define retention, deletion, cleanup authorization, and audit rules for artifacts, caches, downloads, logs, cloud-request records, and generated Resolve timelines.
7. Define the benchmark protocol, baseline procedure, evidence requirements, authority for choosing thresholds, and MVP sign-off rule.

## Decision rule

Do not bounce ordinary engineering decisions back to the user when they can be resolved from the approved product goals and safety constraints. Prefer the smallest deterministic contract that supports the MVP.

Escalate only a decision that materially changes user-visible product behavior, privacy policy, data retention expectations, or MVP scope and cannot be inferred safely from approved decisions.

Do not introduce infrastructure that is not required by the current MVP. Resolve-version-specific capability values may remain `TBD_BY_SPIKE` only where the technical design explicitly permits them.

## Review requirements

While resolving the blockers:

- maintain compatibility with all approved decisions in `docs/DECISIONS.md`;
- preserve local-first and deny-by-default cloud behavior;
- preserve strict client isolation;
- keep frame/time semantics deterministic;
- keep Analyze/Dry Run incapable of Resolve mutation;
- keep Apply limited to an approved frozen plan and a generated duplicate timeline;
- keep schemas and contracts versionable without silent migration;
- define testable invariants and acceptance criteria for every newly frozen contract;
- remove the blocker from section 25 only when its contract is concrete enough to implement without inventing missing behavior.

Use Superpowers. Modify documentation/specification only. Do not implement product code.

## Completion condition

When all seven blockers are resolved:

1. Run a final consistency review of the complete specification.
2. Update section 25 to state that no unresolved technical-contract blockers remain, while retaining any permitted `TBD_BY_SPIKE` items.
3. Update this file to the **explicit specification approval gate**.
4. Commit and push documentation changes.
5. Report the commit SHA, what was frozen, any remaining human decisions, and whether the specification is ready for explicit approval.
6. Stop. Do not begin the implementation plan until the specification is explicitly approved.
