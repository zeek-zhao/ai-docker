#!/usr/bin/env bash
# =============================================================================
# entrypoint.sh —— devbox 启动入口（PLAN §7.2 六步序列）
# 文档编号：RT-001 · 版本：v1.0 · 2026-11-27 · 维护人：zeek.zhao
# 序列：1权限对齐 → 2密码 → 3age解密还原 → 4目录准备 → 5拉起服务 → 6Caddy前台守护
# =============================================================================
set -euo pipefail

DEV_USER="${DEV_USER:-dev}"
HOST_UID="${HOST_UID:-1000}"
HOST_GID="${HOST_GID:-1000}"
DEV_PASSWORD="${DEV_PASSWORD:-}"
ROOT_PASSWORD="${ROOT_PASSWORD:-}"
ROOT_PASSWORD="${ROOT_PASSWORD:-root}"
ENABLE_TAILSCALE="${ENABLE_TAILSCALE:-0}"
ENABLE_DSH="${ENABLE_DSH:-0}"
ENABLE_MAGPIE="${ENABLE_MAGPIE:-0}"
RUN_DIR=/run/devbox

log() { echo "[entrypoint] $*"; }

# ---------- 1) 对齐权限：开发用户 UID/GID 对齐本地（PLAN §7.2.1） ----------
mkdir -p "$RUN_DIR"
# D37：ubuntu:24.04 基础镜像自带 ubuntu 用户/组（uid/gid=1000），与 compose 默认
# HOST_UID/GID=1000 冲突（groupadd/useradd 报 already exists → set -e 退出 → restart 循环）。
# 建账号前先清理内置 ubuntu 账号，其余 uid/gid 冲突仍按错误处理（真实占用需人工确认）
userdel -r ubuntu 2>/dev/null || true
groupdel ubuntu 2>/dev/null || true
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

# ---------- 2) 设置密码（TD-009/D30：默认随机生成；显式弱密码仅警告——需求方拍板） ----------
# 未显式提供时生成 24 字符随机密码（openssl rand -base64 18），写入服务汇总文件与启动日志；
# 弱密码（<6 位/纯数字/常见弱表）打警告继续，公网部署请务必显式传入强密码
DEV_PW_GENERATED=0
if [ -z "$DEV_PASSWORD" ]; then
  DEV_PASSWORD="$(openssl rand -base64 18 2>/dev/null || head -c 24 /dev/urandom | base64 | tr -d '/+=' | cut -c1-24)"
  DEV_PW_GENERATED=1
fi
if [ -z "$ROOT_PASSWORD" ]; then
  ROOT_PASSWORD="$(openssl rand -base64 18 2>/dev/null || head -c 24 /dev/urandom | base64 | tr -d '/+=' | cut -c1-24)"
fi
case "$DEV_PASSWORD" in
  [0-9][0-9][0-9][0-9][0-9]*|[0-9][0-9][0-9][0-9]|[0-9][0-9][0-9]|123|123456|password|admin|root|dev|000000|111111)
    log "警告: DEV_PASSWORD 为弱密码，公网部署请更换（本容器仅为联调便利放行）" ;;
esac
if [ ${#DEV_PASSWORD} -lt 6 ] && [ "$DEV_PW_GENERATED" = "0" ]; then
  log "警告: DEV_PASSWORD 长度不足 6 位，存在被暴力破解风险"
fi
echo "$DEV_USER:$DEV_PASSWORD" | chpasswd
echo "root:$ROOT_PASSWORD" | chpasswd
log "密码已写入（dev/root${DEV_PW_GENERATED:+，dev 密码为随机生成，见服务汇总文件}）"

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

# 5.6 Tailscale（用户态模式；M12/D29：凭证加密固化 + state 卷持久化免重登录）
# 首启链路：state 缺失时从 age 密文解密 auth key（密文随镜像/挂载包分发，私钥 key.txt 仅本地/compose 挂载，
# 公开镜像只含密文不含密钥）；一旦 /var/lib/tailscale/tailscaled.state 由 named volume 持久化，
# 后续重启走免登录路径（机器身份已在 state 内，仅 up 保持连接）。
if [ "$ENABLE_TAILSCALE" = "1" ]; then
  mkdir -p /var/lib/tailscale
  TS_SOCK=/run/devbox/tailscaled.sock
  # D29 修正：state 存在性判断必须在 tailscaled 启动之前——daemon 启动 ~1s 内即写入空 state，
  # 启动后再判断会恒为「已持久化」而跳过首启解密登录链（首启实机踩坑，见 R19）
  TS_NEEDS_LOGIN=0
  [ ! -f /var/lib/tailscale/tailscaled.state ] && TS_NEEDS_LOGIN=1
  tailscaled --tun=userspace-networking --statedir=/var/lib/tailscale --socket="$TS_SOCK" &
  sleep 2
  TS_UP_ARGS="--hostname=${TS_HOSTNAME:-devbox}"
  # D29：需求方确认开启出口节点广播（须在 Tailscale 管理台 approve 该设备后生效）
  TS_UP_ARGS="$TS_UP_ARGS --advertise-exit-node"
  # R21：up 统一后台化+限时探测——authkey 型节点重启后 state 可能失效（Logged out），
  # 前台 up 会无限阻塞拖死整个启动序列；失败只警告，绝不阻塞核心服务
  ts_up_bg() {
    # $@ = up 参数；返回 0=已连接
    tailscale --socket="$TS_SOCK" up "$@" &
    local UP_PID=$! _i=0
    while [ "$_i" -lt 15 ]; do
      sleep 1; _i=$((_i + 1))
      if tailscale --socket="$TS_SOCK" status >/dev/null 2>&1; then
        return 0
      fi
    done
    kill "$UP_PID" 2>/dev/null
    return 1
  }
  if [ "$TS_NEEDS_LOGIN" = "1" ]; then
    TS_AUTHKEY_RESOLVED="${TS_AUTHKEY:-}"
    if [ -z "$TS_AUTHKEY_RESOLVED" ]; then
      # 密文探测顺序：compose 挂载包 > 镜像内置密文；解密私钥：TS_AGE_KEY_FILE > /run/devbox/key.txt
      for AGE_PKG in /secrets-pkg/tailscale-authkey.age /usr/local/share/devbox/secrets/tailscale-authkey.age; do
        AGE_KEY_FILE="${TS_AGE_KEY_FILE:-/run/devbox/key.txt}"
        if [ -f "$AGE_PKG" ] && [ -f "$AGE_KEY_FILE" ]; then
          TS_AUTHKEY_RESOLVED="$(age -d -i "$AGE_KEY_FILE" "$AGE_PKG" 2>/dev/null)" && break
        fi
      done
    fi
    if [ -n "$TS_AUTHKEY_RESOLVED" ]; then
      log "Tailscale 首启：使用解密 auth key 登录（hostname=${TS_HOSTNAME:-devbox}，advertise-exit-node）"
      if ts_up_bg --authkey="$TS_AUTHKEY_RESOLVED" $TS_UP_ARGS; then
        log "Tailscale 已连接（首次登录）"
      else
        log "警告：tailscale 首启登录未在 15s 内完成（authkey 失效/网络受限），后台重试中；核心服务不受影响"
      fi
    else
      log "提示：state 缺失且未提供 TS_AUTHKEY/可解密密文，tailscaled 已就绪待登录（免重登录需挂载 key.txt 或命名卷）"
    fi
  else
    log "Tailscale：检测到持久化 state，尝试免登录保持连接"
    if ts_up_bg $TS_UP_ARGS; then
      log "Tailscale 已连接（免登录）"
    else
      # state 失效（authkey ephemeral/节点过期）：回退解密链重登一次
      log "state 失效或登录超时，回退 authkey 重登"
      TS_AUTHKEY_RESOLVED="${TS_AUTHKEY:-}"
      if [ -z "$TS_AUTHKEY_RESOLVED" ]; then
        for AGE_PKG in /secrets-pkg/tailscale-authkey.age /usr/local/share/devbox/secrets/tailscale-authkey.age; do
          AGE_KEY_FILE="${TS_AGE_KEY_FILE:-/run/devbox/key.txt}"
          if [ -f "$AGE_PKG" ] && [ -f "$AGE_KEY_FILE" ]; then
            TS_AUTHKEY_RESOLVED="$(age -d -i "$AGE_KEY_FILE" "$AGE_PKG" 2>/dev/null)" && break
          fi
        done
      fi
      if [ -n "$TS_AUTHKEY_RESOLVED" ]; then
        if ts_up_bg --authkey="$TS_AUTHKEY_RESOLVED" $TS_UP_ARGS; then
          log "Tailscale 已重新连接（authkey 重登）"
        else
          log "警告：Tailscale 重登失败（不阻塞核心服务；检查 authkey 有效期/网络）"
        fi
      else
        log "警告：无可用 authkey（TS_AUTHKEY/key.txt），Tailscale 保持未登录；核心服务不受影响"
      fi
    fi
  fi
  unset TS_AUTHKEY TS_AUTHKEY_RESOLVED
  log "tailscale 已启动（用户态模式；状态卷 /var/lib/tailscale）"
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

# ---------- 6.1) 服务汇总文件（TD-009/T13.4：启动后一览全部服务/入口/密钥位置） ----------
SUMMARY="${RUN_DIR}/SERVICES.md"
cat > "$SUMMARY" <<EOF
# DevBox 服务一览（容器启动时自动生成）

## 登录凭证
- 网页/网关登录：dev / ${DEV_PASSWORD}$([ "$DEV_PW_GENERATED" = "1" ] && echo '（本次为随机生成，请立即保存；下次重启将重新生成，可用 -e DEV_PASSWORD 固定）')
- root 密码：${ROOT_PASSWORD}
- Magpie 面板 key：\${MAGPIE_WEB_KEY:-devbox-magpie-key}（?k= 兑换链接见下方）

## 服务入口（宿主映射 http://<宿主IP>:\${WEB_PORT:-8080}）
| 服务 | 入口 | 用途 |
|------|------|------|
| 首页 | / | HomePage 导航面板 |
| Web 终端 | /term/ | ttyd（dev 用户 zsh，自动进入 tmux） |
| 文件共享 | /file-share/ | File Browser（dev 数据目录） |
| DSH | /dsh/ | DeepSeek Harness Web（token 链接见 /run/devbox/dsh/url.txt） |
| Magpie | /magpie/?k=<key> | AI 网关面板（API 网关 /v1/* 直通免网页登录） |
| SSH | ssh -p \${SSH_PORT:-2222} dev@<宿主IP> | 密码同上；root 禁登 |
| Tailscale | tailscale status | 见 Tailscale 段（ENABLE_TAILSCALE=1 时） |

## 密钥与状态位置
| 项 | 位置 |
|------|------|
| age 私钥（运行期） | /run/devbox/key.txt（宿主只读挂载，勿入镜像/仓库） |
| 内置密文 | /usr/local/share/devbox/secrets/*.age（镜像内，需私钥解密） |
| Tailscale state | docker 卷 devbox-tailscale:/var/lib/tailscale（免登录持久化） |
| DSH 会话 token 链接 | /run/devbox/dsh/url.txt |
| 本汇总文件 | /run/devbox/SERVICES.md（docker exec devbox cat /run/devbox/SERVICES.md） |

## 升级与维护
- 容器内一键升级（Tailscale/DSH/Magpie+插件自动匹配）：bash /usr/local/share/devbox/tools/upgrade.sh
- 镜像级升级：改 docker-compose ARG / 拉取 ghcr.io/zeek-zhao/devbox:latest（docs/guides/upgrade.md）
- 故障排查：docs/guides/troubleshooting.md；Tailscale 访问各服务：docs/guides/tailscale-access.md
EOF
chmod 600 "$SUMMARY"
log "服务汇总已生成: docker exec devbox cat /run/devbox/SERVICES.md"

wait "$CADDY_PID"
