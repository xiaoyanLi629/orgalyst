import re

import pytest

from bioagent.chats import (CHAT_ID_RE, append_event, create_chat, delete_chat, find_by_session,
                            get_chat, list_chats, new_chat_id, read_events)
from bioagent.store import UserStore


def test_new_chat_id_format():
    assert re.match(CHAT_ID_RE, new_chat_id())


def test_create_and_meta(tmp_path):
    st = UserStore(tmp_path, "a").ensure()
    c = create_chat(st, model="claude-opus-5", source="web")
    assert c.dir.parent == st.chats_dir and c.outputs_dir.is_dir()
    m = c.meta()
    assert m["id"] == c.id and m["model"] == "claude-opus-5" and m["source"] == "web"
    assert m["session_id"] is None and m["cost"] == 0 and m["turns"] == 0 and m["title"] == ""
    c.update(title="第一句话", session_id="sid-1", cost=0.5, turns=1)
    assert c.meta()["title"] == "第一句话" and c.meta()["updated"] >= m["updated"]


def test_get_list_delete(tmp_path):
    st = UserStore(tmp_path, "a").ensure()
    c1 = create_chat(st, model="m", source="cli", title="one")
    c2 = create_chat(st, model="m", source="web", title="two")
    c2.update(title="two")
    rows = list_chats(st)
    assert [r["id"] for r in rows] == [c2.id, c1.id]  # 最近更新在前
    assert get_chat(st, c1.id).id == c1.id
    assert get_chat(st, "nope") is None and get_chat(st, "../x") is None
    delete_chat(c1)
    assert get_chat(st, c1.id) is None


def test_delete_chat_not_found(tmp_path):
    """Deleting an already-deleted chat must raise FileNotFoundError."""
    st = UserStore(tmp_path, "a").ensure()
    c = create_chat(st, model="m", source="web")
    delete_chat(c)
    # Second delete should raise FileNotFoundError
    with pytest.raises(FileNotFoundError):
        delete_chat(c)


def test_events_roundtrip(tmp_path):
    st = UserStore(tmp_path, "a").ensure()
    c = create_chat(st, model="m", source="web")
    assert read_events(c) == []
    append_event(c, {"type": "text", "text": "你好"})
    append_event(c, {"type": "tool_use", "name": "Read", "input": {"file_path": "/x"}})
    evs = read_events(c)
    assert len(evs) == 2 and evs[0]["text"] == "你好" and "ts" in evs[0]


def test_find_by_session(tmp_path):
    st = UserStore(tmp_path, "a").ensure()
    c = create_chat(st, model="m", source="cli")
    c.update(session_id="abc")
    assert find_by_session(st, "abc").id == c.id
    assert find_by_session(st, "zzz") is None
