import statistics
import time

import pytest

from bioagent.web.auth import Accounts, CookieSigner, RateLimiter, check_password, hash_password, load_or_create_secret


def test_password_hash_roundtrip():
    h = hash_password("s3cret")
    assert h.startswith("$argon2id$") and check_password("s3cret", h) and not check_password("x", h)


def test_accounts_crud(tmp_path):
    p = tmp_path / "users.yaml"
    p.write_text("users:\n  old: {daily_usd: 5}\ndefault: {daily_usd: 5, monthly_usd: 50}\n")
    acc = Accounts(p)
    assert acc.get("old")["daily_usd"] == 5 and acc.get("old").get("password_hash") is None
    u = acc.create("zhangsan", "pw123", role="admin")
    assert u["role"] == "admin" and u["enabled"] is True and "created" in u
    assert acc.verify("zhangsan", "pw123") and not acc.verify("zhangsan", "bad")
    assert not acc.verify("old", "anything")  # 没设密码不能登录
    with pytest.raises(ValueError):
        acc.create("zhangsan", "again")
    with pytest.raises(ValueError):
        acc.create("bad name!", "x")
    acc.update("zhangsan", enabled=False, daily_usd=2, quota_gb=10)
    assert acc.get("zhangsan")["enabled"] is False and acc.get("zhangsan")["quota_gb"] == 10
    assert not acc.verify("zhangsan", "pw123")  # 停用后不能登录
    acc.set_password("zhangsan", "new")
    acc.update("zhangsan", enabled=True)
    assert acc.verify("zhangsan", "new")
    rows = acc.list()
    assert all("password_hash" not in r for r in rows) and {r["name"] for r in rows} == {"old", "zhangsan"}
    acc.delete("old")
    assert acc.get("old") is None
    # default 段保留
    assert Accounts(p).load()["default"]["monthly_usd"] == 50
    assert oct(p.stat().st_mode & 0o777) == "0o600"


def test_cookie_signer():
    s = CookieSigner(b"k" * 32, max_age=2)
    tok = s.sign("zhangsan")
    assert s.unsign(tok) == "zhangsan"
    assert s.unsign(tok + "x") is None
    assert CookieSigner(b"other" * 8).unsign(tok) is None


def test_rate_limiter_and_lock():
    rl = RateLimiter()
    assert all(rl.allow("ip1", 3, 60) for _ in range(3))
    assert not rl.allow("ip1", 3, 60)
    for _ in range(5):
        rl.record_failure("a")
    assert rl.locked("a") and not rl.locked("b")
    rl.clear("a")
    assert not rl.locked("a")


def test_secret_file(tmp_path):
    p = tmp_path / "web_secret"
    s1 = load_or_create_secret(p)
    assert len(s1) >= 32 and load_or_create_secret(p) == s1
    assert oct(p.stat().st_mode & 0o777) == "0o600"


def test_verify_timing_uniform(tmp_path):
    p = tmp_path / "users.yaml"
    acc = Accounts(p)
    acc.create("zhangsan", "pw123")

    def timed(name, password, n=7):
        times = []
        for _ in range(n):
            t0 = time.perf_counter()
            ok = acc.verify(name, password)
            times.append(time.perf_counter() - t0)
            assert ok is False
        return statistics.median(times)

    unknown_median = timed("nobody", "x")
    known_median = timed("zhangsan", "wrong")
    assert unknown_median >= 0.5 * known_median


def test_rate_limiter_caps_key_count():
    """键是攻击者可控的（用户名、X-Forwarded-For），字典不能无上限地长。"""
    rl = RateLimiter()
    for i in range(10_001):
        rl.allow(f"ip{i}", 100, 60)
    assert len(rl.hits) <= 10_000
    assert "ip10000" in rl.hits and "ip0" not in rl.hits   # 淘汰最早插入的一半
    for i in range(10_001):
        rl.record_failure(f"u{i}")
    assert len(rl.failures) <= 10_000
    assert "u10000" in rl.failures and "u0" not in rl.failures
