#!/usr/bin/env bash
# =============================================================================
# encrypt.sh —— 按 manifest 用公钥加密目录/文件（PLAN §8.3，SC-003，本地执行）
# 目录：tar 后 age 加密；文件：直接 age 加密；越权路径拒绝
# =============================================================================
set -euo pipefail

usage() { echo "用法: encrypt.sh [--manifest secrets/manifest.json] [--pubkey secrets/key.pub] [--root \$HOME] [--out-dir secrets]"; exit 2; }

cd "$(dirname "$0")/.."
MANIFEST=secrets/manifest.json
PUBKEY=secrets/key.pub
ROOT="${HOME}"
OUT=secrets
while [ $# -gt 0 ]; do
  case "$1" in
    --manifest) MANIFEST="$2"; shift 2;;
    --pubkey) PUBKEY="$2"; shift 2;;
    --root) ROOT="$2"; shift 2;;
    --out-dir) OUT="$2"; shift 2;;
    *) usage;;
  esac
done

need() { command -v "$1" >/dev/null 2>&1 || { echo "[encrypt] 缺少依赖: $1（apt install age jq）"; exit 1; }; }
need jq; need age; need tar
[ -f "$MANIFEST" ] || { echo "[encrypt] 清单不存在: $MANIFEST"; exit 1; }
[ -f "$PUBKEY" ] || { echo "[encrypt] 公钥不存在: $PUBKEY（先运行 age-keygen.sh）"; exit 1; }
mkdir -p "$OUT"

fail=0
while IFS= read -r e; do
  etype=$(jq -r '.type' <<<"$e")
  source=$(jq -r '.source' <<<"$e")
  enc=$(jq -r '.encrypted' <<<"$e")
  case "$source" in ..*) echo "[encrypt] 拒绝越权路径: $source（跳过）"; fail=1; continue;; esac
  src="$ROOT/${source#./}"
  if [ ! -e "$src" ]; then echo "[encrypt] 源不存在（跳过）: $src"; fail=1; continue; fi
  if [ "$DRY_RUN_QUIET" != "1" ]; then echo "[encrypt] $etype $source → $OUT/$enc"; fi
  if [ "$etype" = "dir" ]; then
    tar -C "$ROOT" -czf - "${source#./}" | age -R "$PUBKEY" -o "$OUT/$enc"
  else
    age -R "$PUBKEY" -o "$OUT/$enc" "$src"
  fi
done < <(jq -c '.entries[]' "$MANIFEST")

echo "[encrypt] 完成（产物位于 $OUT/，仅密文可入库）"
exit "$fail"
