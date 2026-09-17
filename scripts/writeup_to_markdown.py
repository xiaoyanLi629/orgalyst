#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 docs/kaggle_writeup_{zh,en}.html 转成可直接贴进 Kaggle Writeup 编辑器的 Markdown（图片处用占位说明，图另存到 docs/writeup_images/ 供上传为附件）。"""
import os, re, base64
from bs4 import BeautifulSoup, NavigableString
HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(os.path.dirname(HERE), "docs"); IMG = os.path.join(D, "writeup_images"); os.makedirs(IMG, exist_ok=True)
def inline(el):
    out = []
    for c in el.children:
        if isinstance(c, NavigableString): out.append(str(c))
        elif c.name in ("b", "strong"): out.append("**" + inline(c).strip() + "**")
        elif c.name == "code": out.append("`" + c.get_text() + "`")
        elif c.name == "a": out.append(c.get_text())
        elif c.name == "br": out.append("  \n")
        else: out.append(inline(c))
    return "".join(out)
def convert(lang):
    html = open(f"{D}/kaggle_writeup_{lang}.html", encoding="utf-8").read(); soup = BeautifulSoup(html, "html.parser"); main = soup.find("main"); lines = []; n = 0
    for el in main.children:
        if isinstance(el, NavigableString): continue
        cls = " ".join(el.get("class", []))
        if el.name == "header":
            lines.append("# " + el.find("h1").get_text().strip()); sub = el.find("p"); lines.append("\n*" + sub.get_text().strip() + "*\n" if sub else "")
        elif "decl" in cls: lines.append("\n**" + el.get_text().strip() + "**\n")
        elif "links" in cls:
            kids = [k for k in el.children if not isinstance(k, NavigableString)]
            for b, v in zip(kids[0::2], kids[1::2]): lines.append(f"- **{b.get_text().strip()}**: {inline(v).strip()}")
            lines.append("")
        elif el.name in ("h2", "h3"): lines.append(("\n## " if el.name == "h2" else "\n### ") + el.get_text().strip() + "\n")
        elif el.name == "p": lines.append(inline(el).strip() + "\n")
        elif el.name == "blockquote": lines.append("> " + inline(el).strip() + "\n")
        elif el.name == "figure" or "two" in cls:
            for fig in ([el] if el.name == "figure" else el.find_all("figure")):
                n += 1; src = fig.find("img")["src"]; ext = "jpg" if "jpeg" in src[:30] else "png"; fn = f"{lang}_fig{n}.{ext}"
                open(f"{IMG}/{fn}", "wb").write(base64.b64decode(src.split(",", 1)[1]))
                cap = inline(fig.find("figcaption")).strip() if fig.find("figcaption") else ""
                lines.append(f"![{fn}](上传附件 {fn} 后替换此链接)\n\n*{cap}*\n" if lang == "zh" else f"![{fn}](replace with the attachment link of {fn})\n\n*{cap}*\n")
        elif "tw" in cls or el.name == "table":
            t = el if el.name == "table" else el.find("table"); rows = t.find_all("tr")
            for i, r in enumerate(rows):
                cells = [inline(c).strip().replace("|", "\\|") for c in r.find_all(["th", "td"])]; lines.append("| " + " | ".join(cells) + " |")
                if i == 0: lines.append("|" + "---|" * len(cells))
            lines.append("")
        else: lines.append(inline(el).strip() + "\n")
    md = "\n".join(lines); md = re.sub(r"\n{3,}", "\n\n", md)
    open(f"{D}/kaggle_writeup_{lang}.md", "w", encoding="utf-8").write(md); print(lang, len(md), "chars,", n, "figures →", IMG)
for lang in ("zh", "en"): convert(lang)
