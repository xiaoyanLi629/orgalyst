#!/usr/bin/env python
"""从 ~/.config/bioagent/nodes.yaml（节点定义，含密钥）生成 ~/.config/bioagent/mihomo.yaml。

密钥类文件都放 home 下的密钥目录（可用 BIOAGENT_SECRETS_DIR 覆盖），因为项目所在的
Fdisk 是 fuseblk 挂载，chmod 600 不起作用。
"""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bioagent.config import load_settings, secrets_dir  # noqa: E402
from bioagent.proxy import render_proxy_config  # noqa: E402

s = load_settings(ROOT)
sd = secrets_dir()
sd.mkdir(parents=True, exist_ok=True)
sd.chmod(0o700)
nodes_file = sd / "nodes.yaml"
if not nodes_file.exists():
    sys.exit(f"缺少 {nodes_file}：格式为 {{proxies: [mihomo 节点...]}}，可从 Clash 配置的 proxies 段复制")
nodes = yaml.safe_load(nodes_file.read_text())
cfg = render_proxy_config(
    nodes, port=s.proxy.port, controller_port=s.proxy.controller_port, domains=s.proxy.domains
)
out = sd / "mihomo.yaml"
out.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False))
out.chmod(0o600)
print("written", out, "nodes:", [p["name"] for p in nodes["proxies"]])
