#!/bin/bash
# 把 bioagent 完整部署到一台新的 Linux 服务器（为 AutoDL 设计，其它 Ubuntu 也适用）。
# 在 Mac 上运行：bash scripts/deploy.sh <ssh别名> [远端目录] [数据湖来源]
#   ssh别名   ~/.ssh/config 里已配置、免密可用的主机名，如 autodl
#   远端目录  默认 /root/autodl-fs/bioagent（AutoDL 跨实例持久盘；系统盘小，一切都放这里）
#   数据湖来源 qdyy | s3   默认 qdyy（从 qdyy 直传，比 S3 快时用）
# 步骤：代码 → 密钥 → uv/mihomo → bioagent venv → 配置 → 工具库（后台）→ 数据湖（后台）→ 自检
set -uo pipefail
HOST="${1:?用法: deploy.sh <ssh别名> [远端目录] [qdyy|s3]}"
DEST="${2:-/root/autodl-fs/bioagent}"
LAKE="${3:-qdyy}"
LOCAL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
R() { ssh -o BatchMode=yes -o ConnectTimeout=20 "$HOST" "[ -f ~/.bioagent_env ] && source ~/.bioagent_env; $*"; }
step() { echo; echo "### $* $(date +%H:%M:%S)"; }

step "0/8 连通性"
R 'echo "$(hostname) $(whoami) $(nproc)核 $(free -g | awk "/Mem/{print \$2}")G内存"; nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -2; df -h '"$(dirname "$DEST")"' | tail -1' || { echo "连不上 $HOST"; exit 1; }

step "1/8 同步代码 → $DEST"
R "mkdir -p $DEST"
rsync -a --exclude .venv --exclude .git --exclude proxy/mihomo --exclude proxy/run --exclude sessions --exclude workspace --exclude 'biomni/' "$LOCAL/" "$HOST:$DEST/"
rsync -a "$LOCAL/biomni/mcp_server.py" "$HOST:$DEST/biomni/"

step "2/8 密钥（.env 与节点，从本机 ~/.config/bioagent 或 qdyy 取）"
R 'mkdir -p ~/.config/bioagent && chmod 700 ~/.config/bioagent'
if [ -f "$HOME/.config/bioagent/.env" ]; then
  scp -q "$HOME/.config/bioagent/.env" "$HOME/.config/bioagent/nodes.yaml" "$HOST:~/.config/bioagent/"
else
  ssh -o BatchMode=yes qdyy 'cat ~/.config/bioagent/.env' | R 'cat > ~/.config/bioagent/.env'
  ssh -o BatchMode=yes qdyy 'cat ~/.config/bioagent/nodes.yaml' | R 'cat > ~/.config/bioagent/nodes.yaml'
fi
R 'chmod 600 ~/.config/bioagent/.env ~/.config/bioagent/nodes.yaml && ls -la ~/.config/bioagent | tail -2'

step "2.5/8 缓存目录与环境变量（~/.bioagent_env，.bashrc 顶部加载）"
R "mkdir -p $DEST/.cache && cat > ~/.bioagent_env <<'EOF'
# bioagent：缓存放持久盘，避免系统盘写满（交互 shell 与脚本都加载此文件）
export DEST_CACHE=$DEST/.cache
export XDG_CACHE_HOME=\$DEST_CACHE UV_CACHE_DIR=\$DEST_CACHE/uv PIP_CACHE_DIR=\$DEST_CACHE/pip HF_HOME=\$DEST_CACHE/huggingface TORCH_HOME=\$DEST_CACHE/torch MAMBA_ROOT_PREFIX=\$DEST_CACHE/mamba
export BIOAGENT_HOME=$DEST
export PATH=\$HOME/.local/bin:\$PATH
EOF
grep -q bioagent_env ~/.bashrc || { { echo '[ -f ~/.bioagent_env ] && source ~/.bioagent_env   # bioagent 缓存与路径'; cat ~/.bashrc; } > ~/.bashrc.new && mv ~/.bashrc.new ~/.bashrc; }
source ~/.bioagent_env; mkdir -p \$UV_CACHE_DIR \$PIP_CACHE_DIR \$HF_HOME \$TORCH_HOME \$MAMBA_ROOT_PREFIX; echo UV_CACHE_DIR=\$UV_CACHE_DIR"

step "3/8 uv 与 mihomo"
R 'command -v ~/.local/bin/uv >/dev/null || (source /etc/network_turbo 2>/dev/null; curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1 || pip install -q uv && mkdir -p ~/.local/bin && ln -sf $(command -v uv) ~/.local/bin/uv); ~/.local/bin/uv --version'
R "mkdir -p $DEST/proxy/run; [ -x $DEST/proxy/mihomo ] || (source /etc/network_turbo 2>/dev/null; cd $DEST/proxy && curl -sL --max-time 300 -o mihomo.gz https://github.com/MetaCubeX/mihomo/releases/download/v1.19.30/mihomo-linux-amd64-v1.19.30.gz && gunzip -f mihomo.gz && chmod +x mihomo); $DEST/proxy/mihomo -v | head -1" \
  || { echo "GitHub 下载失败，改从 qdyy 复制 mihomo"; ssh -o BatchMode=yes qdyy 'cat /media/ubuntu/Fdisk/BJQDP/bioagent/proxy/mihomo' | R "cat > $DEST/proxy/mihomo && chmod +x $DEST/proxy/mihomo && $DEST/proxy/mihomo -v | head -1"; }

step "4/8 bioagent 环境"
# 注意：AutoDL 的学术加速（network_turbo）只对 GitHub/HF 有效，会让镜像站超时，所以 Python 下载用它、pip 安装不用它
R "cd $DEST && ( source /etc/network_turbo >/dev/null 2>&1; ~/.local/bin/uv python install 3.11 2>&1 | tail -1 ); [ -x .venv/bin/python ] || ~/.local/bin/uv venv --python 3.11 .venv -q; unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY; ~/.local/bin/uv pip install --python .venv/bin/python --index-url https://mirrors.aliyun.com/pypi/simple -q -e '.[dev]' 2>&1 | tail -1; chmod +x .venv/lib/python3.11/site-packages/claude_agent_sdk/_bundled/claude; .venv/bin/python -c 'import claude_agent_sdk;print(\"sdk\",claude_agent_sdk.__version__)'; chmod +x bioagent.sh scripts/*.sh"

step "5/8 配置（按新服务器路径）"
R "cd $DEST && .venv/bin/python - <<'PY'
import yaml, pathlib
p = pathlib.Path('config.yaml'); c = yaml.safe_load(p.read_text())
c['cwd'] = '$DEST/workspace'
c['readonly_dirs'] = []
p.write_text(yaml.safe_dump(c, allow_unicode=True, sort_keys=False))
print('cwd =', c['cwd'], '| readonly_dirs =', c['readonly_dirs'])
PY
mkdir -p workspace sessions && .venv/bin/python scripts/gen_proxy_config.py && ./bioagent.sh --check 2>&1 | grep -v 'not a terminal'"

step "6/8 工具库（后台，约 15 分钟）"
# 实例可能自带 git 全局代理（指向不存在的 127.0.0.1:7890），先清掉；源码优先从 qdyy 复制，避免 GitHub
R "git config --global --unset http.proxy 2>/dev/null; git config --global --unset https.proxy 2>/dev/null; mkdir -p $DEST/biomni; [ -d $DEST/biomni/Biomni ] || rsync -a -e 'ssh -p 10022 -o StrictHostKeyChecking=accept-new' --exclude .git ubuntu@221.224.32.107:/media/ubuntu/Fdisk/BJQDP/bioagent/biomni/Biomni/ $DEST/biomni/Biomni/ 2>/dev/null || true"
R "cd $DEST && unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY; (nohup bash scripts/install_biomni.sh > biomni_install.log 2>&1 < /dev/null &) && echo launched"

step "7/8 数据湖 15GB（后台）"
if [ "$LAKE" = "qdyy" ]; then
  # qdyy → 新服务器直传：需要新服务器能免密连 qdyy（把新服务器公钥加到 qdyy），否则退回 S3
  R "ssh -o BatchMode=yes -o ConnectTimeout=10 -p 10022 ubuntu@221.224.32.107 true 2>/dev/null" \
    && R "cd $DEST && mkdir -p biomni/data/biomni_data && (nohup rsync -a --partial -e 'ssh -p 10022' ubuntu@221.224.32.107:/media/ubuntu/Fdisk/BJQDP/bioagent/biomni/data/biomni_data/ biomni/data/biomni_data/ > biomni_datalake.log 2>&1 < /dev/null &) && echo 'rsync from qdyy launched'" \
    || { echo "新服务器连不上 qdyy，改用 S3 下载"; LAKE=s3; }
fi
if [ "$LAKE" = "s3" ]; then
  R "cd $DEST && (nohup bash -c 'until [ -x biomni/.venv/bin/python ] && [ -f biomni/Biomni/biomni/env_desc.py ]; do sleep 20; done; bash scripts/download_datalake.sh' > biomni_datalake.log 2>&1 < /dev/null &) && echo 'S3 download launched (waits for venv)'"
fi

step "7.5/8 Python 环境搬到本地盘（AutoDL 网络盘跑不动小文件；无 autodl-tmp 的机器自动跳过）"
R "[ -d /root/autodl-tmp ] && cd $DEST && bash scripts/envs_local.sh move || echo '无本地盘，跳过'"
R "[ -d /root/autodl-tmp ] && mkdir -p /root/autodl-tmp/bioagent-envs/biomni_tools && cd $DEST && { [ -L biomni/tools ] || ln -s /root/autodl-tmp/bioagent-envs/biomni_tools biomni/tools; } && echo 'biomni/tools → 本地盘' || true"

step "8/8 完成提示"
cat <<EOF
后台仍在进行：工具库安装（$DEST/biomni_install.log）、数据湖（$DEST/biomni_datalake.log）。
完成后在新服务器执行：
  cd $DEST && bash scripts/install_biomni_extras.sh      # 可选：命令行生信工具 + R\n  bash scripts/envs_local.sh backup                        # AutoDL：把本地盘环境备份到网络盘
  biomni/.venv/bin/python scripts/mcp_client_test.py       # 验证工具库
  ./bioagent.sh --user <名字>                               # 开始使用
EOF
