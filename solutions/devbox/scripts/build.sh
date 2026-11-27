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

echo "[build] target=${TARGET} tag=${TAG}"
# 镜像源类构建参数经 --build-arg 覆盖，示例:
#   --build-arg APT_MIRROR=mirrors.tuna.tsinghua.edu.cn \
#   --build-arg GH_PROXY=https://ghproxy.net/ \
#   --build-arg BASE_IMAGE=docker.m.daocloud.io/library/ubuntu:24.04
docker build --target "${TARGET}" -t "${TAG}" "$@" .
echo "[build] done: ${TAG}"
