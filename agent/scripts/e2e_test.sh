#!/bin/bash
# 端到端功能测试：从 Mac 通过伪终端驱动服务器上的 bioagent，逐项验证。
# 用法：bash scripts/e2e_test.sh            （需要 ssh qdyy 免密）
# 输出每项 PASS/FAIL，日志在 /tmp/bioagent_e2e_*.log
set -u
HOST=qdyy
DIR=/media/ubuntu/Fdisk/BJQDP/bioagent
LOG=/tmp/bioagent_e2e_$(date +%H%M%S).log
pass=0; fail=0
check() { if grep -qE "$2" "$3"; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1   (expect /$2/)"; fail=$((fail+1)); fi; }
clean() { sed 's/\x1b\[[0-9;?]*[a-zA-Z]//g; s/\r//g' | grep -v "^\s*$" | awk '!seen[$0]++'; }
send() { printf '%s\r' "$1"; }

echo "== 0. 静态检查"
ssh -o BatchMode=yes $HOST "cd $DIR && ./bioagent.sh --check" 2>&1 | clean > "$LOG.check"
check "代理与 API 连通" "API 连通" "$LOG.check"
check "工具库 MCP: 已配置" "工具库 MCP: 已配置" "$LOG.check"
ssh -o BatchMode=yes $HOST "cd $DIR && .venv/bin/pytest -q 2>&1 | tail -1" > "$LOG.unit"
check "单元测试全部通过" "passed" "$LOG.unit"

echo "== 1. 会话 A：工具与命令"
( sleep 18
  send '用 query_uniprot 工具 查人类 BRCA1 的 accession 和长度，一句话回答。'; sleep 60
  send '用 query_pubmed 工具 找一篇关于 organoid segmentation 的论文，只给标题。'; sleep 45
  send '用 run_python_repl 工具：import pandas as pd; df = pd.read_pickle("/media/ubuntu/Fdisk/BJQDP/bioagent/biomni/data/biomni_data/data_lake/gwas_catalog.pkl"); print(df.shape)。然后再用 run_python_repl 执行 print(df.columns[:3].tolist())。报告两次输出。'; sleep 30
  send 'y'; sleep 60
  send '用 Bash 运行 plink2 --version 和 blastn -version | head -1，报告版本。'; sleep 45
  send '尝试用 Write 工具在 /media/ubuntu/Fdisk/BJQDP/肺癌/e2e_test.txt 写入 x，看看会怎样，然后如实告诉我结果。'; sleep 40
  send '/model claude-opus-5'; sleep 3
  send '/model'; sleep 3
  send '/proxy'; sleep 20
  send '/expand'; sleep 3
  send '/cost'; sleep 3
  send '/sessions'; sleep 3
  send '/quit'; sleep 3
) | ssh -tt -o BatchMode=yes $HOST "cd $DIR && TERM=xterm-256color COLUMNS=140 ./bioagent.sh --user e2e" 2>&1 | clean > "$LOG.a"

check "数据库工具 query_uniprot" "P38398" "$LOG.a"
check "BRCA1 长度 1863" "1863" "$LOG.a"
check "文献工具 query_pubmed" "mcp__biotools__query_pubmed" "$LOG.a"
check "REPL 确认提示只出现" "常驻 Python REPL" "$LOG.a"
check "REPL 读取本地数据湖（gwas_catalog 行数）" "622784" "$LOG.a"
check "REPL 跨步骤保留变量（columns）" "DATE ADDED TO CATALOG|PUBMEDID" "$LOG.a"
check "Bash 能用 PLINK2" "PLINK.{0,3}v2" "$LOG.a"
check "Bash 能用 BLAST" "blastn.{0,6}2\.[0-9]+\.[0-9]+\+" "$LOG.a"
check "只读目录写入被拒绝" "只读|禁止|拒绝" "$LOG.a"
check "/model 切换" "模型 → claude-opus-5" "$LOG.a"
check "/proxy 节点延迟表" "日本大阪" "$LOG.a"
check "/cost 输出" "本会话累计" "$LOG.a"
check "/sessions 列表" "费用\\$" "$LOG.a"

echo "== 2. 会话 B：--resume 记忆"
SID=$(ssh -o BatchMode=yes $HOST "cd $DIR && .venv/bin/python -c \"from bioagent.sessions import SessionIndex; print(SessionIndex('sessions/e2e/index.json').latest_id())\"")
( sleep 18; send '刚才我让你查的第一个基因是什么？只回基因名。'; sleep 40; send '/quit'; sleep 3 ) \
  | ssh -tt -o BatchMode=yes $HOST "cd $DIR && TERM=xterm-256color COLUMNS=140 ./bioagent.sh --user e2e --resume" 2>&1 | clean > "$LOG.b"
check "--resume 恢复上一会话并记得内容" "BRCA1" "$LOG.b"

echo "== 3. 退出后清理"
# 注意 pgrep 模式要避免匹配到这条 ssh 命令自身（用 [r] 技巧）
ssh -o BatchMode=yes $HOST "ss -ltn | grep -E ':(17890|19090) ' || echo PROXY_STOPPED; pgrep -f 'mcp_serve[r].py' >/dev/null && echo MCP_ALIVE || echo MCP_STOPPED; ls -t $DIR/workspace/e2e/repl_*.py | head -1 | xargs cat" > "$LOG.c" 2>&1
check "代理已停止" "PROXY_STOPPED" "$LOG.c"
check "Biomni MCP 进程已退出" "MCP_STOPPED" "$LOG.c"
check "REPL 代码已留档" "read_pickle" "$LOG.c"

echo; echo "结果：$pass 通过，$fail 失败。日志：$LOG.*"
[ $fail = 0 ]
