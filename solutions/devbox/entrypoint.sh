#!/usr/bin/env bash
# =============================================================================
# entrypoint.sh —— zeek-ai-devbox 启动入口（PLAN §7.2 六步序列）
# 文档编号：RT-001 · 版本：v1.0 · 2026-11-27 · 维护人：zeek.zhao
# 序列：1权限对齐 → 2密码 → 3age解密还原 → 4目录准备 → 5拉起服务 → 6Caddy前台守护
# =============================================================================
set -euo pipefail

DEV_USER="${DEV_USER:-dev}"
HOST_UID="${HOST_UID:-1000}"
HOST_GID="${HOST_GID:-1000}"
DEV_PASSWORD="${DEV_PASSWORD:-123}"
ROOT_PASSWORD="${ROOT_PASSWORD:-root}"
ENABLE_TAILSCALE="${ENABLE_TAILSCALE:-0}"
ENABLE_DSH="${ENABLE_DSH:-0}"
ENABLE_MAGPIE="${ENABLE_MAGPIE:-0}"
RUN_DIR=/run/devbox

log() { echo "[entrypoint] $*"; }

# ---------- 1) 对齐权限：开发用户 UID/GID 对齐本地（PLAN §7.2.1） ----------
mkdir -p "$RUN_DIR"
if ! getent group "$DEV_USER" >/dev/null 2>&1; then
  groupadd -g "$HOST_GID" "$DEV_USER"
fi
if id "$DEV_USER" >/dev/null 2>&1; then
  usermod -o -u "$HOST_UID" -g "$HOST_GID" -d "/home/$DEV_USER" -s /usr/bin/zsh "$DEV_USER"
else
  useradd -M -u "$HOST_UID" -g "$HOST_GID" -d "/home/$DEV_USER" -s /usr/bin/zsh "$DEV_USER"
  cp -a /etc/skel/. "/home/$DEV_USER/"
fi
echo "$DEV_USER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/dev
chmod 440 /etc/sudoers.d/dev
log "dev 用户就绪: uid=${HOST_UID} gid=${HOST_GID} shell=zsh"

# ---------- 2) 设置密码（PLAN §7.2.2，测试默认弱密码，公网必改） ----------
echo "$DEV_USER:$DEV_PASSWORD" | chpasswd
echo "root:$ROOT_PASSWORD" | chpasswd
log "密码已写入（dev/root）"

# ---------- 3) 解密还原配置（age + manifest，PLAN §7.2.3 / §8） ----------
if [ -f /secrets/key.txt ]; then
  if [ -x /usr/local/bin/restore.sh ]; then
    log "检测到 age 私钥，执行配置还原"
    /usr/local/bin/restore.sh || log "警告：配置还原失败，继续启动"
  else
    log "警告：缺少 /usr/local/bin/restore.sh，跳过还原"
  fi
else
  log "未提供 /secrets/key.txt，跳过配置还原"
fi

# ---------- 4) 准备目录（PLAN §7.2.4） ----------
mkdir -p "/home/$DEV_USER/data" "/home/$DEV_USER/.config" "/home/$DEV_USER/go" \
         /var/lib/devbox /var/lib/tailscale /var/run/sshd
chown -R "$DEV_USER:$DEV_USER" "/home/$DEV_USER"
log "目录就绪: /home/$DEV_USER/{data,.config,go}"

# ---------- 5) 拉起服务（PLAN §7.2.5） ----------

# 5.1 SSH（禁 root 直登）
cat > /etc/ssh/sshd_config.d/50-devbox.conf <<EOF
PasswordAuthentication yes
PermitRootLogin no
PrintMotd no
EOF
ssh-keygen -A >/dev/null
/usr/sbin/sshd
log "sshd 已启动（容器内 :22）"

# 5.2 auth-gate 统一会话鉴权（Cookie 签名密钥持久化，重启不失效）
SECRET_FILE=/var/lib/devbox/cookie-secret
if [ ! -s "$SECRET_FILE" ]; then
  openssl rand -hex 32 > "$SECRET_FILE"
  chmod 600 "$SECRET_FILE"
fi
AUTH_USER="$DEV_USER" AUTH_PASSWORD="$DEV_PASSWORD" \
SESSION_TTL_HOURS="${SESSION_TTL_HOURS:-168}" COOKIE_SECRET="$(cat "$SECRET_FILE")" \
LISTEN_ADDR=127.0.0.1:9090 /usr/local/bin/auth-gate &
log "auth-gate 已启动 (127.0.0.1:9090, 会话 ${SESSION_TTL_HOURS:-168}h)"

# 5.3 ttyd Web 终端（以 dev 身份，禁 root 会话，PLAN §6.1）
runuser -u "$DEV_USER" -- env HOME="/home/$DEV_USER" \
  /usr/local/bin/ttyd -b /term -p 7681 -W zsh -l &
log "ttyd 已启动 (127.0.0.1:7681, /term)"

# 5.4 filebrowser 文件共享（根目录绑定 devbox 数据目录，PLAN §6.2）
FB_DB_DIR="/home/$DEV_USER/.filebrowser"
FB_DB="$FB_DB_DIR/filebrowser.db"
mkdir -p "$FB_DB_DIR"
chown -R "$DEV_USER:$DEV_USER" "$FB_DB_DIR"
runuser -u "$DEV_USER" -- env HOME="/home/$DEV_USER" sh -c "\
  filebrowser -d '$FB_DB' config init >/dev/null 2>&1 || true; \
  filebrowser -d '$FB_DB' users add '$DEV_USER' '$DEV_PASSWORD' --perm.admin >/dev/null 2>&1 || \
  filebrowser -d '$FB_DB' users update '$DEV_USER' -p '$DEV_PASSWORD' >/dev/null 2>&1 || true"
runuser -u "$DEV_USER" -- env HOME="/home/$DEV_USER" \
  filebrowser -d "$FB_DB" -a 127.0.0.1 -p 8081 -b /file-share -r "/home/$DEV_USER/data" &
log "filebrowser 已启动 (127.0.0.1:8081, /file-share, root=/home/$DEV_USER/data)"

# 5.5 HomePage 导航首页（聚合全部对外服务入口，PLAN §6.1）
chown -R "$DEV_USER:$DEV_USER" /opt/homepage
NODE_BIN="$(bash -c '. /opt/nvm/nvm.sh >/dev/null 2>&1; command -v node')"
if [ -n "$NODE_BIN" ] && [ -f /opt/homepage/server.js ]; then
  runuser -u "$DEV_USER" -- env HOME="/home/$DEV_USER" \
    PATH="$(dirname "$NODE_BIN"):/usr/local/bin:/usr/bin:/bin" \
    PORT=3000 HOSTNAME=0.0.0.0 node /opt/homepage/server.js &
  log "HomePage 已启动 (127.0.0.1:3000, node=$(basename "$NODE_BIN"))"
else
  log "警告：node 或 /opt/homepage/server.js 缺失，HomePage 未启动"
fi

# 5.6 Tailscale（用户态模式，可选开关，PLAN §6.4）
if [ "$ENABLE_TAILSCALE" = "1" ]; then
  tailscaled --tun=userspace-networking \
    --statedir=/var/lib/tailscale --socket=/run/devbox/tailscaled.sock &
  sleep 1
  if [ -n "${TS_AUTHKEY:-}" ]; then
    tailscale --socket=/run/devbox/tailscaled.sock up \
      --authkey="${TS_AUTHKEY}" --hostname="${TS_HOSTNAME:-devbox}" || log "警告：tailscale up 失败"
  else
    log "提示：未提供 TS_AUTHKEY，tailscaled 已就绪待登录"
  fi
  log "tailscale 已启动（用户态模式）"
else
  log "tailscale 未启用（ENABLE_TAILSCALE=0）"
fi

# 5.7 DSH 远程桌面网关（预留路由 + 启停开关，PLAN §6.6；本体 3080 不对外）
if [ "$ENABLE_DSH" = "1" ]; then
  if [ -x /run/devbox/dsh/dsh ]; then
    mkdir -p "$RUN_DIR/dsh" && touch "$RUN_DIR/dsh/enabled"
    /run/devbox/dsh/dsh &
    log "DSH 已启动 (127.0.0.1:3081 网关)"
  else
    log "警告：ENABLE_DSH=1 但未注入可执行 /run/devbox/dsh/dsh，/dsh 将返回 503"
  fi
else
  log "DSH 未启用（ENABLE_DSH=0）"
fi

# 5.8 Magpie AI 网关面板（预留路由 + 启停开关，PLAN §6.6；网关 API 3425 不对外）
if [ "$ENABLE_MAGPIE" = "1" ]; then
  if [ -x /run/devbox/magpie/magpie ]; then
    mkdir -p "$RUN_DIR/magpie" && touch "$RUN_DIR/magpie/enabled"
    env MAGPIE_WEB_KEY="${MAGPIE_WEB_KEY:-}" MAGPIE_PORT="${MAGPIE_PORT:-3425}" \
      MAGPIE_WEB_PORT="${MAGPIE_WEB_PORT:-3430}" /run/devbox/magpie/magpie &
    log "Magpie 已启动 (面板 127.0.0.1:3430)"
  else
    log "警告：ENABLE_MAGPIE=1 但未注入可执行 /run/devbox/magpie/magpie，/magpie 将返回 503"
  fi
else
  log "Magpie 未启用（ENABLE_MAGPIE=0）"
fi

# ---------- 6) Caddy 单端口统一反代，前台守护（PLAN §7.2.5/7.2.6） ----------
log "Caddy 启动（对外 :8080，统一会话鉴权）"
exec /usr/local/bin/caddy run --config /etc/devbox/caddy/Caddyfile --adapter caddyfile
