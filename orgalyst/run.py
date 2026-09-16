"""运行目录（可追溯留档）：每次分析一个目录，含输入清单与哈希、模型标识、参数、软件版本、产物。"""
from __future__ import annotations
import hashlib, json, os, platform, sys, time, uuid

def file_md5(p, chunk=1 << 20):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(chunk), b""): h.update(c)
    return h.hexdigest()

def versions():
    v = dict(python=sys.version.split()[0], platform=platform.platform())
    for m in ("numpy", "torch", "cellpose", "ultralytics", "skimage", "pandas"):
        try: v[m] = __import__(m).__version__ if m != "cellpose" else __import__(m).version
        except Exception: v[m] = None
    try:
        import torch; v["cuda"] = torch.version.cuda; v["gpu"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except Exception: pass
    return v

class Run:
    def __init__(self, out_root: str, name: str = "analysis"):
        self.id = time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
        self.dir = os.path.join(out_root, f"{name}_{self.id}")
        for d in ("masks", "overlays", "tables", "figures"): os.makedirs(os.path.join(self.dir, d), exist_ok=True)
        self.manifest = dict(run_id=self.id, name=name, created=time.strftime("%Y-%m-%d %H:%M:%S"), inputs=[], models={}, params={},
                             versions=versions(), outputs=[], log=[])
    def add_input(self, path, **meta): self.manifest["inputs"].append(dict(path=os.path.abspath(path), md5=file_md5(path), **meta))
    def add_output(self, path, kind=""): self.manifest["outputs"].append(dict(path=os.path.relpath(path, self.dir), kind=kind))
    def log(self, msg): self.manifest["log"].append(f"{time.strftime('%H:%M:%S')} {msg}"); print(msg, flush=True)
    def path(self, *parts): return os.path.join(self.dir, *parts)
    def save(self):
        with open(self.path("manifest.json"), "w") as f: json.dump(self.manifest, f, indent=2, ensure_ascii=False)
        return self.path("manifest.json")
