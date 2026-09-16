#!/usr/bin/env bash
# Orgalyst 环境安装（适合 AutoDL 这种单连接慢、多连接快的网络）：
#   1) uv 只解析依赖 → requirements.lock.txt（读元数据，不下整包）
#   2) 从清华镜像索引页找每个包的 wheel 地址 → aria2c 16 线程下载到 /root/autodl-tmp/wheelhouse
#   3) uv 离线从 wheelhouse 安装并验证 CUDA
# 用法：bash scripts/wheelhouse_install.sh   （幂等，已下载的 wheel 跳过）
set -uo pipefail
ROOT=/root/autodl-fs/AI4S
ENV=/root/autodl-tmp/orgalyst-env
WH=/root/autodl-tmp/wheelhouse
UV=/root/miniconda3/bin/uv
IDX=https://pypi.tuna.tsinghua.edu.cn/simple
export UV_CACHE_DIR=/root/autodl-tmp/.cache/uv TMPDIR=/root/autodl-tmp/.tmp
mkdir -p "$WH" "$UV_CACHE_DIR" "$TMPDIR"
PYVER=$("$ENV/bin/python" -c 'import sys;print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
echo "=== step 1: resolve (python $PYVER)"
"$UV" pip compile --quiet --index-url "$IDX" --python-platform x86_64-manylinux_2_28 --python-version "$PYVER" \
  --no-header --no-annotate -o "$ROOT/scripts/requirements.lock.txt" "$ROOT/scripts/requirements.txt" || { echo "resolve failed"; exit 1; }
echo "resolved $(grep -c == "$ROOT/scripts/requirements.lock.txt") packages"

echo "=== step 2: wheel URLs from mirror index"
"$ENV/bin/python" - "$ROOT/scripts/requirements.lock.txt" "$WH" "$IDX" "$PYVER" <<'PY'
import sys, re, os, html, urllib.request
lock, wh, idx, pyver = sys.argv[1:5]
cp = "cp" + pyver.replace(".", "")
def ok_tag(fn):
    if not fn.endswith(".whl"): return False
    body = fn[:-4]; parts = body.split("-")
    pytag, abi, plat = parts[-3], parts[-2], parts[-1]
    minor = int(pyver.split(".")[1])
    def py_tag_ok(t):
        if t in (cp, "py3", "py2", "cp3") or t.startswith("py3"): return True
        return t.startswith("cp3") and t[3:].isdigit() and int(t[3:]) <= minor   # cp37-abi3 之类向上兼容
    py_ok = any(py_tag_ok(t) for t in pytag.split("."))
    abi_ok = any(a in (cp, "abi3", "none") for a in abi.split("."))
    plat_ok = plat == "any" or any(("manylinux" in p or p == "linux_x86_64") and ("x86_64" in p) for p in plat.split("."))
    return py_ok and abi_ok and plat_ok
def score(fn):
    plat = fn[:-4].split("-")[-1]
    m = re.findall(r"manylinux_2_(\d+)", plat); glibc = max(map(int, m)) if m else (17 if "manylinux2014" in plat else 5)
    return (0 if glibc <= 28 else -1, glibc, "abi3" in fn or "none-any" in fn)
lines = []; missing = []
for line in open(lock):
    line = line.strip()
    if not line or line.startswith("#") or "==" not in line: continue
    name, ver = line.split("==")[0].strip(), line.split("==")[1].split()[0].split(";")[0].strip()
    norm = re.sub(r"[-_.]+", "-", name).lower()
    page = urllib.request.urlopen(f"{idx}/{norm}/", timeout=60).read().decode()
    cands = []
    for href, text in re.findall(r'href="([^"]+)"[^>]*>([^<]+)<', page):
        fn = html.unescape(text.strip())
        vpart = fn[:-4].split("-")[1] if fn.endswith(".whl") else ""
        if vpart == ver and ok_tag(fn): cands.append((score(fn), fn, html.unescape(href)))
    if not cands: missing.append(line); continue
    cands.sort(reverse=True); fn, href = cands[0][1], cands[0][2]
    url = href.split("#")[0]
    if url.startswith("../../"): url = idx.rsplit("/simple", 1)[0] + "/" + url[6:]
    if not os.path.exists(os.path.join(wh, fn)): lines.append(f"{url}\n  out={fn}")
open(os.path.join(wh, "urls.txt"), "w").write("\n".join(lines) + ("\n" if lines else ""))
print(f"{len(lines)} wheels to download; missing (no wheel found): {missing}")
PY

echo "=== step 3: aria2c"
if [ -s "$WH/urls.txt" ]; then
  aria2c -x16 -s16 -k1M -j3 -c --file-allocation=none --summary-interval=60 --console-log-level=warn -d "$WH" -i "$WH/urls.txt" | grep -E "Download Results|ERR|^[0-9a-f]{6}\|" || true
fi
ls "$WH"/*.aria2 2>/dev/null && { echo "incomplete downloads remain"; exit 1; }

echo "=== step 4: offline install"
"$UV" pip install --python "$ENV/bin/python" --no-index --find-links "$WH" -r "$ROOT/scripts/requirements.lock.txt" 2>&1 | tail -3
"$ENV/bin/python" - <<'PY'
import torch, cellpose, ultralytics, skimage
print("torch", torch.__version__, "cuda", torch.version.cuda, "available", torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else "-")
print("cellpose", cellpose.version, "| ultralytics", ultralytics.__version__, "| skimage", skimage.__version__)
x = torch.randn(64, 64, device="cuda") @ torch.randn(64, 64, device="cuda"); print("cuda matmul ok", tuple(x.shape))
PY
echo "=== wheelhouse_install DONE"
