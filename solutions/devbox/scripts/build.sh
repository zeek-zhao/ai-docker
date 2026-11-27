#!/usr/bin/env bash
# =============================================================================
# build.sh —— zeek-ai-devbox 分层构建脚本
# 文档编号：SC-001 · 版本：v1.0 · 2026-11-27 · 维护人：zeek.zhao
# 用法: TARGET=final TAG=zeek-ai-devbox:latest ./scripts/build.sh [--no-cache ...]
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

TARGET="${TARGET:-final}"          # 可选: base / toolchain-build / config / services / final
TAG="${TAG:-zeek-ai-devbox:latest}"

# ---- 企业网私有 CA 注入（Dockerfile base 阶段 1.5 步）-------------------------
# 宿主机出网被企业 TLS 网关重签时，容器内缺企业根 CA 会导致 apt/git/下载全链握手失败。
# 构建前把宿主机私有根证书复制进构建上下文 .buildctx/ca/（不入库、构建后即删）。
mkdir -p .buildctx/ca
if ls /usr/local/share/ca-certificates/*.crt >/dev/null 2>&1; then
  cp /usr/local/share/ca-certificates/*.crt .buildctx/ca/
  echo "[build] 注入宿主机私有 CA: $(ls .buildctx/ca/ | tr '\n' ' ')"
else
  : > .buildctx/ca/.gitkeep
  echo "[build] 未发现宿主机私有 CA，标准公网信任库"
fi
cleanup() { rm -rf .buildctx; }
trap cleanup EXIT

echo "[build] target=${TARGET} tag=${TAG}"
# 镜像源类构建参数经 --build-arg 覆盖，示例:
#   --build-arg APT_MIRROR=mirrors.tuna.tsinghua.edu.cn \
#   --build-arg GH_PROXY=https://ghproxy.net/ \
#   --build-arg BASE_IMAGE=docker.m.daocloud.io/library/ubuntu:24.04
docker build --target "${TARGET}" -t "${TAG}" "$@" .
echo "[build] done: ${TAG}"
