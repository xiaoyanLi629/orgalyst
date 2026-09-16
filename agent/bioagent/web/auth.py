"""账号（users.yaml）、密码（argon2id）、登录 cookie、限流、FastAPI 依赖。

users.yaml 与 usage.load_limits 共用同一文件：
users:
  xiaoyan: {password_hash: "...", role: admin, enabled: true, daily_usd: null, monthly_usd: null, quota_gb: 50, created: "2026-09-10"}
default: {daily_usd: 5, monthly_usd: 50, quota_gb: 50}
"""
from __future__ import annotations

import os
import re
import secrets
import time
from collections import defaultdict, deque
from pathlib import Path

import yaml
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner

from ..config import USER_NAME_RE

COOKIE_NAME = "bioagent_session"
_ph = PasswordHasher()
_DUMMY_HASH = _ph.hash("bioagent-dummy-password")


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def check_password(pw: str, h: str | None) -> bool:
    if not h:
        return False
    try:
        return _ph.verify(h, pw)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


class Accounts:
    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> dict:
        if not self.path.exists():
            return {"users": {}}
        data = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        data.setdefault("users", {})
        data["users"] = data["users"] or {}
        return data

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)
        os.chmod(self.path, 0o600)

    def get(self, name: str) -> dict | None:
        u = self.load()["users"].get(name)
        return dict(u, name=name) if u is not None else None

    def list(self) -> list[dict]:
        out = []
        for name, u in self.load()["users"].items():
            row = {k: v for k, v in (u or {}).items() if k != "password_hash"}
            row.update(name=name, has_password=bool((u or {}).get("password_hash")),
                       enabled=(u or {}).get("enabled", True), role=(u or {}).get("role", "user"))
            out.append(row)
        return sorted(out, key=lambda r: r["name"])

    def create(self, name: str, password: str, role: str = "user") -> dict:
        if not re.match(USER_NAME_RE, name or ""):
            raise ValueError("用户名只能包含字母、数字、下划线、连字符，且以字母或数字开头（最长 32 字符）")
        data = self.load()
        if name in data["users"]:
            raise ValueError("账号已存在")
        data["users"][name] = {"password_hash": hash_password(password), "role": role, "enabled": True,
                               "created": time.strftime("%Y-%m-%d")}
        self._save(data)
        return self.get(name)

    def set_password(self, name: str, password: str) -> None:
        data = self.load()
        if name not in data["users"]:
            raise KeyError(name)
        data["users"][name] = data["users"][name] or {}
        data["users"][name]["password_hash"] = hash_password(password)
        self._save(data)

    def update(self, name: str, **fields) -> dict:
        data = self.load()
        if name not in data["users"]:
            raise KeyError(name)
        data["users"][name] = data["users"][name] or {}
        for k, v in fields.items():
            if k in ("password_hash", "name"):
                continue
            data["users"][name][k] = v
        self._save(data)
        return self.get(name)

    def delete(self, name: str) -> None:
        data = self.load()
        data["users"].pop(name, None)
        self._save(data)

    def verify(self, name: str, password: str) -> bool:
        u = self.get(name)
        h = u.get("password_hash") if u else None
        if not u or not u.get("enabled", True) or not h:
            check_password(password, _DUMMY_HASH)  # 支付相同的 argon2 代价，避免用户名/状态计时旁道
            return False
        return check_password(password, h)


class CookieSigner:
    def __init__(self, secret: bytes, max_age: int = 30 * 86400):
        self.signer = TimestampSigner(secret, salt="bioagent-session")
        self.max_age = max_age

    def sign(self, name: str) -> str:
        return self.signer.sign(name.encode()).decode()

    def unsign(self, token: str | None) -> str | None:
        if not token:
            return None
        try:
            return self.signer.unsign(token.encode(), max_age=self.max_age).decode()
        except (BadSignature, SignatureExpired, UnicodeDecodeError):
            return None


MAX_LIMITER_KEYS = 10_000


class RateLimiter:
    """allow(): 滑动窗口计数；record_failure()/locked(): 同一账号连续失败 5 次锁 60 秒。"""

    def __init__(self, max_failures: int = 5, lock_seconds: float = 60.0):
        self.hits: dict[str, deque] = defaultdict(deque)
        self.failures: dict[str, list[float]] = defaultdict(list)
        self.max_failures = max_failures
        self.lock_seconds = lock_seconds

    @staticmethod
    def _cap(d: dict) -> None:
        """键来自外部输入（用户名、客户端 IP），字典不能无限长：超上限就淘汰最早插入的一半。

        dict 保持插入顺序，前一半就是最早进来的那批。"""
        if len(d) > MAX_LIMITER_KEYS:
            for k in list(d)[: len(d) // 2]:
                d.pop(k, None)

    def allow(self, key: str, limit: int, window: float) -> bool:
        now = time.monotonic()
        q = self.hits[key]
        while q and q[0] < now - window:
            q.popleft()
        ok = len(q) < limit
        if ok:
            q.append(now)
        self._cap(self.hits)
        return ok

    def record_failure(self, name: str) -> None:
        self.failures[name].append(time.monotonic())
        self._cap(self.failures)

    def locked(self, name: str) -> bool:
        now = time.monotonic()
        recent = [t for t in self.failures.get(name, []) if t > now - self.lock_seconds]
        if recent:
            self.failures[name] = recent
        else:
            self.failures.pop(name, None)   # 窗口内没有失败记录就不留键
        self._cap(self.failures)
        return len(recent) >= self.max_failures

    def clear(self, name: str) -> None:
        self.failures.pop(name, None)


def load_or_create_secret(path: Path) -> bytes:
    path = Path(path)
    if path.exists():
        return path.read_bytes()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = secrets.token_bytes(48)
    path.write_bytes(data)
    os.chmod(path, 0o600)
    return data


def auth_log(path: Path, ip: str, name: str, ok: bool, note: str = "") -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {ip} {name} {'OK' if ok else 'FAIL'} {note}\n".rstrip() + "\n")
    except OSError:
        pass


# ---- FastAPI 依赖 ----
def current_user(request: Request) -> dict:
    """从 cookie 取账号；未登录/账号被停用 → 401。app.state 需有 signer 与 accounts。"""
    name = request.app.state.signer.unsign(request.cookies.get(COOKIE_NAME))
    if not name:
        raise HTTPException(401, "未登录")
    u = request.app.state.accounts.get(name)
    if not u or not u.get("enabled", True):
        raise HTTPException(401, "账号不可用")
    return u


def admin_only(user: dict = Depends(current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(403, "需要管理员")
    return user
