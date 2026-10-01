from backend.app.generic_coverage import derive_topic_queries, merge_unique


def test_topic_queries_are_concrete_then_progressively_broader():
    assert derive_topic_queries("Ancient Egypt tombs and Cairo travel", "")[:2] == ["Ancient Egypt tombs Cairo travel", "Ancient Egypt"]
    assert "sustainable" in " ".join(derive_topic_queries("sustainable green energy", "")).lower()


def test_merge_unique_is_stable_limited_and_reports_shortfall():
    rows=merge_unique([[{"provider_id":"1"},{"provider_id":"2"}],[{"provider_id":"2"},{"provider_id":"3"}]],limit=12)
    assert [r["provider_id"] for r in rows["items"]] == ["1","2","3"]
    assert rows["shortfall"] == 9
