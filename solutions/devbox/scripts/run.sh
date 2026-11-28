#!/usr/bin/env bash
# =============================================================================
# run.sh —— devbox 启动/挂载/端口映射示例（参数化，等价 PLAN §10.2）
# 文档编号：SC-002 · 版本：v1.0 · 2026-11-27 · 维护人：zeek.zhao
# 用法: ./scripts/run.sh           # 默认参数启动
#       NAME=x WEB_PORT=9090 ./scripts/run.sh
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

NAME="${NAME:-zeek-devbox}"
IMAGE="${IMAGE:-devbox:latest}"
WEB_PORT="${WEB_PORT:-8080}"
SSH_PORT="${SSH_PORT:-2222}"

mkdir -p data secrets

# 可选挂载自动探测：存在才挂，避免误报
DOCKER_ARGS=()
[ -f secrets/key.txt ] && DOCKER_ARGS+=(-v "$(pwd)/secrets/key.txt:/secrets/key.txt:ro")
if [ "${MOUNT_DOCKER_SOCK:-0}" = "1" ]; then
  # 警示：只读挂载仍有提权面，仅可信环境开启（PLAN §12.2）
  DOCKER_ARGS+=(-v /var/run/docker.sock:/var/run/docker.sock:ro)
fi

docker rm -f "${NAME}" >/dev/null 2>&1 || true

docker run -d \
  --name "${NAME}" \
  -p "${WEB_PORT}:8080" \
  -p "${SSH_PORT}:22" \
  -e HOST_UID="$(id -u)" \
  -e HOST_GID="$(id -g)" \
  -v "$(pwd)/data:/home/dev/data" \
  "${DOCKER_ARGS[@]}" \
  "${IMAGE}"

echo "[run] ${NAME} started"
echo "  Web : http://localhost:${WEB_PORT}/   (dev / 123 —— 本地测试弱密码，公网必改)"
echo "  SSH : ssh -p ${SSH_PORT} dev@localhost"
