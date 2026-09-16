"""读取 config.yaml 与 .env，并清理会干扰 API 路由的继承环境变量。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import dotenv_values

# 从用户 shell 继承下来、会把 API 请求导向第三方中转站或别的代理的变量
POISON_ENV_VARS = (
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_AUTH_TOKEN",
    "http_proxy",
    "https_proxy",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "all_proxy",
    "ALL_PROXY",
)


@dataclass
class ProxySettings:
    enabled: bool = True
    port: int = 17890
    controller_port: int = 19090
    stop_on_exit: bool = True
    domains: list[str] = field(default_factory=lambda: ["anthropic.com", "claude.ai"])

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"


@dataclass
class MemorySettings:
    enabled: bool = True
    auto_summarize: bool = True   # /quit、/new 时自动把本次会话要点合并进记忆
    max_chars: int = 4000         # 记忆文件长度上限（注入 system prompt，太长费钱）


@dataclass
class BiomniSettings:
    enabled: bool = True
    modules: list[str] = field(default_factory=list)          # 可用（已安装）的全部模块
    default_modules: list[str] = field(default_factory=list)  # 新对话默认加载的模块（空 = 全部）
    all_modules: list[str] = field(default_factory=list)      # 运行时：可用模块全集（modules 会被替换成本对话的选择）
    python: Path = Path()
    server: Path = Path()


USER_NAME_RE = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$"


@dataclass
class Settings:
    root: Path
    assistant_name: str
    model: str
    cwd: Path
    readonly_dirs: list[Path]
    daily_cost_cap_usd: float
    api_key: str
    proxy: ProxySettings
    biomni: BiomniSettings
    memory: MemorySettings = field(default_factory=MemorySettings)
    context_limit_tokens: int = 1_000_000  # 单个对话的上下文上限；状态条分母，达到后拒绝继续、提示开新对话
    extra_mcp: list = field(default_factory=list)  # 额外的 MCP 工具服务器（config.yaml 的 mcp_servers 列表：name/command/args/env/enabled）
    user: str = ""  # 使用者名字（--user），会话索引、输入历史、输出目录、记忆都按它隔离

    @property
    def users_root(self) -> Path:
        from .store import users_root
        return users_root(self.root)

    @property
    def user_dir(self) -> Path:
        return self.users_root / self.user if self.user else self.users_root

    @property
    def store(self):
        from .store import UserStore
        return UserStore(self.root, self.user)

    # 兼容旧名字：会话相关文件（历史、用量、stderr 日志）都在使用者目录下
    @property
    def sessions_dir(self) -> Path:
        return self.user_dir

    @property
    def workspace_dir(self) -> Path:
        """助理产物目录 = 当前工作目录（终端版每个对话指向 chats/<id>/outputs）。"""
        return self.cwd

    @property
    def memory_file(self) -> Path:
        return self.user_dir / "memory.md"

    def other_users_dirs(self) -> list[Path]:
        """其他使用者的目录 users/<x>，agent 不得访问。"""
        from .store import other_user_dirs
        return other_user_dirs(self.root, self.user) if self.user else []

    @property
    def proxy_dir(self) -> Path:
        return self.root / "proxy"

    @property
    def secrets_dir(self) -> Path:
        return secrets_dir()


def secrets_dir() -> Path:
    """密钥目录。项目盘（Fdisk）是 fuseblk 挂载，chmod 无效，所以密钥必须放在 home 下。"""
    return Path(os.environ.get("BIOAGENT_SECRETS_DIR", "~/.config/bioagent")).expanduser()


def validate_user(name: str) -> str:
    """--user 的取值：字母数字开头，只含字母、数字、下划线、连字符，最长 32。"""
    import re

    name = (name or "").strip()
    if not re.match(USER_NAME_RE, name):
        raise ValueError("用户名只能包含字母、数字、下划线、连字符，且以字母或数字开头（最长 32 字符）")
    return name


def scrub_environment() -> list[str]:
    """删除会干扰路由的环境变量，返回被删除的变量名。"""
    removed = [k for k in POISON_ENV_VARS if k in os.environ]
    for k in removed:
        os.environ.pop(k, None)
    return removed


def load_settings(root: Path) -> Settings:
    root = Path(root).resolve()
    raw = yaml.safe_load((root / "config.yaml").read_text()) or {}
    # 优先 ~/.config/bioagent/.env（权限可控），其次项目目录 .env
    candidates = [secrets_dir() / ".env", root / ".env"]
    env: dict = {}
    for env_file in candidates:
        if env_file.exists():
            env = dotenv_values(env_file)
            break
    api_key = env.get("ANTHROPIC_API_KEY") or ""
    if not api_key:
        raise RuntimeError(f"ANTHROPIC_API_KEY 未设置，请写入 {candidates[0]}")
    p = raw.get("proxy") or {}
    b = raw.get("biomni") or {}
    m = raw.get("memory") or {}
    return Settings(
        root=root,
        assistant_name=raw.get("assistant_name", "BioAgent"),
        model=raw.get("model", "claude-sonnet-5"),
        cwd=Path(raw.get("cwd", str(root))).expanduser(),
        readonly_dirs=[Path(d).expanduser() for d in raw.get("readonly_dirs", [])],
        daily_cost_cap_usd=float(raw.get("daily_cost_cap_usd", 20)),
        context_limit_tokens=int(raw.get("context_limit_tokens", 1_000_000)),
        api_key=api_key,
        proxy=ProxySettings(
            enabled=bool(p.get("enabled", True)),
            port=int(p.get("port", 17890)),
            controller_port=int(p.get("controller_port", 19090)),
            stop_on_exit=bool(p.get("stop_on_exit", True)),
            domains=list(p.get("domains", ["anthropic.com", "claude.ai"])),
        ),
        biomni=BiomniSettings(
            enabled=bool(b.get("enabled", True)),
            modules=list(b.get("modules", [])),
            default_modules=list(b.get("default_modules", [])),
            python=root / "biomni" / ".venv" / "bin" / "python",
            server=root / "biomni" / "mcp_server.py",
        ),
        extra_mcp=[dict(x) for x in (raw.get("mcp_servers") or []) if isinstance(x, dict) and x.get("name") and x.get("command")],
        memory=MemorySettings(
            enabled=bool(m.get("enabled", True)),
            auto_summarize=bool(m.get("auto_summarize", True)),
            max_chars=int(m.get("max_chars", 4000)),
        ),
    )
