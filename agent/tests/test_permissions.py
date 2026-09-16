from pathlib import Path

from bioagent.permissions import Allow, Ask, Deny, decide

RO = [Path("/data/raw")]
CWD = Path("/data")


def d(tool, inp):
    return decide(tool, inp, readonly_dirs=RO, cwd=CWD)


def test_read_tools_allowed():
    assert isinstance(d("Read", {"file_path": "/data/raw/a.tif"}), Allow)
    assert isinstance(d("Grep", {"pattern": "x", "path": "/data/raw"}), Allow)
    assert isinstance(d("Glob", {"pattern": "**/*.py"}), Allow)


def test_write_into_readonly_denied():
    r = d("Write", {"file_path": "/data/raw/new.txt", "content": ""})
    assert isinstance(r, Deny) and "只读" in r.reason
    assert isinstance(d("Edit", {"file_path": "/data/raw/x.py"}), Deny)
    assert isinstance(d("Write", {"file_path": "/data/raw/sub/deep/x.py"}), Deny)


def test_write_elsewhere_allowed():
    assert isinstance(d("Write", {"file_path": "/data/work/out.csv", "content": ""}), Allow)
    assert isinstance(d("Write", {"file_path": "/data/rawer/out.csv", "content": ""}), Allow)


def test_bash_touching_readonly_denied():
    assert isinstance(d("Bash", {"command": "rm -rf /data/raw/LU554"}), Deny)
    assert isinstance(d("Bash", {"command": "echo x > /data/raw/note.txt"}), Deny)
    assert isinstance(d("Bash", {"command": "sed -i 's/a/b/' /data/raw/meta.csv"}), Deny)


def test_bash_reading_readonly_allowed():
    assert isinstance(d("Bash", {"command": "ls /data/raw && head -3 /data/raw/meta.csv"}), Allow)


def test_bash_dangerous_asks():
    r = d("Bash", {"command": "rm -rf /data/work/tmp"})
    assert isinstance(r, Ask) and "rm" in r.summary
    assert isinstance(d("Bash", {"command": "git push origin main"}), Ask)
    assert isinstance(d("Bash", {"command": "pip install foo"}), Ask)
    assert isinstance(d("Bash", {"command": "sudo apt install x"}), Ask)
    assert isinstance(d("Bash", {"command": "cat a > b.txt"}), Ask)


def test_bash_benign_allowed():
    assert isinstance(d("Bash", {"command": "ls -la /data/work && wc -l a.csv"}), Allow)
    assert isinstance(d("Bash", {"command": "python analyze.py 2>&1 | tail"}), Allow)
    assert isinstance(d("Bash", {"command": "grep -r foo . >/dev/null; echo done"}), Allow)


def test_biomni_query_allowed_and_compute_asks():
    assert isinstance(d("mcp__biotools__query_uniprot", {"prompt": "x"}), Allow)
    assert isinstance(d("mcp__biotools__search_protocols", {"q": "x"}), Allow)
    assert isinstance(d("mcp__biotools__annotate_celltype_scRNA", {"path": "a.h5ad"}), Ask)


def test_unknown_tool_asks():
    assert isinstance(d("SomeNewTool", {}), Ask)


def test_other_users_private_dirs_denied():
    others = [Path("/data/bioagent/sessions/lisi"), Path("/data/bioagent/workspace/lisi")]
    dd = lambda tool, inp: decide(tool, inp, readonly_dirs=RO, cwd=CWD, private_dirs=others)  # noqa: E731
    assert isinstance(dd("Read", {"file_path": "/data/bioagent/sessions/lisi/memory.md"}), Deny)
    assert isinstance(dd("Grep", {"pattern": "x", "path": "/data/bioagent/workspace/lisi"}), Deny)
    assert isinstance(dd("Bash", {"command": "cat /data/bioagent/sessions/lisi/memory.md"}), Deny)
    assert isinstance(dd("mcp__biotools__run_python_repl", {"command": "open('/data/bioagent/workspace/lisi/a.csv')"}), Deny)
    # 自己的目录不受影响
    assert isinstance(dd("Read", {"file_path": "/data/bioagent/sessions/zhangsan/memory.md"}), Allow)
    assert isinstance(dd("Write", {"file_path": "/data/bioagent/workspace/zhangsan/out.csv", "content": ""}), Allow)


def test_repl_asks_and_denies_readonly_writes():
    assert isinstance(d("mcp__biotools__run_python_repl", {"command": "import scanpy as sc\nadata = sc.read_h5ad('/data/raw/a.h5ad')"}), Ask)
    r = d("mcp__biotools__run_python_repl", {"command": "df.to_csv('/data/raw/out.csv')"})
    assert isinstance(r, Deny) and "只读" in r.reason
    assert isinstance(d("mcp__biotools__run_python_repl", {"command": "open('/data/raw/x.txt','w').write('a')"}), Deny)
    assert isinstance(d("mcp__biotools__run_python_repl", {"command": "df.to_csv('/data/work/out.csv')"}), Ask)


async def test_can_use_tool_logs_repl_code_and_asks_once():
    from bioagent.permissions import make_can_use_tool
    from bioagent.config import BiomniSettings, ProxySettings, Settings

    s = Settings(root=Path("/x"), assistant_name="a", model="m", cwd=CWD, readonly_dirs=RO,
                 daily_cost_cap_usd=1, api_key="k", proxy=ProxySettings(), biomni=BiomniSettings())
    asked, logged = [], []

    async def confirm(summary):
        asked.append(summary)
        return True

    cb = make_can_use_tool(s, confirm, set(), on_repl_code=logged.append)
    r1 = await cb("mcp__biotools__run_python_repl", {"command": "x = 1"}, None)
    r2 = await cb("mcp__biotools__run_python_repl", {"command": "y = x + 1"}, None)
    assert r1.behavior == "allow" and r2.behavior == "allow"
    assert len(asked) == 1                      # 只确认一次
    assert logged == ["x = 1", "y = x + 1"]     # 两段代码都被记录
    r3 = await cb("mcp__biotools__run_python_repl", {"command": "open('/data/raw/a','w')"}, None)
    assert r3.behavior == "deny" and len(logged) == 2   # 被拒绝的不记录


def test_secret_dir_denied():
    sec = Path("/home/x/.config/bioagent")
    r = decide("Read", {"file_path": "/home/x/.config/bioagent/.env"}, readonly_dirs=RO, cwd=CWD, secret_dirs=[sec])
    assert isinstance(r, Deny)
    r = decide("Bash", {"command": "cat /home/x/.config/bioagent/users.yaml"}, readonly_dirs=RO, cwd=CWD, secret_dirs=[sec])
    assert isinstance(r, Deny)
    r = decide("mcp__biotools__run_python_repl", {"command": "open('/home/x/.config/bioagent/.env').read()"},
               readonly_dirs=RO, cwd=CWD, secret_dirs=[sec])
    assert isinstance(r, Deny)


# ---- 路径归一化后的越权访问（评审 C1）----
def _sec_decide(sec, tool, inp, cwd=CWD):
    return decide(tool, inp, readonly_dirs=RO, cwd=cwd, secret_dirs=[sec])


def test_secret_dir_tilde_and_home_var_denied(tmp_path, monkeypatch):
    """~ / ~user / $HOME / 先 cd 再相对路径，都不能绕过密钥目录检查。"""
    home = tmp_path / "home"
    (home / ".config" / "bioagent").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    sec = home / ".config" / "bioagent"
    for cmd in ("cat ~/.config/bioagent/.env",
                "cat $HOME/.config/bioagent/users.yaml",
                "cat ${HOME}/.config/bioagent/users.yaml",
                "cd ~/.config/bioagent && cat .env",
                "head -1 ~/.config/bioagent/web_secret"):
        assert isinstance(_sec_decide(sec, "Bash", {"command": cmd}), Deny), cmd
    assert isinstance(_sec_decide(sec, "Read", {"file_path": "~/.config/bioagent/.env"}), Deny)
    assert isinstance(_sec_decide(sec, "Grep", {"pattern": "KEY", "path": "$HOME/.config/bioagent"}), Deny)
    assert isinstance(_sec_decide(sec, "mcp__biotools__run_python_repl",
                                  {"command": "print(open('~/.config/bioagent/.env').read())"}), Deny)


def test_relative_path_to_other_user_denied(tmp_path):
    """从对话 outputs 目录用 ../../../../ 爬到另一个账号目录，Read 和 Bash 都要拒。"""
    other = tmp_path / "users" / "langhuan"
    other.mkdir(parents=True)
    cwd = tmp_path / "users" / "zhangsan" / "chats" / "c1" / "outputs"
    cwd.mkdir(parents=True)
    dd = lambda tool, inp: decide(tool, inp, readonly_dirs=RO, cwd=cwd, private_dirs=[other])  # noqa: E731
    assert isinstance(dd("Bash", {"command": "cat ../../../../langhuan/memory.md"}), Deny)
    assert isinstance(dd("Read", {"file_path": "../../../../langhuan/memory.md"}), Deny)
    assert isinstance(dd("Grep", {"pattern": "x", "path": "../../../../langhuan"}), Deny)
    assert isinstance(dd("mcp__biotools__run_python_repl",
                         {"command": "open('../../../../langhuan/memory.md').read()"}), Deny)
    # 自己目录下的相对路径不受影响
    assert isinstance(dd("Read", {"file_path": "notes.md"}), Allow)
    assert isinstance(dd("Bash", {"command": "cat ./out/result.csv"}), Allow)


def test_bash_env_dump_denied():
    """API Key 只在进程环境里，任何形式的环境变量导出都拒绝。"""
    for cmd in ("echo $ANTHROPIC_API_KEY", "cat /proc/self/environ", "printenv", "env",
                "env | grep ANTHROPIC", "cat /proc/1234/environ"):
        assert isinstance(d("Bash", {"command": cmd}), Deny), cmd


def test_bash_secret_filenames_denied():
    for cmd in ("find / -name users.yaml", "cat proxy/mihomo.yaml", "grep -r . .config/bioagent",
                "cat nodes.yaml", "cat web_secret"):
        assert isinstance(d("Bash", {"command": cmd}), Deny), cmd


def test_legit_commands_still_allowed(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    sec = home / ".config" / "bioagent"
    for cmd in ("ls ~/", "python3 script.py", "cat data/x.csv", "wc -l ./out/a.tsv",
                "ls -la", "head -3 /data/raw/meta.csv"):
        assert isinstance(_sec_decide(sec, "Bash", {"command": cmd}), Allow), cmd
    assert isinstance(_sec_decide(sec, "Read", {"file_path": "/data/work/mine.csv"}), Allow)
    assert isinstance(_sec_decide(sec, "Read", {"file_path": str(home / "notes.md")}), Allow)


def test_monitor_follows_bash_rules_and_task_tools_allowed():
    assert isinstance(d("Monitor", {"command": "until [ -f done.flag ]; do sleep 2; done"}), Allow)
    assert isinstance(d("Monitor", {"command": "rm -rf /data/raw/x"}), Deny)
    assert isinstance(d("Monitor", {"command": "cat /home/x/.config/bioagent/.env"}), Deny) or isinstance(
        decide("Monitor", {"command": "cat /home/x/.config/bioagent/.env"}, readonly_dirs=RO, cwd=CWD, secret_dirs=[Path("/home/x/.config/bioagent")]), Deny)
    assert isinstance(d("TaskOutput", {"task_id": "abc"}), Allow) and isinstance(d("TaskStop", {"task_id": "abc"}), Allow)


def test_heredoc_body_not_scanned_for_dangerous_patterns():
    cmd = "python - <<'EOF'\nimport os\nif 3 > 2: print('x')\nos.remove('/tmp/x')\nEOF"
    assert isinstance(d("Bash", {"command": cmd}), Allow)
    # heredoc 之外的重定向/危险命令仍然要确认
    assert isinstance(d("Bash", {"command": "python - <<'EOF'\nprint(1)\nEOF\nrm -f out.txt"}), Ask)
    assert isinstance(d("Bash", {"command": "cat <<'EOF' > out.txt\nhello\nEOF"}), Ask)


import asyncio as _asyncio


def _cb(mode, confirm_answer=True):
    from bioagent.config import BiomniSettings, ProxySettings, Settings
    from bioagent.permissions import make_can_use_tool
    s = Settings(root=Path("/tmp/x"), assistant_name="X", model="m", cwd=Path("/tmp/x/out"), readonly_dirs=RO, daily_cost_cap_usd=1,
                 api_key="k", proxy=ProxySettings(), biomni=BiomniSettings(), user="")
    asked, auto = [], []
    async def confirm(summary): asked.append(summary); return confirm_answer
    cb = make_can_use_tool(s, confirm, set(), mode=lambda: mode, on_auto=auto.append)
    return cb, asked, auto


def _run(cb, tool, inp):
    return type(_asyncio.run(cb(tool, inp, None))).__name__


def test_permission_modes():
    cb, asked, auto = _cb("edits")
    assert _run(cb, "Write", {"file_path": "/tmp/x/out/a.txt", "content": ""}) == "PermissionResultAllow"
    assert _run(cb, "mcp__biotools__run_python_repl", {"command": "print(1)"}) == "PermissionResultAllow" and auto  # 自动放行并记录
    assert _run(cb, "Bash", {"command": "rm -rf build"}) == "PermissionResultAllow" and asked  # 命令仍要问
    cb, asked, auto = _cb("auto")
    assert _run(cb, "Bash", {"command": "sudo apt install x"}) == "PermissionResultAllow" and not asked and auto
    cb, asked, auto = _cb("readonly")
    assert _run(cb, "Write", {"file_path": "/tmp/x/out/a.txt", "content": ""}) == "PermissionResultDeny"
    assert _run(cb, "Bash", {"command": "rm -rf build"}) == "PermissionResultDeny"
    assert _run(cb, "Bash", {"command": "ls -la"}) == "PermissionResultAllow" and not asked
    assert _run(cb, "Read", {"file_path": "/tmp/x/out/a.txt"}) == "PermissionResultAllow"
    cb, asked, auto = _cb("ask", confirm_answer=False)
    assert _run(cb, "Bash", {"command": "rm -rf build"}) == "PermissionResultDeny" and asked
    # 任何模式下硬性拒绝不变
    cb, asked, auto = _cb("auto")
    assert _run(cb, "Write", {"file_path": "/data/raw/x.txt", "content": ""}) == "PermissionResultDeny"
