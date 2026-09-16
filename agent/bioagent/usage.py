"""按账号的用量记录与上限。

记录：sessions/<user>/usage.jsonl，每轮一行：
    {"ts": "2026-09-09T10:21:03", "date": "2026-09-09", "session": "...", "model": "claude-opus-5",
     "input": 1200, "output": 300, "cache_read": 120000, "cache_write": 0, "cost": 0.4123}
上限：<secrets_dir>/users.yaml（管理员维护）：
    users:
      xiaoyan:  {daily_usd: 20, monthly_usd: 300}
      langhuan: {daily_usd: 5,  monthly_usd: 50}
    default:    {daily_usd: 5,  monthly_usd: 50}     # 未单独列出的账号用这个；没有 default 则不限
超限：启动时拒绝进入；对话中超限则本轮之后不再接受新任务（命令仍可用），次日/次月自动恢复。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

FIELDS = ("input", "output", "cache_read", "cache_write")


def _now() -> datetime:
    return datetime.now()


class UsageLog:
    def __init__(self, path: Path):
        self.path = Path(path)

    def add(self, *, session: str | None, model: str, usage: dict | None, cost: float, now: datetime | None = None) -> dict:
        u = usage or {}
        now = now or _now()
        rec = {
            "ts": now.strftime("%Y-%m-%dT%H:%M:%S"),
            "date": now.strftime("%Y-%m-%d"),
            "session": session or "",
            "model": model,
            "input": int(u.get("input_tokens") or 0),
            "output": int(u.get("output_tokens") or 0),
            "cache_read": int(u.get("cache_read_input_tokens") or 0),
            "cache_write": int(u.get("cache_creation_input_tokens") or 0),
            "cost": round(float(cost or 0.0), 6),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

    def records(self) -> list[dict]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    def spent(self, period: str, now: datetime | None = None) -> float:
        """period: 'day' 今日 / 'month' 本月 / 'all' 全部，返回美元。"""
        now = now or _now()
        key = now.strftime("%Y-%m-%d") if period == "day" else now.strftime("%Y-%m") if period == "month" else ""
        return round(sum(float(r.get("cost") or 0) for r in self.records() if r.get("date", "").startswith(key)), 6)


# ---------------------------------------------------------------------------
# 上限
# ---------------------------------------------------------------------------
def load_limits(path: Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def limits_for(user: str, limits: dict) -> dict:
    """返回 {"daily_usd": float|None, "monthly_usd": float|None}。"""
    users = limits.get("users") or {}
    cfg = users.get(user)
    if cfg is None:
        cfg = limits.get("default") or {}
    cfg = cfg or {}
    out = {}
    for k in ("daily_usd", "monthly_usd"):
        v = cfg.get(k)
        out[k] = float(v) if v is not None else None
    return out


def check_limits(log: UsageLog, user: str, limits: dict, now: datetime | None = None) -> tuple[bool, str]:
    """(是否允许继续, 说明文字)。说明文字用于 /cost 与超限提示。"""
    lim = limits_for(user, limits)
    now = now or _now()
    day, month = log.spent("day", now), log.spent("month", now)
    parts, blocked = [], []
    for label, spent, cap in (("今日", day, lim["daily_usd"]), ("本月", month, lim["monthly_usd"])):
        if cap is None:
            parts.append(f"{label} ${spent:.2f}")
        else:
            parts.append(f"{label} ${spent:.2f}/{cap:.2f}")
            if spent >= cap:
                blocked.append(f"{label}上限 ${cap:.2f} 已用完（已用 ${spent:.2f}）")
    if blocked:
        return False, "；".join(blocked) + "。次日/次月自动恢复，或请管理员在 users.yaml 调整。"
    return True, " · ".join(parts)


# ---------------------------------------------------------------------------
# 管理员报表
# ---------------------------------------------------------------------------
def report(sessions_root: Path, users: list[str] | None = None, by: str = "user", since: str = "", until: str = "") -> list[dict]:
    """汇总各账号用量。by: user / day / month。since/until 为 YYYY-MM-DD 前缀（含）。"""
    rows: dict[tuple, dict] = {}
    root = Path(sessions_root)
    if not root.is_dir():
        return []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        if users and d.name not in users:
            continue
        for r in UsageLog(d / "usage.jsonl").records():
            date = r.get("date", "")
            if since and date < since:
                continue
            if until and date > until:
                continue
            period = date if by == "day" else date[:7] if by == "month" else ""
            key = (d.name, period)
            row = rows.setdefault(key, {"账号": d.name, **({"日期" if by == "day" else "月份": period} if period else {}),
                                        "轮数": 0, "输入": 0, "输出": 0, "缓存读": 0, "缓存写": 0, "费用$": 0.0})
            row["轮数"] += 1
            row["输入"] += int(r.get("input") or 0)
            row["输出"] += int(r.get("output") or 0)
            row["缓存读"] += int(r.get("cache_read") or 0)
            row["缓存写"] += int(r.get("cache_write") or 0)
            row["费用$"] += float(r.get("cost") or 0)
    out = sorted(rows.values(), key=lambda x: (x["账号"], x.get("日期", x.get("月份", ""))))
    for x in out:
        x["费用$"] = round(x["费用$"], 4)
    return out


def _w(t: str) -> int:
    """终端显示宽度：中日韩全角字符按 2 计。"""
    import unicodedata

    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in t)


def _fmt_table(rows: list[dict]) -> str:
    if not rows:
        return "(无记录)"
    cols = list(rows[0].keys())
    cell = lambda v: f"{v:,}" if isinstance(v, int) else str(v)
    widths = {c: max(_w(str(c)), *(_w(cell(r[c])) for r in rows)) for c in cols}
    pad = lambda t, c: " " * (widths[c] - _w(t)) + t
    head = "  ".join(pad(str(c), c) for c in cols)
    return "\n".join([head, "-" * _w(head)] + ["  ".join(pad(cell(r[c]), c) for c in cols) for r in rows])


def main(argv=None) -> int:
    import argparse

    from .config import secrets_dir

    ROOT = Path(__file__).resolve().parents[1]

    ap = argparse.ArgumentParser(prog="bioagent --usage", description="各账号用量与上限（管理员）")
    ap.add_argument("--user", action="append", help="只看这些账号（可重复）")
    ap.add_argument("--by", choices=["user", "day", "month"], default="user", help="汇总粒度")
    ap.add_argument("--since", default="", help="起始日期 YYYY-MM-DD")
    ap.add_argument("--until", default="", help="结束日期 YYYY-MM-DD")
    args = ap.parse_args(argv)
    sessions_root = ROOT / "users"
    rows = report(sessions_root, users=args.user, by=args.by, since=args.since, until=args.until)
    print(_fmt_table(rows))
    limits_path = secrets_dir() / "users.yaml"
    limits = load_limits(limits_path)
    print(f"\n上限配置 {limits_path}{'' if limits else '（不存在，未设上限）'}")
    if limits:
        now = _now()
        names = sorted({d.name for d in sessions_root.iterdir() if d.is_dir() and not d.name.startswith(".")} | set((limits.get("users") or {}).keys()))
        for name in names:
            if args.user and name not in args.user:
                continue
            ok, msg = check_limits(UsageLog(sessions_root / name / "usage.jsonl"), name, limits, now)
            print(f"  {name:<16} {'正常' if ok else '已超限'}  {msg}")
        if limits.get("default"):
            print(f"  (未列出的账号按 default：{limits['default']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
