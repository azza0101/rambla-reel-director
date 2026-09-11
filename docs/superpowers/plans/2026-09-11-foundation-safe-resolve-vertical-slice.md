# Foundation + Safe Resolve Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first executable RAMBLA Reel Director slice: isolated local backend, versioned contracts/artifacts, review/freeze flow, Dry Run, and a safe end-to-end Apply against a duplicated Resolve timeline using one deterministic `PUNCH_IN` decision before adding real AI/model breadth.

**Architecture:** Python modular monolith with ports/adapters. Domain logic remains runnable without Resolve through a fake adapter; the real Resolve adapter is introduced only after the contract, artifact, orchestration, and Apply safety layers pass tests. The first real vertical slice deliberately avoids model/provider complexity so we can prove the product control plane and mutation safety first.

**Tech Stack:** Python 3.12 in a repository-local virtual environment; FastAPI; Uvicorn; Pydantic v2; pytest; pytest-asyncio; Hypothesis; HTTPX; `rfc8785` for canonical JSON; standard-library filesystem primitives. No ComfyUI environment, no global Python installs, and no model installs in this plan.

**Spec:**
- `docs/superpowers/specs/2026-09-11-rambla-reel-director-mvp-design.md`
- `docs/superpowers/specs/2026-09-11-rambla-reel-director-mvp-contracts-v1.md`

## Global Constraints

- Source timeline `REEL_MASTER` MUST NOT be mutated.
- Analyze and Dry Run MUST have no reachable Resolve mutation path.
- Apply accepts only an approved frozen plan and mutates only a generated duplicate timeline.
- Persisted JSON is versioned, closed, validated, canonical-hashable, and written immutably.
- Client isolation is enforced in domain access, not only by folder naming.
- Runtime/client data lives outside the Git repository under a configurable data root.
- Cloud access is deny-by-default; this plan performs no cloud calls.
- ComfyUI and its Python environment MUST NOT be modified or imported.
- Resolve-version-specific behavior is capability-gated; unsupported behavior fails preflight rather than being approximated.
- Implementation tasks use a feature branch, tests, commits, push, and pull request; no autonomous merge.

---

### Task 0: Prove the Codex/Git delivery path before product edits

**Files:**
- Create temporarily on the task branch: `docs/dev-workflow-smoke.md`
- Delete before the task PR is finalized.

**Interfaces:**
- Consumes: current `main`, `AGENTS.md` delivery workflow.
- Produces: evidence that Codex can create/switch branch, write files, run tests/commands, commit, push, and open/update a PR without asking the user to run PowerShell manually.

- [ ] **Step 1: Create implementation branch**

Use branch name:

```text
feat/foundation-safe-resolve-slice
```

If sandboxed Git writes are denied, request the minimum explicit out-of-sandbox/elevated Git execution required by `AGENTS.md`; do not ask the user to type Git commands manually.

- [ ] **Step 2: Write smoke file**

```markdown
# Development workflow smoke test

Codex branch/write/commit/push path verified for RAMBLA Reel Director.
```

- [ ] **Step 3: Commit and push only the smoke file**

```bash
git add docs/dev-workflow-smoke.md
git commit -m "chore: verify development workflow"
git push -u origin feat/foundation-safe-resolve-slice
```

Expected: remote branch exists and HEAD matches the local commit.

- [ ] **Step 4: Remove the smoke file and commit the cleanup**

```bash
git rm docs/dev-workflow-smoke.md
git commit -m "chore: remove development workflow smoke file"
git push
```

Expected: clean working tree. If this task cannot complete, stop implementation and report the exact Codex/Git permission blocker.

---

### Task 1: Scaffold an isolated backend with a health endpoint

**Files:**
- Create: `pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/config.py`
- Create: `tests/unit/test_config.py`
- Create: `tests/integration/test_health_api.py`

**Interfaces:**
- Consumes: configurable external data root.
- Produces: `create_app() -> FastAPI`, `Settings`, `/health`.

- [ ] **Step 1: Write failing configuration test**

```python
from pathlib import Path
from backend.app.config import Settings


def test_data_root_is_external_to_repository(tmp_path: Path):
    repo = tmp_path / "repo"
    data = tmp_path / "data"
    repo.mkdir()
    data.mkdir()
    settings = Settings(repo_root=repo, data_root=data)
    assert settings.data_root == data.resolve()
```

- [ ] **Step 2: Write failing health API test**

```python
from fastapi.testclient import TestClient
from backend.app.main import create_app


def test_health():
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

- [ ] **Step 3: Run tests and verify failure**

```bash
python -m pytest tests/unit/test_config.py tests/integration/test_health_api.py -v
```

Expected: import/module failures because implementation does not exist.

- [ ] **Step 4: Add minimal project configuration**

`pyproject.toml` MUST declare Python `>=3.12,<3.13` and project dependencies `fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`, `rfc8785`; dev dependencies `pytest`, `pytest-asyncio`, `hypothesis`, `httpx`.

- [ ] **Step 5: Implement minimal settings and app factory**

```python
# backend/app/config.py
from pathlib import Path
from pydantic import BaseModel


class Settings(BaseModel):
    repo_root: Path = Path.cwd()
    data_root: Path = Path(r"Z:\RAMBLA-reel-data")

    def model_post_init(self, __context) -> None:
        self.repo_root = self.repo_root.resolve()
        self.data_root = self.data_root.resolve()
        if self.data_root == self.repo_root or self.repo_root in self.data_root.parents:
            raise ValueError("data_root must be outside repository")
```

```python
# backend/app/main.py
from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="RAMBLA Reel Director", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 6: Run tests**

```bash
python -m pytest tests/unit/test_config.py tests/integration/test_health_api.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml backend tests/unit/test_config.py tests/integration/test_health_api.py
git commit -m "feat: scaffold isolated local backend"
```

---

### Task 2: Implement v1 common types, plan models, and canonical hashing

**Files:**
- Create: `backend/app/contracts/common.py`
- Create: `backend/app/contracts/errors.py`
- Create: `backend/app/contracts/plans.py`
- Create: `backend/app/contracts/runs.py`
- Create: `backend/app/contracts/apply.py`
- Create: `backend/app/contracts/hashing.py`
- Create: `backend/app/contracts/schema_export.py`
- Create: `tests/unit/contracts/test_closed_models.py`
- Create: `tests/unit/contracts/test_plan_hashing.py`
- Create: `tests/unit/contracts/test_schema_export.py`

**Interfaces:**
- Produces: `TypedError`, `Run`, `EditPlan`, `EditDecision`, `ApplyOperation`, `ApplyReport`, `canonical_sha256(model) -> str`, checked-in JSON Schema generation.

- [ ] **Step 1: Write failing closed-model test**

```python
import pytest
from pydantic import ValidationError
from backend.app.contracts.errors import TypedError


def test_typed_error_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        TypedError(
            schema_version="1.0",
            code="X",
            category="INTERNAL",
            retryable=False,
            message="x",
            diagnostic_id="00000000-0000-0000-0000-000000000001",
            details=None,
            unexpected=True,
        )
```

- [ ] **Step 2: Write failing canonical-hash stability test**

```python
from backend.app.contracts.hashing import canonical_sha256


def test_hash_is_key_order_independent():
    assert canonical_sha256({"b": 2, "a": 1}) == canonical_sha256({"a": 1, "b": 2})
```

- [ ] **Step 3: Implement closed Pydantic v2 models**

Every persisted model MUST use:

```python
model_config = ConfigDict(extra="forbid")
```

Use the exact field names/enums from the v1 contracts supplement. Do not broaden enums or make required fields optional.

- [ ] **Step 4: Implement RFC 8785 + SHA-256 hashing**

```python
import hashlib
import rfc8785


def canonical_sha256(value: object) -> str:
    payload = rfc8785.dumps(value)
    return "sha256:" + hashlib.sha256(payload).hexdigest()
```

`EditPlan` approval hashing MUST exclude only the fields permitted by the approved design.

- [ ] **Step 5: Add schema export command and tests**

Export JSON Schemas under `backend/schemas/v1/` and test that every top-level schema sets `additionalProperties: false` where applicable and that repeated export is byte-stable.

- [ ] **Step 6: Run contract tests**

```bash
python -m pytest tests/unit/contracts -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/contracts backend/schemas tests/unit/contracts
git commit -m "feat: add frozen v1 contracts and canonical hashing"
```

---

### Task 3: Implement immutable ArtifactStore and run manifest

**Files:**
- Create: `backend/app/ports/artifacts.py`
- Create: `backend/app/adapters/persistence/filesystem_artifacts.py`
- Create: `backend/app/domain/runs/manifest.py`
- Create: `tests/contract/test_artifact_store_contract.py`
- Create: `tests/unit/persistence/test_filesystem_artifacts.py`

**Interfaces:**
- Produces: `ArtifactStore.write_immutable`, `read`, `exists`, `mark_stale`, `list_manifest`.

- [ ] **Step 1: Write contract test for immutable write**

Test that writing the same final artifact path twice returns a typed `STORAGE` conflict and never overwrites the original bytes.

- [ ] **Step 2: Write crash-safety test**

Monkeypatch the final rename to fail and assert that no final artifact appears and that stale temp data can be identified for cleanup.

- [ ] **Step 3: Implement same-filesystem temp write + flush + atomic replace policy**

Use a sibling temporary file, `flush()`, `os.fsync()`, then atomic rename into a versioned path. Never overwrite an existing immutable artifact.

- [ ] **Step 4: Implement manifest dependency hashes and stale propagation**

A selected upstream artifact change MUST mark descendants stale without deleting previous versions.

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/contract/test_artifact_store_contract.py tests/unit/persistence/test_filesystem_artifacts.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/ports backend/app/adapters/persistence backend/app/domain/runs tests/contract tests/unit/persistence
git commit -m "feat: add immutable artifact persistence"
```

---

### Task 4: Implement run orchestration, leases, Dry Run, review, validation, and freeze

**Files:**
- Create: `backend/app/orchestration/state_machine.py`
- Create: `backend/app/orchestration/leases.py`
- Create: `backend/app/domain/plans/validation.py`
- Create: `backend/app/domain/plans/service.py`
- Create: `backend/app/domain/runs/service.py`
- Create: `tests/unit/orchestration/test_state_machine.py`
- Create: `tests/unit/orchestration/test_leases.py`
- Create: `tests/unit/plans/test_validation.py`
- Create: `tests/integration/test_dry_run_no_mutation.py`

**Interfaces:**
- Produces: deterministic step transitions, plan validation, plan versioning, `dry_run`, `freeze_plan`.

- [ ] **Step 1: Test every allowed and forbidden state transition**

Encode exactly the transition table from the approved design. Forbidden transitions return typed `CONFLICT` errors.

- [ ] **Step 2: Test lease exclusivity and expiry recovery**

Two workers MUST NOT hold the same run-step lease concurrently. Expired lease recovery increments attempt and records recovery provenance.

- [ ] **Step 3: Implement five-action validator**

Implement the exact v1 frame ranges, required parameters, collision/layer rules, selected-asset/hash requirements, and action-specific postconditions from the contracts supplement.

- [ ] **Step 4: Test Dry Run graph cannot reach mutation**

Use a fake Resolve adapter whose mutating methods raise immediately and record invocations. Execute Dry Run and assert:

```python
assert fake_resolve.mutation_calls == []
assert report.resolve_mutations_performed is False
assert plan.status == "DRAFT"
```

- [ ] **Step 5: Test freeze invalidates on semantic edit**

Freeze a valid reviewed plan, edit one semantic decision parameter through the service, and assert a new draft version with no approval record.

- [ ] **Step 6: Run tests**

```bash
python -m pytest tests/unit/orchestration tests/unit/plans tests/integration/test_dry_run_no_mutation.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/orchestration backend/app/domain tests/unit/orchestration tests/unit/plans tests/integration/test_dry_run_no_mutation.py
git commit -m "feat: add deterministic review and dry-run orchestration"
```

---

### Task 5: Add FastAPI v1 resources, idempotency, and SSE

**Files:**
- Create: `backend/app/api/v1/runs.py`
- Create: `backend/app/api/v1/plans.py`
- Create: `backend/app/api/v1/apply.py`
- Create: `backend/app/api/v1/events.py`
- Create: `backend/app/api/idempotency.py`
- Modify: `backend/app/main.py`
- Create: `tests/integration/api/test_v1_contract.py`
- Create: `tests/integration/api/test_idempotency.py`
- Create: `tests/integration/api/test_sse.py`

**Interfaces:**
- Produces: the exact `/v1` HTTP resources and SSE behavior frozen in the contracts supplement.

- [ ] **Step 1: Write API status/error contract tests**

Cover `201`, `202`, `400`, `403`, `404`, `409`, `422`, `424`, `429`, `500`, `503` mappings with `TypedError` bodies only for failures.

- [ ] **Step 2: Write idempotency tests**

Same `Idempotency-Key` + canonical-equivalent request returns the original result; same key + different canonical request returns `409 IDEMPOTENCY_CONFLICT`.

- [ ] **Step 3: Write SSE replay test**

Publish events 1..3, reconnect with `Last-Event-ID: 1`, assert replay of 2 and 3 only. Add a retained-history miss case that emits `SNAPSHOT_REQUIRED` and closes.

- [ ] **Step 4: Implement routers and event store**

State remains authoritative in resources; SSE carries progress/notification only.

- [ ] **Step 5: Run API tests**

```bash
python -m pytest tests/integration/api -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api backend/app/main.py tests/integration/api
git commit -m "feat: add v1 control plane and progress events"
```

---

### Task 6: Implement Apply journaling with a FakeResolveAdapter and prove the complete vertical slice

**Files:**
- Create: `backend/app/ports/resolve.py`
- Create: `backend/app/adapters/resolve/fake.py`
- Create: `backend/app/domain/apply/journal.py`
- Create: `backend/app/domain/apply/service.py`
- Create: `tests/contract/test_resolve_adapter_contract.py`
- Create: `tests/integration/test_fake_vertical_slice.py`
- Create: `tests/integration/test_apply_retry_reconciliation.py`

**Interfaces:**
- Produces: `ResolveAdapter` contract, fake adapter, preflight/duplicate/apply/verify lifecycle, durable operation journal.

- [ ] **Step 1: Write safety contract tests**

Every mutating fake-adapter method MUST reject:

```text
source identity
unregistered target identity
expired or mismatched preflight
wrong apply attempt
```

- [ ] **Step 2: Write first complete vertical-slice test**

Fixture: a deterministic manually seeded `PUNCH_IN` decision. Flow:

```text
create run -> build/validate plan -> review -> freeze -> preflight -> duplicate -> apply -> verify
```

Assert source snapshot is byte-identical before/after; only generated target changes; ApplyReport is `SUCCEEDED`.

- [ ] **Step 3: Write ambiguous-timeout retry test**

Simulate adapter timeout after a mutation may have completed. Retry MUST inspect journal + target postcondition before deciding whether to resume. It MUST NOT blindly replay the mutation.

- [ ] **Step 4: Implement durable before/after operation journal**

Journal each operation ID, precondition, call start, observed result/postcondition, and typed failure. No automatic cleanup after ambiguous failure.

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/contract/test_resolve_adapter_contract.py tests/integration/test_fake_vertical_slice.py tests/integration/test_apply_retry_reconciliation.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/ports/resolve.py backend/app/adapters/resolve backend/app/domain/apply tests/contract/test_resolve_adapter_contract.py tests/integration/test_fake_vertical_slice.py tests/integration/test_apply_retry_reconciliation.py
git commit -m "feat: prove safe apply lifecycle with fake Resolve"
```

---

### Task 7: Enforce client/path isolation and retention-v1

**Files:**
- Create: `backend/app/security/paths.py`
- Create: `backend/app/domain/retention/service.py`
- Create: `tests/security/test_client_isolation.py`
- Create: `tests/security/test_windows_path_aliases.py`
- Create: `tests/unit/retention/test_retention_v1.py`

**Interfaces:**
- Produces: canonical-root validation, client namespace enforcement, retention decision engine and tombstones.

- [ ] **Step 1: Add adversarial path tests**

Cover `..`, case variation, symlink/junction where test environment permits, alternate Windows separators/forms, direct foreign asset ID lookup, foreign cache key, foreign preview/download path.

- [ ] **Step 2: Implement canonical root enforcement**

Access is authorized from logical ownership + canonicalized path under configured root. Knowing a path or ID from another client MUST NOT grant access.

- [ ] **Step 3: Implement retention-v1 policy**

Encode the approved 24h temp/quarantine, 7d unselected remote, 30d non-approved run/cache/log defaults, 90d cloud audit, and never-auto-delete classes. Cleanup creates minimal audit tombstones.

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/security tests/unit/retention -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/security backend/app/domain/retention tests/security tests/unit/retention
git commit -m "feat: enforce client isolation and retention policy"
```

---

### Task 8: Perform the Resolve Studio compatibility spike without mutating the source timeline

**Files:**
- Create: `backend/app/adapters/resolve/davinci.py`
- Create: `backend/app/adapters/resolve/capabilities.py`
- Create: `scripts/resolve_probe.py`
- Create: `tests/contract/test_davinci_capability_mapping.py`
- Create: `docs/resolve/COMPATIBILITY_MATRIX.md`

**Interfaces:**
- Consumes: official Resolve scripting API available on the workstation.
- Produces: persisted `ResolveCapabilities`, stable/compound identity strategy, tolerance facts for the installed build, and a read-only capability matrix.

- [ ] **Step 1: Implement read-only probe first**

Probe project/timeline context, timebase, track/item enumeration, stable identifiers exposed by the installed version, and Workflow Integration availability. No duplicate/import/edit/delete calls are allowed in this step.

- [ ] **Step 2: Record exact installed capability facts**

Update `docs/resolve/COMPATIBILITY_MATRIX.md` with Resolve version, API capability, identity strategy, timebase behavior, title/caption capability, and unsupported operations. Values may be `unsupported`; they may not be guessed.

- [ ] **Step 3: Add isolated disposable-project duplicate test**

Only after the read-only probe passes, exercise timeline duplication in a disposable test project/timeline. Verify source identity rejection and target registration. Do not use production client media.

- [ ] **Step 4: Run adapter contract tests**

```bash
python -m pytest tests/contract/test_resolve_adapter_contract.py tests/contract/test_davinci_capability_mapping.py -v
```

Expected: PASS for supported capabilities; unsupported features are explicit capability negatives, not test skips hiding unknown behavior.

- [ ] **Step 5: Commit**

```bash
git add backend/app/adapters/resolve scripts/resolve_probe.py tests/contract docs/resolve/COMPATIBILITY_MATRIX.md
git commit -m "feat: add Resolve capability probe"
```

---

### Task 9: Prove the first real safe Apply with one PUNCH_IN decision

**Files:**
- Modify: `backend/app/adapters/resolve/davinci.py`
- Create: `tests/manual/README.md`
- Create: `tests/manual/resolve_punch_in_fixture.json`
- Update: `docs/resolve/COMPATIBILITY_MATRIX.md`

**Interfaces:**
- Consumes: approved plan, real `ResolveAdapter`, known capability matrix.
- Produces: first real `Analyze/Review/Approve/Duplicate/Apply/Verify` proof using a manually seeded plan and no AI models.

- [ ] **Step 1: Add only the minimum mutation needed for PUNCH_IN**

Implement against duplicated target items only. Exact transform tolerances come from Task 8 capability findings.

- [ ] **Step 2: Run preflight against a disposable controlled Resolve fixture**

Preflight MUST verify the captured source identity/hash, generated target naming availability, capability matrix version, and active Resolve session before duplication.

- [ ] **Step 3: Execute and verify**

Expected result:

```text
REEL_MASTER unchanged
new REEL_AI_v01 (or collision-safe successor) created
only target timeline receives the expected PUNCH_IN
ApplyReport status SUCCEEDED
verification postcondition satisfied
```

- [ ] **Step 4: Exercise failure cleanup path without automatic deletion**

Create a controlled failed attempt, confirm target remains until an explicit cleanup command is approved, and confirm cleanup refuses ambiguous identity.

- [ ] **Step 5: Run all automated tests**

```bash
python -m pytest -v
```

Expected: PASS.

- [ ] **Step 6: Final plan self-review and PR**

Verify spec coverage for this slice, run `git diff --check`, push the feature branch, and open a PR to `main` describing tests, manual Resolve evidence, unsupported capabilities, and follow-up work. Do not merge autonomously.

---

## Completion / stopping point

This plan is complete when the backend can run independently, Dry Run is demonstrably non-mutating, the fake end-to-end flow is green, client/path isolation tests are green, the installed Resolve build has a factual compatibility matrix, and a manually seeded approved `PUNCH_IN` plan is safely applied only to a generated duplicate timeline.

Do **not** add ASR, forced alignment, Director models, embeddings/reranking, Pexels/Pixabay, stickers, B-roll, editorial inserts, caption emphasis implementation, cloud providers, or the final Resolve panel in this plan. Those are separate implementation plans after the control plane and mutation-safety slice is accepted.
