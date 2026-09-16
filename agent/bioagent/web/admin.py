"""管理后台 API（仅 admin）。"""
from __future__ import annotations

import csv
import io
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

from ..store import UserStore, list_users, safe_join
from ..usage import UsageLog, report
from .auth import admin_only
from .files import _entries, base_for, cached_dir_size, quota_bytes

router = APIRouter(prefix="/api/admin", dependencies=[Depends(admin_only)])


class NewUser(BaseModel):
    name: str
    password: str
    role: str = "user"


class PatchUser(BaseModel):
    enabled: bool | None = None
    role: str | None = None
    daily_usd: float | None = None
    monthly_usd: float | None = None
    quota_gb: float | None = None


class PasswordIn(BaseModel):
    password: str


def _acc(request: Request):
    return request.app.state.accounts


@router.get("/users")
async def users(request: Request):
    root = request.app.state.settings.root
    rows = _acc(request).list()
    for r in rows:
        st = UserStore(root, r["name"])
        log = UsageLog(st.usage_file)
        r["usage_today"] = log.spent("day")
        r["usage_month"] = log.spent("month")
        r["storage_bytes"] = await cached_dir_size(r["name"], st.files_dir)
    return rows


@router.post("/users")
async def user_create(body: NewUser, request: Request):
    if body.role not in ("admin", "user"):
        raise HTTPException(400, "角色只能是 admin 或 user")
    if len(body.password) < 6:
        raise HTTPException(400, "密码至少 6 位")
    try:
        u = _acc(request).create(body.name, body.password, role=body.role)
    except ValueError as e:
        raise HTTPException(400, str(e))
    UserStore(request.app.state.settings.root, body.name).ensure()
    return {k: v for k, v in u.items() if k != "password_hash"}


@router.patch("/users/{name}")
async def user_patch(name: str, body: PatchUser, request: Request, admin: dict = Depends(admin_only)):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if "role" in fields and fields["role"] not in ("admin", "user"):
        raise HTTPException(400, "角色只能是 admin 或 user")
    if name == admin["name"] and (fields.get("enabled") is False or fields.get("role") == "user"):
        raise HTTPException(400, "不能停用或降级自己")
    try:
        u = _acc(request).update(name, **fields)
    except KeyError:
        raise HTTPException(404, "账号不存在")
    return {k: v for k, v in u.items() if k != "password_hash"}


@router.delete("/users/{name}")
async def user_delete(name: str, request: Request, admin: dict = Depends(admin_only)):
    if name == admin["name"]:
        raise HTTPException(400, "不能删除自己")
    if not _acc(request).get(name):
        raise HTTPException(404, "账号不存在")
    _acc(request).delete(name)
    return {"ok": True, "note": "数据目录未删除，如需清理请在服务器上手动删除"}


@router.post("/users/{name}/password")
async def user_password(name: str, body: PasswordIn, request: Request):
    if len(body.password) < 6:
        raise HTTPException(400, "密码至少 6 位")
    try:
        _acc(request).set_password(name, body.password)
    except KeyError:
        raise HTTPException(404, "账号不存在")
    return {"ok": True}


@router.get("/usage")
async def usage(request: Request, by: str = "user", user: str = "", since: str = "", until: str = "", format: str = "json"):
    if by not in ("user", "day", "month"):
        raise HTTPException(400, "by 只能是 user/day/month")
    rows = report(request.app.state.settings.users_root, users=[user] if user else None, by=by, since=since, until=until)
    if format == "csv":
        buf = io.StringIO()
        if rows:
            w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
        return PlainTextResponse(buf.getvalue(), media_type="text/csv",
                                 headers={"Content-Disposition": f"attachment; filename=usage-{time.strftime('%Y%m%d')}.csv"})
    return rows


@router.get("/storage")
async def storage(request: Request):
    root = request.app.state.settings.root
    acc = _acc(request)
    return [{"name": u, "bytes": await cached_dir_size(u, UserStore(root, u).files_dir),
             "quota_gb": quota_bytes(acc, u) / 2**30}
            for u in list_users(root)]


def _admin_target(request: Request, user: str, scope: str, path: str):
    root = request.app.state.settings.root
    if user not in list_users(root):
        raise HTTPException(404, "账号目录不存在")
    store = UserStore(root, user)
    base = base_for(store, scope)
    try:
        return base, safe_join(base, path)
    except ValueError:
        raise HTTPException(400, "路径不合法")


@router.get("/files")
async def admin_files(user: str, scope: str = "files", path: str = "", request: Request = None):
    _, t = _admin_target(request, user, scope, path)
    if not t.is_dir():
        raise HTTPException(404, "目录不存在")
    return {"path": path.strip("/"), "entries": _entries(t)}


@router.get("/files/download")
async def admin_download(user: str, scope: str, path: str, request: Request):
    _, t = _admin_target(request, user, scope, path)
    if not t.is_file():
        raise HTTPException(404, "文件不存在")
    return FileResponse(t, filename=t.name)


@router.get("/logs")
async def logs(request: Request, n: int = 200):
    st = request.app.state

    def tail(p, n):
        try:
            return p.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
        except OSError:
            return []

    return {"auth": tail(st.auth_log_path, n), "web": tail(st.logs_dir / "web.log", n)}
