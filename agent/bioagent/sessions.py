"""会话索引：SDK 自己保存会话内容，这里只记录目录（id、标题、费用），供 /sessions 与 /resume 使用。"""
from __future__ import annotations

import json
import time
from pathlib import Path


class SessionIndex:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.rows: dict[str, dict] = {}
        if self.path.exists():
            try:
                self.rows = json.loads(self.path.read_text())
            except json.JSONDecodeError:
                self.rows = {}

    def upsert(self, session_id: str, *, title: str, cwd: str, model: str, cost: float) -> None:
        row = self.rows.get(session_id) or {
            "session_id": session_id,
            "created": time.time(),
            "title": (title or "").strip().replace("\n", " ")[:40],
        }
        row.update({"updated": time.time(), "cwd": cwd, "model": model, "cost": round(cost, 4)})
        self.rows[session_id] = row
        self.path.write_text(json.dumps(self.rows, ensure_ascii=False, indent=1))

    def list(self) -> list[dict]:
        return sorted(self.rows.values(), key=lambda r: r["updated"], reverse=True)

    def latest_id(self) -> str | None:
        rows = self.list()
        return rows[0]["session_id"] if rows else None
