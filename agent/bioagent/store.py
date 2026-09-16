"""按人目录布局 users/<账号>/，终端版与网页版共用。

users/<账号>/
├── files/            上传区（.uploads/ 放分块上传的临时文件）
├── chats/<id>/       每次对话一个目录（见 chats.py）
├── memory.md         长期记忆
├── usage.jsonl       用量
├── .history          终端输入历史
├── settings.yaml     个人设置（model）
└── cli-stderr.log    Claude CLI 子进程日志
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

USERS_DIRNAME = "users"


def users_root(root: Path) -> Path:
    return Path(root) / USERS_DIRNAME


@dataclass(frozen=True)
class UserStore:
    root: Path
    user: str

    @property
    def dir(self) -> Path:
        return users_root(self.root) / self.user

    @property
    def files_dir(self) -> Path:
        return self.dir / "files"

    @property
    def uploads_dir(self) -> Path:
        return self.files_dir / ".uploads"

    @property
    def chats_dir(self) -> Path:
        return self.dir / "chats"

    @property
    def memory_file(self) -> Path:
        return self.dir / "memory.md"

    @property
    def usage_file(self) -> Path:
        return self.dir / "usage.jsonl"

    @property
    def history_file(self) -> Path:
        return self.dir / ".history"

    @property
    def settings_file(self) -> Path:
        return self.dir / "settings.yaml"

    @property
    def stderr_log(self) -> Path:
        return self.dir / "cli-stderr.log"

    def ensure(self) -> "UserStore":
        self.files_dir.mkdir(parents=True, exist_ok=True)
        self.chats_dir.mkdir(parents=True, exist_ok=True)
        return self

    def read_settings(self) -> dict:
        if not self.settings_file.exists():
            return {}
        try:
            data = yaml.safe_load(self.settings_file.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            return {}
        return data if isinstance(data, dict) else {}

    def write_settings(self, data: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.settings_file.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=True), encoding="utf-8")


def safe_join(base: Path, rel: str) -> Path:
    """把用户给的相对路径拼到 base 下；任何形式的越界（..、绝对路径跳出）都抛 ValueError。"""
    base = Path(base)
    rel = (rel or "").strip().lstrip("/")
    target = (base / rel) if rel else base
    # 不 resolve 符号链接目标之外的东西：用 normpath 处理 .. 再做前缀判断
    norm = Path(os.path.normpath(str(target)))
    base_norm = Path(os.path.normpath(str(base)))
    if norm != base_norm and base_norm not in norm.parents:
        raise ValueError("路径越界")
    # 检查symlink攻击：在已resolve的路径上进行包含检查
    base_res = Path(base).resolve()
    target_res = norm.resolve(strict=False)  # strict=False: 不存在的目标尽可能往上resolve
    if target_res != base_res and base_res not in target_res.parents:
        raise ValueError("路径越界")
    return norm


def list_users(root: Path) -> list[str]:
    ur = users_root(root)
    if not ur.is_dir():
        return []
    return sorted(p.name for p in ur.iterdir() if p.is_dir() and not p.name.startswith("."))


def other_user_dirs(root: Path, user: str) -> list[Path]:
    return [users_root(root) / u for u in list_users(root) if u != user]


def dir_size(path: Path) -> int:
    total = 0
    if not Path(path).exists():
        return 0
    for dirpath, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.lstat(os.path.join(dirpath, f)).st_size
            except OSError:
                continue
    return total
