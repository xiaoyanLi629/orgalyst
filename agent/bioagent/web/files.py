"""文件面板 API：浏览/下载/zip/预览/删除/建目录；分块上传（断点续传、配额）。"""
from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
import tempfile
import time
import uuid
import zipfile
from pathlib import Path
from urllib.parse import quote

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from ..chats import get_chat
from ..store import UserStore, dir_size, safe_join
from .auth import current_user

router = APIRouter()
CHUNK_SIZE = 5 * 2**20
MAX_FILE = 10 * 2**30
TEXT_EXT = {".txt", ".md", ".csv", ".tsv", ".json", ".yaml", ".yml", ".py", ".r", ".log", ".fa", ".fasta", ".fastq", ".gtf", ".bed", ".vcf", ".sh"}
IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
SIZE_TTL = 300.0                                        # dir_size 缓存 5 分钟（规格 §3）
_size_cache: dict[str, tuple[float, str, int]] = {}      # {账号: (时间戳, 目录, 字节数)}


def invalidate(user: str) -> None:
    """写操作后立刻让容量缓存失效，别让管理页和配额判断看到旧数字。"""
    _size_cache.pop(user, None)


async def cached_dir_size(user: str, path: Path) -> int:
    """dir_size 要走整棵树，几万个文件时是几百毫秒的同步 IO：丢线程池 + 缓存 5 分钟。

    缓存里连目录一起存，换了目录（测试、账号改名）就算未命中。"""
    hit = _size_cache.get(user)
    if hit and hit[1] == str(path) and time.time() - hit[0] < SIZE_TTL:
        return hit[2]
    n = await run_in_threadpool(dir_size, path)
    _size_cache[user] = (time.time(), str(path), n)
    return n


def sanitize_name(name: str) -> str:
    name = (name or "").replace("\\", "/").split("/")[-1]
    name = re.sub(r"[\x00-\x1f]", "", name).strip()
    name = name.lstrip(".") if name.startswith("..") else name
    return name or "unnamed"


def unique_name(d: Path, name: str) -> Path:
    stem, ext = os.path.splitext(name)
    cand = d / name
    i = 1
    while cand.exists():
        cand = d / f"{stem} ({i}){ext}"
        i += 1
    return cand


def quota_bytes(accounts, name: str) -> int:
    u = accounts.get(name) or {}
    q = u.get("quota_gb")
    if q is None:
        q = (accounts.load().get("default") or {}).get("quota_gb", 50)
    return int(float(q) * 2**30)


def _store(request: Request, user: dict) -> UserStore:
    return UserStore(request.app.state.settings.root, user["name"]).ensure()


def base_for(store: UserStore, scope: str) -> Path:
    if scope == "files":
        return store.files_dir
    if scope.startswith("chat:"):
        chat = get_chat(store, scope[5:])
        if chat is None:
            raise HTTPException(404, "对话不存在")
        chat.outputs_dir.mkdir(parents=True, exist_ok=True)
        return chat.outputs_dir
    raise HTTPException(404, "未知范围")


def _target(store: UserStore, scope: str, rel: str) -> tuple[Path, Path]:
    base = base_for(store, scope)
    try:
        return base, safe_join(base, rel)
    except ValueError:
        raise HTTPException(400, "路径不合法")


def _entries(d: Path) -> list[dict]:
    out = []
    for p in sorted(d.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
        if p.name.startswith("."):
            continue
        try:
            stt = p.stat()
        except OSError:
            continue
        out.append({"name": p.name, "type": "dir" if p.is_dir() else "file", "size": stt.st_size if p.is_file() else None,
                    "mtime": stt.st_mtime})
    return out


class MkdirIn(BaseModel):
    scope: str
    path: str


class InitIn(BaseModel):
    name: str
    size: int
    dir: str = ""
    fingerprint: str = ""
    scope: str = "files"


@router.get("/api/files")
async def list_files(scope: str, path: str = "", request: Request = None, user: dict = Depends(current_user)):
    store = _store(request, user)
    _, t = _target(store, scope, path)
    if not t.is_dir():
        raise HTTPException(404, "目录不存在")
    return {"path": path.strip("/"), "entries": _entries(t)}


@router.get("/api/files/download")
async def download(scope: str, path: str, request: Request, user: dict = Depends(current_user)):
    _, t = _target(_store(request, user), scope, path)
    if not t.is_file():
        raise HTTPException(404, "文件不存在")
    return FileResponse(t, filename=t.name)


def _zip_build(base: Path, t: Path, tmp_dir: Path | None = None) -> str:
    """同步构建临时 zip，返回路径。整个打包过程会阻塞，调用方必须放线程池里跑。

    临时文件写在账号自己的目录下（网络盘）：系统盘只有几个 G，打包一个稍满的 files/ 就撑爆了。"""
    if tmp_dir is not None:
        Path(tmp_dir).mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip", dir=str(tmp_dir) if tmp_dir else None)
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            for root, _dirs, files in os.walk(t):
                if "/." in root or os.path.basename(root).startswith("."):
                    continue
                for f in files:
                    if f.startswith("."):
                        continue
                    fp = Path(root) / f
                    z.write(fp, arcname=str(fp.relative_to(base)))
    except BaseException:
        tmp.close()
        try:
            os.unlink(tmp.name)      # 构建失败不留半个 zip
        except OSError:
            pass
        raise
    tmp.close()
    return tmp.name


def _zip_iter(path: str):
    """流式读出并在读完/中途被关闭（客户端断开）时删除临时文件。"""
    try:
        with open(path, "rb") as fh:
            while chunk := fh.read(1 << 20):
                yield chunk
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass


def _zip_stream(base: Path, t: Path, root_name: str = "root", tmp_dir: Path | None = None):
    """同步版（构建 + 流）；HTTP 路径走 _zip_build + _zip_iter，把构建放线程池。"""
    return _zip_iter(_zip_build(base, t, tmp_dir)), (t.name if t != base else root_name) + ".zip"


@router.get("/api/files/zip")
async def zip_dir(scope: str, path: str = "", request: Request = None, user: dict = Depends(current_user)):
    store = _store(request, user)
    base, t = _target(store, scope, path)
    if not t.is_dir():
        raise HTTPException(404, "目录不存在")
    tmp = await run_in_threadpool(_zip_build, base, t, store.uploads_dir)
    name = (t.name if t != base else scope.replace(":", "_")) + ".zip"
    return StreamingResponse(_zip_iter(tmp), media_type="application/zip",
                             headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


@router.get("/api/files/preview")
async def preview(scope: str, path: str, request: Request, user: dict = Depends(current_user)):
    _, t = _target(_store(request, user), scope, path)
    if not t.is_file():
        raise HTTPException(404, "文件不存在")
    ext = t.suffix.lower()
    if ext in IMG_EXT or ext == ".pdf":
        return FileResponse(t, media_type=mimetypes.guess_type(t.name)[0] or "application/octet-stream")
    if ext in TEXT_EXT or t.stat().st_size < 256 * 1024:
        async with aiofiles.open(t, "rb") as fh:
            data = await fh.read(1 << 20)
        return PlainTextResponse(data.decode("utf-8", errors="replace"))
    raise HTTPException(415, "该类型不支持预览")


@router.post("/api/files/mkdir")
async def mkdir(body: MkdirIn, request: Request, user: dict = Depends(current_user)):
    _, t = _target(_store(request, user), body.scope, body.path)
    try:
        t.mkdir(parents=True, exist_ok=True)
    except FileExistsError:
        raise HTTPException(400, "同名文件已存在")
    invalidate(user["name"])
    return {"ok": True}


@router.delete("/api/files")
async def delete(scope: str, path: str, request: Request, user: dict = Depends(current_user)):
    base, t = _target(_store(request, user), scope, path)
    if t == base:
        raise HTTPException(400, "不能删除根目录")
    if t.is_dir():
        await run_in_threadpool(shutil.rmtree, t)
    elif t.is_file():
        t.unlink()
    else:
        raise HTTPException(404, "不存在")
    invalidate(user["name"])
    return {"ok": True}


# ---- 分块上传 ----
def _upload_state_path(store: UserStore, uid: str) -> Path:
    if not re.match(r"^[0-9a-f]{32}$", uid):
        raise HTTPException(404, "上传不存在")
    return store.uploads_dir / f"{uid}.json"


def _load_state(store: UserStore, uid: str) -> dict:
    p = _upload_state_path(store, uid)
    if not p.exists():
        raise HTTPException(404, "上传不存在")
    return json.loads(p.read_text())


def _received(store: UserStore, uid: str) -> list[int]:
    d = store.uploads_dir / uid
    return sorted(int(p.name) for p in d.glob("*") if p.name.isdigit()) if d.is_dir() else []


def _pending_upload_bytes(store: UserStore) -> int:
    """所有未完成上传声明的总大小（配额预留）：分块尚未写完时，磁盘占用远小于声明大小，
    仅靠 dir_size 会低估未来占用，须把声明大小也计入，防止并发/连续 init 超卖配额。"""
    total = 0
    if not store.uploads_dir.is_dir():
        return 0
    for p in store.uploads_dir.glob("*.json"):
        try:
            st = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        total += int(st.get("size", 0))
    return total


@router.post("/api/upload/init")
async def upload_init(body: InitIn, request: Request, user: dict = Depends(current_user)):
    store = _store(request, user)
    if body.scope != "files":
        raise HTTPException(400, "只能上传到我的数据")
    if body.size < 0 or body.size > MAX_FILE:
        raise HTTPException(413, "单文件最大 10 GB")
    used = await cached_dir_size(user["name"], store.files_dir) + _pending_upload_bytes(store)
    if used + body.size > quota_bytes(request.app.state.accounts, user["name"]):
        raise HTTPException(413, "超出容量上限，请删除一些文件或联系管理员")
    _, dest_dir = _target(store, "files", body.dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    uid = uuid.uuid4().hex
    store.uploads_dir.mkdir(parents=True, exist_ok=True)
    (store.uploads_dir / uid).mkdir()
    state = {"upload_id": uid, "name": sanitize_name(body.name), "size": body.size, "dir": body.dir.strip("/"),
             "fingerprint": body.fingerprint, "chunk_size": CHUNK_SIZE, "created": time.time()}
    _upload_state_path(store, uid).write_text(json.dumps(state, ensure_ascii=False))
    return {**state, "received": []}


@router.get("/api/upload/find")
async def upload_find(fingerprint: str, request: Request, user: dict = Depends(current_user)):
    store = _store(request, user)
    for p in store.uploads_dir.glob("*.json") if store.uploads_dir.is_dir() else []:
        try:
            st = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        if st.get("fingerprint") == fingerprint:
            return {**st, "received": _received(store, st["upload_id"])}
    raise HTTPException(404, "没有未完成的上传")


@router.put("/api/upload/{uid}/{n}")
async def upload_chunk(uid: str, n: int, request: Request, user: dict = Depends(current_user)):
    store = _store(request, user)
    st = _load_state(store, uid)
    if n < 0 or n * st["chunk_size"] >= max(st["size"], 1):
        raise HTTPException(400, "块序号越界")
    cl = request.headers.get("content-length")
    if cl is None:
        # chunked 传输没有长度可查：先读完再判断，等于让人用一个请求把进程撑爆
        raise HTTPException(411, "缺少 Content-Length")
    try:
        if int(cl) > st["chunk_size"]:
            raise HTTPException(413, "块过大")
    except ValueError:
        pass
    data = await request.body()
    if len(data) > st["chunk_size"]:
        raise HTTPException(400, "块过大")
    async with aiofiles.open(store.uploads_dir / uid / str(n), "wb") as fh:
        await fh.write(data)
    return {"ok": True, "n": n}


@router.post("/api/upload/{uid}/complete")
async def upload_complete(uid: str, request: Request, user: dict = Depends(current_user)):
    store = _store(request, user)
    st = _load_state(store, uid)
    cs = st["chunk_size"]
    expected = (st["size"] + cs - 1) // cs if st["size"] else 0
    got = _received(store, uid)
    if got != list(range(expected)):
        raise HTTPException(400, f"缺少分块：已收到 {len(got)}/{expected}")
    _, dest_dir = _target(store, "files", st["dir"])
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = unique_name(dest_dir, st["name"])

    def _concat() -> None:
        # 10 GB 的拼接是几分钟的同步 IO：留在事件循环里会让所有 HTTP 和 WebSocket 一起卡住
        with open(dest, "wb") as out:
            for i in range(expected):
                with open(store.uploads_dir / uid / str(i), "rb") as fh:
                    shutil.copyfileobj(fh, out)

    await run_in_threadpool(_concat)
    invalidate(user["name"])
    if dest.stat().st_size != st["size"]:
        dest.unlink()
        raise HTTPException(400, "文件大小不符，请重新上传")
    await run_in_threadpool(shutil.rmtree, store.uploads_dir / uid, True)
    _upload_state_path(store, uid).unlink(missing_ok=True)
    return {"path": str(dest.relative_to(store.files_dir))}


def cleanup_stale_uploads(store: UserStore, max_age: float = 86400) -> int:
    """删除超过 24 小时未完成的上传；由 app 的定时任务对每个账号调用。"""
    n = 0
    if not store.uploads_dir.is_dir():
        return 0
    for p in store.uploads_dir.glob("*.json"):
        try:
            st = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        if time.time() - st.get("created", 0) > max_age:
            shutil.rmtree(store.uploads_dir / st["upload_id"], ignore_errors=True)
            p.unlink(missing_ok=True)
            n += 1
    return n
