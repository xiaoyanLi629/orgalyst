"""WebSocket：一个对话一条连接，先回放历史再实时转发；可多连接同看一个对话。"""
from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlsplit

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..chats import get_chat, read_events
from ..store import UserStore
from .auth import COOKIE_NAME

router = APIRouter()
log = logging.getLogger("bioagent.web.ws")


def _hostname(value: str) -> str | None:
    """从 "host" 或 "host:port" 里取主机名（小写，去端口）。"""
    return urlsplit(f"//{value.strip()}").hostname


def _origin_ok(ws: WebSocket) -> bool:
    """跨站 WebSocket 劫持只有 SameSite=Lax 一层挡着；握手时再显式比一次 Origin 和 Host。

    只比主机名，不比端口：AutoDL 的公网代理把 Host 写成不带端口的域名，
    而浏览器的 Origin 带着 :8443，带端口比会把所有公网连接判成跨站。
    完全没有 Origin 的（脚本、curl）不是浏览器发起的跨站请求，放行；
    但带了 Origin 又解析不出主机名的（沙箱 iframe 的 null、垃圾值）一律当跨站。"""
    origin = ws.headers.get("origin")
    if not origin:
        return True
    origin_host = urlsplit(origin).hostname
    if origin_host is None:
        return False
    fwd = (ws.headers.get("x-forwarded-host") or "").split(",")[0]   # 代理可能串成列表，取最前面那个
    allowed = {h for h in (_hostname(ws.headers.get("host", "")), _hostname(fwd)) if h}
    return origin_host in allowed


@router.websocket("/ws/chat/{chat_id}")
async def chat_ws(ws: WebSocket, chat_id: str):
    st = ws.app.state
    name = st.signer.unsign(ws.cookies.get(COOKIE_NAME))
    user = st.accounts.get(name) if name else None
    if not user or not user.get("enabled", True):
        await ws.close(code=4401)
        return
    if not _origin_ok(ws):
        await ws.close(code=4403)
        return
    store = UserStore(st.settings.root, name)
    chat = get_chat(store, chat_id)
    if chat is None:
        await ws.close(code=4404)
        return
    # 先拿 runner 再 accept：并发上限满了要在握手阶段就回绝，不要先建连接再关
    try:
        runner = await st.pool.get(name, chat_id)
    except KeyError:
        # 连接建立与 pool.get 之间对话被并发删除
        await ws.close(code=4404)
        return
    except RuntimeError:
        await ws.close(code=1013)  # try again later
        return
    await ws.accept()
    q = None
    pump_task: asyncio.Task | None = None
    try:
        q = runner.subscribe()
        await ws.send_json({"type": "history", "events": read_events(chat)})
        await ws.send_json(runner.status())
        prewarm_task = asyncio.create_task(runner.prewarm())  # 后台预热；结果通过 status 事件回推

        def start_pump(queue: asyncio.Queue) -> asyncio.Task:
            async def pump():
                # pump 一旦静默死掉，socket 还开着、receive_json 还在等、队列还在涨，
                # 浏览器那边什么都看不到也不会重连；所以出错必须把连接关掉。
                try:
                    while True:
                        ev = await queue.get()
                        await ws.send_json(ev)
                        if ev.get("type") == "chat_deleted":
                            await ws.close(code=4404)
                            return
                except (asyncio.CancelledError, WebSocketDisconnect):
                    raise
                except Exception:  # noqa: BLE001
                    log.exception("ws pump 异常，关闭连接：chat=%s", chat_id)
                    try:
                        await ws.close(code=1011)
                    except Exception:  # noqa: BLE001
                        pass

            return asyncio.create_task(pump())

        pump_task = start_pump(q)
        try:
            while True:
                msg = await ws.receive_json()
                t = msg.get("type")
                if t == "prompt":
                    ok, why = await runner.submit(str(msg.get("text", "")))
                    if not ok and runner.closing:
                        # 对话正在被池回收：换一个新 runner，把订阅迁过去，重试一次再报结果
                        old = runner
                        runner = await st.pool.get(name, chat_id)
                        old.unsubscribe(q)
                        q = runner.subscribe()
                        pump_task.cancel()
                        await asyncio.gather(pump_task, return_exceptions=True)
                        pump_task = start_pump(q)
                        ok, why = await runner.submit(str(msg.get("text", "")))
                    await ws.send_json({"type": "accepted"} if ok else {"type": "rejected", "reason": why})
                elif t == "confirm_reply":
                    await runner.confirm_reply(str(msg.get("id", "")), bool(msg.get("ok")))
                elif t == "interrupt":
                    await runner.interrupt()
                elif t == "ping":
                    await ws.send_json({"type": "pong"})
        finally:
            if pump_task is not None:
                pump_task.cancel()
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        try:
            await ws.close(code=1011)
        except Exception:
            pass
    finally:
        if runner is not None and q is not None:
            runner.unsubscribe(q)
