"""FastAPI 应用：登录、对话、设置、记忆、静态页；files/admin/ws 路由在各自模块里挂载。"""
from __future__ import annotations

import asyncio
import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..chats import create_chat, delete_chat, get_chat, list_chats, read_events
from ..config import USER_NAME_RE
from ..store import UserStore, list_users
from ..usage import UsageLog, check_limits, load_limits
from .auth import COOKIE_NAME, Accounts, CookieSigner, RateLimiter, auth_log, current_user, load_or_create_secret
from .runner import RunnerPool
from ..modules import COUNT, LABEL, MODULES, normalize, short
from ..permissions import PERMISSION_MODES

STATIC = Path(__file__).parent / "static"
MODELS = ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5-20251001"]
log = logging.getLogger("bioagent.web")


class LoginIn(BaseModel):
    name: str
    password: str


class TitleIn(BaseModel):
    title: str = ""


class SettingsIn(BaseModel):
    model: str | None = None
    permission_mode: str | None = None  # ask | auto


class PasswordIn(BaseModel):
    old: str
    new: str


class MemoryIn(BaseModel):
    text: str


class ModulesIn(BaseModel):
    modules: list[str]


class PermissionIn(BaseModel):
    mode: str


def _store(request: Request, user: dict) -> UserStore:
    return UserStore(request.app.state.settings.root, user["name"]).ensure()


def _chat_or_404(request: Request, user: dict, chat_id: str):
    chat = get_chat(_store(request, user), chat_id)
    if chat is None:
        raise HTTPException(404, "对话不存在")
    return chat


def create_app(settings, *, proxy_env: dict | None = None, agent_factory=None,
               accounts_path: Path | None = None, secret_path: Path | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        st = app.state

        async def reaper():
            while True:
                await asyncio.sleep(60)
                try:
                    await st.pool.reap_idle()
                    from .files import cleanup_stale_uploads
                    for u in list_users(settings.root):
                        cleanup_stale_uploads(UserStore(settings.root, u))
                except Exception as e:  # noqa: BLE001
                    log.warning("reap_idle: %r", e)

        st.reaper = asyncio.create_task(reaper())
        try:
            yield
        finally:
            st.reaper.cancel()
            await st.pool.close_all()

    app = FastAPI(title="BioAgent", docs_url=None, redoc_url=None, lifespan=lifespan)
    st = app.state
    st.settings = settings
    st.accounts = Accounts(accounts_path or settings.secrets_dir / "users.yaml")
    st.signer = CookieSigner(load_or_create_secret(secret_path or settings.secrets_dir / "web_secret"))
    st.limiter = RateLimiter()
    st.pool = RunnerPool(settings, proxy_env or {}, agent_factory=agent_factory)
    st.logs_dir = settings.root / "logs"
    st.auth_log_path = st.logs_dir / "auth.log"

    # ---- 登录 ----
    @app.post("/api/login")
    async def login(body: LoginIn, request: Request, response: Response):
        ip = request.client.host if request.client else "?"
        # 用户名先按 USER_NAME_RE 校验：不合法的名字不该在限流字典里留键，也不该写进 auth.log
        if not re.match(USER_NAME_RE, body.name or ""):
            raise HTTPException(401, "用户名或密码错误")
        # 公网访问全部经 AutoDL 代理，客户端 IP 是同一个，20/分钟会误伤正常用户
        if not st.limiter.allow(f"ip:{ip}", 60, 60) or st.limiter.locked(body.name):
            auth_log(st.auth_log_path, ip, body.name, False, "rate-limited")
            raise HTTPException(429, "尝试过于频繁，请 1 分钟后再试")
        if not st.accounts.verify(body.name, body.password):
            st.limiter.record_failure(body.name)
            auth_log(st.auth_log_path, ip, body.name, False)
            raise HTTPException(401, "用户名或密码错误")
        st.limiter.clear(body.name)
        auth_log(st.auth_log_path, ip, body.name, True)
        secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
        response.set_cookie(COOKIE_NAME, st.signer.sign(body.name), max_age=30 * 86400, httponly=True,
                            samesite="lax", secure=secure, path="/")
        u = st.accounts.get(body.name)
        return {"name": body.name, "role": u.get("role", "user")}

    @app.post("/api/logout")
    async def logout(response: Response):
        response.delete_cookie(COOKIE_NAME, path="/")
        return {"ok": True}

    @app.get("/api/me")
    async def me(request: Request, user: dict = Depends(current_user)):
        store = _store(request, user)
        ok, text = check_limits(UsageLog(store.usage_file), user["name"], load_limits(st.accounts.path))
        return {"name": user["name"], "role": user.get("role", "user"),
                "model": store.read_settings().get("model") or settings.model, "limit_text": text, "over_limit": not ok}

    # ---- 对话 ----
    @app.get("/api/chats")
    async def chats(request: Request, user: dict = Depends(current_user)):
        return list_chats(_store(request, user))

    @app.post("/api/chats")
    async def chat_new(body: TitleIn, request: Request, user: dict = Depends(current_user)):
        store = _store(request, user)
        model = store.read_settings().get("model") or settings.model
        return create_chat(store, model=model, source="web", title=body.title).meta()

    @app.patch("/api/chats/{chat_id}")
    async def chat_rename(chat_id: str, body: TitleIn, request: Request, user: dict = Depends(current_user)):
        return _chat_or_404(request, user, chat_id).update(title=body.title.strip()[:80])

    @app.delete("/api/chats/{chat_id}")
    async def chat_delete(chat_id: str, request: Request, user: dict = Depends(current_user)):
        chat = _chat_or_404(request, user, chat_id)
        r = st.pool.peek(user["name"], chat_id)
        if r:
            r.emit({"type": "chat_deleted"})
        await st.pool.drop(user["name"], chat_id, summarize=False)
        delete_chat(chat)
        return {"ok": True}

    @app.get("/api/chats/{chat_id}/events")
    async def chat_events(chat_id: str, request: Request, user: dict = Depends(current_user)):
        return read_events(_chat_or_404(request, user, chat_id))

    @app.get("/api/chats/{chat_id}/status")
    async def chat_status(chat_id: str, request: Request, user: dict = Depends(current_user)):
        """只查不建：浏览器轮询状态不该顺手占掉一个并发额度（runner 会拖着 agent 子进程）。"""
        chat = _chat_or_404(request, user, chat_id)
        r = st.pool.peek(user["name"], chat_id)
        if r is not None:
            return r.status()
        store = _store(request, user)
        ok, text = check_limits(UsageLog(store.usage_file), user["name"], load_limits(st.accounts.path))
        return {"type": "status", "running": False, "over_limit": not ok, "limit_text": text,
                "context_tokens": 0, "context_window": settings.context_limit_tokens, "context_full": False,
                "modules": (await chat_modules_get(chat_id, request, user))["modules"], "modules_total": len(settings.biomni.modules),
                "permission_mode": chat.meta().get("permission_mode") or _store(request, user).read_settings().get("permission_mode") or "ask", "cost_total": chat.meta().get("cost", 0.0),
                "model": store.read_settings().get("model") or settings.model}

    # ---- 工具库模块（按需加载）----
    @app.get("/api/modules")
    async def modules_list(user: dict = Depends(current_user)):
        avail = {short(m) for m in settings.biomni.modules}
        default = [short(m) for m in normalize(settings.biomni.default_modules, settings.biomni.modules)] or sorted(avail, key=[n for n, _, _ in MODULES].index)
        return {"available": [{"name": n, "label": LABEL[n], "count": COUNT[n]} for n, _, _ in MODULES if n in avail], "default": default}

    @app.get("/api/chats/{chat_id}/modules")
    async def chat_modules_get(chat_id: str, request: Request, user: dict = Depends(current_user)):
        chat = _chat_or_404(request, user, chat_id)
        r = st.pool.peek(user["name"], chat_id)
        if r is not None:
            return {"modules": r.modules()}
        picked = chat.meta().get("modules") or settings.biomni.default_modules
        mods = normalize(picked, settings.biomni.modules) if picked else list(settings.biomni.modules)
        return {"modules": [short(m) for m in mods]}

    @app.put("/api/chats/{chat_id}/modules")
    async def chat_modules_put(chat_id: str, body: ModulesIn, request: Request, user: dict = Depends(current_user)):
        _chat_or_404(request, user, chat_id)
        try:
            r = await st.pool.get(user["name"], chat_id)
        except RuntimeError as e:
            raise HTTPException(503, str(e))
        ok, why = await r.set_modules(body.modules)
        if not ok:
            raise HTTPException(409, why)
        return {"modules": r.modules()}

    @app.put("/api/chats/{chat_id}/permission")
    async def chat_permission_put(chat_id: str, body: PermissionIn, request: Request, user: dict = Depends(current_user)):
        chat = _chat_or_404(request, user, chat_id)
        if body.mode not in PERMISSION_MODES:
            raise HTTPException(400, "确认方式只能是 " + "/".join(PERMISSION_MODES))
        r = st.pool.peek(user["name"], chat_id)
        if r is not None:
            r.set_permission_mode(body.mode)
        else:
            chat.update(permission_mode=body.mode)
        return {"permission_mode": body.mode}

    # ---- 设置 / 记忆 / 密码 ----
    @app.get("/api/settings")
    async def settings_get(request: Request, user: dict = Depends(current_user)):
        store = _store(request, user)
        st_ = store.read_settings()
        return {"model": st_.get("model") or settings.model, "models": MODELS, "permission_mode": st_.get("permission_mode") or "ask"}

    @app.put("/api/settings")
    async def settings_put(body: SettingsIn, request: Request, user: dict = Depends(current_user)):
        store = _store(request, user)
        data = store.read_settings()
        if body.model is not None:
            if body.model not in MODELS:
                raise HTTPException(400, "不支持的模型")
            data["model"] = body.model
        if body.permission_mode is not None:
            if body.permission_mode not in PERMISSION_MODES:
                raise HTTPException(400, "确认方式只能是 " + "/".join(PERMISSION_MODES))
            data["permission_mode"] = body.permission_mode
        store.write_settings(data)
        return {"ok": True}

    @app.get("/api/memory")
    async def memory_get(request: Request, user: dict = Depends(current_user)):
        f = _store(request, user).memory_file
        return {"text": f.read_text(encoding="utf-8") if f.exists() else ""}

    @app.put("/api/memory")
    async def memory_put(body: MemoryIn, request: Request, user: dict = Depends(current_user)):
        _store(request, user).memory_file.write_text(body.text[:20000], encoding="utf-8")
        return {"ok": True}

    @app.post("/api/password")
    async def password(body: PasswordIn, user: dict = Depends(current_user)):
        if not st.accounts.verify(user["name"], body.old):
            raise HTTPException(400, "原密码不对")
        if len(body.new) < 6:
            raise HTTPException(400, "新密码至少 6 位")
        st.accounts.set_password(user["name"], body.new)
        return {"ok": True}

    # ---- 其它模块的路由 ----
    from .admin import router as admin_router  # noqa: E402
    from .files import router as files_router  # noqa: E402
    from .ws import router as ws_router  # noqa: E402
    app.include_router(files_router)
    app.include_router(admin_router)
    app.include_router(ws_router)

    # ---- 静态页 ----
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

    @app.get("/")
    async def index():
        # 静态文件带版本号（修改时间），改了前端刷新即可生效，不受浏览器缓存影响
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        for name in ("app.js", "style.css"):
            try:
                v = int((STATIC / name).stat().st_mtime)
            except OSError:
                v = 0
            html = html.replace(f"/static/{name}", f"/static/{name}?v={v}")
        return HTMLResponse(html, headers={"Cache-Control": "no-cache"})

    return app
