"""封装 ClaudeSDKClient：构建 options，把 SDK 消息流归一为简单事件。

只在这里接触 claude_agent_sdk 的类型，UI 与 CLI 只认 Event。
"""
from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    StreamEvent,
    SystemMessage,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)


@dataclass
class Event:
    kind: str  # text | tool_use | tool_result | result | system
    text: str = ""
    name: str = ""
    data: dict[str, Any] = field(default_factory=dict)


def normalize(msg) -> list[Event]:
    """把一条 SDK 消息转成 0..n 个 Event。

    文本只从 StreamEvent 的 text_delta 取（AssistantMessage 里的 TextBlock 是同一段文本的完整版，
    取了会重复打印）。
    """
    if isinstance(msg, StreamEvent):
        ev = msg.event
        if ev.get("type") == "content_block_delta" and ev.get("delta", {}).get("type") == "text_delta":
            return [Event("text", text=ev["delta"]["text"])]
        return []
    if isinstance(msg, AssistantMessage):
        out: list[Event] = []
        if msg.usage:
            # 每次 API 调用的 usage：输入 + 缓存读 + 缓存写 = 当前上下文占用（与 Claude Code 状态栏口径一致）
            u = msg.usage
            used = int(u.get("input_tokens") or 0) + int(u.get("cache_read_input_tokens") or 0) + int(u.get("cache_creation_input_tokens") or 0)
            if used:
                out.append(Event("usage", data={"context_tokens": used, "model": msg.model}))
        out += [
            Event("tool_use", name=b.name, data={"input": b.input, "id": b.id})
            for b in msg.content
            if isinstance(b, ToolUseBlock)
        ]
        return out
    if isinstance(msg, UserMessage) and isinstance(msg.content, list):
        out: list[Event] = []
        for b in msg.content:
            if isinstance(b, ToolResultBlock):
                if isinstance(b.content, str):
                    text = b.content
                else:
                    text = "\n".join(x.get("text", "") for x in (b.content or []) if isinstance(x, dict))
                out.append(Event("tool_result", text=text or "", data={"id": b.tool_use_id, "error": bool(b.is_error)}))
        return out
    if isinstance(msg, ResultMessage):
        return [
            Event(
                "result",
                data={
                    "cost": msg.total_cost_usd or 0.0,
                    "session_id": msg.session_id,
                    "turns": msg.num_turns,
                    "error": msg.is_error,
                    "usage": msg.usage or {},
                    "context_window": max((int(v.get("contextWindow") or 0) for v in (msg.model_usage or {}).values()), default=0),
                    "result": msg.result or "",
                    "errors": msg.errors or [],
                },
            )
        ]
    if isinstance(msg, SystemMessage):
        return [Event("system", name=msg.subtype, data=msg.data)]
    return []


# Monitor/TaskOutput/TaskStop：等待后台任务用（Claude CLI 禁止 `sleep N; cmd` 式等待）
# TaskCreate/TaskUpdate/TaskList/TaskGet：CLI 的任务清单（规划→逐项执行）；旧的 TodoWrite/MultiEdit 在当前 CLI 里已不存在
BUILTIN_TOOLS = ["Read", "Write", "Edit", "Bash", "Grep", "Glob", "WebSearch", "WebFetch", "TaskCreate", "TaskUpdate", "TaskList", "TaskGet", "Monitor", "TaskOutput", "TaskStop"]


class Agent:
    def __init__(self, settings, proxy_env: dict[str, str], can_use_tool, system_prompt: str, resume: str | None = None):
        self.s = settings
        self.session_id: str | None = resume
        self.last_cost = 0.0
        self.total_cost = 0.0
        self.context_tokens = 0          # 最近一次 API 调用的上下文占用
        self.context_window = int(getattr(settings, "context_limit_tokens", 1_000_000))  # 配置的上限；模型窗口更小时取更小者
        # PATH 顺序（决定助理敲 python/pip/samtools 时用到哪个）：
        #   1) 工具库主环境 .venv/bin —— python/pip 默认就是它：科学计算包齐全，pip install 装进网络盘上的这个环境，不碰系统盘
        #   2) 生信命令行工具（micromamba prefix）与 PLINK/IQ-TREE 等二进制
        #   3) 系统 PATH
        biomni_dir = settings.root / "biomni"
        head_bins = [biomni_dir / ".venv" / "bin", biomni_dir / "tools" / "bin", biomni_dir / "cli_tools" / "bin"]
        path = ":".join([str(p) for p in head_bins if p.is_dir()] + [os.environ.get("PATH", "")])
        env = {"ANTHROPIC_API_KEY": settings.api_key, "PATH": path, **proxy_env}
        # 内置研究流程 skill（项目自带的本地插件 skillpack/），只启用列出的这些；不读服务器上其他 skill
        self.skillpack = settings.root / "skillpack"
        self.skill_names = sorted(
            f"bioagent:{d.name}" for d in (self.skillpack / "skills").iterdir() if (d / "SKILL.md").exists()
        ) if (self.skillpack / "skills").is_dir() else []
        mcp: dict[str, Any] = {}
        # modules 为空时不接 Biomni（Biomni 把空列表当作"全部模块"，这里显式挡住）
        if settings.biomni.enabled and settings.biomni.modules and settings.biomni.server.exists() and settings.biomni.python.exists():
            mcp["biotools"] = {
                "type": "stdio",
                "command": str(settings.biomni.python),
                "args": [str(settings.biomni.server)],
                "env": {
                    **proxy_env,
                    "KMP_DUPLICATE_LIB_OK": "TRUE",
                    "ANTHROPIC_API_KEY": settings.api_key,
                    "BIOMNI_DATA_PATH": str(biomni_dir / "data"),
                    "BIOMNI_MODULES": ",".join(settings.biomni.modules),
                    "PATH": path,
                },
            }
        # 额外的领域工具服务器（config.yaml 的 mcp_servers），例如 Orgalyst 类器官图像分析
        for srv in getattr(settings, "extra_mcp", []) or []:
            if not srv.get("enabled", True) or not Path(str(srv["command"])).exists():
                continue
            mcp[str(srv["name"])] = {
                "type": "stdio",
                "command": str(srv["command"]),
                "args": [str(a) for a in srv.get("args", [])],
                "env": {**proxy_env, "PATH": path, **{str(k): str(v) for k, v in (srv.get("env") or {}).items()}},
            }
        self.has_biomni = bool(mcp)
        self.stderr_log = settings.sessions_dir / "cli-stderr.log"
        self.stderr_log.parent.mkdir(parents=True, exist_ok=True)
        # CLI 的 API 级调试日志（请求/耗时/错误），排查"本轮失败"用；超过 20 MB 就清空重来
        self.debug_log = settings.sessions_dir / "cli-debug.log"
        try:
            if self.debug_log.exists() and self.debug_log.stat().st_size > 20 * 1024 * 1024:
                self.debug_log.write_text("")
        except OSError:
            pass
        self.options = ClaudeAgentOptions(
            system_prompt=system_prompt,
            model=settings.model,
            cwd=str(settings.cwd),
            env=env,
            # tools= 决定哪些内置工具可用；allowed_tools 留空，否则会整体预批准、绕过 can_use_tool
            tools=BUILTIN_TOOLS,
            allowed_tools=[],
            mcp_servers=mcp,
            permission_mode="default",
            can_use_tool=can_use_tool,
            include_partial_messages=True,
            resume=resume,
            setting_sources=[],  # SDK 隔离模式：不读 ~/.claude 与项目 .claude 的设置、hooks、插件
            max_budget_usd=settings.daily_cost_cap_usd,
            # SDK 默认单条消息 1 MB：工具返回大文件/长输出会触发 CLIJSONDecodeError 中断整轮，放宽到 512 MB
            max_buffer_size=512 * 1024 * 1024,
            extra_args={"debug": "api", "debug-file": str(self.debug_log)},
            plugins=[{"type": "local", "path": str(self.skillpack)}] if self.skill_names else [],
            skills=self.skill_names or [],
            stderr=self._log_stderr,
        )
        self.client = ClaudeSDKClient(self.options)

    def _log_stderr(self, line: str) -> None:
        """CLI 子进程的 stderr 写日志文件，不刷屏。"""
        try:
            with open(self.stderr_log, "a") as f:
                f.write(line.rstrip("\n") + "\n")
        except OSError:
            pass

    async def start(self) -> None:
        await self.client.connect()

    async def send(self, prompt: str) -> AsyncIterator[Event]:
        await self.client.query(prompt)
        async for msg in self.client.receive_response():
            for ev in normalize(msg):
                if ev.kind == "usage":
                    self.context_tokens = ev.data["context_tokens"]
                if ev.kind == "result":
                    if ev.data.get("context_window"):
                        self.context_window = min(self.context_window, int(ev.data["context_window"]))
                    total = float(ev.data["cost"])
                    self.last_cost = max(total - self.total_cost, 0.0) if total >= self.total_cost else total
                    self.total_cost = total
                    self.session_id = ev.data["session_id"]
                yield ev

    @property
    def context_full(self) -> bool:
        return self.context_tokens >= self.context_window

    async def interrupt(self) -> None:
        await self.client.interrupt()

    async def set_model(self, model: str) -> None:
        await self.client.set_model(model)
        self.s.model = model

    async def tools(self) -> list[str]:
        names: list[str] = []
        try:
            info = await self.client.get_server_info() or {}
            for t in info.get("tools", []) or []:
                names.append(t.get("name") if isinstance(t, dict) else str(t))
        except Exception:
            pass
        try:
            st = await self.client.get_mcp_status()
            for srv in st.get("mcpServers", []) or []:
                for t in srv.get("tools", []) or []:
                    tn = t.get("name") if isinstance(t, dict) else str(t)
                    names.append(f"mcp__{srv.get('name')}__{tn}")
        except Exception:
            pass
        return sorted({n for n in names if n})

    async def mcp_status(self) -> list[dict]:
        try:
            st = await self.client.get_mcp_status()
            return [
                {"server": s.get("name"), "status": s.get("status"), "tools": len(s.get("tools") or [])}
                for s in st.get("mcpServers", []) or []
            ]
        except Exception as e:
            return [{"server": "?", "status": f"error: {e!r}", "tools": 0}]

    async def close(self) -> None:
        try:
            await self.client.disconnect()
        except Exception:
            pass
