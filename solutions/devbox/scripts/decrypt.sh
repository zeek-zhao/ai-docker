#!/usr/bin/env bash
# =============================================================================
# decrypt.sh —— 容器内按 manifest 解密还原（PLAN §8.3，SC-005）
# 支持：目录条目（tar+age）/ 文件条目（age）、dry-run、越权路径拒绝、权限修复
# =============================================================================
set -euo pipefail

usage() { echo "用法: decrypt.sh [--key FILE] [--manifest FILE] [--home-root DIR] [--encrypted-root DIR] [--owner USER:GROUP] [--dry-run]"; exit 2; }

KEY=/secrets/key.txt
MANIFEST=/usr/local/share/devbox/manifest.json
HOME_ROOT=/home/dev
ENC_ROOT=""
OWNER=""
DRY_RUN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --key) KEY="$2"; shift 2;;
    --manifest) MANIFEST="$2"; shift 2;;
    --home-root) HOME_ROOT="$2"; shift 2;;
    --encrypted-root) ENC_ROOT="$2"; shift 2;;
    --owner) OWNER="$2"; shift 2;;
    --dry-run) DRY_RUN=1; shift;;
    *) usage;;
  esac
done

need() { command -v "$1" >/dev/null 2>&1 || { echo "[decrypt] 缺少依赖: $1"; exit 1; }; }
need jq; need age; need tar

[ -f "$KEY" ] || { echo "[decrypt] 私钥不存在: $KEY"; exit 1; }
[ -f "$MANIFEST" ] || { echo "[decrypt] 清单不存在: $MANIFEST"; exit 1; }
ENC_DIR="${ENC_ROOT:-$(dirname "$MANIFEST")}"

resolve() { echo "${1/#\~/$HOME_ROOT}"; }   # ~ 展开到开发用户家目录

safe_target() { case "$1" in ..*|*/..*|"") return 1 ;; esac; return 0; }

fail=0
while IFS= read -r e; do
  etype=$(jq -r '.type' <<<"$e")
  enc=$(jq -r '.encrypted' <<<"$e")
  target=$(resolve "$(jq -r '.target' <<<"$e")")
  mode=$(jq -r '.mode // ""' <<<"$e")
  if [ ! -f "$ENC_DIR/$enc" ]; then echo "[decrypt] 缺少密文: $ENC_DIR/$enc（跳过）"; fail=1; continue; fi
  if ! safe_target "$target"; then echo "[decrypt] 拒绝越权路径: $target（跳过）"; fail=1; continue; fi
  if [ "$DRY_RUN" = "1" ]; then
    echo "[decrypt][dry-run] $etype $enc → $target (mode=${mode:-默认})"
    continue
  fi
  mkdir -p "$(dirname "$target")"
  if [ "$etype" = "dir" ]; then
    mkdir -p "$target"
    age -d -i "$KEY" "$ENC_DIR/$enc" | tar -xzf - -C "$target"
  else
    age -d -i "$KEY" "$ENC_DIR/$enc" > "$target"
  fi
  [ -n "$mode" ] && chmod "$mode" "$target"
  if [ -n "$OWNER" ]; then chown -R "$OWNER" "$target" 2>/dev/null || true; fi
  echo "[decrypt] 已还原: $etype $enc → $target"
done < <(jq -c '.entries[]' "$MANIFEST")

exit "$fail"
