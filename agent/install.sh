#!/bin/bash
# bioagent 一键安装（qdyy 服务器）。可重复运行。
#   bash install.sh                 只装 bioagent 本体 + 代理
#   bash install.sh --with-biomni   另外安装 Biomni 与数据湖（后台，约 1–3 小时）
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$ROOT"
UV="${UV:-$HOME/.local/bin/uv}"
SECRETS="${BIOAGENT_SECRETS_DIR:-$HOME/.config/bioagent}"
MIHOMO_VER="${MIHOMO_VER:-v1.19.30}"

step() { echo; echo "### $*"; }

step "1/6 检查 uv"
[ -x "$UV" ] || { echo "缺少 uv：curl -LsSf https://astral.sh/uv/install.sh | sh"; exit 1; }

step "2/6 Python 环境"
[ -x .venv/bin/python ] || "$UV" venv --python 3.11 .venv
"$UV" pip install --python .venv/bin/python -e ".[dev]" -q
chmod +x .venv/lib/python3.11/site-packages/claude_agent_sdk/_bundled/claude 2>/dev/null || true
.venv/bin/python -c "import claude_agent_sdk; print('claude-agent-sdk', claude_agent_sdk.__version__)"

step "3/6 密钥目录 $SECRETS"
mkdir -p "$SECRETS" && chmod 700 "$SECRETS"
if [ ! -f "$SECRETS/.env" ]; then
  echo "请创建 $SECRETS/.env，内容：ANTHROPIC_API_KEY=sk-ant-...   然后 chmod 600"; MISSING=1
fi
if [ ! -f "$SECRETS/nodes.yaml" ]; then
  echo "请创建 $SECRETS/nodes.yaml，内容：{proxies: [mihomo 节点...]}（从 Clash 配置的 proxies 段复制）"; MISSING=1
fi
[ -n "${MISSING:-}" ] && { echo "补齐后重新运行 install.sh"; exit 1; }

step "4/6 代理程序 mihomo"
mkdir -p proxy/run
if [ ! -x proxy/mihomo ]; then
  URL="https://github.com/MetaCubeX/mihomo/releases/download/$MIHOMO_VER/mihomo-linux-amd64-$MIHOMO_VER.gz"
  curl -sL --max-time 300 -o proxy/mihomo.gz "$URL" && gunzip -f proxy/mihomo.gz && chmod +x proxy/mihomo
fi
proxy/mihomo -v | head -1
.venv/bin/python scripts/gen_proxy_config.py

step "5/6 目录与知识文件"
mkdir -p sessions workspace
[ -f BIOAGENT.md ] && echo "BIOAGENT.md 已就位" || echo "提示：可写 BIOAGENT.md 提供项目背景"

step "6/6 自检"
./bioagent.sh --check || exit $?

if [ "${1:-}" = "--with-biomni" ]; then
  step "Biomni（后台）"
  chmod +x scripts/*.sh
  (nohup bash scripts/install_biomni.sh > biomni_install.log 2>&1 < /dev/null &)
  (nohup bash -c "until [ -x biomni/.venv/bin/python ] && [ -f biomni/Biomni/biomni/env_desc.py ]; do sleep 20; done; bash scripts/download_datalake.sh" > biomni_datalake.log 2>&1 < /dev/null &)
  echo "已在后台安装：tail -f biomni_install.log / biomni_datalake.log；完成后 biomni/.venv/bin/python scripts/mcp_client_test.py 验证"
fi
echo; echo "安装完成。启动：./bioagent.sh"
