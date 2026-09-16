from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    StreamEvent,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from bioagent.agent import normalize


def test_stream_text_delta():
    ev = StreamEvent(
        uuid="u",
        session_id="s",
        event={"type": "content_block_delta", "delta": {"type": "text_delta", "text": "hi"}},
    )
    out = normalize(ev)
    assert out[0].kind == "text" and out[0].text == "hi"


def test_stream_non_text_ignored():
    ev = StreamEvent(uuid="u", session_id="s", event={"type": "message_start"})
    assert normalize(ev) == []


def test_assistant_emits_tool_use_only():
    am = AssistantMessage(
        content=[TextBlock(text="x"), ToolUseBlock(id="t1", name="Read", input={"file_path": "/a"})],
        model="m",
    )
    out = normalize(am)
    assert [e.kind for e in out] == ["tool_use"]
    assert out[0].name == "Read" and out[0].data["input"] == {"file_path": "/a"} and out[0].data["id"] == "t1"


def test_result_cost_and_session():
    rm = ResultMessage(
        subtype="success", duration_ms=1, duration_api_ms=1, is_error=False,
        num_turns=1, session_id="s", total_cost_usd=0.01,
    )
    r = normalize(rm)[0]
    assert r.kind == "result" and r.data["cost"] == 0.01 and r.data["session_id"] == "s"


def test_user_tool_result_string_and_blocks():
    um = UserMessage(content=[ToolResultBlock(tool_use_id="t1", content="ok", is_error=False)])
    e = normalize(um)[0]
    assert e.kind == "tool_result" and e.text == "ok" and e.data["error"] is False
    um2 = UserMessage(content=[ToolResultBlock(tool_use_id="t2", content=[{"type": "text", "text": "a"}, {"type": "text", "text": "b"}], is_error=True)])
    e2 = normalize(um2)[0]
    assert e2.text == "a\nb" and e2.data["error"] is True


def test_plain_user_string_ignored():
    assert normalize(UserMessage(content="hello")) == []


def test_assistant_usage_event_and_context_window():
    from claude_agent_sdk.types import AssistantMessage, TextBlock
    from bioagent.agent import normalize
    m = AssistantMessage(content=[TextBlock(text="hi")], model="claude-opus-5",
                         usage={"input_tokens": 1000, "cache_read_input_tokens": 40000, "cache_creation_input_tokens": 500, "output_tokens": 20})
    evs = normalize(m)
    assert evs[0].kind == "usage" and evs[0].data["context_tokens"] == 41500
    r = ResultMessage(subtype="success", duration_ms=1, duration_api_ms=1, is_error=False,
                      num_turns=1, session_id="s", total_cost_usd=0.01,
                      model_usage={"claude-opus-5": {"contextWindow": 1000000}})
    assert normalize(r)[0].data["context_window"] == 1000000


def test_context_bar():
    from bioagent.ui import UI
    bar = UI.context_bar(42000, 200000)
    assert bar.endswith("21% (42k/200k)") and bar.count("▮") == 4
    assert UI.context_bar(0, 200000).startswith("░" * 20)


def test_context_limit_from_settings(tmp_path):
    from bioagent.config import BiomniSettings, ProxySettings, Settings
    from bioagent.agent import Agent
    s = Settings(root=tmp_path, assistant_name="X", model="m", cwd=tmp_path, readonly_dirs=[], daily_cost_cap_usd=1,
                 api_key="k", proxy=ProxySettings(enabled=False), biomni=BiomniSettings(enabled=False), user="u",
                 context_limit_tokens=150_000)
    a = Agent(s, {}, None, "p")
    assert a.context_window == 150_000 and not a.context_full
    a.context_tokens = 150_000
    assert a.context_full


def test_agent_buffer_size_raised(tmp_path):
    from bioagent.config import BiomniSettings, ProxySettings, Settings
    from bioagent.agent import Agent
    s = Settings(root=tmp_path, assistant_name="X", model="m", cwd=tmp_path, readonly_dirs=[], daily_cost_cap_usd=1,
                 api_key="k", proxy=ProxySettings(enabled=False), biomni=BiomniSettings(enabled=False), user="u")
    assert Agent(s, {}, None, "p").options.max_buffer_size == 512 * 1024 * 1024


def test_agent_loads_skillpack(tmp_path):
    from bioagent.config import BiomniSettings, ProxySettings, Settings
    from bioagent.agent import Agent
    (tmp_path / "skillpack" / "skills" / "literature-review").mkdir(parents=True)
    (tmp_path / "skillpack" / "skills" / "literature-review" / "SKILL.md").write_text("---\nname: literature-review\n---\n")
    (tmp_path / "skillpack" / "skills" / "junk").mkdir()
    s = Settings(root=tmp_path, assistant_name="X", model="m", cwd=tmp_path, readonly_dirs=[], daily_cost_cap_usd=1,
                 api_key="k", proxy=ProxySettings(enabled=False), biomni=BiomniSettings(enabled=False), user="u")
    a = Agent(s, {}, None, "p")
    assert a.skill_names == ["bioagent:literature-review"]
    assert a.options.skills == ["bioagent:literature-review"] and a.options.plugins[0]["path"].endswith("skillpack")
