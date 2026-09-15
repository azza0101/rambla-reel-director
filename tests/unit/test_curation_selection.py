from backend.app.curation_selection import SelectionStore


def test_ordered_mixed_assets_get_deterministic_tracks(tmp_path):
    store = SelectionStore(tmp_path, {"video-a": {"chunk_id": "chunk-1"}, "image-c": {"chunk_id": "chunk-1"}, "video-b": {"chunk_id": "chunk-1"}}, ["chunk-1"])
    row = store.set_chunk_selection("chunk-1", ["video-a", "image-c", "video-b"], no_broll=False)
    assert [(x["asset_id"], x["track"], x["order"]) for x in row["selected_assets"]] == [("video-a", "V2", 0), ("image-c", "V3", 1), ("video-b", "V4", 2)]
