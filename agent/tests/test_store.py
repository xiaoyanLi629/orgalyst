import os
from pathlib import Path

import pytest

from bioagent.store import UserStore, dir_size, list_users, other_user_dirs, safe_join, users_root


def test_layout(tmp_path):
    st = UserStore(tmp_path, "zhangsan")
    st.ensure()
    assert st.dir == tmp_path / "users" / "zhangsan"
    assert st.files_dir.is_dir() and st.chats_dir.is_dir()
    assert st.uploads_dir == st.files_dir / ".uploads"
    assert st.memory_file == st.dir / "memory.md"
    assert st.usage_file == st.dir / "usage.jsonl"
    assert st.history_file == st.dir / ".history"
    assert st.settings_file == st.dir / "settings.yaml"


def test_settings_roundtrip(tmp_path):
    st = UserStore(tmp_path, "a")
    assert st.read_settings() == {}
    st.write_settings({"model": "claude-sonnet-5"})
    assert st.read_settings()["model"] == "claude-sonnet-5"


def test_safe_join(tmp_path):
    base = tmp_path / "files"
    base.mkdir()
    assert safe_join(base, "a/b.txt") == base / "a" / "b.txt"
    assert safe_join(base, "") == base
    assert safe_join(base, "/abs") == base / "abs"
    with pytest.raises(ValueError):
        safe_join(base, "../x")
    with pytest.raises(ValueError):
        safe_join(base, "a/../../x")


def test_safe_join_symlink_escape(tmp_path):
    """Symlinks pointing outside base must be rejected."""
    base = tmp_path / "files"
    base.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    # Create a symlink inside base pointing outside
    link = base / "link"
    os.symlink(outside, link)
    # Attempting to traverse through the escape symlink must raise ValueError
    with pytest.raises(ValueError):
        safe_join(base, "link/secret.txt")
    # But symlinks pointing inside base are OK
    inner_dir = base / "a"
    inner_dir.mkdir()
    inner_link = base / "inner_link"
    os.symlink(inner_dir, inner_link)
    # This should not raise (inner_link points to base/a which is inside base)
    result = safe_join(base, "inner_link/file.txt")
    assert result == base / "inner_link" / "file.txt"


def test_list_and_other_users(tmp_path):
    for u in ("a", "b", ".hidden"):
        (users_root(tmp_path) / u).mkdir(parents=True)
    assert list_users(tmp_path) == ["a", "b"]
    assert other_user_dirs(tmp_path, "a") == [users_root(tmp_path) / "b"]


def test_dir_size(tmp_path):
    (tmp_path / "x").write_bytes(b"12345")
    (tmp_path / "d").mkdir()
    (tmp_path / "d" / "y").write_bytes(b"12")
    assert dir_size(tmp_path) == 7
    assert dir_size(tmp_path / "missing") == 0
