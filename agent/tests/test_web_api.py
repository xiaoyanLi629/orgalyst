import pytest
from fastapi.testclient import TestClient

from bioagent.config import BiomniSettings, ProxySettings, Settings
from bioagent.web.app import create_app
from bioagent.web.auth import Accounts
from tests.test_web_runner import FakeAgent


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BIOAGENT_SECRETS_DIR", str(tmp_path / "sec"))
    s = Settings(root=tmp_path, assistant_name="X", model="claude-opus-5", cwd=tmp_path, readonly_dirs=[],
                 daily_cost_cap_usd=1, api_key="k", proxy=ProxySettings(enabled=False), biomni=BiomniSettings(enabled=False))
    acc = Accounts(tmp_path / "sec" / "users.yaml")
    acc.create("admin1", "pw-admin", role="admin")
    acc.create("bob", "pw-bob")
    acc.create("off", "pw-off"); acc.update("off", enabled=False)
    app = create_app(s, proxy_env={}, agent_factory=FakeAgent, accounts_path=acc.path, secret_path=tmp_path / "sec" / "web_secret")
    with TestClient(app) as c:
        yield c


def login(c, name, pw):
    return c.post("/api/login", json={"name": name, "password": pw})


def test_login_logout_me(client):
    assert client.get("/api/me").status_code == 401
    r = login(client, "bob", "wrong"); assert r.status_code == 401
    assert "set-cookie" not in r.headers
    r = login(client, "off", "pw-off"); assert r.status_code == 401
    r = login(client, "bob", "pw-bob"); assert r.status_code == 200 and r.json()["role"] == "user"
    me = client.get("/api/me").json()
    assert me["name"] == "bob" and me["model"] == "claude-opus-5" and me["over_limit"] is False
    client.post("/api/logout")
    assert client.get("/api/me").status_code == 401


def test_login_lockout(client):
    for _ in range(5):
        login(client, "bob", "wrong")
    r = login(client, "bob", "pw-bob")
    assert r.status_code == 429


def test_chats_crud_and_isolation(client):
    login(client, "bob", "pw-bob")
    r = client.post("/api/chats", json={}); assert r.status_code == 200
    cid = r.json()["id"]
    assert [m["id"] for m in client.get("/api/chats").json()] == [cid]
    assert client.patch(f"/api/chats/{cid}", json={"title": "改名"}).json()["title"] == "改名"
    assert client.get(f"/api/chats/{cid}/events").json() == []
    assert client.get(f"/api/chats/{cid}/status").json()["running"] is False
    # 别人的对话 404
    client.post("/api/logout"); login(client, "admin1", "pw-admin")
    assert client.get(f"/api/chats/{cid}/events").status_code == 404
    assert client.delete(f"/api/chats/{cid}").status_code == 404
    client.post("/api/logout"); login(client, "bob", "pw-bob")
    assert client.delete(f"/api/chats/{cid}").status_code == 200
    assert client.get("/api/chats").json() == []
    assert client.get("/api/chats/../x/events").status_code in (404, 422)


def test_settings_memory_password(client):
    login(client, "bob", "pw-bob")
    assert client.get("/api/settings").json()["model"] == "claude-opus-5"
    assert client.put("/api/settings", json={"model": "claude-sonnet-5"}).status_code == 200
    assert client.get("/api/settings").json()["model"] == "claude-sonnet-5"
    assert client.put("/api/settings", json={"model": "gpt-9"}).status_code == 400
    assert client.get("/api/memory").json()["text"] == ""
    client.put("/api/memory", json={"text": "- 2026-09-10 记住我"})
    assert "记住我" in client.get("/api/memory").json()["text"]
    assert client.post("/api/password", json={"old": "bad", "new": "x"}).status_code == 400
    assert client.post("/api/password", json={"old": "pw-bob", "new": "pw2"}).status_code == 400
    assert client.post("/api/password", json={"old": "pw-bob", "new": "pw2-longer"}).status_code == 200
    client.post("/api/logout")
    assert login(client, "bob", "pw2-longer").status_code == 200


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "<html" in r.text.lower()



def recv_skip_status(ws):
    """预热会额外回推 status 事件；读到下一条非 status 消息。"""
    while True:
        ev = ws.receive_json()
        if ev["type"] != "status":
            return ev


def test_websocket_turn_and_replay(client):
    login(client, "bob", "pw-bob")
    cid = client.post("/api/chats", json={}).json()["id"]
    with client.websocket_connect(f"/ws/chat/{cid}") as ws:
        first = ws.receive_json(); assert first["type"] == "history" and first["events"] == []
        assert ws.receive_json()["type"] == "status"
        ws.send_json({"type": "prompt", "text": "hi"})
        assert recv_skip_status(ws)["type"] == "accepted"
        seen = []
        while True:
            ev = ws.receive_json(); seen.append(ev["type"])
            if ev["type"] == "confirm_request":
                ws.send_json({"type": "confirm_reply", "id": ev["id"], "ok": True})
            if ev["type"] == "result":
                break
        assert "text_delta" in seen and "tool_use" in seen and "tool_result" in seen
        assert ws.receive_json()["type"] == "status"  # 回合结束 runner 会再发一次 status
        ws.send_json({"type": "prompt", "text": ""})
        assert ws.receive_json()["type"] == "rejected"
    # 重连回放
    with client.websocket_connect(f"/ws/chat/{cid}") as ws:
        h = ws.receive_json()
        types = [e["type"] for e in h["events"]]
        assert types[0] == "user" and "text" in types and "result" in types


def test_websocket_rejects_foreign_and_anonymous(client):
    login(client, "bob", "pw-bob")
    cid = client.post("/api/chats", json={}).json()["id"]
    client.post("/api/logout")
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/chat/{cid}") as ws:
            ws.receive_json()
    login(client, "admin1", "pw-admin")
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/chat/{cid}") as ws:
            ws.receive_json()


def test_websocket_receives_chat_deleted_and_closes(client):
    """另一个连接（或同一个客户端的普通 HTTP 请求）删除了正在被 ws 订阅的对话：
    ws 要先收到 chat_deleted 广播，随后连接被服务端关闭（4404），不能悬空挂着。"""
    from starlette.websockets import WebSocketDisconnect
    login(client, "bob", "pw-bob")
    cid = client.post("/api/chats", json={}).json()["id"]
    with client.websocket_connect(f"/ws/chat/{cid}") as ws:
        ws.receive_json()  # history
        ws.receive_json()  # status
        assert client.delete(f"/api/chats/{cid}").status_code == 200
        ev = recv_skip_status(ws)
        assert ev["type"] == "chat_deleted"
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_websocket_migrates_subscription_when_runner_closing(client):
    """模拟 reap_idle 已经把 runner 从池里摘掉、正在慢慢 close（closing=True）时收到 prompt：
    ws 要迁到新 runner，且旧 runner 的订阅必须被正确摘掉，不能留下悬空队列。"""
    login(client, "bob", "pw-bob")
    cid = client.post("/api/chats", json={}).json()["id"]
    with client.websocket_connect(f"/ws/chat/{cid}") as ws:
        ws.receive_json()  # history
        ws.receive_json()  # status
        pool = client.app.state.pool
        old = pool.peek("bob", cid)
        assert old is not None
        pool.runners.pop(("bob", cid), None)  # 模拟 reap_idle：已从池摘除
        old.closing = True  # 模拟 close() 已开始，正在慢慢收尾
        ws.send_json({"type": "prompt", "text": "hi"})
        assert recv_skip_status(ws)["type"] == "accepted"
        new = pool.peek("bob", cid)
        assert new is not None and new is not old
        assert len(old.subscribers) == 0
        assert len(new.subscribers) == 1
        # 把这一轮跑完，避免连接关闭时留下悬空的确认等待任务
        seen = []
        while True:
            ev = ws.receive_json(); seen.append(ev["type"])
            if ev["type"] == "confirm_request":
                ws.send_json({"type": "confirm_reply", "id": ev["id"], "ok": True})
            if ev["type"] == "result":
                break
        assert "tool_result" in seen


def test_admin_users_and_usage(client):
    login(client, "bob", "pw-bob")
    assert client.get("/api/admin/users").status_code == 403
    client.post("/api/logout"); login(client, "admin1", "pw-admin")
    rows = client.get("/api/admin/users").json()
    assert {r["name"] for r in rows} >= {"admin1", "bob", "off"} and "password_hash" not in rows[0]
    assert client.post("/api/admin/users", json={"name": "carol", "password": "pw-carol", "role": "user"}).status_code == 200
    assert client.post("/api/admin/users", json={"name": "carol", "password": "x", "role": "user"}).status_code == 400
    r = client.patch("/api/admin/users/carol", json={"daily_usd": 1.5, "quota_gb": 5, "enabled": False})
    assert r.json()["daily_usd"] == 1.5 and r.json()["enabled"] is False
    assert client.post("/api/admin/users/carol/password", json={"password": "new-pw"}).status_code == 200
    assert client.delete("/api/admin/users/admin1").status_code == 400
    assert client.delete("/api/admin/users/carol").status_code == 200
    # 用量表
    from bioagent.store import UserStore
    from bioagent.usage import UsageLog
    UsageLog(UserStore(client.app.state.settings.root, "bob").ensure().usage_file).add(session="s", model="m", usage={"input_tokens": 3}, cost=0.25)
    rows = client.get("/api/admin/usage", params={"by": "user"}).json()
    assert [r for r in rows if r["账号"] == "bob"][0]["费用$"] == 0.25
    csv = client.get("/api/admin/usage", params={"by": "day", "format": "csv"}).text
    assert csv.splitlines()[0].startswith("账号,") and "bob" in csv
    assert any(r["name"] == "bob" and r["usage_today"] == 0.25 for r in client.get("/api/admin/users").json())
    st = client.get("/api/admin/storage").json()
    assert any(r["name"] == "bob" for r in st)


def test_admin_files_and_logs(client):
    login(client, "bob", "pw-bob")
    client.post("/api/files/mkdir", json={"scope": "files", "path": "d1"})
    client.post("/api/logout"); login(client, "admin1", "pw-admin")
    r = client.get("/api/admin/files", params={"user": "bob", "scope": "files", "path": ""})
    assert r.status_code == 200 and r.json()["entries"][0]["name"] == "d1"
    assert client.get("/api/admin/files", params={"user": "nobody", "scope": "files", "path": ""}).status_code == 404
    logs = client.get("/api/admin/logs").json()
    assert any("admin1 OK" in line for line in logs["auth"])


def test_static_assets(client):
    for p in ("/static/app.js", "/static/style.css", "/static/vendor/marked.min.js", "/static/vendor/purify.min.js"):
        assert client.get(p).status_code == 200, p
    html = client.get("/").text
    for id_ in ("view-login", "view-chat", "view-settings", "view-admin", "prompt-form", "file-list", "users-table"):
        assert f'id="{id_}"' in html, id_


def test_login_rejects_malformed_name_without_storing_state(client):
    """用户名先按 USER_NAME_RE 校验：1 MB 的用户名不能在限流字典里留下键。"""
    r = login(client, "a" * 100_000, "x")
    assert r.status_code == 401 and r.json()["detail"] == "用户名或密码错误"
    assert login(client, "bob; rm -rf /", "x").status_code == 401
    assert dict(client.app.state.limiter.hits) == {} and dict(client.app.state.limiter.failures) == {}


def test_websocket_rejects_foreign_origin(client):
    """只比主机名：AutoDL 公网代理把 Host 写成不带端口的域名，浏览器的 Origin 却带着 :8443。"""
    from starlette.websockets import WebSocketDisconnect
    login(client, "bob", "pw-bob")
    cid = client.post("/api/chats", json={}).json()["id"]
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/chat/{cid}", headers={"origin": "https://evil.example"}) as ws:
            ws.receive_json()
    # 带了 Origin 但解析不出主机名（沙箱 iframe 发的 null）也算跨站
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/chat/{cid}", headers={"origin": "null"}) as ws:
            ws.receive_json()
    with client.websocket_connect(f"/ws/chat/{cid}", headers={"origin": "http://testserver"}) as ws:
        assert ws.receive_json()["type"] == "history"
    # Origin 带端口、Host 不带（公网代理的实际形态）
    with client.websocket_connect(f"/ws/chat/{cid}", headers={"origin": "https://testserver:8443"}) as ws:
        assert ws.receive_json()["type"] == "history"
    # Origin 对上的是 X-Forwarded-Host 而不是 Host
    with client.websocket_connect(f"/ws/chat/{cid}",
                                  headers={"origin": "https://pub.example:8443", "x-forwarded-host": "pub.example"}) as ws:
        assert ws.receive_json()["type"] == "history"


def test_status_does_not_allocate_runner(client):
    """状态查询不能顺手起一个 runner（浏览器轮询会把并发额度耗光）。"""
    login(client, "bob", "pw-bob")
    cid = client.post("/api/chats", json={}).json()["id"]
    r = client.get(f"/api/chats/{cid}/status").json()
    assert r["type"] == "status" and r["running"] is False and r["over_limit"] is False
    assert r["model"] == "claude-opus-5" and r["cost_total"] == 0.0
    assert client.app.state.pool.peek("bob", cid) is None


def test_websocket_prewarms_agent(client):
    login(client, "bob", "pw-bob")
    cid = client.post("/api/chats", json={}).json()["id"]
    with client.websocket_connect(f"/ws/chat/{cid}") as ws:
        assert ws.receive_json()["type"] == "history"
        assert ws.receive_json()["type"] == "status"
        st = ws.receive_json()  # 预热完成后回推的 status
        assert st["type"] == "status" and st["running"] is False
        r = client.app.state.pool.peek("bob", cid)
        assert r is not None and r.agent is not None and r.agent.started


def test_modules_endpoints(client):
    login(client, "bob", "pw-bob")
    cat = client.get("/api/modules").json()
    assert cat["available"] == [] and cat["default"] == []  # 测试配置未启用工具库
    cid = client.post("/api/chats", json={}).json()["id"]
    assert client.get(f"/api/chats/{cid}/modules").json() == {"modules": []}
    assert client.put(f"/api/chats/{cid}/modules", json={"modules": ["database"]}).status_code == 409
    assert client.get("/api/chats/../x/modules").status_code in (404, 422)
    assert "modules" in client.get(f"/api/chats/{cid}/status").json()


def test_settings_permission_mode(client):
    login(client, "bob", "pw-bob")
    assert client.get("/api/settings").json()["permission_mode"] == "ask"
    assert client.put("/api/settings", json={"permission_mode": "auto"}).status_code == 200
    assert client.get("/api/settings").json()["permission_mode"] == "auto"
    assert client.put("/api/settings", json={"permission_mode": "yolo"}).status_code == 400
    assert client.get("/api/settings").json()["model"] == "claude-opus-5"  # 未改动模型


def test_chat_permission_mode_per_chat(client):
    login(client, "bob", "pw-bob")
    cid = client.post("/api/chats", json={}).json()["id"]
    assert client.get(f"/api/chats/{cid}/status").json()["permission_mode"] == "ask"
    assert client.put(f"/api/chats/{cid}/permission", json={"mode": "auto"}).json()["permission_mode"] == "auto"
    assert client.get(f"/api/chats/{cid}/status").json()["permission_mode"] == "auto"
    cid2 = client.post("/api/chats", json={}).json()["id"]
    assert client.get(f"/api/chats/{cid2}/status").json()["permission_mode"] == "ask"  # 另一个对话不受影响
    assert client.put(f"/api/chats/{cid}/permission", json={"mode": "yolo"}).status_code == 400
