# DevBox 整体使用指南

> 文档编号：GD-001 · 版本：v1.0 · 日期：2026-11-28 · 作者：zeek.zhao · 状态：已发布 · 维护章节：使用方法

## 1 范围

本文档描述 DevBox（zeek-ai-devbox 全栈随身开发容器）的获取、启动、访问与日常使用。

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

## 4 快速开始

```bash
git clone https://github.com/zeek-zhao/ai-docker && cd ai-docker/solutions/devbox
WEB_PORT=8080 SSH_PORT=2222 ENABLE_DSH=1 ENABLE_MAGPIE=1 docker compose -p devbox up -d
```

## 5 访问入口（登录账号 dev / DEV_PASSWORD，默认 123）

| 入口 | 地址 | 说明 |
|---|---|---|
| 首页仪表盘 | `http://<宿主>:8080/` | 服务卡片导航 |
| Web 终端 | `http://<宿主>:8080/term/` | ttyd zsh（自动进入 tmux 田字格会话） |
| 文件共享 | `http://<宿主>:8080/file-share/` | filebrowser（scope=/home/dev/data） |
| DSH | `http://<宿主>:8080/dsh/` | 镜像内置，`ENABLE_DSH=1` 启用 |
| Magpie | `http://<宿主>:8080/magpie/` | 面板+网关，`ENABLE_MAGPIE=1` 启用；Magpie API 网关经 `/v1/*` 直通 |
| SSH | `ssh -p <SSH_PORT> dev@<宿主>` | dev 免密 sudo，root 禁登 |

首次访问任意网页入口会被重定向到 `/login`（统一登录态，Cookie 7 天）。DSH/Magpie 的登录链接含 token/key，由容器日志或 `docker exec devbox cat /run/devbox/dsh/url.txt` 获取。

## 6 Tailscale（可选持久连接）

1. 在 Tailscale 管理台生成 **reusable auth key**；
2. 本地生成/复用 age 私钥 `secrets/key.txt`（`bash scripts/age-keygen.sh`），并用 `scripts/encrypt.sh` 将 auth key 加密为 `secrets/tailscale-authkey.age`（该密文**允许入库并随镜像分发**，私钥严禁入库）；
3. compose 取消 key.txt 挂载注释并设置 `ENABLE_TAILSCALE=1`；
4. 首启自动解密登录（`--hostname devbox --advertise-exit-node`）；此后 state 存于命名卷 `devbox-tailscale`，**容器重建免重登录**。

## 7 容器内预置能力速览

zsh(ys)+oh-my-zsh / tmux(oh-my-tmux+`tmuxs` 田字格) / vim 9.1(websimple+中文帮助) / node LTS+pnpm / Go / rg / lf / yq / hadolint / repo / age / dsh CLI / magpie CLI / bun / `/usr/local/share/devbox/tools/plugin-version-match.sh`。

## 8 修订历史

| 版本 | 日期 | 说明 |
|---|---|---|
| v1.0 | 2026-11-28 | 首版发布（M12 文档体系重组） |
