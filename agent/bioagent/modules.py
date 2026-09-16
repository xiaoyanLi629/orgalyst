"""工具库模块注册表：名称、中文名、工具数。终端 /modules 与网页"工具模块"面板共用。

按需加载：每个对话只把选中的模块交给工具库 MCP 服务器，减少每轮固定的上下文开销
（全部 22 个模块约 12 万 token；默认 3 个模块约 3 万）。
"""
from __future__ import annotations

PREFIX = "biomni.tool."

# (短名, 中文名, 工具数)
MODULES: list[tuple[str, str, int]] = [
    ("support_tools", "常驻 Python 环境与辅助", 3),
    ("database", "数据库查询", 40),
    ("literature", "文献与网页", 8),
    ("genomics", "单细胞与基因组", 19),
    ("genetics", "遗传学", 9),
    ("molecular_biology", "分子生物学", 18),
    ("protocols", "实验方案", 4),
    ("pharmacology", "药理学", 25),
    ("immunology", "免疫学", 10),
    ("cancer_biology", "癌症生物学", 6),
    ("cell_biology", "细胞生物学", 5),
    ("microbiology", "微生物学", 12),
    ("pathology", "病理学", 7),
    ("physiology", "生理学", 11),
    ("bioimaging", "生物医学影像", 10),
    ("biochemistry", "生物化学", 6),
    ("biophysics", "生物物理", 3),
    ("bioengineering", "生物工程", 7),
    ("synthetic_biology", "合成生物学", 8),
    ("systems_biology", "系统生物学", 7),
    ("glycoengineering", "糖工程", 3),
    ("lab_automation", "实验室自动化", 3),
]
LABEL = {n: label for n, label, _ in MODULES}
COUNT = {n: c for n, _, c in MODULES}


def short(name: str) -> str:
    return name[len(PREFIX):] if name.startswith(PREFIX) else name


def full(name: str) -> str:
    return name if name.startswith(PREFIX) else PREFIX + name


def normalize(names: list[str] | None, available: list[str]) -> list[str]:
    """把用户/配置给的模块名（短名或全名，任意顺序）规范为全名列表，按注册表顺序，去重，只保留 available 里有的。"""
    want = {short(n) for n in (names or [])}
    avail = {short(n) for n in available}
    return [full(n) for n, _, _ in MODULES if n in want and n in avail]


def describe(loaded: list[str], available: list[str]) -> str:
    """给 system prompt 用的模块清单文字。"""
    l = {short(n) for n in loaded}
    a = [short(n) for n in available]
    on = "、".join(f"{LABEL.get(n, n)}({n})" for n in a if n in l) or "（无）"
    off = "、".join(f"{LABEL.get(n, n)}({n})" for n in a if n not in l) or "（无）"
    return f"已加载：{on}\n未加载（需要时请使用者开启）：{off}"
