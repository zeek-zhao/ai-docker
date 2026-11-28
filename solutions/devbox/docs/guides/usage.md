# DevBox 整体使用指南

> 文档编号：GD-001 · 版本：v1.1 · 日期：2026-11-29 · 作者：zeek.zhao · 状态：已发布 · 维护章节：使用方法

## 1 范围

本文档描述 DevBox（devbox 全栈随身开发容器）的获取、启动、访问与日常使用。

## 2 规范性引用文件

- `docs/architecture/design.md`（AD-001，架构设计）
- `docs/guides/upgrade.md`（GD-002，升级流程）
- `docs/guides/maintenance.md`（GD-003，维护指南）

## 3 术语和定义

| 术语 | 含义 |
|---|---|
| DevBox | 本工程交付的多阶段 Ubuntu 容器镜像及其运行实例 |
| 鉴权网关 | auth-gate（Go），为全部 Web 服务提供统一 Cookie 登录态 |
| fence | DSH/Magpie 自带的浏览器信任校验（Origin/X-Forwarded-Host），由 Caddy header_up 同源化解决 |

## 4 快速开始（.env 集中配置，M15+）

```bash
git clone https://github.com/zeek-zhao/ai-docker && cd ai-docker/solutions/devbox
cp .env.example .env && vi .env     # 一次编辑全部参数（端口/开关/Tailscale/PUBLIC_URL…）
docker compose -p devbox up -d
```

`.env` 主要参数：`WEB_PORT`/`SSH_PORT`/`HOST_UID`(=id -u)/`HOST_GID`/`DEV_PASSWORD`(留空=自动生成 24 位随机)/`ENABLE_DSH`/`ENABLE_MAGPIE`/`ENABLE_TAILSCALE`/`PUBLIC_URL`/`MAGPIE_WEB_KEY`。环境变量前缀传参（`WEB_PORT=9090 docker compose -p devbox up -d`）仍兼容且优先于 .env。

## 5 访问入口（登录账号 dev / 密码见服务汇总文件）

| 入口 | 地址 | 说明 |
|---|---|---|
| 首页仪表盘 | `http://<宿主>:8080/` | 服务卡片导航 |
| Web 终端 | `http://<宿主>:8080/term/` | ttyd zsh（自动进入 tmux 田字格会话） |
| 文件共享 | `http://<宿主>:8080/file-share/` | filebrowser（scope=/home/dev/data） |
| DSH | `http://<宿主>:8080/dsh/` | 镜像内置，`ENABLE_DSH=1` 启用 |
| Magpie | `http://<宿主>:8080/magpie/` | 面板+网关，`ENABLE_MAGPIE=1` 启用；Magpie API 网关经 `/v1/*` 直通 |
| SSH | `ssh -p <SSH_PORT> dev@<宿主>` | dev 免密 sudo，root 禁登 |

首次访问任意网页入口会被重定向到 `/login`（统一登录态，Cookie 7 天）。

**凭证查询（密码随机生成，M15+）**：

```bash
docker exec devbox cat /run/devbox/SERVICES.md   # dev/root 密码、Magpie key、全部入口与密钥位置
docker exec devbox cat /run/devbox/dsh/url.txt   # DSH 免登 token 链接
```

注意：`DEV_PASSWORD` 留空时**每次容器重建都会重新生成随机密码**；固定密码请在 `.env` 显式设置。DSH/Magpie 的登录链接含 token/key。

## 6 Tailscale 首启自动登录（D29，免重登录）

原理：auth key 以 age 密文随镜像分发（公开镜像只含密文），私钥仅在启动时挂载进容器解密；机器身份存命名卷，重建免重登录。

**一次性准备（构建/部署机）**：

1. 管理台生成 **reusable auth key**；
2. 生成 age 私钥并加密 auth key（私钥 `secrets/key.txt` **严禁入库/入镜像**，密文允许入库）：

```bash
bash scripts/age-keygen.sh                                  # 生成 secrets/key.txt（0600）与 key.pub
printf '%s' "<你的 auth key>" | age -R secrets/key.pub -o secrets/tailscale-authkey.age
# 或用封装脚本：TS_KEY="<auth key>" bash scripts/encrypt.sh（详见 docs/guides/maintenance.md §2）
```

**启用（部署机）**：

3. `.env` 设 `ENABLE_TAILSCALE=1`（模板默认已开）；
4. 编辑 `docker-compose.yml` volumes，取消 key.txt 挂载注释：`- ./secrets/key.txt:/run/devbox/key.txt:ro`；
5. `docker compose -p devbox up -d`。

**验证与行为**：

- 首启日志出现「Tailscale 首启：使用解密 auth key 登录」→「Tailscale 已连接（首次登录）」（`docker logs devbox | grep -i tailscale`）；
- 固定机器名 `TS_HOSTNAME`（默认 devbox，重名自动 -1 后缀）；自动广播出口节点（`--advertise-exit-node`，需管理台 approve 才生效）；
- 此后容器重启/重建：state 命名卷命中即免登录保持连接（日志「Tailscale 已连接（免登录）」）；state 失效自动回退 authkey 重登（R21）；
- 管理台访问：`http://<tailscale-ip>:8080/`，或 `tailscale status` 查看 IP；轮换流程见 `docs/guides/maintenance.md` §2。

## 7 冒烟测试（Bats，BTS-001）

```bash
./tests/run-tests.sh            # 20 用例：软件版本/服务连通登录/凭证有效/动态文件真实可用
```

镜像内置 bats；测试计划见 `docs/plans/21-测试计划-BTS-001.md`，用例 `tests/smoke.bats`（BDD：B1 软件/B2 服务/B3 凭证/B4 动态文件）。

## 8 容器内预置能力速览

zsh(ys)+oh-my-zsh / tmux(oh-my-tmux+`tmuxs` 田字格) / vim 9.1(websimple+中文帮助) / nvim(LazyVim) / node LTS+pnpm+bats / Go / rg / lf / yq / hadolint / repo / age / dsh CLI / magpie CLI / bun / `tools/upgrade.sh`（运行期升级）与 `tools/plugin-version-match.sh`。

## 9 修订历史

| 版本 | 日期 | 说明 |
|---|---|---|
| v1.1 | 2026-11-29 | 快速开始改 .env 集中配置流程；凭证改随机密码+SERVICES.md 查询；Tailscale 首启五步细化+验证；新增 Bats 测试节（M16） |
| v1.0 | 2026-11-28 | 首版发布（M12 文档体系重组） |
