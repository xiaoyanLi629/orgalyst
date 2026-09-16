#!/bin/bash
# 把 ~/.config/bioagent 里不含密钥的账号文件（users.yaml、web_secret）备份到网络盘，换实例后恢复。
#   bash scripts/config_backup.sh backup    # 备份到 <项目>/.config_backup/config.tar（chmod 600）
#   bash scripts/config_backup.sh restore   # 从备份恢复到 ~/.config/bioagent（已存在的文件先留 .bak）
# .env / nodes.yaml / mihomo.yaml 含 API key 与代理密钥，不入此备份；从 qdyy 的 ~/.config/bioagent/ 另取。
# 同事网页账号（bio01–bio10）的初始密码记录在本机 ~/Documents/我的工具/bioagent/private/bioagent_accounts.txt（git 忽略）。
set -uo pipefail
B="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; C="$HOME/.config/bioagent"; BK="$B/.config_backup"
case "${1:-}" in
  backup)
    mkdir -p "$BK"; tar -C "$C" -cf "$BK/config.tar" users.yaml web_secret 2>/dev/null && chmod 600 "$BK/config.tar" && date > "$BK/BACKUP_TIME" && echo "备份 → $BK/config.tar ($(cat "$BK/BACKUP_TIME"))" ;;
  restore)
    [ -f "$BK/config.tar" ] || { echo "无备份 $BK/config.tar"; exit 1; }
    mkdir -p "$C"; chmod 700 "$C"; for f in users.yaml web_secret; do [ -f "$C/$f" ] && cp "$C/$f" "$C/$f.bak"; done
    tar -C "$C" -xf "$BK/config.tar" && chmod 600 "$C"/* && echo "已恢复 users.yaml、web_secret（备份时间 $(cat "$BK/BACKUP_TIME")）" ;;
  *) echo "用法: config_backup.sh backup|restore"; exit 1 ;;
esac
