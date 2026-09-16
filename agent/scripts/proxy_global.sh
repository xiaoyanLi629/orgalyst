#!/bin/bash
# 临时"全局代理"：用 bioagent 的节点起第二个 mihomo 实例（另一个端口），供装包、下载模型权重等使用。
# 与 bioagent 自己的代理（17890，只分流 Anthropic 等域名）互不影响。
#   bash scripts/proxy_global.sh start [节点名]   默认选延迟最低的；可指定如 "日本大阪-Hysteria2"
#   bash scripts/proxy_global.sh stop
#   bash scripts/proxy_global.sh env              打印 export 语句：eval "$(bash scripts/proxy_global.sh env)"
#   bash scripts/proxy_global.sh test             测出口 IP 与几个下载源速度
set -uo pipefail
B="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECRETS="${BIOAGENT_SECRETS_DIR:-$HOME/.config/bioagent}"
PORT=17891; CTL=19091; DIR="$B/proxy/global"; CFG="$SECRETS/mihomo-global.yaml"; P="http://127.0.0.1:$PORT"

case "${1:-}" in
  start)
    mkdir -p "$DIR"
    "$B/.venv/bin/python" - "$SECRETS/nodes.yaml" "$CFG" "$PORT" "$CTL" <<'PY'
import sys, yaml, pathlib
nodes = yaml.safe_load(open(sys.argv[1]))
cfg = {"mixed-port": int(sys.argv[3]), "bind-address": "127.0.0.1", "allow-lan": False, "mode": "global",
       "log-level": "warning", "ipv6": False, "external-controller": f"127.0.0.1:{sys.argv[4]}",
       "proxies": nodes["proxies"],
       "proxy-groups": [{"name": "GLOBAL", "type": "url-test", "url": "https://www.gstatic.com/generate_204",
                         "interval": 300, "tolerance": 100, "proxies": [p["name"] for p in nodes["proxies"]]}],
       "rules": ["MATCH,GLOBAL"]}
out = pathlib.Path(sys.argv[2]); out.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False)); out.chmod(0o600)
PY
    if ! curl -s --max-time 2 "http://127.0.0.1:$CTL/version" >/dev/null; then
      (nohup "$B/proxy/mihomo" -d "$DIR" -f "$CFG" > "$DIR/mihomo.log" 2>&1 < /dev/null &); sleep 3
    fi
    if [ -n "${2:-}" ]; then
      # url-test 组不能手动选；指定节点时改用 select 组重启
      "$B/.venv/bin/python" - "$CFG" "$2" <<'PY'
import sys, yaml
c = yaml.safe_load(open(sys.argv[1])); c["proxy-groups"][0] = {"name": "GLOBAL", "type": "select", "proxies": c["proxy-groups"][0]["proxies"]}
yaml.safe_dump(c, open(sys.argv[1], "w"), allow_unicode=True, sort_keys=False)
PY
      pkill -f "mihomo -d $DIR" 2>/dev/null; sleep 1
      (nohup "$B/proxy/mihomo" -d "$DIR" -f "$CFG" > "$DIR/mihomo.log" 2>&1 < /dev/null &); sleep 3
      curl -s -X PUT "http://127.0.0.1:$CTL/proxies/GLOBAL" -d "{\"name\":\"$2\"}" -o /dev/null
    fi
    # conda/micromamba 不看环境变量、只认 ~/.condarc 的 proxy_servers：临时改到本代理，stop 时恢复
    if [ -f ~/.condarc ] && [ ! -f ~/.condarc.bioagent-bak ]; then cp ~/.condarc ~/.condarc.bioagent-bak; fi
    "$B/.venv/bin/python" - "$P" <<'PY'
import sys, re, pathlib
p = pathlib.Path.home()/".condarc"; s = p.read_text() if p.exists() else ""
s = re.sub(r"(?ms)^proxy_servers:.*?(?=^\S|\Z)", "", s).rstrip("\n")
p.write_text(s + f"\nproxy_servers:\n  http: {sys.argv[1]}\n  https: {sys.argv[1]}\n")
PY
    echo "全局代理就绪：$P（节点 $(curl -s "http://127.0.0.1:$CTL/proxies/GLOBAL" | "$B/.venv/bin/python" -c 'import sys,json;print(json.load(sys.stdin).get("now"))')）"
    echo "用法：eval \"\$(bash $B/scripts/proxy_global.sh env)\"" ;;
  stop)
    pkill -f "mihomo -d $DIR" && echo "已停止" || echo "未在运行"
    if [ -f ~/.condarc.bioagent-bak ]; then mv ~/.condarc.bioagent-bak ~/.condarc; echo "已恢复 ~/.condarc"; fi ;;
  env) echo "export HTTPS_PROXY=$P HTTP_PROXY=$P https_proxy=$P http_proxy=$P NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1" ;;
  test)
    echo "出口 IP: $(curl -s -x $P --max-time 15 https://api.ipify.org)"
    for u in "https://github.com/MetaCubeX/mihomo/releases/download/v1.19.30/mihomo-linux-amd64-v1.19.30.gz GitHub" \
             "https://conda.anaconda.org/conda-forge/linux-64/repodata.json.zst conda-forge" \
             "https://biomni-release.s3.amazonaws.com/data_lake/affinity_capture-ms.parquet S3" \
             "https://huggingface.co/api/models?limit=1 HuggingFace"; do
      set -- $u; printf "%-12s " "$2"; curl -sL -x $P -o /dev/null -r 0-20000000 --max-time 30 -w "%{speed_download} B/s http=%{http_code}\n" "$1"
    done ;;
  *) echo "用法: proxy_global.sh start [节点名] | stop | env | test"; exit 1 ;;
esac
