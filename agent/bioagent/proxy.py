"""bioagent 私有代理：随 bioagent 启停，只监听本机高位端口，不影响服务器上的其他代理。

设计要点
- mihomo 二进制、配置、pid、日志全部在 bioagent/proxy/ 下，用目录做身份，不会误伤别的 mihomo/clash。
- 不开 TUN、不开 DNS 监听、不改系统代理；代理地址只通过 ProxyManager.env 注入给子进程。
- 引用计数：proxy/run/sessions/<pid> 每个 bioagent 会话一个文件，最后一个退出时才停代理。
"""
from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

import httpx


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, ValueError, OverflowError):
        return False
    except PermissionError:
        return True
    return True


def stale_session_files(run_sessions: Path) -> list[Path]:
    """返回对应进程已不存在（或文件名不是 pid）的会话标记文件。"""
    out: list[Path] = []
    for p in run_sessions.glob("*"):
        try:
            if not pid_alive(int(p.name)):
                out.append(p)
        except ValueError:
            out.append(p)
    return out


def render_proxy_config(nodes: dict, *, port: int, controller_port: int, domains: list[str]) -> dict:
    """由节点列表生成最小 mihomo 配置：只有指定域名走代理，其余直连。"""
    proxies = nodes["proxies"]
    names = [p["name"] for p in proxies]
    return {
        "mixed-port": port,
        "bind-address": "127.0.0.1",
        "allow-lan": False,
        "mode": "rule",
        "log-level": "warning",
        "ipv6": False,
        "external-controller": f"127.0.0.1:{controller_port}",
        "proxies": proxies,
        "proxy-groups": [
            {"name": "PROXY", "type": "select", "proxies": ["AUTO", *names]},
            {
                "name": "AUTO",
                "type": "url-test",
                "url": "https://www.gstatic.com/generate_204",
                "interval": 300,
                "tolerance": 100,
                "proxies": names,
            },
        ],
        "rules": [f"DOMAIN-SUFFIX,{d},PROXY" for d in domains] + ["MATCH,DIRECT"],
    }


class ProxyManager:
    def __init__(self, settings):
        self.s = settings.proxy
        self.dir: Path = settings.proxy_dir
        self.api_key: str = settings.api_key
        self.run = self.dir / "run"
        self.sessions = self.run / "sessions"
        self.pidfile = self.run / "mihomo.pid"
        self.logfile = self.run / "mihomo.log"
        self.binary = self.dir / "mihomo"
        # 含节点密钥的配置放在 home 下的密钥目录（项目盘 chmod 无效）
        self.config_file: Path = settings.secrets_dir / "mihomo.yaml"
        self.started_by_us = False
        self.sessions.mkdir(parents=True, exist_ok=True)

    # ---- 注入给子进程的环境 ----
    @property
    def env(self) -> dict[str, str]:
        return {"HTTP_PROXY": self.s.url, "HTTPS_PROXY": self.s.url, "NO_PROXY": "localhost,127.0.0.1"}

    # ---- 控制口 ----
    def _ctl(self, path: str, timeout: float = 3.0) -> httpx.Response:
        return httpx.get(f"http://127.0.0.1:{self.s.controller_port}{path}", timeout=timeout)

    def is_alive(self) -> bool:
        try:
            return self._ctl("/version").status_code == 200
        except httpx.HTTPError:
            return False

    # ---- 生命周期 ----
    def ensure_running(self) -> bool:
        """确保代理在跑。返回 True 表示本次由我们拉起。"""
        if self.is_alive():
            return False
        if self.pidfile.exists():
            try:
                old = int(self.pidfile.read_text().strip())
                if pid_alive(old):
                    os.kill(old, signal.SIGTERM)
                    time.sleep(1)
            except ValueError:
                pass
            self.pidfile.unlink(missing_ok=True)
        if not self.binary.exists():
            raise RuntimeError(f"缺少代理程序 {self.binary}，请先运行 install.sh")
        if not self.config_file.exists():
            raise RuntimeError(f"缺少 {self.config_file}，请运行 scripts/gen_proxy_config.py")
        with open(self.logfile, "ab") as log:
            proc = subprocess.Popen(
                [str(self.binary), "-d", str(self.dir), "-f", str(self.config_file)],
                stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True,
            )
        self.pidfile.write_text(str(proc.pid))
        for _ in range(60):
            if self.is_alive():
                self.started_by_us = True
                return True
            time.sleep(0.25)
        raise RuntimeError(f"代理 15 秒内未就绪，日志见 {self.logfile}")

    def health_check(self, attempts: int = 4) -> tuple[bool, str]:
        """经代理访问 Anthropic API，验证网络与 Key。

        代理刚启动时 url-test 分组还没测完，首个请求可能落在坏节点上（SSL EOF），
        所以失败后等几秒重试，给自动选路留时间。
        """
        last = ""
        for i in range(attempts):
            try:
                r = httpx.get(
                    "https://api.anthropic.com/v1/models",
                    proxy=self.s.url,
                    timeout=15,
                    headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
                )
                if r.status_code == 200:
                    return True, "ok"
                if r.status_code in (401, 403):
                    return False, f"API 返回 {r.status_code}: {r.text[:120]}"
                last = f"API 返回 {r.status_code}: {r.text[:120]}"
            except httpx.HTTPError as e:
                last = f"经代理访问 API 失败：{e!r}"
            if i < attempts - 1:
                time.sleep(3 + 2 * i)
        return False, last

    def node_delays(self) -> dict[str, int | None]:
        out: dict[str, int | None] = {}
        try:
            names = self._ctl("/proxies/AUTO").json().get("all", [])
        except Exception:
            return out
        for n in names:
            try:
                r = self._ctl(
                    f"/proxies/{n}/delay?timeout=5000&url=https://www.gstatic.com/generate_204", timeout=8
                )
                out[n] = r.json().get("delay") if r.status_code == 200 else None
            except Exception:
                out[n] = None
        return out

    def register_session(self) -> None:
        for p in stale_session_files(self.sessions):
            p.unlink(missing_ok=True)
        (self.sessions / str(os.getpid())).write_text("")

    def unregister_session_and_maybe_stop(self) -> None:
        (self.sessions / str(os.getpid())).unlink(missing_ok=True)
        remaining = [p for p in self.sessions.glob("*") if p.name.isdigit() and pid_alive(int(p.name))]
        if not remaining and self.s.stop_on_exit:
            self.stop()

    def stop(self) -> None:
        if not self.pidfile.exists():
            return
        try:
            pid = int(self.pidfile.read_text().strip())
            if pid_alive(pid):
                os.kill(pid, signal.SIGTERM)
        except ValueError:
            pass
        self.pidfile.unlink(missing_ok=True)
