import asyncio
import json
from pathlib import Path

import pytest

from bioagent.agent import Event
from bioagent.chats import create_chat, read_events
from bioagent.config import BiomniSettings, ProxySettings, Settings
from bioagent.store import UserStore
from bioagent.web.runner import ChatRunner, RunnerPool


class FakeAgent:
    """按脚本产事件；遇到 tool_use 时调用 can_use_tool 走确认流程。"""
    instances = []

    def __init__(self, settings, proxy_env, can_use_tool, system_prompt, resume=None):
        self.s, self.cb, self.resume = settings, can_use_tool, resume
        self.session_id = resume or "sess-1"
        self.last_cost = 0.0; self.total_cost = 0.0
        self.context_tokens = 0; self.context_window = getattr(settings, "context_limit_tokens", 200000)
        self.started = False; self.closed = False; self.interrupted = False
        self.prompts: list[str] = []
        FakeAgent.instances.append(self)

    @property
    def context_full(self):
        return self.context_tokens >= self.context_window

    async def start(self):
        self.started = True

    async def send(self, prompt):
        self.prompts.append(prompt)
        if prompt.startswith("本次会话即将结束"):
            yield Event("text", text="无需更新"); yield Event("result", data={"cost": self.total_cost, "session_id": self.session_id, "usage": {}}); return
        yield Event("text", text="你好")
        yield Event("text", text="，世界")
        yield Event("tool_use", name="Bash", data={"input": {"command": "rm -rf /tmp/x"}, "id": "t1"})
        allowed = await self.cb("Bash", {"command": "rm -rf /tmp/x"}, None)
        yield Event("tool_result", text="done" if type(allowed).__name__ == "PermissionResultAllow" else "denied",
                    data={"id": "t1", "error": False})
        self.context_tokens = 1234
        self.total_cost += 0.05; self.last_cost = 0.05
        yield Event("result", data={"cost": self.total_cost, "session_id": self.session_id,
                                    "usage": {"input_tokens": 10, "output_tokens": 5}})

    async def interrupt(self):
        self.interrupted = True

    async def close(self):
        self.closed = True


def make_settings(tmp_path, user="u"):
    return Settings(root=tmp_path, assistant_name="X", model="m", cwd=tmp_path, readonly_dirs=[],
                    daily_cost_cap_usd=1, api_key="k", proxy=ProxySettings(enabled=False), biomni=BiomniSettings(enabled=False), user=user)


async def drain(q, n, timeout=3):
    out = []
    for _ in range(n):
        out.append(await asyncio.wait_for(q.get(), timeout))
    return out


@pytest.mark.asyncio
async def test_turn_with_confirm_allow(tmp_path):
    s = make_settings(tmp_path)
    st = s.store.ensure()
    chat = create_chat(st, model="m", source="web")
    r = ChatRunner(s, st, chat, {}, agent_factory=FakeAgent)
    q = r.subscribe()
    ok, _ = await r.submit("hi")
    assert ok
    # 等到确认请求
    evs = []
    while True:
        ev = await asyncio.wait_for(q.get(), 3); evs.append(ev)
        if ev["type"] == "confirm_request":
            break
    assert any(e["type"] == "text_delta" for e in evs) and any(e["type"] == "user" for e in evs)
    await r.confirm_reply(ev["id"], True)
    while True:
        ev = await asyncio.wait_for(q.get(), 3); evs.append(ev)
        if ev["type"] == "result":
            break
    types = [e["type"] for e in evs]
    assert "tool_use" in types and "tool_result" in types and "confirm_reply" in types
    assert [e for e in evs if e["type"] == "tool_result"][0]["text"] == "done"
    assert not r.running
    # 落盘：user/text/tool_use/tool_result/confirm_*/result；text 合并成一段
    disk = read_events(chat)
    dtypes = [e["type"] for e in disk]
    assert dtypes[:3] == ["user", "text", "tool_use"] and disk[1]["text"] == "你好，世界"
    assert "text_delta" not in dtypes and "status" not in dtypes
    m = chat.meta()
    assert m["session_id"] == "sess-1" and m["turns"] == 1 and m["title"] == "hi" and m["cost"] == 0.05
    assert (st.usage_file).exists() and "0.05" in st.usage_file.read_text()
    assert r.status()["context_tokens"] == 1234


@pytest.mark.asyncio
async def test_confirm_timeout_denies(tmp_path):
    s = make_settings(tmp_path)
    st = s.store.ensure(); chat = create_chat(st, model="m", source="web")
    r = ChatRunner(s, st, chat, {}, agent_factory=FakeAgent, confirm_timeout=0.2)
    q = r.subscribe()
    await r.submit("hi")
    evs = []
    while True:
        ev = await asyncio.wait_for(q.get(), 3); evs.append(ev)
        if ev["type"] == "result":
            break
    assert [e for e in evs if e["type"] == "tool_result"][0]["text"] == "denied"
    assert [e for e in evs if e["type"] == "confirm_reply"][0]["ok"] is False


@pytest.mark.asyncio
async def test_reject_while_running_and_over_limit(tmp_path):
    s = make_settings(tmp_path)
    st = s.store.ensure(); chat = create_chat(st, model="m", source="web")
    r = ChatRunner(s, st, chat, {}, agent_factory=FakeAgent, confirm_timeout=0.2)
    ok, _ = await r.submit("a")
    ok2, why = await r.submit("b")
    assert ok and not ok2 and "进行中" in why
    q = r.subscribe()
    while (await asyncio.wait_for(q.get(), 3))["type"] != "result":
        pass
    ok3, why3 = await r.submit("")
    assert not ok3


@pytest.mark.asyncio
async def test_over_limit_blocks(tmp_path, monkeypatch):
    monkeypatch.setenv("BIOAGENT_SECRETS_DIR", str(tmp_path / "sec"))
    (tmp_path / "sec").mkdir()
    (tmp_path / "sec" / "users.yaml").write_text("users:\n  u: {daily_usd: 0.01}\n")
    s = make_settings(tmp_path)
    st = s.store.ensure(); chat = create_chat(st, model="m", source="web")
    r = ChatRunner(s, st, chat, {}, agent_factory=FakeAgent, confirm_timeout=0.2)
    q = r.subscribe()
    await r.submit("a")
    while (await asyncio.wait_for(q.get(), 3))["type"] != "result":
        pass
    ok, why = await r.submit("b")
    assert not ok and "上限" in why and r.status()["over_limit"]


@pytest.mark.asyncio
async def test_close_summarizes_and_pool(tmp_path):
    s = make_settings(tmp_path)
    pool = RunnerPool(s, {}, agent_factory=FakeAgent, idle_seconds=0, confirm_timeout=0.2)
    st = UserStore(tmp_path, "u").ensure(); chat = create_chat(st, model="m", source="web")
    r = await pool.get("u", chat.id)
    assert pool.peek("u", chat.id) is r
    q = r.subscribe()
    await r.submit("a")
    while (await asyncio.wait_for(q.get(), 3))["type"] != "result":
        pass
    agent = FakeAgent.instances[-1]
    await pool.reap_idle()
    assert pool.peek("u", chat.id) is None and agent.closed
    assert any(p.startswith("本次会话即将结束") for p in agent.prompts)  # 记忆总结
    # 重新 get 会用 session_id 恢复
    r2 = await pool.get("u", chat.id)
    await r2.submit("b")
    q2 = r2.subscribe()
    while (await asyncio.wait_for(q2.get(), 3))["type"] != "result":
        pass
    assert FakeAgent.instances[-1].resume == "sess-1"
    await pool.close_all()


@pytest.mark.asyncio
async def test_start_failure_does_not_wedge_agent(tmp_path):
    """agent.start() 第一次抛异常：self.agent 不该卡在半初始化状态，下一轮要能重试并成功。"""
    class FlakyStartAgent(FakeAgent):
        attempts = 0

        async def start(self):
            type(self).attempts += 1
            if type(self).attempts == 1:
                raise RuntimeError("boom on first start")
            await super().start()

    s = make_settings(tmp_path)
    st = s.store.ensure(); chat = create_chat(st, model="m", source="web")
    r = ChatRunner(s, st, chat, {}, agent_factory=FlakyStartAgent, confirm_timeout=0.2)
    q = r.subscribe()

    ok, _ = await r.submit("hi")
    assert ok
    while True:
        ev = await asyncio.wait_for(q.get(), 3)
        if ev["type"] == "error":
            break
    assert not r.running and r.agent is None

    ok2, _ = await r.submit("hi again")
    assert ok2
    while True:
        ev = await asyncio.wait_for(q.get(), 3)
        if ev["type"] == "confirm_request":
            break
    await r.confirm_reply(ev["id"], True)
    while True:
        ev = await asyncio.wait_for(q.get(), 3)
        if ev["type"] == "result":
            break
    assert not r.running and r.agent is not None


@pytest.mark.asyncio
async def test_bookkeeping_survives_mid_stream_failure(tmp_path):
    """agent.send() 中途抛异常也要落账（用量、轮数），不然会漏记已经产生的花费。"""
    class RaisingMidStreamAgent(FakeAgent):
        async def send(self, prompt):
            self.prompts.append(prompt)
            yield Event("text", text="部分输出")
            raise RuntimeError("boom mid-stream")

    s = make_settings(tmp_path)
    st = s.store.ensure(); chat = create_chat(st, model="m", source="web")
    r = ChatRunner(s, st, chat, {}, agent_factory=RaisingMidStreamAgent, confirm_timeout=0.2)
    q = r.subscribe()

    ok, _ = await r.submit("hi")
    assert ok
    while True:
        ev = await asyncio.wait_for(q.get(), 3)
        if ev["type"] == "error":
            break
    assert not r.running
    assert chat.meta()["turns"] == 1
    rows = [ln for ln in st.usage_file.read_text().splitlines() if ln.strip()]
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_reap_idle_vs_submit_race(tmp_path):
    """reap_idle 摘除一个正在慢慢 close 的 runner 期间，旧 runner 对象上的 submit 必须被拒绝，
    且随后 pool.get 必须拿到一个全新的 runner（不是复用被摘除又复活的那个）。"""
    class SlowCloseAgent(FakeAgent):
        async def close(self):
            await asyncio.sleep(0.2)
            self.closed = True

    s = make_settings(tmp_path)
    pool = RunnerPool(s, {}, agent_factory=SlowCloseAgent, idle_seconds=0, confirm_timeout=0.2)
    st = UserStore(tmp_path, "u").ensure(); chat = create_chat(st, model="m", source="web")
    r = await pool.get("u", chat.id)
    q = r.subscribe()
    await r.submit("a")
    while (await asyncio.wait_for(q.get(), 3))["type"] != "result":
        pass

    reap_task = asyncio.create_task(pool.reap_idle())
    await asyncio.sleep(0)  # 让 reap_idle 跑到摘除+开始 close（卡在 close 的 sleep 里）
    assert r.closing  # 此时应该已经被摘除、正在回收
    assert pool.peek("u", chat.id) is None

    ok, why = await r.submit("b")
    assert not ok and "回收" in why

    await reap_task
    assert pool.peek("u", chat.id) is None

    r2 = await pool.get("u", chat.id)
    assert r2 is not r
    await pool.close_all()


@pytest.mark.asyncio
async def test_no_stale_cost_on_failed_turn(tmp_path):
    """第二轮 send() 中途异常时，不该沿用第一轮残留在 agent.last_cost 上的花费重复入账。"""
    class FirstOkThenRaiseAgent(FakeAgent):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self.call = 0

        async def send(self, prompt):
            self.call += 1
            self.prompts.append(prompt)
            if self.call == 1:
                yield Event("text", text="ok")
                self.total_cost += 0.05; self.last_cost = 0.05
                yield Event("result", data={"cost": self.total_cost, "session_id": self.session_id,
                                            "usage": {"input_tokens": 1, "output_tokens": 1}})
            else:
                yield Event("text", text="部分输出")
                raise RuntimeError("boom mid-stream on second turn")

    s = make_settings(tmp_path)
    st = s.store.ensure(); chat = create_chat(st, model="m", source="web")
    r = ChatRunner(s, st, chat, {}, agent_factory=FirstOkThenRaiseAgent, confirm_timeout=0.2)
    q = r.subscribe()

    ok, _ = await r.submit("first")
    assert ok
    while (await asyncio.wait_for(q.get(), 3))["type"] != "result":
        pass

    ok2, _ = await r.submit("second")
    assert ok2
    while True:
        ev = await asyncio.wait_for(q.get(), 3)
        if ev["type"] == "error":
            break

    assert chat.meta()["turns"] == 2
    rows = [json.loads(ln) for ln in st.usage_file.read_text().splitlines() if ln.strip()]
    assert len(rows) == 2
    assert rows[0]["cost"] == 0.05
    assert rows[1]["cost"] == 0.0


@pytest.mark.asyncio
async def test_error_event_on_api_failure(tmp_path):
    """result 事件里 error=True（如鉴权失败）时，除了照常发 result 事件，还要广播一条 error 事件，
    不然浏览器端只看到一个没有任何文字说明的 result，不知道这轮其实失败了。"""
    class AuthFailAgent(FakeAgent):
        async def send(self, prompt):
            self.prompts.append(prompt)
            yield Event("result", data={"cost": 0, "session_id": "s", "usage": {},
                                        "error": True, "result": "Failed to authenticate. API Error: 403"})

    s = make_settings(tmp_path)
    st = s.store.ensure(); chat = create_chat(st, model="m", source="web")
    r = ChatRunner(s, st, chat, {}, agent_factory=AuthFailAgent, confirm_timeout=0.2)
    q = r.subscribe()
    ok, _ = await r.submit("hi")
    assert ok
    evs = []
    while True:
        ev = await asyncio.wait_for(q.get(), 3); evs.append(ev)
        if ev["type"] == "error":
            break
    errors = [e for e in evs if e["type"] == "error"]
    assert len(errors) == 1 and "403" in errors[0]["message"]
    assert any(e["type"] == "result" for e in evs)


@pytest.mark.asyncio
async def test_close_always_resets_state_even_if_agent_close_raises(tmp_path):
    """agent.close() 本身炸了，close() 也不能停在半关闭状态：agent/turns/closing 必须归位。"""
    class RaisingCloseAgent(FakeAgent):
        async def close(self):
            raise RuntimeError("boom on agent.close")

    s = make_settings(tmp_path)
    st = s.store.ensure(); chat = create_chat(st, model="m", source="web")
    r = ChatRunner(s, st, chat, {}, agent_factory=RaisingCloseAgent, confirm_timeout=0.2)
    q = r.subscribe()
    await r.submit("a")
    while (await asyncio.wait_for(q.get(), 3))["type"] != "result":
        pass

    await r.close()  # 不应该抛出

    assert r.agent is None
    assert r.turns == 0
    assert r.closing is False


@pytest.mark.asyncio
async def test_pool_refuses_new_runner_over_max_active(tmp_path):
    """每个跑起来的 runner 都拖着一个 Claude CLI 子进程 + Biomni MCP：并发数必须有上限。"""
    s = make_settings(tmp_path)
    pool = RunnerPool(s, {}, agent_factory=FakeAgent, confirm_timeout=0.2, max_active=1)
    st = UserStore(tmp_path, "u").ensure()
    c1 = create_chat(st, model="m", source="web")
    c2 = create_chat(st, model="m", source="web")
    r1 = await pool.get("u", c1.id)
    assert await pool.get("u", c2.id) is not None   # 还没起 agent 的 runner 不占额度
    await pool.drop("u", c2.id, summarize=False)
    r1.running = True                               # 模拟这一个已经在跑
    with pytest.raises(RuntimeError) as e:
        await pool.get("u", c2.id)
    assert "繁忙" in str(e.value)
    assert await pool.get("u", c1.id) is r1         # 已存在的对话不受限
    await pool.close_all()


@pytest.mark.asyncio
async def test_slow_subscriber_is_dropped(tmp_path):
    """浏览器不再消费事件（pump 挂了）时，队列不能无限涨；满了就把这个订阅摘掉。"""
    s = make_settings(tmp_path)
    st = s.store.ensure(); chat = create_chat(st, model="m", source="web")
    r = ChatRunner(s, st, chat, {}, agent_factory=FakeAgent)
    q = r.subscribe()
    assert q.maxsize == 2000
    for _ in range(2100):
        r.emit({"type": "text_delta", "text": "x"})
    assert q not in r.subscribers and r.subscribers == set()
    assert q.qsize() == 2000


@pytest.mark.asyncio
async def test_submit_rejected_when_context_full(tmp_path):
    s = make_settings(tmp_path)
    st = s.store.ensure(); chat = create_chat(st, model="m", source="web")
    r = ChatRunner(s, st, chat, {}, agent_factory=FakeAgent, confirm_timeout=0.2)
    q = r.subscribe()
    await r.submit("a")
    while (await asyncio.wait_for(q.get(), 3))["type"] != "result":
        pass
    r.agent.context_tokens = r.agent.context_window  # 模拟上下文用满
    ok, why = await r.submit("b")
    assert not ok and "上下文已满" in why
    assert r.status()["context_full"] is True and r.status()["context_window"] == s.context_limit_tokens


@pytest.mark.asyncio
async def test_set_modules_restarts_agent_with_selection(tmp_path):
    from bioagent.config import BiomniSettings
    s = make_settings(tmp_path)
    s.biomni = BiomniSettings(enabled=True, modules=["biomni.tool.support_tools", "biomni.tool.database", "biomni.tool.genomics"],
                              default_modules=["support_tools", "database"])
    st = s.store.ensure(); chat = create_chat(st, model="m", source="web")
    r = ChatRunner(s, st, chat, {}, agent_factory=FakeAgent, confirm_timeout=0.2)
    assert r.modules() == ["support_tools", "database"]  # 默认
    await r.ensure_agent()
    first = FakeAgent.instances[-1]
    assert first.s.biomni.modules == ["biomni.tool.support_tools", "biomni.tool.database"]
    ok, _ = await r.set_modules(["genomics", "database"])
    assert ok and r.modules() == ["database", "genomics"] and chat.meta()["modules"] == ["database", "genomics"]
    assert first.closed and FakeAgent.instances[-1] is not first
    assert FakeAgent.instances[-1].s.biomni.modules == ["biomni.tool.database", "biomni.tool.genomics"]
    assert r.status()["modules"] == ["database", "genomics"] and r.status()["modules_total"] == 3
    ok, why = await r.set_modules(["nope"])
    assert not ok and "至少" in why


@pytest.mark.asyncio
async def test_turn_auto_retries_once_when_model_reply_lost(tmp_path):
    class FlakyAgent(FakeAgent):
        calls = 0
        async def send(self, prompt):
            FlakyAgent.calls += 1
            if FlakyAgent.calls == 1:
                yield Event("tool_use", name="Read", data={"input": {"file_path": "/x"}, "id": "t1"})
                yield Event("tool_result", text="ok", data={"id": "t1", "error": False})
                yield Event("result", data={"cost": 0.1, "session_id": self.session_id, "usage": {}, "error": True, "result": "", "errors": ["[ede_diagnostic] result_type=user"]})
                return
            self.prompts.append(prompt)
            yield Event("text", text="完成")
            yield Event("result", data={"cost": 0.2, "session_id": self.session_id, "usage": {}})
    s = make_settings(tmp_path)
    st = s.store.ensure(); chat = create_chat(st, model="m", source="web")
    r = ChatRunner(s, st, chat, {}, agent_factory=FlakyAgent, confirm_timeout=0.2)
    q = r.subscribe()
    await r.submit("做一件事")
    evs = []
    while True:
        ev = await asyncio.wait_for(q.get(), 5); evs.append(ev)
        if ev["type"] == "status" and not ev["running"] and any(e["type"] == "result" for e in evs):
            break
    types = [e["type"] for e in evs]
    assert FlakyAgent.calls == 2 and "继续" in FlakyAgent.instances[-1].prompts[-1]
    assert any(e["type"] == "error" and "自动重试" in e["message"] for e in evs)
    assert any(e["type"] == "text" and e["text"] == "完成" for e in evs) and types.count("result") == 1


@pytest.mark.asyncio
async def test_auto_permission_mode_skips_confirm(tmp_path):
    s = make_settings(tmp_path)
    st = s.store.ensure(); st.write_settings({"permission_mode": "auto"})
    chat = create_chat(st, model="m", source="web")
    r = ChatRunner(s, st, chat, {}, agent_factory=FakeAgent, confirm_timeout=0.2)
    q = r.subscribe()
    await r.submit("hi")
    evs = []
    while True:
        ev = await asyncio.wait_for(q.get(), 3); evs.append(ev)
        if ev["type"] == "result":
            break
    req = [e for e in evs if e["type"] == "confirm_request"][0]; rep = [e for e in evs if e["type"] == "confirm_reply"][0]
    assert req["auto"] is True and rep["ok"] is True and rep["auto"] is True
    assert [e for e in evs if e["type"] == "tool_result"][0]["text"] == "done"
    assert r.status()["permission_mode"] == "auto"
