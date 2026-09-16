from bioagent.sessions import SessionIndex


def test_upsert_and_order(tmp_path):
    idx = SessionIndex(tmp_path / "index.json")
    idx.upsert("a", title="first", cwd="/x", model="m", cost=0.1)
    idx.upsert("b", title="second", cwd="/x", model="m", cost=0.2)
    idx.upsert("a", title="first", cwd="/x", model="m", cost=0.5)
    rows = idx.list()
    assert [r["session_id"] for r in rows] == ["a", "b"]
    assert rows[0]["cost"] == 0.5 and idx.latest_id() == "a"
    # 重新加载仍然一致
    again = SessionIndex(tmp_path / "index.json")
    assert again.latest_id() == "a" and len(again.list()) == 2


def test_empty_index(tmp_path):
    idx = SessionIndex(tmp_path / "index.json")
    assert idx.list() == [] and idx.latest_id() is None
