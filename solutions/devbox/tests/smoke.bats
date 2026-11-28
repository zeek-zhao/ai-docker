#!/usr/bin/env bats
# =============================================================================
# smoke.bats —— DevBox 冒烟测试（BTS-001 v1.0，BDD 风格）
# 运行：tests/run-tests.sh（容器内 bats /tests/smoke.bats）
# 环境变量：SMOKE_HOST（默认 127.0.0.1）、WEB_PORT（默认 8080）
# =============================================================================
setup() {
  HOST="${SMOKE_HOST:-127.0.0.1}"
  PORT="${WEB_PORT:-8080}"
  BASE="http://${HOST}:${PORT}"
  RUN=/run/devbox
  SUMMARY="${RUN}/SERVICES.md"
  # 从服务汇总解析真实凭证（密码/key 由 entrypoint 动态生成）
  DEV_PW=$(sed -n 's|^.*dev / \([^ （（]*\).*$|\1|p' "$SUMMARY" | head -1)
  MAG_KEY=$(sed -n 's|.*magpie/?k=\([^) ]*\).*|\1|p' "$SUMMARY" | head -1)
  [ -z "$MAG_KEY" ] && MAG_KEY="devbox-magpie-key"
  JAR=$(mktemp)
}
teardown() { rm -f "$JAR"; }

# ---------- B1 软件安装与版本 ----------

@test "B1.1 Given 镜像内环境 When 查询核心工具链 Then node/go/pnpm/bun/dsh 版本可用" {
  local NB; NB=$(ls -d /opt/nvm/versions/node/*/bin | head -1)
  PATH="$NB:/usr/local/bin:/usr/bin:/bin:$PATH" HOME=/home/dev bash -c '
    set -e
    node --version | grep -q "^v2[0-9]"
    go version   | grep -q "go1\.2[0-9]"
    pnpm --version | grep -q "^1[0-9]"
    bun --version | grep -q "^1\."
    PATH="'"$NB"':$PATH" dsh --version | grep -q "^0\." '
}

@test "B1.2 Given 镜像内环境 When 查询常用 CLI Then rg/tmux/age/fzf/vim/lf 全部在 PATH" {
  for c in rg tmux age fzf vim lf; do command -v "$c" >/dev/null; done
  rg --version | grep -q ripgrep
  tmux -V | grep -q tmux
  age --version | grep -qE "(^age|^[0-9]+\.)"
  vim --version | grep -q "^VIM"
}

@test "B1.3 Given M13 增强件 Then 十件全在且 fd/bat 链接生效" {
  for c in ag fd bat ncdu btop http tldr delta lazygit dust; do command -v "$c" >/dev/null; done
  fd --version >/dev/null; bat --version >/dev/null
}

@test "B1.4 Given 服务与工具二进制 Then yq/hadolint/repo/magpie/caddy/filebrowser/ttyd/tailscale/bats 可执行" {
  for c in yq hadolint magpie caddy filebrowser ttyd tailscale bats; do command -v "$c" >/dev/null; done
  test -x /usr/bin/repo -o -x /usr/local/bin/repo
  yq --version >/dev/null; hadolint --version >/dev/null
}

# ---------- B2 服务运行/连通/登录 ----------

@test "B2.1 Given 容器启动 When 查监听 Then 六服务端口全 LISTEN" {
  local out; out=$(ss -tln)
  for p in ":22 " ":3000 " ":7681 " ":8081 " ":9090 " ":8080 "; do
    echo "$out" | grep -qF "$p"
  done
}

@test "B2.2 Given 未认证请求 When 访问首页 Then 302 重定向登录页" {
  local code; code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/")
  [ "$code" = "302" ]
}

@test "B2.3 Given SERVICES.md 的 dev 密码 When POST /login Then 302 且种下会话 Cookie" {
  local hdr
  hdr=$(curl -s -c "$JAR" -o /dev/null -D - -X POST "$BASE/login" \
        --data-urlencode "username=dev" --data-urlencode "password=$DEV_PW")
  echo "$hdr" | grep -q " 302"
  echo "$hdr" | grep -qi "set-cookie: devbox_auth="
}

@test "B2.4 Given 已认证会话 When 访问路由矩阵 Then 首页/终端/文件共享 200 且裸路径 308" {
  # 独立登录种 cookie（bats 每 test 独立 setup/teardown）
  local code; code=$(curl -s -c "$JAR" -o /dev/null -w '%{http_code}' \
    --data-urlencode "username=dev" --data-urlencode "password=$DEV_PW" "$BASE/login")
  [ "$code" = "302" ]
  for path in / /term/ /file-share/; do
    local code; code=$(curl -s -b "$JAR" -o /dev/null -w '%{http_code}' "$BASE$path")
    [ "$code" = "200" ]
  done
  local bare; bare=$(curl -s -b "$JAR" -o /dev/null -w '%{http_code}' "$BASE/term")
  [ "$bare" = "308" ]
}

@test "B2.5 Given DSH/Magpie 已启用 Then 路由非 503（302/200 均视为门控已解除）" {
  if [ -f "$RUN/dsh/enabled" ]; then
    local c1; c1=$(curl -s -b "$JAR" -o /dev/null -w '%{http_code}' "$BASE/dsh/")
    [ "$c1" != "503" ]
  fi
  if [ -f "$RUN/magpie/enabled" ]; then
    local c2; c2=$(curl -s -b "$JAR" -o /dev/null -w '%{http_code}' "$BASE/magpie/")
    [ "$c2" != "503" ]
  fi
}

@test "B2.6 Given filebrowser 后端 Then 容器内 8081 带前缀可达" {
  local code; code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8081/file-share/)
  [ "$code" != "000" ] && [ "$code" != "502" ] && [ "$code" != "503" ]
}

@test "B2.7 Given magpie 网关 3425 Then /v1/models 返回 200 JSON" {
  local body; body=$(curl -s http://127.0.0.1:3425/v1/models)
  echo "$body" | grep -q '"object"'
}

@test "B2.8 Given sshd Then 容器内 22 端口握手横幅非空" {
  local banner; banner=$(timeout 5 bash -c 'exec 3<>/dev/tcp/127.0.0.1/22 && head -c 32 <&3' || true)
  [[ "$banner" == SSH-* ]]
}

# ---------- B3 账号密码有效性 ----------

@test "B3.1 Given SERVICES.md 凭证段 Then dev/root 密码均解析成功且非弱密码" {
  [ -n "$DEV_PW" ] && [ "$DEV_PW" != "123" ]
  local root_pw; root_pw=$(sed -n 's|^.*root 密码：\([^ （（]*\).*$|\1|p' "$SUMMARY" | head -1)
  [ -n "$root_pw" ] && [ "$root_pw" != "root" ]
}

@test "B3.2 Given dev 账号 When sudo 非交互提权 Then NOPASSWD 生效" {
  sudo -n true
}

@test "B3.3 Given magpie key When 以 ?k= 兑换 Then 非 401 拦截（302/200 可进入）" {
  local code; code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/magpie/?k=$MAG_KEY")
  [ "$code" != "401" ] && [ "$code" != "000" ]
}

# ---------- B4 动态文件真实可用 ----------

@test "B4.1 Given entrypoint 已运行 Then SERVICES.md 存在、600 权限、含四段" {
  [ -f "$SUMMARY" ]
  [ "$(stat -c %a "$SUMMARY")" = "600" ]
  for sec in "登录凭证" "服务入口" "密钥与状态位置" "升级与维护"; do
    grep -qF "$sec" "$SUMMARY"
  done
}

@test "B4.2 Given dsh url.txt Then 存在且为非 127.0.0.1 的完整 token 链接" {
  local url; url=$(cat "$RUN/dsh/url.txt" 2>/dev/null || true)
  [ -n "$url" ]
  [[ "$url" == http://*/dsh/?token=* ]]
  [[ "$url" != http://127.0.0.1* ]]
}

@test "B4.3 Given url.txt 中 token When 全新浏览器链兑换 Then 页面 200 非 401" {
  if [ ! -f "$RUN/dsh/enabled" ]; then skip "DSH 未启用"; fi
  # 兑换需经过网关（auth-gate Cookie + dsh 会话）；直接复用已认证 Jar 打 token 链
  local code; code=$(curl -s -L -b "$JAR" -c "$JAR" -o /dev/null -w '%{http_code}' "$(cat "$RUN/dsh/url.txt")")
  [ "$code" = "200" ]
}

@test "B4.4 Given ENABLE_DSH/MAGPIE=1 Then enabled 标记文件存在" {
  [ -f "$RUN/dsh/enabled" ]
  [ -f "$RUN/magpie/enabled" ]
}

@test "B4.5 Given auth-gate Then cookie-secret 已持久化且足够长" {
  local f=/var/lib/devbox/cookie-secret
  [ -f "$f" ]
  [ "$(wc -c < "$f")" -ge 32 ]
}

@test "B4.6 Given ENABLE_TAILSCALE=1（若启用）Then state 存在且 tailscale 非 Offline" {
  if [ ! -d /var/lib/tailscale ]; then skip "Tailscale 未启用"; fi
  [ -f /var/lib/tailscale/tailscaled.state ]
  local st; st=$(tailscale --socket=/run/devbox/tailscaled.sock status 2>/dev/null || true)
  [[ "$st" != *"Offline"* ]]
}
