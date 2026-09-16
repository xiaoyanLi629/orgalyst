"""斜杠命令解析。"""
from __future__ import annotations

from dataclasses import dataclass

COMMANDS = {
    "new", "resume", "sessions", "cd", "model", "cost", "tools", "expand", "proxy", "memory", "modules", "auto", "help", "quit", "exit",
}

HELP = """命令：
  /new              开始新会话
  /resume [id]      恢复会话（不带 id = 最近一次）
  /sessions         列出历史会话
  /cd <目录>        切换工作目录（下个新会话生效）
  /model <名称>     切换模型，如 claude-opus-5 / claude-sonnet-5
  /cost             本轮/累计费用、上下文占用、今日/本月用量与上限
  /tools            列出可用工具
  /expand           展开上一条工具结果
  /proxy            代理状态与节点延迟
  /memory           查看自己的长期记忆（/memory clear 清空）
  /modules [a,b|all] 查看/切换本对话加载的工具库模块（按需加载省开销）
  /auto [档位]      本对话确认方式（由严到宽）：readonly 只读文件 / ask 每步确认 / edits 确认命令 / auto 自动允许
  /help             本帮助
  /quit             退出（Ctrl+D 亦可）
输入时 Ctrl+C 中断当前回答。"""


@dataclass
class Command:
    name: str
    arg: str = ""


def parse_command(text: str) -> Command | None:
    t = text.strip()
    if not t.startswith("/"):
        return None
    name, _, arg = t[1:].partition(" ")
    name = name.lower()
    if name == "exit":
        name = "quit"
    if name not in COMMANDS:
        return Command("help", "")
    return Command(name, arg.strip())
