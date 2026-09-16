from datetime import datetime
from pathlib import Path

from bioagent.usage import UsageLog, check_limits, limits_for, load_limits, report

U = {"input_tokens": 100, "output_tokens": 50, "cache_read_input_tokens": 1000, "cache_creation_input_tokens": 10}


def test_log_and_spent(tmp_path):
    log = UsageLog(tmp_path / "u.jsonl")
    log.add(session="s1", model="m", usage=U, cost=0.5, now=datetime(2026, 9, 9, 10))
    log.add(session="s1", model="m", usage=U, cost=0.25, now=datetime(2026, 9, 8, 10))
    log.add(session="s2", model="m", usage=None, cost=1.0, now=datetime(2026, 8, 30, 10))
    now = datetime(2026, 9, 9, 12)
    assert log.spent("day", now) == 0.5
    assert log.spent("month", now) == 0.75
    assert log.spent("all", now) == 1.75
    assert log.records()[0]["cache_read"] == 1000 and log.records()[2]["input"] == 0


def test_limits(tmp_path):
    p = tmp_path / "users.yaml"
    p.write_text("users:\n  a: {daily_usd: 1, monthly_usd: 10}\ndefault: {daily_usd: 0.3}\n")
    lim = load_limits(p)
    assert limits_for("a", lim) == {"daily_usd": 1.0, "monthly_usd": 10.0}
    assert limits_for("zz", lim) == {"daily_usd": 0.3, "monthly_usd": None}
    assert limits_for("zz", {}) == {"daily_usd": None, "monthly_usd": None}
    log = UsageLog(tmp_path / "u.jsonl")
    now = datetime(2026, 9, 9, 12)
    log.add(session="s", model="m", usage=U, cost=0.4, now=now)
    ok, msg = check_limits(log, "a", lim, now)
    assert ok and "今日 $0.40/1.00" in msg
    ok, msg = check_limits(log, "zz", lim, now)
    assert not ok and "今日上限" in msg
    ok, msg = check_limits(log, "zz", {}, now)  # 无配置 → 不限
    assert ok


def test_report(tmp_path):
    for name, cost in (("a", 0.5), ("b", 0.2)):
        UsageLog(tmp_path / name / "usage.jsonl").add(session="s", model="m", usage=U, cost=cost, now=datetime(2026, 9, 9, 1))
    UsageLog(tmp_path / "a" / "usage.jsonl").add(session="s", model="m", usage=U, cost=0.1, now=datetime(2026, 8, 1, 1))
    rows = report(tmp_path)
    assert [(r["账号"], r["轮数"], r["费用$"]) for r in rows] == [("a", 2, 0.6), ("b", 1, 0.2)]
    rows = report(tmp_path, by="month", users=["a"])
    assert [(r["月份"], r["费用$"]) for r in rows] == [("2026-08", 0.1), ("2026-09", 0.5)]
    assert report(tmp_path, since="2026-09-01")[0]["费用$"] == 0.5
