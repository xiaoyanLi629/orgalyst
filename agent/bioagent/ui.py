"""终端渲染与输入：rich 负责输出，prompt_toolkit 负责输入（支持中文宽度、历史、Ctrl+C/D）。"""
from __future__ import annotations

import json
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.table import Table


class UI:
    def __init__(self, assistant_name: str, history_file: Path):
        self.name = assistant_name
        self.console = Console(highlight=False)
        Path(history_file).parent.mkdir(parents=True, exist_ok=True)
        self.status: dict = {}  # model / context_tokens / context_window，由 cli 更新
        self.session: PromptSession = PromptSession(
            history=FileHistory(str(history_file)), bottom_toolbar=self._toolbar
        )
        self.last_results: list[str] = []

    # ---- 底部状态栏 ----
    def set_status(self, **kw) -> None:
        self.status.update(kw)

    @staticmethod
    def context_bar(used: int, window: int, width: int = 20) -> str:
        """上下文占用条，如 ▮▮▮▮░░░░░░░░░░░░░░░░ 21% (42k/200k)。"""
        window = max(window, 1)
        pct = min(used / window, 1.0)
        filled = round(pct * width)
        k = lambda n: f"{n / 1000:.0f}k" if n >= 1000 else str(n)
        return f"{'▮' * filled}{'░' * (width - filled)} {pct * 100:.0f}% ({k(used)}/{k(window)})"

    def _toolbar(self):
        st = self.status
        used, window = int(st.get("context_tokens") or 0), int(st.get("context_window") or 1_000_000)
        pct = used / max(window, 1)
        color = "ansired" if pct >= 0.8 else "ansiyellow" if pct >= 0.6 else "ansigreen"
        return HTML(f" <b>{self.name}</b> · 上下文 <{color}>{self.context_bar(used, window)}</{color}>")

    # ---- 输入 ----
    async def prompt(self) -> str:
        with patch_stdout():
            return await self.session.prompt_async("你 > ")

    async def confirm(self, summary: str) -> bool:
        self.console.print(f"[yellow]⚠ 需要确认：{summary}[/yellow]")
        with patch_stdout():
            ans = await self.session.prompt_async("允许? [y/N] ")
        return ans.strip().lower() in ("y", "yes", "是")

    # ---- 输出 ----
    def info(self, msg: str) -> None:
        self.console.print(f"[dim]{msg}[/dim]")

    def warn(self, msg: str) -> None:
        self.console.print(f"[red]{msg}[/red]")

    def table(self, title: str, rows: list[dict]) -> None:
        if not rows:
            self.info("(空)")
            return
        t = Table(title=title)
        for k in rows[0]:
            t.add_column(str(k))
        for r in rows:
            t.add_row(*[str(v) for v in r.values()])
        self.console.print(t)

    async def render(self, events) -> dict:
        """流式打印一轮回复；返回 result 事件的 data（可能为空 dict）。"""
        buf = ""
        result: dict = {}
        self.last_results = []
        live = self._live()
        live.start()
        try:
            async for e in events:
                if e.kind == "text":
                    buf += e.text
                    live.update(Markdown(buf))
                elif e.kind == "tool_use":
                    live.stop()  # Live 停止时保留最后一帧，不再重复打印
                    buf = ""
                    arg = json.dumps(e.data.get("input", {}), ensure_ascii=False)
                    self.console.print(f"[cyan]🔧 {e.name}[/cyan] [dim]{arg[:140]}[/dim]")
                    live = self._live()
                    live.start()
                elif e.kind == "tool_result":
                    self.last_results.append(e.text)
                    n = len(e.text.splitlines())
                    mark = "[red]✗[/red]" if e.data.get("error") else "[green]✓[/green]"
                    live.stop()
                    self.console.print(f"   {mark} [dim]{n} 行结果（/expand 展开）[/dim]")
                    live = self._live()
                    live.start()
                elif e.kind == "result":
                    result = e.data
        finally:
            live.stop()
        if result.get("errors"):
            self.warn("错误: " + "; ".join(str(x) for x in result["errors"]))
        return result

    def _live(self) -> Live:
        return Live(Markdown(""), console=self.console, refresh_per_second=12, vertical_overflow="visible")
