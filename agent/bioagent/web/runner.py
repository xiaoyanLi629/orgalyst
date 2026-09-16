"""ChatRunner：服务器内驱动一个对话；RunnerPool：按 (账号, 对话) 管理运行器与空闲回收。

浏览器断开不影响运行：事件同时写 events.jsonl（回放用）和广播给所有订阅队列。
"""
from __future__ import annotations

import asyncio
import dataclasses
import logging
import time
import uuid
from typing import Any, Callable

from ..agent import Agent
from ..chats import Chat, append_event
from ..modules import normalize, short
from ..cli import SUMMARIZE_PROMPT, ReplLogger, build_system_prompt
from ..permissions import make_can_use_tool
from ..store import UserStore
from ..usage import UsageLog, check_limits, load_limits

RETRY_PROMPT = "继续。你上一条回复因网络中断没有送达，之前执行的步骤结果都在，请接着完成并汇报。"
PERSIST = {"user", "text", "tool_use", "tool_result", "confirm_request", "confirm_reply", "result", "error"}
QUEUE_MAX = 2000        # 一个订阅最多积压多少事件；满了就摘掉这个订阅
MAX_ACTIVE_RUNNERS = 20  # 全局最多几个已起 agent 的 runner（每个 = 一个 CLI 子进程 + 一个 Biomni MCP）

log = logging.getLogger("bioagent.web.runner")


class ChatRunner:
    def __init__(self, settings, store: UserStore, chat: Chat, proxy_env: dict[str, str],
                 agent_factory: Callable[..., Any] | None = None, confirm_timeout: float = 60.0):
        self.base = settings
        self.store = store
        self.chat = chat
        self.proxy_env = proxy_env
        self.agent_factory = agent_factory or Agent
        self.confirm_timeout = confirm_timeout
        self.agent = None
        self.running = False
        self.closing = False
        self._agent_lock = asyncio.Lock()
        self.last_active = time.time()
        self.turns = chat.meta().get("turns", 0)
        self.subscribers: set[asyncio.Queue] = set()
        self.pending: dict[str, asyncio.Future] = {}
        self.session_allow: set[str] = set()
        self.usage = UsageLog(store.usage_file)
        self._task: asyncio.Task | None = None
        self._text_buf = ""

    # ---- 订阅/广播 ----
    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAX)
        self.subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self.subscribers.discard(q)

    def emit(self, ev: dict) -> None:
        ev.setdefault("ts", time.time())  # 前端据此显示每步耗时（落盘记录同样带 ts）
        if ev["type"] in PERSIST:
            append_event(self.chat, ev)
        for q in list(self.subscribers):
            try:
                q.put_nowait(ev)
            except asyncio.QueueFull:
                # 没人消费（pump 挂了、浏览器卡死）：摘掉这个订阅，
                # 不让一个死连接把整轮的文字增量和工具输出堆在内存里。
                log.warning("订阅队列已满（%d），丢弃该订阅：chat=%s", QUEUE_MAX, self.chat.id)
                self.subscribers.discard(q)

    def _flush_text(self) -> None:
        if self._text_buf.strip():
            self.emit({"type": "text", "text": self._text_buf})
        self._text_buf = ""

    # ---- 状态 ----
    def _settings(self):
        model = self.store.read_settings().get("model") or self.base.model
        s = dataclasses.replace(self.base, user=self.store.user, cwd=self.chat.outputs_dir, model=model)
        # 按需加载：本对话选择的模块（meta.modules）> 配置默认 > 全部
        all_mods = list(self.base.biomni.modules)
        picked = self.chat.meta().get("modules") or self.base.biomni.default_modules
        mods = normalize(picked, all_mods) if picked else all_mods
        s.biomni = dataclasses.replace(self.base.biomni, modules=mods, all_modules=all_mods)
        return s

    def modules(self) -> list[str]:
        """本对话当前加载的模块短名。"""
        return [short(m) for m in self._settings().biomni.modules]

    async def set_modules(self, names: list[str]) -> tuple[bool, str]:
        """切换本对话的模块；若助理已启动则重启接入（用 session_id 恢复，对话不中断）。进行中时拒绝。"""
        if self.running:
            return False, "上一轮仍在进行中，结束后再切换模块"
        mods = normalize(names, list(self.base.biomni.modules))
        if not mods:
            return False, "至少选择一个模块"
        self.chat.update(modules=[short(m) for m in mods])
        if self.agent is not None:
            async with self._agent_lock:
                try:
                    await self.agent.close()
                except Exception as e:  # noqa: BLE001
                    log.warning("close before module switch: %r", e)
                self.agent = None
            await self.prewarm()
        else:
            self.emit(self.status())
        return True, ""

    def limits(self) -> tuple[bool, str]:
        return check_limits(self.usage, self.store.user, load_limits(self.base.secrets_dir / "users.yaml"))

    def status(self) -> dict:
        ok, text = self.limits()
        a = self.agent
        return {"type": "status", "running": self.running, "over_limit": not ok, "limit_text": text,
                "context_tokens": getattr(a, "context_tokens", 0), "context_window": getattr(a, "context_window", self.base.context_limit_tokens),
                "context_full": bool(getattr(a, "context_full", False)),
                "cost_total": getattr(a, "total_cost", self.chat.meta().get("cost", 0.0)), "model": self._settings().model,
                "modules": self.modules(), "modules_total": len(self.base.biomni.modules), "permission_mode": self.permission_mode()}

    # ---- Agent ----
    async def ensure_agent(self) -> None:
        async with self._agent_lock:  # 预热与首轮可能同时到达，只让一个真正启动
            await self._ensure_agent_locked()

    async def prewarm(self) -> None:
        """打开对话时后台拉起助理进程与工具库，省掉第一条消息前的 10–15 秒等待。失败只记日志，首轮会再试。"""
        if self.agent is not None or self.running or self.closing:
            return
        try:
            await self.ensure_agent()
            self.last_active = time.time()
            self.emit(self.status())
        except Exception as e:  # noqa: BLE001
            log.warning("prewarm failed for %s/%s: %r", self.store.user, self.chat.id, e)

    async def _ensure_agent_locked(self) -> None:
        if self.agent is not None:
            return
        s = self._settings()
        self.chat.outputs_dir.mkdir(parents=True, exist_ok=True)
        repl = ReplLogger(self.chat.outputs_dir)
        resume = self.chat.meta().get("session_id")
        repl.start(resume)
        cb = make_can_use_tool(s, self._confirm, self.session_allow, on_repl_code=repl.log, mode=self.permission_mode, on_auto=self._on_auto)
        agent = self.agent_factory(s, self.proxy_env, cb, build_system_prompt(s), resume=resume)
        await agent.start()  # 失败时不落到 self.agent：下一轮 ensure_agent 会重新尝试，而不是卡在半初始化状态
        self.agent = agent

    def permission_mode(self) -> str:
        """本对话的确认方式：对话自己的设置 > 使用者默认 > ask。每次询问时读取，改了即时生效。"""
        return self.chat.meta().get("permission_mode") or self.store.read_settings().get("permission_mode") or "ask"

    def _on_auto(self, summary: str) -> None:
        cid = uuid.uuid4().hex[:8]
        self.emit({"type": "confirm_request", "id": cid, "summary": summary, "auto": True})
        self.emit({"type": "confirm_reply", "id": cid, "ok": True, "auto": True})

    def set_permission_mode(self, mode: str) -> None:
        self.chat.update(permission_mode=mode)
        self.emit(self.status())

    async def _confirm(self, summary: str) -> bool:
        cid = uuid.uuid4().hex[:8]
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self.pending[cid] = fut
        self.emit({"type": "confirm_request", "id": cid, "summary": summary})
        try:
            ok = bool(await asyncio.wait_for(fut, self.confirm_timeout))
        except asyncio.TimeoutError:
            ok = False
        finally:
            self.pending.pop(cid, None)
        self.emit({"type": "confirm_reply", "id": cid, "ok": ok})
        return ok

    async def confirm_reply(self, cid: str, ok: bool) -> None:
        fut = self.pending.get(cid)
        if fut and not fut.done():
            fut.set_result(ok)

    # ---- 一轮 ----
    async def submit(self, text: str) -> tuple[bool, str]:
        text = (text or "").strip()
        if not text:
            return False, "内容为空"
        if self.closing:
            return False, "对话正在回收，请重新发送"
        if self.running:
            return False, "上一轮仍在进行中，请等它结束"
        ok, why = self.limits()
        if not ok:
            return False, f"已达用量上限：{why}"
        if self.agent is not None and getattr(self.agent, "context_full", False):
            return False, "这个对话的上下文已满，请开一个新对话（要点会自动写入记忆）"
        self.running = True
        self.last_active = time.time()
        self._task = asyncio.create_task(self._run_turn(text))
        return True, ""

    async def _stream(self, text: str) -> dict:
        """把一次 send 的事件流广播出去，返回 result 事件的数据（没有 result 时为 {}）。"""
        result: dict = {}
        self._text_buf = ""
        async for ev in self.agent.send(text):
            if ev.kind == "text":
                self._text_buf += ev.text
                self.emit({"type": "text_delta", "text": ev.text})
            elif ev.kind == "tool_use":
                self._flush_text()
                self.emit({"type": "tool_use", "id": ev.data.get("id"), "name": ev.name, "input": ev.data.get("input", {})})
            elif ev.kind == "tool_result":
                self.emit({"type": "tool_result", "id": ev.data.get("id"), "text": ev.text[:20000], "error": bool(ev.data.get("error"))})
            elif ev.kind == "result":
                result = ev.data
            elif ev.kind == "usage":
                self.emit(self.status())  # 每次模型响应后刷新上下文占用，不等整轮结束
        self._flush_text()
        return result

    async def _run_turn(self, text: str) -> None:
        self.emit({"type": "user", "text": text})
        started = False  # ensure_agent 成功、真正进了 send() 才算“这一轮已开始”
        result: dict = {}
        try:
            await self.ensure_agent()
            started = True
            self.emit(self.status())
            result = await self._stream(text)
            # 模型回复在等待中断掉（result 为空且 error）：多为网络/API 临时故障，自动接续一次；工具效果已保留
            if result.get("error") and not result.get("result") and not self.closing:
                self.emit({"type": "error", "message": "等待模型回复时中断（网络或 API 临时故障），正在自动重试…"})
                await asyncio.sleep(3)
                result = await self._stream(RETRY_PROMPT)
            a = self.agent
            self.emit({"type": "result", "cost": a.total_cost, "turn_cost": a.last_cost})
            if result.get("errors"):
                self.emit({"type": "error", "message": "; ".join(str(x) for x in result["errors"])})
            if result.get("error"):
                msg = result.get("result") or "本轮失败"
                if "ede_diagnostic" in msg or not result.get("result"):
                    msg = "本轮在等待模型回复时中断（多为网络或 API 的临时故障）。已执行的步骤都保留了，直接重发上一条消息即可继续。"
                self.emit({"type": "error", "message": msg})
        except asyncio.CancelledError:
            self._flush_text()
            self.emit({"type": "error", "message": "本轮已中断"})
        except Exception as e:  # noqa: BLE001
            self._flush_text()
            self.emit({"type": "error", "message": f"本轮出错：{e!r}"})
        finally:
            # 记账（用量、对话元数据）与是否发出 result 事件无关：send() 中途出错也可能已经花了钱，
            # 只要 agent 起来过（started）就要落账，不然会漏记支出。record 失败本身不应该掩盖本轮结果。
            if started and self.agent is not None:
                try:
                    self._record_turn(text, result)
                except Exception as e:  # noqa: BLE001
                    log.warning("轮次记账失败：%r", e)
            self.running = False
            self.last_active = time.time()
            self.emit(self.status())

    def _record_turn(self, text: str, result: dict) -> None:
        self.turns += 1
        a = self.agent
        # a.last_cost/total_cost 只在 Agent 处理到 result 事件那一刻才更新；这一轮如果没走到 result
        # （send() 中途异常），last_cost 还停在上一轮的值，直接拿来记账会把上一轮的花费重复计一遍。
        cost = a.last_cost if result else 0.0
        self.usage.add(session=a.session_id, model=self._settings().model,
                       usage=result.get("usage") if result else None, cost=cost)
        meta = self.chat.meta()
        self.chat.update(session_id=a.session_id, cost=a.total_cost, turns=self.turns,
                         title=meta.get("title") or text[:40], model=self._settings().model)

    async def interrupt(self) -> None:
        if self.agent and self.running:
            try:
                await self.agent.interrupt()
            except Exception:
                pass

    async def close(self, summarize: bool = True) -> None:
        self.closing = True  # 立刻挡住新 submit，即便下面还要等在跑的一轮、总结记忆
        try:
            if self._task and not self._task.done():
                await self.interrupt()
                try:
                    await asyncio.wait_for(self._task, 10)
                except Exception as e:  # noqa: BLE001
                    log.warning("等待轮次任务结束失败：%r", e)
            if self.agent is not None:
                s = self._settings()
                if summarize and s.memory.enabled and s.memory.auto_summarize and self.turns > 0:
                    try:
                        async for _ in self.agent.send(SUMMARIZE_PROMPT.format(path=s.memory_file, max_chars=s.memory.max_chars)):
                            pass
                    except Exception as e:  # noqa: BLE001
                        log.warning("记忆总结失败：%r", e)
                try:
                    await self.agent.close()
                except Exception as e:  # noqa: BLE001
                    log.warning("关闭 agent 失败：%r", e)
        finally:
            # 不管上面哪一步炸了，runner 都不能停在半关闭状态：agent/turns/closing 必须归位。
            # closing 归 False 无妨——池已经把这个 runner 摘掉了，谁还攥着这个引用直接 submit，
            # 下一轮 ensure_agent 会重新起一个 agent，不会复用已经关掉的那个。
            self.agent = None
            self.turns = 0
            self.closing = False


class RunnerPool:
    def __init__(self, settings, proxy_env: dict[str, str], agent_factory=None, idle_seconds: float = 1800,
                 confirm_timeout: float = 60.0, max_active: int = MAX_ACTIVE_RUNNERS):
        self.max_active = max_active
        self.settings = settings
        self.proxy_env = proxy_env
        self.agent_factory = agent_factory
        self.idle_seconds = idle_seconds
        self.confirm_timeout = confirm_timeout
        self.runners: dict[tuple[str, str], ChatRunner] = {}
        self._lock = asyncio.Lock()

    def peek(self, user: str, chat_id: str) -> ChatRunner | None:
        return self.runners.get((user, chat_id))

    def active(self) -> int:
        """已经起了 agent（或正在跑）的 runner 数。还没收到过 prompt 的空 runner 很便宜，不计。"""
        return sum(1 for r in self.runners.values() if r.agent is not None or r.running)

    async def get(self, user: str, chat_id: str) -> ChatRunner:
        from ..chats import get_chat
        async with self._lock:
            r = self.runners.get((user, chat_id))
            if r is None:
                if self.active() >= self.max_active:
                    raise RuntimeError("服务器繁忙，请稍后再试")
                store = UserStore(self.settings.root, user).ensure()
                chat = get_chat(store, chat_id)
                if chat is None:
                    raise KeyError(chat_id)
                r = ChatRunner(self.settings, store, chat, self.proxy_env, agent_factory=self.agent_factory,
                               confirm_timeout=self.confirm_timeout)
                self.runners[(user, chat_id)] = r
            return r

    async def drop(self, user: str, chat_id: str, summarize: bool = True) -> None:
        async with self._lock:
            r = self.runners.pop((user, chat_id), None)
        if r:
            await r.close(summarize=summarize)

    async def reap_idle(self) -> None:
        # 判断哪些空闲、并从 runners 摘除都在锁内做完，再在锁外慢慢 close；
        # 不然摘除前让出控制权，close 慢的时候一个并发 get/submit 可能正好拿到即将被摘的 runner。
        now = time.time()
        victims: list[ChatRunner] = []
        async with self._lock:
            for key, r in list(self.runners.items()):
                if not r.running and now - r.last_active >= self.idle_seconds:
                    victims.append(r)
                    del self.runners[key]
        for r in victims:
            await r.close()

    async def close_all(self) -> None:
        for key in list(self.runners):
            await self.drop(*key, summarize=False)
