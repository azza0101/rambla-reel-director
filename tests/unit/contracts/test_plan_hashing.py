from backend.app.contracts.hashing import canonical_sha256, edit_plan_approval_hash
from backend.app.contracts.plans import EditPlan


def _plan_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "id": "00000000-0000-0000-0000-000000000010",
        "run_id": "00000000-0000-0000-0000-000000000011",
        "version": 1,
        "status": "APPROVED",
        "source_timeline_snapshot_ref": "artifacts/timeline.json",
        "source_timeline_hash": "sha256:" + "a" * 64,
        "style_snapshot_ref": "artifacts/style.json",
        "policy_snapshot_ref": "artifacts/policy.json",
        "controls_snapshot": {"preset": "fast"},
        "provider_trace": [],
        "decisions": [],
        "validation": {"valid": True},
        "approval": {
            "actor": "editor@example.test",
            "approved_at": "2026-09-11T12:00:00Z",
            "approved_plan_hash": "sha256:" + "b" * 64,
        },
        "apply_result_ref": "artifacts/apply.json",
        "content_hash": "sha256:" + "c" * 64,
    }


def test_hash_is_key_order_independent() -> None:
    """A key-order-sensitive digest would break equivalent persisted JSON."""
    assert canonical_sha256({"b": 2, "a": 1}) == canonical_sha256({"a": 1, "b": 2})


def test_approval_hash_excludes_only_approval_and_apply_result() -> None:
    """Hashing approval metadata would make an approved plan self-referential."""
    plan = EditPlan.model_validate(_plan_payload())
    changed_approval = plan.model_copy(
        update={"approval": {"actor": "other@example.test", "approved_at": "2026-09-11T12:01:00Z", "approved_plan_hash": "sha256:" + "d" * 64}}
    )
    changed_result = plan.model_copy(update={"apply_result_ref": "artifacts/other-apply.json"})

    assert edit_plan_approval_hash(plan) == edit_plan_approval_hash(changed_approval)
    assert edit_plan_approval_hash(plan) == edit_plan_approval_hash(changed_result)


def test_approval_hash_includes_semantic_plan_content() -> None:
    """Dropping source state from the hash would allow a stale plan to be applied."""
    plan = EditPlan.model_validate(_plan_payload())
    changed_source_hash = plan.model_copy(update={"source_timeline_hash": "sha256:" + "d" * 64})

    assert edit_plan_approval_hash(plan) != edit_plan_approval_hash(changed_source_hash)
