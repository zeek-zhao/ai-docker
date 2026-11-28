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
# 注：filebrowser 新版 CLI 拒绝弱密码（"too short"/"too easy"），测试密码 123 无法
# 经 users add 写入；改用 filebrowser hash 生成 bcrypt 哈希后经 users import 注入。
FB_DB_DIR="/home/$DEV_USER/.filebrowser"
FB_DB="$FB_DB_DIR/filebrowser.db"
mkdir -p "$FB_DB_DIR"
chown -R "$DEV_USER:$DEV_USER" "$FB_DB_DIR"
FB_HASH="$(filebrowser hash "$DEV_PASSWORD" 2>/dev/null | tail -1)"
FB_USERS_JSON="/tmp/devbox-fb-users.json"
printf '[{"username":"%s","password":"%s","scope":".","perm":{"admin":true}}]\n' \
  "$DEV_USER" "$FB_HASH" > "$FB_USERS_JSON"
chown "$DEV_USER:$DEV_USER" "$FB_USERS_JSON"
runuser -u "$DEV_USER" -- env HOME="/home/$DEV_USER" sh -c "\
  filebrowser -d '$FB_DB' config init >/dev/null 2>&1 || true
  if ! filebrowser -d '$FB_DB' users import '$FB_USERS_JSON' >/dev/null 2>&1; then
    filebrowser -d '$FB_DB' users rm '$DEV_USER' >/dev/null 2>&1 || true
    filebrowser -d '$FB_DB' users import '$FB_USERS_JSON' >/dev/null 2>&1 || \
      echo '[devbox][ERROR] filebrowser 用户初始化失败，文件共享登录不可用' >&2
  fi
  exit 0"
rm -f "$FB_USERS_JSON"
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

# 5.7/5.8 DSH Web + Magpie 的启动封装为函数，延迟到 Caddy 监听之后执行（见文末）。
# 依据（D12/D13 排障实证）：dsh fence 在 entrypoint 早期（反代未就绪时）启动会出现代理信任链异常
# （同参数同 env 的实例在 Caddy 就绪后启动则完全正常，复刻实验 3083=200 / entrypoint 3081=401）。
# desktop 档案为 Electron 应用专属（dsh CLI 报 "profile desktop is managed exclusively by the
# Electron application"），CLI 侧一律使用默认 web profile；desktop 档案保留在镜像内供云端导入参考。
start_dsh() {
  if [ "$ENABLE_DSH" = "1" ]; then
    DSH_BIN="$(ls /opt/nvm/versions/node/*/bin/dsh 2>/dev/null | head -1)"
    NODE_BIN_DIR="$(dirname "${DSH_BIN:-/nonexist}" 2>/dev/null || true)"
    if [ -n "$NODE_BIN_DIR" ] && [ -x "${NODE_BIN_DIR}/dsh" ]; then
      mkdir -p "$RUN_DIR/dsh"
      # M10/D26：web 档案插件播种——dsh web 运行于 ~/.dsh/profiles/web（desktop 是 Electron 专属），
      # 首启（web 档案不存在时）用镜像模板 /opt/devbox-skel/web-profile 原位迁移（mv 同文件系统零拷贝），
      # 插件面板即出现完整插件列表；模板属 root，落家目录后统一交还 dev
      if [ ! -f "/home/$DEV_USER/.dsh/profiles/web/package.json" ] && [ -d /opt/devbox-skel/web-profile ]; then
        mkdir -p "/home/$DEV_USER/.dsh/profiles"
        mv /opt/devbox-skel/web-profile "/home/$DEV_USER/.dsh/profiles/web" 2>/dev/null \
          && chown -R "$DEV_USER:$DEV_USER" "/home/$DEV_USER/.dsh/profiles/web" \
          || echo "[warn] web-profile 播种失败，dsh 将使用默认空档案"
      fi
      DSH_PUBLIC_URL="${DSH_PUBLIC_URL:-http://127.0.0.1:8080/dsh/}"
      # D12 实证：dsh fence 在代理场景校验 X-Forwarded-Host 必须 ∈ trusted-host（Caddy 无法删/改 XFH 自动头）
      DSH_TRUSTED_HOST="$(printf '%s' "$DSH_PUBLIC_URL" | sed -E 's|^https?://([^/]+).*|\1|')"
      (
        runuser -u "$DEV_USER" -- env \
          HOME="/home/$DEV_USER" PATH="${NODE_BIN_DIR}:/usr/local/bin:/usr/bin:/bin" DSH_PUBLIC_URL="$DSH_PUBLIC_URL" DSH_TRUSTED_HOST="$DSH_TRUSTED_HOST" \
          MAGPIE_GATEWAY_KEY="${MAGPIE_GATEWAY_KEY:-devbox-magpie-key}" \
          sh -c 'cd "$HOME" && exec dsh web --host 127.0.0.1 --port 3081 --no-open --public-url "$DSH_PUBLIC_URL" --trusted-host "$DSH_TRUSTED_HOST" >>/tmp/dsh-web.log 2>&1'
      ) &
      # M10/D26 排障：22 插件档案使 dsh web 初始化 >3s，token URL 迟出；
      # grep 空匹配在 set -o pipefail + set -e 下会退出整个 entrypoint（Exited(1) 根因）——
      # 轮询等待（最多 30s）并对 grep 空匹配兜底（|| true）
      DSH_URL=""
      _dsh_i=0
      while [ "$_dsh_i" -lt 30 ]; do
        DSH_URL="$(grep -o 'http://[^ ]*token=[A-Za-z0-9._-]*' /tmp/dsh-web.log 2>/dev/null | tail -1 || true)"
        [ -n "$DSH_URL" ] && break
        sleep 1
        _dsh_i=$((_dsh_i + 1))
      done
      if [ -n "$DSH_URL" ]; then
        printf '%s\n' "$DSH_URL" > "$RUN_DIR/dsh/url.txt"
        log "DSH 登录链接（把入口前缀换成宿主映射后访问）：$DSH_URL"
      else
        log "警告：未抓取到 dsh 登录 token 链接（docker exec cat /tmp/dsh-web.log 查看）"
      fi
      touch "$RUN_DIR/dsh/enabled"
      log "DSH 已启动（dsh web 默认档案，127.0.0.1:3081；日志 /tmp/dsh-web.log）"
    else
      log "警告：ENABLE_DSH=1 但镜像内未找到 dsh 可执行，/dsh 将返回 503"
    fi
  else
    log "DSH 未启用（ENABLE_DSH=0）"
  fi
}

start_magpie() {
  if [ "$ENABLE_MAGPIE" = "1" ]; then
    if command -v magpie >/dev/null 2>&1; then
      mkdir -p "$RUN_DIR/magpie"
      MAGPIE_WEB_URL="${MAGPIE_WEB_URL:-http://127.0.0.1:8080/magpie/}"
      runuser -u "$DEV_USER" -- env \
        HOME="/home/$DEV_USER" MAGPIE_WEB_KEY="${MAGPIE_WEB_KEY:-devbox-magpie-key}" MAGPIE_WEB_URL="$MAGPIE_WEB_URL" \
        MAGPIE_TRUST_PROXY=1 \
        sh -c 'cd "$HOME" && exec magpie web --addr 127.0.0.1:3430 --no-open --gateway >/tmp/magpie-web.log 2>&1' &
      touch "$RUN_DIR/magpie/enabled"
      log "Magpie 已启动（面板 127.0.0.1:3430 + 网关 3425；入口 /magpie/?k= 和 MAGPIE_WEB_KEY，默认 devbox-magpie-key）"
    else
      log "警告：ENABLE_MAGPIE=1 但镜像内未找到 magpie 可执行，/magpie 将返回 503"
    fi
  else
    log "Magpie 未启用（ENABLE_MAGPIE=0）"
  fi
}

# ---------- 6) Caddy 单端口统一反代（PLAN §7.2.5/7.2.6） ----------
# 顺序（D12 时序实证）：Caddy 先监听 → dsh/magpie 在反代就绪后启动 → wait 前台守护
log "Caddy 启动（对外 :8080，统一会话鉴权）"
/usr/local/bin/caddy run --config /etc/devbox/caddy/Caddyfile --adapter caddyfile &
CADDY_PID=$!
_wait_i=0
while [ "$_wait_i" -lt 30 ]; do
  if curl -sf -o /dev/null "http://127.0.0.1:8080/" 2>/dev/null; then
    break
  fi
  sleep 1
  _wait_i=$((_wait_i + 1))
done
log "Caddy 就绪（等待 ${_wait_i}s），启动 DSH/Magpie"
start_dsh
start_magpie
wait "$CADDY_PID"
