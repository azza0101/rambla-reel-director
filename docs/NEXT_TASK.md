# Next Task — Design approval gate

Current phase: **architecture proposal review**.

No product implementation, dependency installation, model installation, Resolve integration, or panel scaffolding is authorized yet.

## User decisions required

1. Approve or revise the recommended modular-monolith / ports-and-adapters architecture.
2. Approve the exact MVP boundary and first vertical slice.
3. Choose the initial Resolve path to validate: Python API first, or Python API plus optional MCP adapter from the start.
4. Confirm whether the global asset library is part of MVP or deferred; client-local plus online sources are already proposed.
5. Approve filesystem-first versioned JSON persistence for runs and Edit Plans.
6. Confirm the panel compatibility target: Resolve Studio version(s), operating system, and permitted panel technology.
7. Confirm cloud policy for MVP: interfaces only, or one working cloud provider alongside local providers.

## After approval

1. Convert the approved architecture into a complete technical specification with frozen schemas, interfaces, state machines, invariants, and acceptance criteria.
2. Request explicit review and approval of that specification.
3. Only then write a detailed implementation plan.
4. Only after plan approval begin implementation on a separate branch with tests and a pull request.

