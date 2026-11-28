# DevBox 升级流程（DSH / Magpie / 基础组件）

> 文档编号：GD-002 · 版本：v1.0 · 日期：2026-11-28 · 作者：zeek.zhao · 状态：已发布 · 维护章节：升级

## 1 范围

说明 DSH、Magpie 及基础工具链的版本升级方法：**全部升级只改构建参数（ARG），CI 自动出镜像**。

## 2 版本参数一览（solutions/devbox/Dockerfile ARG）

| 组件 | ARG | 默认值 | 说明 |
|---|---|---|---|
| DSH CLI | `DSH_NPM_SPEC` | `@deepseek-ai/dsh@0.2.2-rc.5` | npm 规格，可写 `@deepseek-ai/dsh@latest` 或精确版本 |
| Magpie | `MAGPIE_VERSION` | 自动（GitHub latest） | 置为 `v0.1.xxxx` 可锁版本 |
| Node | `NVM_VERSION` / 内部 `--lts` | v0.40.3 + LTS | nvm 版本与 Node 大版本 |
| Bun | `BUN_VERSION` | v1.3.4 | |
| Go | `GO_VERSION` | `auto`（跟随官方最新稳定） | 显式如 `1.27.4` |
| ttyd / filebrowser / homepage / caddy / tailscale | 自动 | latest | 各自 ARG 可覆盖，详见 Dockerfile services 阶段 |
| DSH 插件 | `config/dsh/profile-package.json` | 22 插件 | 版本自动匹配工具见 §4 |

## 3 标准升级三步

```bash
# ① 改参数（直接改 Dockerfile ARG 或提交一个一行 commit）
sed -i 's|@deepseek-ai/dsh@0.2.2-rc.5|@deepseek-ai/dsh@<新版本>|' solutions/devbox/Dockerfile
git commit -am "chore(devbox): DSH 升级 <新版本>" && git push        # push 到 ai-devbox/main 自动触发 CI

# ② 等 CI 出镜像（Actions 约 2~15 分钟，缓存命中时更快）
# ③ 拉取并重建容器
docker pull ghcr.io/zeek-zhao/devbox:latest
docker compose -p devbox up -d --no-build   # 或 docker stop devbox && docker rm devbox && docker run …（沿用原参数）
```

> 数据不受影响：`/home/dev/data`（bind）与 `devbox-tailscale`（named volume）独立于镜像生命周期；家目录其余内容（插件档案等）随镜像版本重置，升级前如有自定义请先备份或纳入 `config/` 管理。

## 4 DSH 插件升级（含版本自动匹配）

```bash
# 容器内或宿主（脚本已随镜像发布 /usr/local/share/devbox/tools/）
plugin-version-match.sh dsh-voice-mode --dsh 0.2.2-rc.5          # 输出推荐版本
plugin-version-match.sh @magpie-community/tools-calc --magpie <版本> --json
```

将推荐版本写回 `config/dsh/profile-package.json`（注意同步 `dsh.profile.bundles` 数组）后走 §3 标准三步。兼容性判定规则（核心库 range / 宿主白名单 / 无 peer fallback）见脚本头注释与 TD-007。

## 5 回滚

镜像按日期时间 tag 保留于 GHCR（`ghcr.io/zeek-zhao/devbox:YYYYMMDD-HHmm`，`latest` 恒指最新）：

```bash
docker run -d --name devbox ghcr.io/zeek-zhao/devbox:20261128-1919 …   # 用旧 tag 重建即可
```

## 6 修订历史

| 版本 | 日期 | 说明 |
|---|---|---|
| v1.0 | 2026-11-28 | 首版发布（M12） |
