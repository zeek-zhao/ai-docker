#!/usr/bin/env bash
# =============================================================================
# restore.sh —— 封装「解密 + 按目录还原 + 权限修复」，供 entrypoint 调用（PLAN §8.3，SC-006）
# 清单探测顺序：/secrets-pkg（compose 推荐挂载点）→ /usr/local/share/devbox → /secrets
# 支持 --dry-run 与指定还原根目录透传
# =============================================================================
set -euo pipefail

KEY=/secrets/key.txt
MANIFEST=""
for cand in /secrets-pkg/manifest.json /usr/local/share/devbox/manifest.json /secrets/manifest.json; do
  if [ -f "$cand" ]; then MANIFEST="$cand"; break; fi
done
if [ -z "$MANIFEST" ]; then
  echo "[restore] 未找到 manifest.json（探测路径: /secrets-pkg /usr/local/share/devbox /secrets）"
  exit 1
fi
if [ ! -f "$KEY" ]; then
  echo "[restore] 未找到 age 私钥 /secrets/key.txt"
  exit 1
fi

echo "[restore] manifest=$MANIFEST owner=dev:dev"
exec /usr/local/bin/decrypt.sh \
  --key "$KEY" \
  --manifest "$MANIFEST" \
  --home-root /home/dev \
  --owner dev:dev "$@"
