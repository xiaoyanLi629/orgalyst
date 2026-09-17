"""工具权限策略：只读目录保护、危险命令确认、Biomni 计算类工具确认。

decide() 是纯函数，便于测试；make_can_use_tool() 把它接到 Agent SDK 的 can_use_tool 回调上。
"""
from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable


@dataclass
class Allow:
    pass


@dataclass
class Deny:
    reason: str


@dataclass
class Ask:
    summary: str


Decision = Allow | Deny | Ask

READ_TOOLS = {"Read", "Grep", "Glob", "LS", "WebSearch", "WebFetch", "TodoWrite", "Task", "TaskOutput", "TaskStop", "Skill", "TaskCreate", "TaskUpdate", "TaskList", "TaskGet"}
# Monitor 是"反复执行一段 shell 直到退出"，按 Bash 的规则审查它的 command
SHELL_TOOLS = {"Bash", "Monitor"}
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

# 需要用户确认的命令模式（标签, 正则）
DANGEROUS: list[tuple[str, str]] = [
    ("rm 删除", r"\brm\b"),
    ("mv 移动/重命名", r"\bmv\b"),
    ("git push", r"\bgit\s+push\b"),
    ("安装软件包", r"\b(pip|pip3|conda|mamba|micromamba|apt|apt-get|npm|cargo|brew)\s+install\b|\buv\s+pip\s+install\b"),
    ("改权限/属主", r"\bchmod\b|\bchown\b"),
    ("sudo", r"\bsudo\b"),
    ("杀进程", r"\bkill\b|\bpkill\b|\bkillall\b"),
    ("磁盘操作", r"\bdd\b|\bmkfs\b"),
]
# 会修改文件系统的命令；与只读目录同时出现即拒绝
MUTATING_VERBS = r"\b(rm|mv|tee|truncate|chmod|chown|rmdir|mkdir|touch|sed\s+-i|perl\s+-i|shred)\b"
# 输出重定向目标（排除 2>&1 这类 fd 复制）
REDIRECT_TARGET = re.compile(r"(?<![0-9&])>{1,2}\s*([^\s;&|]+)")
# 常驻 Python REPL：代码会被记录到 workspace/repl_*.py 以便复现
REPL_TOOL = "mcp__biotools__run_python_repl"
# REPL 代码里的写入/删除操作（与只读目录同时出现即拒绝）
PY_MUTATING = (
    r"open\([^)]*[\"'](w|a|x)[\"']|\.to_csv\(|\.to_parquet\(|\.to_excel\(|\.save\(|\.write\(|savefig\(|"
    r"os\.remove|os\.unlink|os\.rename|os\.rmdir|shutil\.(rmtree|move|copy)|Path\([^)]*\)\.(unlink|write_|rename)"
)
# Bash 里直接掏环境/密钥的写法。字符串检查挡不住所有变形（见 README 已知问题），
# 但顺手的几种必须挡住：API Key 只存在于进程环境里，dump 一次就全泄了。
SECRET_PATTERNS: list[tuple[str, str]] = [
    ("导出环境变量", r"\benv\b|\bprintenv\b"),
    ("读取进程环境", r"/proc/[^ ]*/environ"),
    ("API Key", r"ANTHROPIC_API_KEY"),
    ("密钥目录", r"\.config/bioagent"),
    ("密钥/账号文件", r"mihomo\.yaml|nodes\.yaml|users\.yaml|web_secret"),
]
# $HOME / ${HOME}：只展开 HOME，不用 expandvars（免得把别的环境变量塞进路径里）
HOME_RE = re.compile(r"\$\{HOME\}|\$HOME\b")
# REPL 代码里的字符串字面量（引号之间的内容）
PY_STRING_RE = re.compile(r"""['"]([^'"\n]*)['"]""")
# 只读/查询类 Biomni 工具前缀，直接放行
BIOMNI_READONLY_PREFIXES = (
    "query_", "search_", "get_", "list_", "read_", "fetch_", "extract_", "find_", "blast_", "align_",
    "advanced_web_search", "region_to_",
)


def _path_in_readonly(p: str | None, readonly_dirs: list[Path]) -> Path | None:
    if not p:
        return None
    rp = Path(p).expanduser()
    if not rp.is_absolute():
        return None
    rp = Path(rp.as_posix())  # 不 resolve：目标可能不存在
    for d in readonly_dirs:
        if rp == d or d in rp.parents:
            return d
    return None


def _mentions_readonly(text: str, readonly_dirs: list[Path]) -> Path | None:
    for d in readonly_dirs:
        if str(d) in text:
            return d
    return None


HEREDOC_RE = re.compile(r"(<<-?\s*['\"]?(\w+)['\"]?)([^\n]*\n)(.*?)(?:^\2\s*$|\Z)", re.S | re.M)


def _strip_heredocs(cmd: str) -> str:
    """去掉 heredoc 正文（<<'EOF' … EOF），保留 shell 命令部分。"""
    # 保留同一行里 heredoc 之后的部分（如 <<EOF > out.txt 的重定向），只丢掉正文
    return HEREDOC_RE.sub(lambda m: m.group(1) + m.group(3) + "HEREDOC\n", cmd)


def _has_overwrite_redirect(cmd: str) -> bool:
    return any(t != "/dev/null" for t in REDIRECT_TARGET.findall(cmd))


def _expand(token: str) -> str:
    """展开 ~ / ~user / $HOME / ${HOME}。"""
    t = HOME_RE.sub(lambda _m: os.path.expanduser("~"), token)
    try:
        return os.path.expanduser(t)
    except Exception:  # noqa: BLE001  展开失败（用户名不存在等）就按原样比
        return t


def _looks_like_path(tok: str) -> bool:
    return tok.startswith(("/", "./", "../", "~")) or "/" in tok or bool(HOME_RE.match(tok))


def _shell_tokens(cmd: str) -> list[str]:
    try:
        return shlex.split(cmd)
    except ValueError:
        return cmd.split()


def _candidate_paths(tool: str, tool_input: dict[str, Any], cwd: Path) -> list[str]:
    """把工具参数里所有像路径的东西，归一化成绝对路径候选。

    子串匹配挡不住 ~、$HOME 和相对路径（评审 C1）：真正判断包含关系前必须先展开再拼 cwd。
    """
    toks: list[str] = [v for v in tool_input.values() if isinstance(v, str)]
    if tool in SHELL_TOOLS:
        toks += _shell_tokens(str(tool_input.get("command", "")))
    elif tool == REPL_TOOL:
        toks += PY_STRING_RE.findall(str(tool_input.get("command", "")))
    out: list[str] = []
    for tok in toks:
        if not tok or not _looks_like_path(tok):
            continue
        t = _expand(tok)
        out.append(os.path.normpath(t if os.path.isabs(t) else os.path.join(str(cwd), t)))
    return out


def _within(cand: str, base: Path) -> bool:
    """cand 等于 base 或在 base 之下；路径存在时再按 realpath 比一遍（软链接绕行）。"""
    b = os.path.normpath(str(base))
    if cand == b or cand.startswith(b + os.sep):
        return True
    rc, rb = os.path.realpath(cand), os.path.realpath(b)
    return rc == rb or rc.startswith(rb + os.sep)


def _touches_private(tool: str, tool_input: dict[str, Any], private_dirs: list[Path], cwd: Path) -> Path | None:
    """任何工具的任何参数里出现其他使用者/密钥的私有目录路径，都算触碰。"""
    if not private_dirs:
        return None
    blob = " ".join(str(v) for v in tool_input.values())
    cands = _candidate_paths(tool, tool_input, cwd)
    for d in private_dirs:
        if str(d) in blob:
            return d
        # Read/Write 类的绝对路径按父目录判断
        for v in tool_input.values():
            if isinstance(v, str) and v.startswith("/"):
                p = Path(v)
                if p == d or d in p.parents:
                    return d
        for c in cands:
            if _within(c, d):
                return d
    return None


# 自写图像分割/形态测量代码的特征：Orgalyst 已提供这些能力，助手绕过工具自己算会破坏可复现性（技术报告第 8 节记录的越界行为）。
# 命中即 Deny（任何确认方式下都拒绝），提示改用 mcp__orgalyst__ 工具。
CODE_GUARDS = [
    ("图像阈值分割", r"threshold_(otsu|li|yen|triangle|local|sauvola|niblack)\b|cv2\.(threshold|adaptiveThreshold|findContours|connectedComponents\w*|watershed)|skimage\.segmentation|\bwatershed\(|\bfelzenszwalb\(|\bslic\("),
    ("自行调用分割模型", r"from cellpose|import cellpose|models\.(Cellpose|CellposeModel)\(|\bYOLO\(|ultralytics"),
    ("自行做实例测量", r"\bregionprops(_table)?\(|\blabel\(\s*\w*\s*>\s*|binary_fill_holes|remove_small_objects|\bmorphology\.(opening|closing|dilation|erosion)\("),
]
CODE_GUARD_TOOLS = {"Bash", "Write", "Edit", "NotebookEdit"}

def _code_guard_hit(tool: str, tool_input: dict) -> str | None:
    if tool not in CODE_GUARD_TOOLS and tool != REPL_TOOL:
        return None
    text = " ".join(str(v) for k, v in tool_input.items() if k in ("command", "content", "new_string", "new_source", "code"))
    for label, pat in CODE_GUARDS:
        if re.search(pat, text):
            return label
    return None


def decide(
    tool: str,
    tool_input: dict[str, Any],
    *,
    readonly_dirs: list[Path],
    cwd: Path,
    private_dirs: list[Path] | None = None,
    secret_dirs: list[Path] | None = None,
) -> Decision:
    # -1) 密钥目录（API Key、账号文件）：任何工具任何参数提及都拒绝
    hit = _touches_private(tool, tool_input, secret_dirs or [], cwd)
    if hit:
        return Deny(f"{hit} 是密钥目录，禁止访问")

    # 0) 其他使用者的私有目录（记忆、会话、输出）：读写一律拒绝，不靠模型自觉
    hit = _touches_private(tool, tool_input, private_dirs or [], cwd)
    if hit:
        return Deny(f"{hit} 属于其他使用者，禁止访问")

    # 0.5) 自写分割/测量代码：硬拦截，改用 Orgalyst 工具
    g = _code_guard_hit(tool, tool_input)
    if g:
        return Deny(f"检测到{g}代码。类器官的分割、计数与形态测量必须通过 mcp__orgalyst__ 工具完成（analyze_images / count_organoids），不要自己写分割代码；工具失败时如实报告失败，不要自行补救")

    if tool in READ_TOOLS:
        return Allow()

    if tool in WRITE_TOOLS:
        target = tool_input.get("file_path") or tool_input.get("notebook_path")
        hit = _path_in_readonly(target, readonly_dirs)
        return Deny(f"{hit} 是只读的原始数据目录，禁止写入") if hit else Allow()

    if tool in SHELL_TOOLS:
        cmd = str(tool_input.get("command", ""))
        # 0) 环境变量/密钥文件：先于一切判断
        for label, pat in SECRET_PATTERNS:
            if re.search(pat, cmd):
                return Deny(f"命令涉及{label}，禁止")
        # 1) 重定向写入只读目录
        for t in REDIRECT_TARGET.findall(cmd):
            if _path_in_readonly(t, readonly_dirs):
                return Deny(f"命令把输出写入只读目录 {t}，禁止")
        # 2) 修改类命令同时提及只读目录
        hit = _mentions_readonly(cmd, readonly_dirs)
        if hit and re.search(MUTATING_VERBS, cmd):
            return Deny(f"命令涉及只读目录 {hit} 的修改，禁止")
        if hit and re.search(r"\bcp\b", cmd):
            return Ask(f"cp 涉及只读目录 {hit}: {cmd[:160]}")
        # 3) 危险但允许确认的操作（只看 shell 本身，不看 heredoc 里的脚本正文：python - <<'EOF' 里的 > 不是重定向）
        shell_only = _strip_heredocs(cmd)
        if _has_overwrite_redirect(shell_only):
            return Ask(f"> 覆盖写文件: {cmd[:160]}")
        for label, pat in DANGEROUS:
            if re.search(pat, shell_only):
                return Ask(f"{label}: {cmd[:160]}")
        return Allow()

    if tool == REPL_TOOL:
        code = str(tool_input.get("command", ""))
        hit = _mentions_readonly(code, readonly_dirs)
        if hit and re.search(PY_MUTATING, code):
            return Deny(f"REPL 代码涉及只读目录 {hit} 的写入/删除，禁止")
        return Ask("常驻 Python REPL（本会话内确认一次）")

    if tool.startswith("mcp__biotools__"):
        name = tool.removeprefix("mcp__biotools__")
        if name.startswith(BIOMNI_READONLY_PREFIXES):
            return Allow()
        return Ask(f"计算类工具 {name}")

    return Ask(tool)


PERMISSION_MODES = {  # 由严到宽
    "readonly": "只读文件",
    "ask": "每步确认",
    "edits": "确认命令",
    "auto": "自动允许",
}


def make_can_use_tool(
    settings,
    confirm: Callable[[str], Awaitable[bool]],
    session_allow: set[str],
    on_repl_code: Callable[[str], None] | None = None,
    mode: Callable[[], str] | None = None,
    on_auto: Callable[[str], None] | None = None,
):
    """生成 Agent SDK 的 can_use_tool 回调。

    - decide() 给出的 Deny 在任何模式下都拒绝（原始数据、密钥、他人目录）。
    - mode() 返回本对话的确认方式（PERMISSION_MODES 的键，每次询问时读取，改了即时生效）：
        ask       所有 Ask 都问使用者
        edits     改文件 / REPL / 工具库工具自动放行，只有危险的命令行操作（rm、安装、sudo…）才问
        auto      所有 Ask 自动放行
        readonly  所有 Ask 一律拒绝，改文件类工具也拒绝（尽力而为的只读模式）
    - 自动放行时调用 on_auto(summary)，供界面记录"已自动允许"。
    - 计算类工具（含 REPL）确认一次后本会话内放行。
    - 每段被放行的 REPL 代码交给 on_repl_code 记录（不靠模型自觉，由门卫强制留档）。
    """
    from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

    def _allow(tool: str, tool_input: dict[str, Any]):
        if tool == REPL_TOOL and on_repl_code:
            on_repl_code(str(tool_input.get("command", "")))
        return PermissionResultAllow()

    async def can_use_tool(tool: str, tool_input: dict[str, Any], context):
        dec = decide(
            tool, tool_input,
            readonly_dirs=settings.readonly_dirs, cwd=settings.cwd,
            private_dirs=settings.other_users_dirs() if settings.user else [],
            secret_dirs=[settings.secrets_dir],
        )
        if isinstance(dec, Deny):
            return PermissionResultDeny(message=dec.reason)
        m = (mode() if mode else "ask") or "ask"
        if m == "readonly" and (tool in WRITE_TOOLS or isinstance(dec, Ask)):
            return PermissionResultDeny(message="只读模式：本对话不允许修改文件、安装或执行有副作用的操作；需要时把确认方式改为其他档")
        if isinstance(dec, Allow):
            return _allow(tool, tool_input)
        if tool in session_allow:
            return _allow(tool, tool_input)
        shell_ask = tool in SHELL_TOOLS
        if m == "auto" or (m == "edits" and not shell_ask):
            if on_auto:
                on_auto(dec.summary)
            if tool.startswith("mcp__biotools__"):
                session_allow.add(tool)
            return _allow(tool, tool_input)
        ok = await confirm(dec.summary)
        if ok and tool.startswith("mcp__biotools__"):
            session_allow.add(tool)
        return _allow(tool, tool_input) if ok else PermissionResultDeny(message="用户拒绝了该操作")

    return can_use_tool
