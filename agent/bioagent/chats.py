"""对话目录：users/<账号>/chats/<id>/{meta.json, events.jsonl, outputs/}。

- id = 日期_6位十六进制，例如 2026-09-10_a1b2c3
- meta.json：标题、时间、模型、SDK 会话 id（用于恢复）、累计费用、来源（web/cli）、轮数
- events.jsonl：网页端事件流存档（text/tool_use/tool_result/confirm_request/confirm_reply/result/error/user）
- outputs/：该对话的工作目录，助理产物默认放这里
"""
from __future__ import annotations

import json
import re
import secrets
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from .store import UserStore

CHAT_ID_RE = r"^\d{4}-\d{2}-\d{2}_[0-9a-f]{6}$"


def new_chat_id() -> str:
    return f"{time.strftime('%Y-%m-%d')}_{secrets.token_hex(3)}"


@dataclass(frozen=True)
class Chat:
    dir: Path

    @property
    def id(self) -> str:
        return self.dir.name

    @property
    def meta_file(self) -> Path:
        return self.dir / "meta.json"

    @property
    def events_file(self) -> Path:
        return self.dir / "events.jsonl"

    @property
    def outputs_dir(self) -> Path:
        return self.dir / "outputs"

    def meta(self) -> dict:
        try:
            return json.loads(self.meta_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"id": self.id, "title": "", "created": 0, "updated": 0, "model": "", "session_id": None,
                    "cost": 0.0, "source": "", "turns": 0}

    def update(self, **fields) -> dict:
        m = self.meta()
        m.update(fields)
        m["updated"] = time.time()
        self.meta_file.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
        return m


def create_chat(store: UserStore, *, model: str, source: str, title: str = "") -> Chat:
    store.chats_dir.mkdir(parents=True, exist_ok=True)
    chat = Chat(store.chats_dir / new_chat_id())
    chat.outputs_dir.mkdir(parents=True)
    now = time.time()
    chat.meta_file.write_text(json.dumps({
        "id": chat.id, "title": title, "created": now, "updated": now, "model": model,
        "session_id": None, "cost": 0.0, "source": source, "turns": 0,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    return chat


def get_chat(store: UserStore, chat_id: str) -> Chat | None:
    if not re.match(CHAT_ID_RE, chat_id or ""):
        return None
    d = store.chats_dir / chat_id
    return Chat(d) if d.is_dir() and (d / "meta.json").exists() else None


def list_chats(store: UserStore) -> list[dict]:
    if not store.chats_dir.is_dir():
        return []
    rows = [Chat(d).meta() for d in store.chats_dir.iterdir() if d.is_dir() and (d / "meta.json").exists()]
    return sorted(rows, key=lambda m: m.get("updated", 0), reverse=True)


def delete_chat(chat: Chat) -> None:
    shutil.rmtree(chat.dir)


def append_event(chat: Chat, ev: dict) -> None:
    rec = {"ts": time.time(), **ev}
    with open(chat.events_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def read_events(chat: Chat) -> list[dict]:
    if not chat.events_file.exists():
        return []
    out = []
    for line in chat.events_file.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def find_by_session(store: UserStore, session_id: str) -> Chat | None:
    for m in list_chats(store):
        if m.get("session_id") == session_id:
            return Chat(store.chats_dir / m["id"])
    return None
