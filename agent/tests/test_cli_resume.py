from bioagent.chats import create_chat, get_chat
from bioagent.cli import resolve_resume
from bioagent.store import UserStore


def test_resolve_resume_none_creates_new_chat(tmp_path):
    st = UserStore(tmp_path, "u").ensure()
    chat, resume, note = resolve_resume(st, None, "m")
    assert resume is None and note == ""
    assert get_chat(st, chat.id) is not None


def test_resolve_resume_chat_id_with_session(tmp_path):
    st = UserStore(tmp_path, "u").ensure()
    c = create_chat(st, model="m", source="cli")
    c.update(session_id="sess-1")
    chat, resume, note = resolve_resume(st, c.id, "m")
    assert chat.id == c.id and resume == "sess-1" and note == ""


def test_resolve_resume_by_session_id(tmp_path):
    """sid 直接给的是 SDK 会话 id（不是对话目录 id），走 find_by_session 命中同一个对话。"""
    st = UserStore(tmp_path, "u").ensure()
    c = create_chat(st, model="m", source="cli")
    c.update(session_id="sess-xyz")
    chat, resume, note = resolve_resume(st, "sess-xyz", "m")
    assert chat.id == c.id and resume == "sess-xyz" and note == ""


def test_resolve_resume_chat_id_without_session_warns(tmp_path):
    """全新对话（或迁移来的 legacy 对话）还没有 session_id：不能拿对话目录 id 当 SDK 会话 id 用。"""
    st = UserStore(tmp_path, "u").ensure()
    c = create_chat(st, model="m", source="cli")
    chat, resume, note = resolve_resume(st, c.id, "m")
    assert chat.id == c.id and resume is None and "还没有可恢复的会话" in note


def test_resolve_resume_unknown_id_creates_new_chat_and_keeps_sid(tmp_path):
    """本地没有任何对话记录这个 id：新建对话目录，但原样把 id 透传给 SDK（可能是 SDK 自己还留着的老会话）。"""
    st = UserStore(tmp_path, "u").ensure()
    chat, resume, note = resolve_resume(st, "sess-does-not-exist", "m")
    assert resume == "sess-does-not-exist" and note == ""
    assert get_chat(st, chat.id) is not None
    assert chat.meta().get("session_id") is None
