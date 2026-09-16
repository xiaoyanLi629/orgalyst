"""入口：启动顺序（清环境 → 读配置 → 代理 → API 检查 → Agent）、REPL、斜杠命令、退出清理。"""
from __future__ import annotations

import argparse
import sys
import asyncio
import os
import signal
import threading
import time
from pathlib import Path

from bioagent import __version__
from bioagent.agent import Agent
from bioagent.chats import Chat, create_chat, find_by_session, get_chat, list_chats
from bioagent.commands import HELP, parse_command
from bioagent.modules import COUNT as COUNT_, LABEL, MODULES, describe, full as full_, normalize, short
from bioagent.config import Settings, load_settings, scrub_environment, validate_user
from bioagent.usage import UsageLog, check_limits, load_limits
from bioagent.permissions import make_can_use_tool
from bioagent.proxy import ProxyManager
from bioagent.sessions import SessionIndex
from bioagent.ui import UI

ROOT = Path(__file__).resolve().parents[1]


def read_memory(s: Settings) -> str:
    """读取当前使用者的记忆文件（超长则截断，避免撑大 system prompt）。"""
    if not (s.memory.enabled and s.user and s.memory_file.exists()):
        return ""
    text = s.memory_file.read_text().strip()
    if len(text) > s.memory.max_chars:
        text = text[: s.memory.max_chars] + "\n…（记忆过长已截断，请精简 memory.md）"
    return text


def build_system_prompt(s: Settings) -> str:
    project_file = s.root / "BIOAGENT.md"
    project = project_file.read_text() if project_file.exists() else "（暂无项目说明）"
    ro = "\n".join(f"- {d}" for d in s.readonly_dirs) or "- （无）"
    who = f"当前使用者：{s.user}。" if s.user else ""
    memory_section = ""
    if s.memory.enabled and s.user:
        mem = read_memory(s) or "（还没有记忆）"
        memory_section = f"""
# 你对使用者 {s.user} 的长期记忆
记忆文件：{s.memory_file}（只属于这位使用者；其他使用者的 sessions/ 与 workspace/ 目录禁止访问）。
维护规则：
- 使用者说"记住…"，或对话中出现值得长期保留的信息（在做什么项目、进展到哪一步、关键文件路径、方法选择、个人偏好），用 Edit 或 Write 更新记忆文件。
- 写成简短要点，每条带日期（YYYY-MM-DD），同一事项更新而不是重复追加；总长度控制在 {s.memory.max_chars} 字以内，过时内容删掉。
- 不要把大段结果、数据表或代码写进记忆，只写结论和去哪里找。
- 记忆文件不存在时先创建。
当前记忆内容：
{mem}
"""
    return f"""你是 {s.assistant_name}，运行在实验室 Linux 服务器上的生物医学研究助理。用中文回答，专业术语保留英文。{who}
你可以读写文件、执行命令、调用工具库（名字以 mcp__biotools__ 开头）查询生物数据库、检索文献、做单细胞与分子生物学分析。
接到任务先规划：凡是需要两步以上的任务，第一步必须先用 TaskCreate 把任务拆成 3–8 个子任务（subject 用中文动宾短语，按执行顺序逐个创建），并用一两句话告诉使用者你打算怎么做；然后逐个执行：开始一个子任务前用 TaskUpdate 把它标为 in_progress，做完立即标为 completed（同一时间只有一个 in_progress）；全部完成后对照清单简要汇报哪些完成、哪些没做到。一句话能答的简单问题不用规划。
给结论时说明数据来源；不确定就明确说不确定，不要编造。
生成的文件默认放在当前对话目录 {s.cwd}，除非用户指定别处。
每次调用 Bash 都要填 description 参数：用不超过 15 个字的中文说明这一步在做什么（例如"检查中文字体是否可用"），界面会把它显示给使用者，使用者不懂命令行。
耗时命令（安装、下载、训练）用 Bash 的 run_in_background 启动；等待结束不要用 sleep 串联，而是再开一个 run_in_background 的 `until <条件>; do sleep 2; done`，或用 Monitor 工具盯日志，完成后用 Read 看输出文件。
下载 GitHub、Hugging Face 的文件直接用 curl/wget/huggingface_hub 即可（这些域名已走加速通道）；pip 已配置国内镜像。使用者上传的数据在 {s.store.files_dir if s.user else '（无）'}，分析时先到那里找文件。
数据库查询工具（mcp__biotools__query_*）返回 success=false 时：先换措辞重试一次，再用 endpoint 参数给出准确网址，仍不行就用 Python 直接调该库的公开 API。
以下目录是原始数据，只读，绝不修改或删除：
{ro}

# 研究流程 skill（固定套路，保证不同人不同时间做法一致）
做文献综述用 literature-review；做一个主题的系统调研先用 research 建提纲、最后用 research-report 汇总成报告；写学术文稿用 scientific-writing；整理引用用 citation-management。有对应 skill 的任务必须先调用 Skill 工具读取它的流程再动手，不要自行发挥。

# 工具库模块（按需加载，减少每轮开销）
{describe(s.biomni.modules, s.biomni.all_modules) if s.biomni.enabled else '（工具库未启用）'}
任务需要未加载的模块时，不要自己想办法绕过：明确告诉使用者"需要开启 X 模块"，网页在右上角"工具模块"面板勾选，终端用 /modules 命令；开启后会自动重新接入，对话不中断。

# 项目背景
{project}
{memory_section}"""


SUMMARIZE_PROMPT = (
    "本次会话即将结束。请把这次对话中值得长期记住的信息（做了什么项目、进展到哪一步、产出文件的路径、"
    "方法或参数的选择、使用者的偏好）合并进记忆文件 {path}：用 Edit 或 Write 更新，保持要点式、带日期、"
    "不超过 {max_chars} 字，已有条目按需更新而非重复。若本次没有值得记的内容就不要改文件。"
    "最后只回复一行：'记忆已更新' 或 '无需更新'。"
)


class ReplLogger:
    """把每段送进 Biomni REPL 的代码按顺序追加到 workspace/repl_<时间>_<会话>.py，供事后整段重跑。"""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.path: Path | None = None
        self.n = 0
        self.session_id: str | None = None

    def start(self, resume: str | None = None) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        suffix = f"_{resume[:8]}" if resume else ""
        self.path = self.workspace / f"repl_{stamp}{suffix}.py"
        self.n = 0
        self.session_id = resume

    def set_session(self, session_id: str | None) -> None:
        if session_id and self.path and self.session_id != session_id:
            self.session_id = session_id
            with open(self.path, "a") as f:
                f.write(f"# bioagent session {session_id}\n")

    def log(self, code: str) -> None:
        if not self.path:
            self.start()
        self.n += 1
        with open(self.path, "a") as f:
            f.write(f"\n# ---- REPL step {self.n} · {time.strftime('%H:%M:%S')} ----\n{code.rstrip()}\n")


def resolve_resume(store, sid: str | None, model: str) -> tuple[Chat, str | None, str]:
    """决定用哪个对话目录、以及传给 SDK 的 resume 参数。返回 (chat, sdk_resume_id, note)。

    - sid 为空：新建对话，(chat, None, "")。
    - sid 命中已有对话且该对话已有 session_id：(chat, session_id, "")——SDK 用真正的会话 id 恢复。
    - sid 命中已有对话但还没有 session_id（刚建的新对话，或迁移脚本生成的 legacy 对话）：
      对话目录 id 不是 SDK 会话 id，不能拿来传给 SDK，(chat, None, 提示文案)，在该对话目录里开新会话。
    - sid 未命中任何本地对话：新建对话，sid 原样透传给 SDK（可能是本地没有记录、但 SDK 自己还留着的老会话）。
    """
    if not sid:
        return create_chat(store, model=model, source="cli"), None, ""
    chat = get_chat(store, sid) or find_by_session(store, sid)
    if chat is None:
        return create_chat(store, model=model, source="cli"), sid, ""
    session_id = chat.meta().get("session_id")
    if session_id:
        return chat, session_id, ""
    return chat, None, "此对话还没有可恢复的会话，在该对话目录开始新会话"


chat_ref: dict = {}  # 终端版当前对话（供确认回调读取本对话的确认方式）


def _new_agent(s: Settings, pm: ProxyManager, ui: UI, session_allow: set[str], repl_log: ReplLogger, resume: str | None = None) -> Agent:
    proxy_env = pm.env if s.proxy.enabled else {}
    repl_log.workspace = s.cwd
    repl_log.start(resume)
    def mode() -> str:
        c = chat_ref.get("chat")
        return (c.meta().get("permission_mode") if c else None) or s.store.read_settings().get("permission_mode") or "ask"

    cb = make_can_use_tool(s, ui.confirm, session_allow, on_repl_code=repl_log.log, mode=mode,
                           on_auto=lambda summary: ui.info(f"自动允许：{summary[:100]}"))
    return Agent(s, proxy_env, cb, build_system_prompt(s), resume=resume)


async def run(args) -> int:
    scrub_environment()
    s = load_settings(ROOT)
    if args.model:
        s.model = args.model
    if args.cwd:
        s.cwd = Path(args.cwd).expanduser()
    if not args.check:
        try:
            s.user = validate_user(args.user or os.environ.get("BIOAGENT_USER", ""))
        except ValueError as e:
            print(f"必须指定使用者：./bioagent.sh --user <你的名字>（或设置环境变量 BIOAGENT_USER）。{e}")
            return 2
        from bioagent.web.auth import Accounts
        acc = Accounts(s.secrets_dir / "users.yaml")
        if acc.load()["users"]:
            u = acc.get(s.user)
            if not u or not u.get("enabled", True):
                print(f"账号 {s.user} 未开设或已停用，请联系管理员（--web-admin add {s.user}）")
                return 2
    if not args.check:
        s.store.ensure()
    # ---- 用量与上限（按账号）----
    usage_log = UsageLog(s.sessions_dir / "usage.jsonl")
    limits = load_limits(s.secrets_dir / "users.yaml")
    over_limit = False
    if not args.check:
        ok, msg = check_limits(usage_log, s.user, limits)
        if not ok:
            print(f"无法进入：{msg}")
            return 3
    ui = UI(s.assistant_name, s.sessions_dir / ".history")
    pm = ProxyManager(s)

    # ---- 代理与 API ----
    if s.proxy.enabled:
        try:
            started = pm.ensure_running()
        except RuntimeError as e:
            ui.warn(str(e))
            return 2
        ok, why = pm.health_check()
        if not ok:
            ui.warn(f"API 不可达：{why}")
            ui.table("节点延迟(ms)", [{"节点": k, "延迟": v} for k, v in pm.node_delays().items()])
            pm.stop()
            return 2
        pm.register_session()
        ui.info(f"代理就绪（{'新启动' if started else '复用'}），API 连通")
    if args.check:
        ui.info("工具库 MCP: " + ("已配置" if s.biomni.server.exists() and s.biomni.python.exists() else "未安装（将无工具库）"))
        if s.proxy.enabled:
            pm.unregister_session_and_maybe_stop()
        return 0

    # ---- Agent ----
    idx = SessionIndex(s.sessions_dir / "index.json")
    resume: str | None = None
    if args.resume is not None:
        resume = args.resume or idx.latest_id()
        if not resume:
            ui.warn("没有可恢复的会话，开始新会话")
    chat, resume, note = resolve_resume(s.store, resume, s.model)
    chat_ref["chat"] = chat
    if note:
        ui.warn(note)
    if not args.cwd:
        s.cwd = chat.outputs_dir
    s.biomni.all_modules = list(s.biomni.modules)
    picked = chat.meta().get("modules") or s.biomni.default_modules
    s.biomni.modules = normalize(picked, s.biomni.all_modules) if picked else list(s.biomni.all_modules)
    session_allow: set[str] = set()
    repl_log = ReplLogger(s.cwd)
    agent = _new_agent(s, pm, ui, session_allow, repl_log, resume)
    try:
        await agent.start()
    except Exception as e:
        ui.warn(f"Agent 启动失败：{e!r}")
        if s.proxy.enabled:
            pm.unregister_session_and_maybe_stop()
        return 3
    biomni_note = "工具库已接入" if agent.has_biomni else "无工具库"
    mem_note = f"记忆 {len(read_memory(s))} 字" if s.memory.enabled else "无记忆"
    ui.set_status(model=s.model, context_tokens=0, context_window=agent.context_window)
    ui.info(f"{s.assistant_name} v{__version__} 就绪 · 使用者 {s.user} · 模型 {s.model} · 目录 {s.cwd} · {biomni_note} · {mem_note} · /help 看命令")
    first_prompt: str | None = None
    turns = 0

    async def summarize_memory() -> None:
        """会话结束前让 agent 把要点合并进记忆文件（可在 config.yaml 关闭）。"""
        if not (s.memory.enabled and s.memory.auto_summarize and turns > 0):
            return
        ui.info("正在把本次会话要点合并进记忆…")
        try:
            await ui.render(agent.send(SUMMARIZE_PROMPT.format(path=s.memory_file, max_chars=s.memory.max_chars)))
        except Exception as e:
            ui.warn(f"记忆总结失败：{e!r}")

    # 终端断开（SIGHUP）或被 kill（SIGTERM）时：取消主任务 → 走 finally 清理（关 Agent、停代理），不留孤儿进程
    main_task = asyncio.current_task()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGHUP, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: main_task and main_task.cancel())
        except (NotImplementedError, RuntimeError):
            pass

    try:
        while True:
            try:
                text = (await ui.prompt()).strip()
            except (EOFError, KeyboardInterrupt, asyncio.CancelledError):
                break
            if not text:
                continue
            cmd = parse_command(text)
            if not cmd and agent.context_full:
                ui.warn("这个对话的上下文已满，请用 /new 开新对话（要点会自动写入记忆）")
                continue
            if not cmd and over_limit:
                ui.warn(f"已达用量上限，不再接受新任务：{check_limits(usage_log, s.user, limits)[1]}")
                continue
            if cmd:
                if cmd.name == "quit":
                    await summarize_memory()
                    break
                elif cmd.name == "help":
                    ui.info(HELP)
                elif cmd.name == "auto":
                    from bioagent.permissions import PERMISSION_MODES
                    arg = {"on": "auto", "off": "ask"}.get(cmd.arg, cmd.arg)
                    if arg in PERMISSION_MODES:
                        chat.update(permission_mode=arg)
                    elif arg:
                        ui.warn("可选：" + " ".join(f"{k}({v})" for k, v in PERMISSION_MODES.items()))
                    cur = chat.meta().get("permission_mode") or s.store.read_settings().get("permission_mode") or "ask"
                    ui.info(f"本对话确认方式：{PERMISSION_MODES[cur]}（{cur}）  用法：/auto ask|edits|auto|readonly")
                elif cmd.name == "modules":
                    if not cmd.arg:
                        ui.table("工具库模块", [{"模块": n, "名称": LABEL[n], "工具数": COUNT_[n], "状态": "已加载" if full_(n) in s.biomni.modules else ""}
                                            for n, _, _ in MODULES if full_(n) in s.biomni.all_modules])
                        ui.info("用法：/modules 模块1,模块2 …（重新接入工具库，对话不中断）；/modules all 加载全部")
                    else:
                        want = s.biomni.all_modules if cmd.arg.strip() == "all" else [x.strip() for x in cmd.arg.split(",") if x.strip()]
                        mods = normalize(want, s.biomni.all_modules)
                        if not mods:
                            ui.warn("没有识别到有效的模块名，/modules 查看列表")
                            continue
                        s.biomni.modules = mods
                        chat.update(modules=[short(m) for m in mods])
                        sid = agent.session_id
                        await agent.close()
                        agent = _new_agent(s, pm, ui, session_allow, repl_log, resume=sid)
                        await agent.start()
                        ui.info("已加载：" + "、".join(LABEL[short(m)] for m in mods))
                elif cmd.name == "memory":
                    if cmd.arg == "clear":
                        if await ui.confirm(f"清空记忆文件 {s.memory_file}"):
                            s.memory_file.write_text("")
                            ui.info("记忆已清空（下个新会话生效）")
                    else:
                        ui.info(f"记忆文件 {s.memory_file}")
                        ui.console.print(read_memory(s) or "(空)")
                elif cmd.name == "new":
                    await summarize_memory()
                    await agent.close()
                    chat = create_chat(s.store, model=s.model, source="cli")
                    chat_ref["chat"] = chat
                    if not args.cwd:
                        s.cwd = chat.outputs_dir
                    agent = _new_agent(s, pm, ui, session_allow, repl_log)
                    await agent.start()
                    first_prompt = None
                    turns = 0
                    ui.set_status(context_tokens=0)
                    ui.info("已开始新会话（记忆已重新加载）")
                elif cmd.name == "resume":
                    sid = cmd.arg or idx.latest_id()
                    if not sid:
                        ui.warn("没有可恢复的会话")
                        continue
                    await agent.close()
                    chat, sid, note = resolve_resume(s.store, sid, s.model)
                    chat_ref["chat"] = chat
                    if note:
                        ui.warn(note)
                    if not args.cwd:
                        s.cwd = chat.outputs_dir
                    agent = _new_agent(s, pm, ui, session_allow, repl_log, resume=sid)
                    await agent.start()
                    ui.info(f"已恢复会话 {sid[:8]}" if sid else f"已在对话 {chat.id} 开始新会话")
                elif cmd.name == "sessions":
                    ui.table("对话", [
                        {"id": m["id"], "标题": m["title"], "费用$": round(m["cost"], 4), "来源": m["source"]}
                        for m in list_chats(s.store)[:15]
                    ])
                elif cmd.name == "cd":
                    p = Path(cmd.arg).expanduser()
                    if p.is_dir():
                        s.cwd = p
                        ui.info(f"工作目录 → {p}（下个新会话生效）")
                    else:
                        ui.warn("目录不存在")
                elif cmd.name == "model":
                    if not cmd.arg:
                        ui.info(f"当前模型 {s.model}")
                    else:
                        await agent.set_model(cmd.arg)
                        ui.info(f"模型 → {cmd.arg}")
                        ui.set_status(model=s.model)
                elif cmd.name == "cost":
                    ui.info(f"本轮 ${agent.last_cost:.4f} · 本会话累计 ${agent.total_cost:.4f} · 上下文 {ui.context_bar(agent.context_tokens, agent.context_window)}")
                    ui.info(f"账号 {s.user}：{check_limits(usage_log, s.user, limits)[1]}")
                elif cmd.name == "tools":
                    ui.table("MCP 服务器", await agent.mcp_status())
                    names = await agent.tools()
                    ui.info("\n".join(names) if names else "(无)")
                elif cmd.name == "expand":
                    ui.console.print((ui.last_results or ["(无)"])[-1][:6000])
                elif cmd.name == "proxy":
                    if s.proxy.enabled:
                        ui.table("节点延迟(ms)", [{"节点": k, "延迟": v} for k, v in pm.node_delays().items()])
                    else:
                        ui.info("代理未启用")
                continue

            first_prompt = first_prompt or text
            try:
                result = await ui.render(agent.send(text))
            except KeyboardInterrupt:
                await agent.interrupt()
                ui.warn("已中断本轮")
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                ui.warn(f"本轮出错：{e!r}（会话 {agent.session_id}，可 /resume 恢复）")
                continue
            if result:
                turns += 1
                ui.set_status(model=s.model, context_tokens=agent.context_tokens, context_window=agent.context_window)
                usage_log.add(session=agent.session_id, model=s.model, usage=result.get("usage"), cost=agent.last_cost)
                ok, msg = check_limits(usage_log, s.user, limits)
                if not ok and not over_limit:
                    over_limit = True
                    ui.warn(f"已达用量上限：{msg}")
                if agent.session_id:
                    idx.upsert(agent.session_id, title=first_prompt or "", cwd=str(s.cwd), model=s.model, cost=agent.total_cost)
                    chat.update(session_id=agent.session_id, cost=agent.total_cost, turns=turns,
                                title=(chat.meta().get("title") or (first_prompt or "")[:40]), model=s.model)
                    repl_log.set_session(agent.session_id)
    finally:
        try:
            await asyncio.shield(agent.close())
        except Exception:
            pass
        if s.proxy.enabled:
            pm.unregister_session_and_maybe_stop()
        _reap_children()
    return 0


def _reap_children() -> None:
    """兜底：结束仍然存活的直接子进程（Claude CLI、Biomni MCP），避免终端断开后留下孤儿。"""
    me = os.getpid()
    try:
        pids = [int(p) for p in os.listdir("/proc") if p.isdigit()]
    except FileNotFoundError:  # 非 Linux
        return
    for pid in pids:
        try:
            with open(f"/proc/{pid}/stat") as f:
                fields = f.read().split()
            if int(fields[3]) == me:
                os.kill(pid, signal.SIGTERM)
        except (OSError, ValueError, IndexError):
            continue


def _web_admin(argv: list[str]) -> int:
    """管理员命令：--web-admin add <name> [--admin] | passwd <name> | list"""
    import getpass
    from bioagent.config import secrets_dir
    from bioagent.web.auth import Accounts
    acc = Accounts(secrets_dir() / "users.yaml")
    if not argv or argv[0] not in ("add", "passwd", "list"):
        print("用法: bioagent.sh --web-admin add <name> [--admin] | passwd <name> | list"); return 2
    if argv[0] == "list":
        for r in acc.list():
            print(f"{r['name']:<16} {r['role']:<6} {'启用' if r['enabled'] else '停用'} {'有密码' if r['has_password'] else '无密码'}")
        return 0
    name = argv[1] if len(argv) > 1 else ""
    pw = getpass.getpass("密码: ")
    if pw != getpass.getpass("再输一次: "):
        print("两次不一致"); return 2
    try:
        if argv[0] == "add":
            if acc.get(name):
                acc.set_password(name, pw)
                acc.update(name, role="admin" if "--admin" in argv else acc.get(name).get("role", "user"), enabled=True)
                print(f"账号 {name} 已存在，已更新密码")
            else:
                acc.create(name, pw, role="admin" if "--admin" in argv else "user")
                print(f"已创建 {name}")
        else:
            acc.set_password(name, pw); print("密码已更新")
    except (ValueError, KeyError) as e:
        print(f"失败: {e}"); return 2
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="bioagent", description="终端版生物医学研究助理")
    ap.add_argument("--user", help="使用者名字（必填，或设环境变量 BIOAGENT_USER）：会话、历史、输出目录按此隔离")
    ap.add_argument("--check", action="store_true", help="只检查代理与 API，不进入对话")
    ap.add_argument("--resume", nargs="?", const="", default=None, help="恢复会话（不带参数 = 最近一次）")
    ap.add_argument("--model", help="覆盖 config.yaml 的模型")
    ap.add_argument("--cwd", help="覆盖 config.yaml 的工作目录")
    ap.add_argument("--usage", action="store_true", help="管理员：打印各账号用量与上限（其后参数见 --usage --help）")
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "--web-admin":
        return _web_admin(argv[1:])
    if "--usage" in argv:
        from bioagent.usage import main as usage_main

        rest = [a for a in argv if a != "--usage"]
        return usage_main(rest)
    args = ap.parse_args(argv)
    try:
        code = asyncio.run(run(args))
    except KeyboardInterrupt:
        code = 130
    except asyncio.CancelledError:
        code = 129
    # 兜底：若有非守护线程（如 prompt_toolkit）拖住解释器退出，5 秒后强制退出
    t = threading.Timer(5.0, lambda: os._exit(code))
    t.daemon = True
    t.start()
    return code
