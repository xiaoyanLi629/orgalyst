"""直接用 MCP 客户端连一次 biomni/mcp_server.py：列工具数，并调用一次免费的 query_pubmed。
用法：biomni/.venv/bin/python scripts/mcp_client_test.py
"""
import asyncio
import os
import sys
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "biomni" / "mcp_server.py"


async def main():
    env = {**os.environ, "KMP_DUPLICATE_LIB_OK": "TRUE"}
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)], env=env)
    t = time.time()
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = (await s.list_tools()).tools
            names = [x.name for x in tools]
            print(f"connected in {time.time()-t:.1f}s, {len(names)} tools")
            print("sample:", names[:5], "...", [n for n in names if "scRNA" in n][:3])
            res = await s.call_tool("query_pubmed", {"query": "TCF7L2 type 2 diabetes GWAS", "max_papers": 1})
            txt = res.content[0].text if res.content else ""
            print("query_pubmed:", txt[:200].replace("\n", " "))


asyncio.run(main())
