#!/usr/bin/env bash
# =============================================================================
# age-keygen.sh —— 生成/校验 age 密钥对（PLAN §8.3，SC-007，本地一次性）
# 私钥 secrets/key.txt 仅本地保存（0600）；公钥 secrets/key.pub 可入库
# =============================================================================
set -euo pipefail

cd "$(dirname "$0")/.."
KEY=secrets/key.txt
PUB=secrets/key.pub

command -v age-keygen >/dev/null 2>&1 || { echo "[keygen] 缺少 age-keygen（apt install age）"; exit 1; }
mkdir -p secrets

if [ -f "$KEY" ]; then
  echo "[keygen] 私钥已存在: $KEY（不覆盖，校验并刷新公钥）"
  age-keygen -y "$KEY" > "$PUB"
else
  umask 177
  age-keygen -o "$KEY" 2>/dev/null | sed -n 's/^# public key: //p' > "$PUB" || true
  [ -s "$PUB" ] || age-keygen -y "$KEY" > "$PUB"
  chmod 600 "$KEY"
fi

echo "[keygen] 私钥: $KEY（严禁提交仓库/严禁打入镜像）"
echo "[keygen] 公钥: $PUB → $(cat "$PUB")"
