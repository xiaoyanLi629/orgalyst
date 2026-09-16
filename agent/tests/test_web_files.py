import io
import os
import zipfile

import pytest
from fastapi.testclient import TestClient

from bioagent.web.files import sanitize_name, unique_name
from tests.test_web_api import client, login  # noqa: F401  (复用 fixture)


def test_sanitize_and_unique(tmp_path):
    assert sanitize_name("../..\\evil\x00.txt") == "evil.txt"
    assert sanitize_name("  数据 (1).csv ") == "数据 (1).csv"
    (tmp_path / "a.txt").write_text("x")
    assert unique_name(tmp_path, "a.txt").name == "a (1).txt"
    (tmp_path / "a (1).txt").write_text("x")
    assert unique_name(tmp_path, "a.txt").name == "a (2).txt"
    assert unique_name(tmp_path, "b.txt").name == "b.txt"


def upload(c, name, data: bytes, dir="", chunk=None):
    r = c.post("/api/upload/init", json={"name": name, "size": len(data), "dir": dir, "fingerprint": f"fp-{name}-{len(data)}"})
    assert r.status_code == 200, r.text
    uid, cs = r.json()["upload_id"], r.json()["chunk_size"]
    cs = chunk or cs
    for n, off in enumerate(range(0, len(data), cs)):
        assert c.put(f"/api/upload/{uid}/{n}", content=data[off:off + cs]).status_code == 200
    r = c.post(f"/api/upload/{uid}/complete")
    assert r.status_code == 200, r.text
    return r.json()["path"]


def test_upload_list_download_delete(client, monkeypatch):
    import bioagent.web.files as F
    monkeypatch.setattr(F, "CHUNK_SIZE", 4)
    login(client, "bob", "pw-bob")
    assert client.post("/api/files/mkdir", json={"scope": "files", "path": "raw"}).status_code == 200
    p = upload(client, "seq.txt", b"ACGTACGTAC", dir="raw")
    assert p == "raw/seq.txt"
    p2 = upload(client, "seq.txt", b"TTTT", dir="raw")
    assert p2 == "raw/seq (1).txt"
    lst = client.get("/api/files", params={"scope": "files", "path": "raw"}).json()
    assert {e["name"] for e in lst["entries"]} == {"seq.txt", "seq (1).txt"}
    assert client.get("/api/files/download", params={"scope": "files", "path": "raw/seq.txt"}).content == b"ACGTACGTAC"
    assert client.get("/api/files/preview", params={"scope": "files", "path": "raw/seq.txt"}).text == "ACGTACGTAC"
    z = client.get("/api/files/zip", params={"scope": "files", "path": "raw"})
    assert z.status_code == 200 and set(zipfile.ZipFile(io.BytesIO(z.content)).namelist()) == {"raw/seq.txt", "raw/seq (1).txt"}
    assert client.delete("/api/files", params={"scope": "files", "path": "raw/seq (1).txt"}).status_code == 200
    assert client.delete("/api/files", params={"scope": "files", "path": ""}).status_code == 400
    assert client.get("/api/files", params={"scope": "files", "path": "../"}).status_code == 400
    root = client.get("/api/files", params={"scope": "files", "path": ""}).json()
    assert [e["name"] for e in root["entries"]] == ["raw"]  # .uploads 不显示


def test_upload_resume_and_quota(client, monkeypatch):
    import bioagent.web.files as F
    monkeypatch.setattr(F, "CHUNK_SIZE", 4)
    login(client, "bob", "pw-bob")
    r = client.post("/api/upload/init", json={"name": "big.bin", "size": 10, "dir": "", "fingerprint": "fp-big"}).json()
    uid = r["upload_id"]
    client.put(f"/api/upload/{uid}/0", content=b"0123")
    found = client.get("/api/upload/find", params={"fingerprint": "fp-big"}).json()
    assert found["upload_id"] == uid and found["received"] == [0]
    client.put(f"/api/upload/{uid}/1", content=b"4567"); client.put(f"/api/upload/{uid}/2", content=b"89")
    assert client.post(f"/api/upload/{uid}/complete").json()["path"] == "big.bin"
    assert client.get("/api/upload/find", params={"fingerprint": "fp-big"}).status_code == 404
    # 配额：bob 50GB 默认；把 quota 调到 0 后 init 拒绝
    client.app.state.accounts.update("bob", quota_gb=0)
    assert client.post("/api/upload/init", json={"name": "x", "size": 1, "dir": "", "fingerprint": "f"}).status_code == 413
    client.app.state.accounts.update("bob", quota_gb=50)
    assert client.post("/api/upload/init", json={"name": "x", "size": F.MAX_FILE + 1, "dir": "", "fingerprint": "f"}).status_code == 413


def test_chat_scope_and_isolation(client):
    login(client, "bob", "pw-bob")
    cid = client.post("/api/chats", json={}).json()["id"]
    r = client.get("/api/files", params={"scope": f"chat:{cid}", "path": ""})
    assert r.status_code == 200 and r.json()["entries"] == []
    assert client.post("/api/upload/init", json={"name": "x", "size": 1, "dir": "", "fingerprint": "f", "scope": f"chat:{cid}"}).status_code in (200, 400)
    client.post("/api/logout"); login(client, "admin1", "pw-admin")
    assert client.get("/api/files", params={"scope": f"chat:{cid}", "path": ""}).status_code == 404
    client.post("/api/logout")
    assert client.get("/api/files", params={"scope": "files", "path": ""}).status_code == 401


def test_zip_temp_file_cleanup_on_disconnect(tmp_path, monkeypatch):
    import bioagent.web.files as F
    d = tmp_path / "docs"
    d.mkdir()
    (d / "a.txt").write_text("hello world" * 10000)

    created = []
    orig_ntf = F.tempfile.NamedTemporaryFile

    def spy_ntf(*a, **kw):
        f = orig_ntf(*a, **kw)
        created.append(f.name)
        return f

    monkeypatch.setattr(F.tempfile, "NamedTemporaryFile", spy_ntf)
    gen, _name = F._zip_stream(tmp_path, d)
    next(gen)  # consume one chunk, temp file created and partially read
    gen.close()  # simulate client disconnect: generator torn down mid-stream
    assert created and not os.path.exists(created[0])


def test_quota_reservation_aware(client, monkeypatch):
    # 配额远大于状态文件本身的磁盘占用（几百字节），只有把"未完成上传的声明大小"也计入
    # used 才会让第二次 init 超限；否则（未修复前）第二次会误判为仍有空间而放行。
    import bioagent.web.files as F
    monkeypatch.setattr(F, "quota_bytes", lambda accounts, name: 2_000_000)
    login(client, "bob", "pw-bob")
    r1 = client.post("/api/upload/init", json={"name": "a", "size": 1_500_000, "dir": "", "fingerprint": "f1"})
    assert r1.status_code == 200, r1.text
    r2 = client.post("/api/upload/init", json={"name": "b", "size": 1_000_000, "dir": "", "fingerprint": "f2"})
    assert r2.status_code == 413, r2.text


def test_chunk_content_length_guard(client, monkeypatch):
    import bioagent.web.files as F
    monkeypatch.setattr(F, "CHUNK_SIZE", 4)
    login(client, "bob", "pw-bob")
    r = client.post("/api/upload/init", json={"name": "big.bin", "size": 100, "dir": "", "fingerprint": "fp-cl"}).json()
    uid = r["upload_id"]
    resp = client.put(f"/api/upload/{uid}/0", content=b"0123456789")  # 10 bytes > chunk_size 4
    assert resp.status_code == 413


def test_zip_filename_escaped(client):
    login(client, "bob", "pw-bob")
    name = 'a"b c'
    assert client.post("/api/files/mkdir", json={"scope": "files", "path": name}).status_code == 200
    z = client.get("/api/files/zip", params={"scope": "files", "path": name})
    assert z.status_code == 200
    assert "a%22b%20c.zip" in z.headers["content-disposition"]


def test_mkdir_conflict_with_file(client):
    login(client, "bob", "pw-bob")
    upload(client, "x", b"data")
    assert client.post("/api/files/mkdir", json={"scope": "files", "path": "x"}).status_code == 400


def test_chunk_without_content_length_rejected(client):
    """没有 Content-Length（chunked 传输）时先 411，不能先把整个 body 读进内存再判断大小。"""
    login(client, "bob", "pw-bob")
    r = client.post("/api/upload/init", json={"name": "a.bin", "size": 10, "dir": "", "fingerprint": "fp-nocl"}).json()
    resp = client.put(f"/api/upload/{r['upload_id']}/0", content=iter([b"0123"]))
    assert resp.status_code == 411


def test_storage_cache_invalidated_after_upload(client):
    """dir_size 有 5 分钟缓存，但上传完必须立刻失效，否则管理员看到的容量是旧的。"""
    login(client, "admin1", "pw-admin")
    upload(client, "a.txt", b"x" * 1000)
    b0 = [r for r in client.get("/api/admin/storage").json() if r["name"] == "admin1"][0]["bytes"]
    upload(client, "b.txt", b"y" * 5000)
    b1 = [r for r in client.get("/api/admin/storage").json() if r["name"] == "admin1"][0]["bytes"]
    assert b1 >= b0 + 5000
