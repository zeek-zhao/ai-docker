#!/usr/bin/env bash
# =============================================================================
# pack.sh —— 密文 + 清单 + 还原脚本打包为单一发布包（PLAN §8.3，SC-004，本地执行）
# 产物：secrets/devbox-secrets.tar.age（整包 age 加密，可分发/入库）
# =============================================================================
set -euo pipefail

cd "$(dirname "$0")/.."
PUB=secrets/key.pub
OUT=secrets/devbox-secrets.tar.age

need() { command -v "$1" >/dev/null 2>&1 || { echo "[pack] 缺少依赖: $1"; exit 1; }; }
need age; need tar

[ -f "$PUB" ] || { echo "[pack] 公钥不存在（先运行 age-keygen.sh）: $PUB"; exit 1; }

LIST=$(ls secrets/*.age 2>/dev/null | grep -v devbox-secrets || true)
if [ -z "$LIST" ]; then
  echo "[pack] secrets/ 下没有可打包的密文（先运行 encrypt.sh）"
  exit 1
fi

# shellcheck disable=SC2086
tar -czf - secrets/manifest.json $LIST secrets/key.pub scripts/decrypt.sh scripts/restore.sh \
  | age -R "$PUB" -o "$OUT"

echo "[pack] 发布包: $OUT"
echo "  内含: manifest.json + $(echo "$LIST" | wc -l) 个密文 + key.pub + decrypt.sh/restore.sh"
echo "  使用: 挂载解包目录为 /secrets-pkg（ro）+ /secrets/key.txt 私钥，entrypoint 自动还原"
