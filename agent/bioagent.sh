#!/bin/bash
# 启动 bioagent：使用项目自带 venv，不依赖用户 shell 环境
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 模型权重与下载缓存放项目目录下（工具首次运行会下载数 GB 权重；有的服务器系统盘很小）
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$HERE/.cache}"
export HF_HOME="${HF_HOME:-$HERE/.cache/huggingface}"
export TORCH_HOME="${TORCH_HOME:-$HERE/.cache/torch}"
exec "$HERE/.venv/bin/python" -m bioagent "$@"
