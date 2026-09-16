"""python -m bioagent.web：启动网页服务（含 bioagent 私有代理）。"""
from __future__ import annotations

import argparse
import logging
import logging.handlers
import sys
from pathlib import Path

import uvicorn

from ..config import load_settings, scrub_environment
from ..proxy import ProxyManager
from .app import create_app

ROOT = Path(__file__).resolve().parents[2]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="bioagent.web")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=6006)
    ap.add_argument("--no-proxy", action="store_true", help="不启动私有代理（本机可直连 API 时）")
    args = ap.parse_args(argv)

    scrub_environment()
    s = load_settings(ROOT)
    logs = s.root / "logs"; logs.mkdir(exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(logs / "web.log", maxBytes=5 * 2**20, backupCount=3, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[handler, logging.StreamHandler(sys.stdout)])
    log = logging.getLogger("bioagent.web")

    proxy_env: dict = {}
    pm = None
    if s.proxy.enabled and not args.no_proxy:
        pm = ProxyManager(s)
        started = pm.ensure_running()
        ok, why = pm.health_check(attempts=8)  # 首次启动常卡在选路，多给几次机会
        if not ok:
            log.error("API 不可达：%s", why)
            pm.stop()
            return 2
        pm.register_session()
        proxy_env = pm.env
        log.info("代理就绪（%s），API 连通", "新启动" if started else "复用")

    app = create_app(s, proxy_env=proxy_env)
    log.info("BioAgent 网页版启动 http://%s:%d", args.host, args.port)
    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="info", proxy_headers=True, forwarded_allow_ips="127.0.0.1",
                    ws_ping_interval=20, ws_ping_timeout=20, timeout_keep_alive=75)
    finally:
        if pm:
            pm.unregister_session_and_maybe_stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
