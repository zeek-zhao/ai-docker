#!/usr/bin/env bash
# =============================================================================
# upgrade.sh —— DevBox 运行期一键升级（TD-009/T13.7/D34）
# 文档编号：RT-003 · 版本：v1.0 · 2026-11-28 · 维护人：zeek.zhao
# 通道：Tailscale（pkgs.tailscale.com stable）/ DSH（npm dist-tag latest）
#       / Magpie（yetone/magpie GitHub release）/ DSH 插件（plugin-version-match.sh
#       按 DSH 新版本自动匹配重装）。镜像级升级仍走 CI 构建期 auto-latest。
# 用法：upgrade.sh [--check]   # --check 只探测版本不执行
# 注意：需容器可出外网；升级 dsh/magpie 后自动重启对应服务（不中断 Caddy/网关）
# =============================================================================
set -uo pipefail

TS_API='https://pkgs.tailscale.com/stable/?mode=json'
MAGPIE_REPO='yetone/magpie'
NODE_BIN_DIR="$(ls -d /opt/nvm/versions/node/*/bin 2>/dev/null | sort -V | tail -1)"
PROFILES_HOME="${HOME:-/home/dev}"
WEB_PROFILE="${PROFILES_HOME}/.dsh/profiles/web"
MATCH_TOOL="/usr/local/share/devbox/tools/plugin-version-match.sh"
CHECK_ONLY=0
[ "${1:-}" = "--check" ] && CHECK_ONLY=1

log() { printf '[upgrade] %s\n' "$*"; }
warn() { printf '[upgrade][warn] %s\n' "$*" >&2; }

# R21：dsh/npm 都在 NVM bin（env node 需要 PATH），统一注入
export PATH="${NODE_BIN_DIR}:${PATH}"
DSH_NPM_PKG='@deepseek-ai/dsh'

# ---------- 版本探测 ----------
cur_tailscale="$(tailscale version 2>/dev/null | head -1 || echo unknown)"
cur_dsh="$("$NODE_BIN_DIR/dsh" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+[^ ]*' | head -1 || echo unknown)"
cur_magpie="$(magpie version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || magpie --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | head -1 || echo unknown)"

new_tailscale="$(curl -fsSL "$TS_API" 2>/dev/null | grep -o '"Version": *"[^"]*"' | head -1 | cut -d'"' -f4 || true)"
new_dsh="$(npm view ${DSH_NPM_PKG} dist-tags.latest 2>/dev/null || true)"
new_magpie="$(curl -fsSL "https://api.github.com/repos/${MAGPIE_REPO}/releases/latest" 2>/dev/null | grep -o '"tag_name": *"[^"]*"' | head -1 | cut -d'"' -f4 || true)"

log "当前版本: tailscale=${cur_tailscale} dsh=${cur_dsh} magpie=${cur_magpie}"
log "最新版本: tailscale=${new_tailscale:-探测失败} dsh=${new_dsh:-探测失败} magpie=${new_magpie:-探测失败}"
[ "$CHECK_ONLY" = "1" ] && exit 0

# ---------- 1) Tailscale（官方自带 update；无则跳过提示走镜像升级） ----------
if [ -n "$new_tailscale" ] && [ "$new_tailscale" != "$cur_tailscale" ]; then
  if tailscale update 2>/dev/null; then
    log "Tailscale 已升级 → $(tailscale version 2>/dev/null | head -1)"
  else
    warn "tailscale update 不可用（容器用户态安装形态），走镜像级升级：CI 构建 TAILSCALE_VERSION=auto"
  fi
else
  log "Tailscale 已是最新"
fi

# ---------- 2) DSH（npm 全局升级） ----------
if [ -n "$new_dsh" ] && [ -n "$NODE_BIN_DIR" ] && [ "$new_dsh" != "$cur_dsh" ]; then
  if npm install -g ${DSH_NPM_PKG}@latest >/dev/null 2>&1; then
    log "DSH 已升级 → $("$NODE_BIN_DIR/dsh" --version 2>/dev/null | head -1)"
    DSH_UPGRADED=1
  else
    warn "DSH npm 升级失败，保留旧版本"
  fi
else
  log "DSH 已是最新（或探测失败）"
fi

# ---------- 3) Magpie（GitHub release 二进制替换） ----------
if [ -n "$new_magpie" ] && [ "$new_magpie" != "$cur_magpie" ]; then
  if curl -fsSL -o /tmp/magpie.new \
      "https://github.com/${MAGPIE_REPO}/releases/download/${new_magpie}/magpie-cli-linux-amd64" \
     && chmod +x /tmp/magpie.new && mv /tmp/magpie.new /usr/local/bin/magpie 2>/dev/null; then
    log "Magpie 已升级 → ${new_magpie}"
    MAGPIE_UPGRADED=1
  else
    warn "Magpie 下载/替换失败（可能需 root），保留旧版本"
  fi
else
  log "Magpie 已是最新（或探测失败）"
fi

# ---------- 4) DSH 插件自动匹配升级（plugin-version-match.sh 按新 DSH 版本） ----------
if [ -f "$MATCH_TOOL" ] && [ -f "${WEB_PROFILE}/package.json" ] && [ -n "$new_dsh" ]; then
  log "开始插件版本自动匹配（目标 DSH=${new_dsh}）"
  TMP_PK="${WEB_PROFILE}/package.json.upgrade"
  cp "${WEB_PROFILE}/package.json" "$TMP_PK"
  for PKG in $(python3 -c "import json;print('\n'.join(json.load(open('${WEB_PROFILE}/package.json'))['dependencies'].keys()))" 2>/dev/null); do
    BEST="$("$MATCH_TOOL" "$PKG" --dsh "$new_dsh" 2>/dev/null | grep -oE '推荐[:：] *[^ ]+' | awk '{print $2}' | tail -1)"
    [ -z "$BEST" ] && BEST="$("$MATCH_TOOL" "$PKG" --dsh "$new_dsh" --json 2>/dev/null | python3 -c "import json,sys;print(json.load(sys.stdin).get('recommended',''))" 2>/dev/null)"
    if [ -n "$BEST" ] && [ "$BEST" != "none" ]; then
      python3 - "$TMP_PK" "$PKG" "$BEST" <<'EOF'
import json,sys
p,k,v=sys.argv[1],sys.argv[2],sys.argv[3]
d=json.load(open(p)); d['dependencies'][k]=v
json.dump(d,open(p,'w'),indent=2,ensure_ascii=False)
EOF
      log "  插件 ${PKG} → ${BEST}"
    else
      log "  插件 ${PKG} 无兼容版本，保留现值"
    fi
  done
  mv "$TMP_PK" "${WEB_PROFILE}/package.json"
  if command -v pnpm >/dev/null 2>&1 || [ -x "$NODE_BIN_DIR/pnpm" ]; then
    (cd "$WEB_PROFILE" && PATH="$NODE_BIN_DIR:$PATH" pnpm install --prefer-offline >/dev/null 2>&1) \
      && log "插件依赖安装完成" || warn "pnpm install 失败，插件依赖未更新"
  fi
else
  warn "跳过插件匹配（缺 ${MATCH_TOOL} 或 web profile 或 DSH 版本探测失败）"
fi

# ---------- 5) 服务重启（dsh/magpie 后台进程；Caddy/网关不动） ----------
RESTART_NOTE=""
if [ "${DSH_UPGRADED:-0}" = "1" ]; then
  PID="$(pgrep -f 'dsh web' | head -1)"; [ -n "$PID" ] && kill "$PID" 2>/dev/null && RESTART_NOTE="${RESTART_NOTE} dsh"
  (cd "$PROFILES_HOME" && PATH="$NODE_BIN_DIR:/usr/local/bin:/usr/bin:/bin" \
    DSH_PUBLIC_URL="${DSH_PUBLIC_URL:-http://127.0.0.1:8080/dsh/}" \
    sh -c 'exec dsh web --host 127.0.0.1 --port 3081 --no-open --public-url "$DSH_PUBLIC_URL" --trusted-host "$(printf "%s" "$DSH_PUBLIC_URL" | sed -E "s|^.https?://([^/]+).*|\1|")" >>/tmp/dsh-web.log 2>&1' &) || warn "dsh 重启失败（查看 /tmp/dsh-web.log）"
fi
if [ "${MAGPIE_UPGRADED:-0}" = "1" ]; then
  PID="$(pgrep -f 'magpie web' | head -1)"; [ -n "$PID" ] && kill "$PID" 2>/dev/null && RESTART_NOTE="${RESTART_NOTE} magpie"
  (cd "$PROFILES_HOME" && MAGPIE_WEB_KEY="${MAGPIE_WEB_KEY:-devbox-magpie-key}" MAGPIE_WEB_URL="${MAGPIE_WEB_URL:-http://127.0.0.1:8080/magpie/}" MAGPIE_TRUST_PROXY=1 \
    sh -c 'exec magpie web --addr 127.0.0.1:3430 --no-open --gateway >>/tmp/magpie-web.log 2>&1' &) || warn "magpie 重启失败（查看 /tmp/magpie-web.log）"
fi
[ -n "$RESTART_NOTE" ] && log "已重启服务:${RESTART_NOTE}（token 链接如有变化见 /run/devbox/dsh/url.txt）"
log "升级流程结束"
