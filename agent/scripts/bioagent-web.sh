#!/bin/bash
# BioAgent 网页版：start | stop | restart | status | logs | autostart
set -uo pipefail
B="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${BIOAGENT_WEB_PORT:-6006}"
RUN="$B/proxy/run"; PID="$RUN/web.pid"; LOG="$B/logs/web.out"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$B/.cache}" HF_HOME="${HF_HOME:-$B/.cache/huggingface}" TORCH_HOME="${TORCH_HOME:-$B/.cache/torch}"
mkdir -p "$RUN" "$B/logs"

# pid 文件在 autodl-fs 上，实例重启后还在，而 pid 会被别的进程复用；
# 有 /proc 时再确认这个 pid 真是本服务，否则 status 会对着别人的进程说“运行中”。
alive() {
  [ -f "$PID" ] || return 1
  local pid; pid="$(cat "$PID" 2>/dev/null)"
  [ -n "$pid" ] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  if [ -d /proc ] && [ -r "/proc/$pid/cmdline" ]; then
    tr '\0' ' ' < "/proc/$pid/cmdline" | grep -q "bioagent.web" || return 1
  fi
  return 0
}

case "${1:-}" in
  start)
    if alive; then echo "已在运行 (pid $(cat "$PID"))，端口 $PORT"; exit 0; fi
    nohup "$B/.venv/bin/python" -m bioagent.web --port "$PORT" >> "$LOG" 2>&1 < /dev/null &
    pid=$!; echo "$pid" > "$PID"
    # 起代理 + API 连通性检查（最多 8 次退避重试）在 uvicorn 绑端口之前，实测 15–40 秒。
    # 只等 3 秒会在服务其实起来了的时候报“启动失败”，操作员照着提示去 kill 一个健康的服务。
    for _ in $(seq 1 30); do
      kill -0 "$pid" 2>/dev/null || break
      if curl -s --max-time 3 "http://127.0.0.1:$PORT/" >/dev/null; then
        echo "已启动 pid $pid，http://127.0.0.1:$PORT"; exit 0
      fi
      sleep 2
    done
    echo "启动失败（60 秒内未就绪），见 $LOG"; tail -20 "$LOG"; exit 1 ;;
  stop)
    if alive; then kill "$(cat "$PID")"; sleep 2; alive && kill -9 "$(cat "$PID")"; rm -f "$PID"; echo "已停止"; else echo "未在运行"; fi ;;
  restart) "$0" stop; "$0" start ;;
  status) if alive; then echo "运行中 pid $(cat "$PID")，端口 $PORT"; else echo "未运行"; fi ;;
  logs) tail -n 50 -f "$B/logs/web.log" ;;
  autostart)
    if [ -w /init/supervisor ]; then
      cat > /init/supervisor/bioagent-web.ini <<EOF
[program:bioagent-web]
command=$B/scripts/bioagent-web.sh start-fg
directory=$B
autostart=true
autorestart=true
startsecs=5
stdout_logfile=$B/logs/supervisor.log
redirect_stderr=true
EOF
      echo "已写 /init/supervisor/bioagent-web.ini（supervisord 开机拉起并自动重启）"
      supervisorctl -c /init/supervisor/supervisor.ini reread >/dev/null 2>&1 && supervisorctl -c /init/supervisor/supervisor.ini update >/dev/null 2>&1 && echo "supervisord 已加载"
    else
      grep -q "bioagent-web.sh start" ~/.bioagent_env 2>/dev/null || printf '\n# BioAgent 网页版：登录 shell 时若未运行则拉起\n[ -x "%s/scripts/bioagent-web.sh" ] && "%s/scripts/bioagent-web.sh" start >/dev/null 2>&1\n' "$B" "$B" >> ~/.bioagent_env
      echo "已加入 ~/.bioagent_env（每次登录 shell 时检查并拉起）"
    fi ;;
  start-fg)  # supervisord 用：前台运行
    exec "$B/.venv/bin/python" -m bioagent.web --port "$PORT" ;;
  *) echo "用法: bioagent-web.sh start|stop|restart|status|logs|autostart"; exit 1 ;;
esac
