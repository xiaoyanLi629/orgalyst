import os
from pathlib import Path

import pytest

from bioagent.config import POISON_ENV_VARS, load_settings, scrub_environment


@pytest.fixture(autouse=True)
def _isolate_secrets_dir(tmp_path_factory, monkeypatch):
    # 默认指向一个空目录，避免读到开发机上的真实 ~/.config/bioagent
    monkeypatch.setenv("BIOAGENT_SECRETS_DIR", str(tmp_path_factory.mktemp("nosecrets")))


def write(root: Path, cfg: str, env: str = "ANTHROPIC_API_KEY=sk-test\n"):
    (root / "config.yaml").write_text(cfg)
    (root / ".env").write_text(env)


def test_loads_defaults_and_paths(tmp_path):
    write(tmp_path, "model: claude-sonnet-5\ncwd: /tmp\nreadonly_dirs: [/tmp/ro]\n")
    s = load_settings(tmp_path)
    assert s.model == "claude-sonnet-5"
    assert s.cwd == Path("/tmp")
    assert s.readonly_dirs == [Path("/tmp/ro")]
    assert s.api_key == "sk-test"
    assert s.proxy.port == 17890 and s.proxy.controller_port == 19090
    assert s.proxy.url == "http://127.0.0.1:17890"
    assert s.biomni.python == tmp_path / "biomni" / ".venv" / "bin" / "python"
    assert s.biomni.server == tmp_path / "biomni" / "mcp_server.py"
    assert s.sessions_dir == tmp_path / "users"
    assert s.proxy_dir == tmp_path / "proxy"


def test_missing_key_raises(tmp_path):
    write(tmp_path, "cwd: /tmp\n", env="")
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        load_settings(tmp_path)


def test_secrets_dir_env_takes_precedence(tmp_path, monkeypatch):
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / ".env").write_text("ANTHROPIC_API_KEY=sk-from-secrets\n")
    monkeypatch.setenv("BIOAGENT_SECRETS_DIR", str(secrets))
    write(tmp_path, "cwd: /tmp\n", env="ANTHROPIC_API_KEY=sk-from-project\n")
    s = load_settings(tmp_path)
    assert s.api_key == "sk-from-secrets"
    assert s.secrets_dir == secrets


def test_user_scoped_dirs(tmp_path):
    write(tmp_path, "cwd: /tmp\n")
    s = load_settings(tmp_path)
    # workspace_dir 现在就是当前工作目录（终端版每个对话指向 chats/<id>/outputs），不再按使用者分目录
    assert s.sessions_dir == tmp_path / "users" and s.workspace_dir == Path("/tmp")
    s.user = "zhangsan"
    assert s.sessions_dir == tmp_path / "users" / "zhangsan"
    assert s.workspace_dir == Path("/tmp")


def test_memory_paths_and_other_users(tmp_path):
    write(tmp_path, "cwd: /tmp\nmemory: {max_chars: 100}\n")
    s = load_settings(tmp_path)
    s.user = "zhangsan"
    assert s.memory_file == tmp_path / "users" / "zhangsan" / "memory.md"
    assert s.memory.max_chars == 100 and s.memory.auto_summarize is True
    for u in ("zhangsan", "lisi"):
        (tmp_path / "users" / u).mkdir(parents=True)
    others = {p.name for p in s.other_users_dirs()}
    assert others == {"lisi"} and len(s.other_users_dirs()) == 1


def test_validate_user():
    from bioagent.config import validate_user

    assert validate_user(" li_xy-2 ") == "li_xy-2"
    for bad in ["", "张三", "-abc", "a b", "x" * 33, "../etc"]:
        with pytest.raises(ValueError):
            validate_user(bad)


def test_scrub_environment_removes_relay_and_proxy(monkeypatch):
    for k in POISON_ENV_VARS:
        monkeypatch.setenv(k, "x")
    removed = scrub_environment()
    assert set(removed) == set(POISON_ENV_VARS)
    for k in POISON_ENV_VARS:
        assert k not in os.environ


def test_user_layout_paths(tmp_path):
    from bioagent.config import BiomniSettings, ProxySettings, Settings
    s = Settings(root=tmp_path, assistant_name="X", model="m", cwd=tmp_path, readonly_dirs=[],
                 daily_cost_cap_usd=1, api_key="k", proxy=ProxySettings(), biomni=BiomniSettings(), user="u1")
    assert s.user_dir == tmp_path / "users" / "u1"
    assert s.sessions_dir == s.user_dir and s.memory_file == s.user_dir / "memory.md"
    assert s.store.files_dir == s.user_dir / "files"
    (tmp_path / "users" / "u2").mkdir(parents=True)
    assert s.other_users_dirs() == [tmp_path / "users" / "u2"]
