#!/usr/bin/env bash
# 把 AI4S 工作目录整理成可公开的比赛仓库 repo/orgalyst（只拷代码、文档、结果表和小型配置；数据与权重走下载脚本）。
set -e
SRC=/root/autodl-fs/AI4S; BA=/root/autodl-fs/bioagent; R=$SRC/repo/orgalyst; SCAF=/tmp/repo_scaffold
mkdir -p $R
rsync -a --delete --exclude __pycache__ $SRC/orgalyst/ $R/orgalyst/
rsync -a --delete --exclude __pycache__ $SRC/scripts/ $R/scripts/
rsync -a --delete $SRC/configs/ $R/configs/
rsync -a --delete $SRC/results/ $R/results/
mkdir -p $R/docs $R/e5/ref $R/weights $R/data
rsync -a $SRC/docs/*.html $R/docs/
cp $SRC/e5/ref/refs.json $R/e5/ref/refs.json
cp $SRC/download_orgline.sh $R/scripts/download_orgline.sh
cp $SRC/data/OrgLine/DATASET.md $R/data/DATASET.md 2>/dev/null || true
cp $SCAF/Dockerfile $SCAF/.gitignore $SCAF/LICENSE $SCAF/pyproject.toml $R/
cp $SCAF/download_weights.sh $R/scripts/download_weights.sh; chmod +x $R/scripts/*.sh
cp $SCAF/weights_README.md $R/weights/README.md
cp $SRC/scripts/requirements.txt $R/requirements.txt
# ---- Agent 路径：bioagent 的精简副本（代码 + skill 包 + 测试；不含任何账号、代理节点、会话）----
A=$R/agent; mkdir -p $A
rsync -a --delete --exclude __pycache__ $BA/bioagent/ $A/bioagent/
rsync -a --delete $BA/skillpack/ $A/skillpack/
rsync -a --delete --exclude __pycache__ $BA/tests/ $A/tests/
mkdir -p $A/scripts; for f in bioagent-web.sh proxy_global.sh config_backup.sh gen_proxy_config.py e2e_test.sh mcp_client_test.py; do [ -f $BA/scripts/$f ] && cp $BA/scripts/$f $A/scripts/; done
for f in pyproject.toml bioagent.sh install.sh deploy.sh BIOAGENT.md README.md; do [ -f $BA/$f ] && cp $BA/$f $A/; done
# 示例配置：去掉本机路径与隐私相关项，orgalyst MCP 指向仓库内路径
python3 - <<'PY'
import re
src = open("/root/autodl-fs/bioagent/config.yaml", encoding="utf-8").read()
src = re.sub(r"^cwd: .*$", "cwd: ./workspace", src, flags=re.M)
src = src.replace("/root/autodl-fs/AI4S/.venv/bin/python", "python").replace("/root/autodl-fs/AI4S/orgalyst/mcp_server.py", "../orgalyst/mcp_server.py")
src = src.replace("CELLPOSE_LOCAL_MODELS_PATH: /root/autodl-tmp/.cellpose/models", "CELLPOSE_LOCAL_MODELS_PATH: ../weights/cellpose")
src = src.replace("biomni:\n  enabled: true", "biomni:\n  enabled: false   # Orgalyst 演示不需要 Biomni 工具库；装了 biomni/ 后可改为 true")
open("/root/autodl-fs/AI4S/repo/orgalyst/agent/config.example.yaml", "w", encoding="utf-8").write("# 复制为 config.yaml 再改；API key 与代理节点放 ~/.config/bioagent/（见 agent/README.md），不进仓库\n" + src)
PY
rm -f $A/config.yaml
# 不该出现在公开仓库里的东西做最后检查
! grep -rIl --exclude-dir=.git -E "sk-ant-|ANTHROPIC_API_KEY=sk|password:|hysteria|mihomo\.yaml" $R >/dev/null || { echo "!!! 发现疑似密钥/私有配置："; grep -rIl --exclude-dir=.git -E "sk-ant-|ANTHROPIC_API_KEY=sk|password:|hysteria|mihomo\.yaml" $R; exit 1; }
du -sh $R; find $R -type f | wc -l
