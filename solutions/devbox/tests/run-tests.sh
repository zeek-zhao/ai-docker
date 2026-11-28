#!/usr/bin/env bash
# DevBox Bats 冒烟测试入口（BTS-001）：把用例拷进容器执行（bats 为镜像内置，位于 nvm node bin）
# 用法：./tests/run-tests.sh [容器名]     （默认 devbox；WEB_PORT 缺省 8080）
set -euo pipefail
C=${1:-devbox}
PORT=${WEB_PORT:-8080}
command -v docker >/dev/null || { echo "需要 docker"; exit 1; }
docker ps --format '{{.Names}}' | grep -qx "$C" || { echo "容器 $C 未运行"; exit 1; }
# /tests 可能残留为同名文件（早期误拷），先清理再建目录
docker exec "$C" sh -c 'rm -rf /tests && mkdir -p /tests'
docker cp "$(cd "$(dirname "$0")" && pwd)/smoke.bats" "$C:/tests/smoke.bats"
# bats 在 nvm node bin 下，exec 非登录 shell 需显式补 PATH
docker exec "$C" sh -c 'export PATH="$(ls -d /opt/nvm/versions/node/*/bin | head -1)":$PATH; export SMOKE_HOST=127.0.0.1 SMOKE_WEB_PORT='"$PORT"'; bats --tap /tests/smoke.bats'
