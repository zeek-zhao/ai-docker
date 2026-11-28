#!/usr/bin/env bash
# =============================================================================
# tests/run-tests.sh —— DevBox Bats 冒烟测试入口（BTS-001）
# 用法：./tests/run-tests.sh [容器名]        # 默认 devbox
#   SMOKE_HOST=10.0.0.5 WEB_PORT=9090 ./tests/run-tests.sh devbox
# 原理：把 tests/ 只读挂载进容器，用镜像内置 bats 执行（需容器重建一次以获得 bats）。
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

CNAME="${1:-devbox}"
HOST="${SMOKE_HOST:-127.0.0.1}"
PORT="${WEB_PORT:-8080}"

docker exec "${CNAME}" mkdir -p /tests
docker cp tests/smoke.bats "${CNAME}":/tests/smoke.bats
docker exec \
  -e SMOKE_HOST="${HOST}" -e WEB_PORT="${PORT}" \
  "${CNAME}" bats /tests/smoke.bats
