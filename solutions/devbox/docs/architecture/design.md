# DevBox 架构设计

> 文档编号：AD-001 · 版本：v1.0 · 日期：2026-11-28 · 作者：zeek.zhao · 状态：已发布 · 维护章节：架构

## 1 范围

DevBox 镜像与运行时的整体架构、关键设计决策（D 系列索引）与数据流。

## 2 总体结构

```
宿主 ──8080──> Caddy(统一入口/鉴权网关 auth-gate) ──> HomePage(3000) / ttyd(7681) / filebrowser(8081)
                                             ├──> DSH web(3081)      [ENABLE_DSH=1]
                                             └──> Magpie 面板(3430)/网关(3425, /v1/* 直通)  [ENABLE_MAGPIE=1]
宿主 ──2222──> sshd(22, 禁 root)
tailscaled(用户态) ──> Tailscale 网状网（state 卷持久化）
```

## 3 镜像分层（Dockerfile 五阶段）

| 阶段 | 内容 |
|---|---|
| base | ubuntu:24.04 + 阿里云 apt + 中文/locale + 企业 CA 注入（http bootstrap→CA→https，R10） |
| toolchain-build | NVM+Node LTS+pnpm、Go、DSH CLI（`DSH_NPM_SPEC` ARG）、bun、DSH 插件档案（jq 剔除不可装插件+`--allow-build`）、auth-gate 编译 |
| config | zsh/oh-my-zsh/ys 主题、tmux(oh-my-tmux+tmuxs)、vim-fast 编译+中文帮助、LazyVim、字体 |
| services | ttyd/filebrowser/caddy/homepage(ghcr 镜像提取)/tailscale/yq/hadolint/repo/magpie |
| final | 汇总+entrypoint+decrypt/restore+manifest+secrets/*.age 密文 |

## 4 关键设计决策索引

| 决策 | 摘要 | 详情 |
|---|---|---|
| D1 auth-gate | Caddy 无原生 Session 鉴权→自研 Go forward_auth+HMAC Cookie（7 天） | docs/01 |
| D12 反代时序 | Caddy 先监听→dsh/magpie 后启动；`--public-url/--trusted-host` 过 fence | TD-003/PL-003 |
| D15/D18 fence 同源化 | dsh 改写 Origin、magpie 改写 Origin/Referer 为 listen origin | TD-005/TD-006 |
| D16 /api 分流 | magpie XHR 绝对路径按 Referer 归属，与 homepage /api 区分 | TD-006 |
| D26 web-profile | web 档案由构建期模板首启播种（22 插件） | TD-006 |
| D27/D28 | pnpm store 固定；插件版本自动匹配三形态判定 | TD-007 |
| D29 Tailscale | auth key age 加密入库/入镜像+state 命名卷免重登录 | TD-008/GD-003 |
| D6/D9/D10 | GHA 缓存 CI；filebrowser scope 相对；homepage 键名式服务 | TD-002~004 |

## 5 数据与生命周期

| 数据 | 位置 | 生命周期 |
|---|---|---|
| 用户数据 | `./data` → `/home/dev/data` | bind 持久 |
| Tailscale 身份 | 卷 `devbox-tailscale` | 卷持久（重建免登录） |
| 登录态 | `/var/lib/devbox/cookie-secret` | 容器层（可挂载持久化） |
| 密文凭证 | 镜像 `/usr/local/share/devbox/secrets/` | 随镜像；私钥 compose 挂载 |

## 6 安全边界

- 镜像公开仅含 age 密文；私钥/明文 key/明文 state 永不入库不入镜像。
- dev/123、root/root 为本地测试弱密码（compose 可覆盖）；公网部署必改+启用 Tailscale 内网访问。
- fence 同源化仅限容器内部 Caddy→dsh/magpie 链路，不放宽对外鉴权（auth-gate 全局拦截在前）。

## 7 修订历史

| 版本 | 日期 | 说明 |
|---|---|---|
| v1.0 | 2026-11-28 | 首版发布（M12 文档体系重组，D 系列索引化） |
