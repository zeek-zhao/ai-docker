# GD-005 异常处理手册（troubleshooting）

> 文档编号：GD-005 · 版本：v1.0 · 日期：2026-11-28 · 覆盖：M1-M13 已知故障模式（与 issues/README R1-R19 对应）

## 1. 容器启动类

### 1.1 容器反复退出 / Exit(1)
1. `docker logs devbox` 看 `[entrypoint]` 最后一行；
2. 已知模式：`set -euo pipefail` 对管道吞错敏感（R5/R19）——若卡在服务启动行，检查 `/tmp/dsh-web.log`、`/tmp/magpie-web.log`；
3. 密码未设时自动随机生成（TD-009/D30），日志出现「随机生成」属正常。

### 1.2 端口冲突
- 8080/2222 被占：compose 改 `WEB_PORT`/`SSH_PORT`；容器名冲突：`docker rm -f devbox`。

## 2. 网页服务类

### 2.1 登录后 401/403
- DSH 401：`DSH_PUBLIC_URL` 必须与浏览器实际入口一致（宿主端口/Tailscale IP 形态），`--trusted-host` 由 entrypoint 自动推导；
- Magpie 401「isn't signed in」：先访问 `/magpie/?k=<key>` 兑换，再开 `/magpie/`；
- 403「answers own page only」（写类 API）：确认镜像 ≥ D18（Origin/Referer 同源化已内建）。

### 2.2 503「未启用」
- `/dsh/` `/magpie/` 503：compose 缺 `ENABLE_DSH=1`/`ENABLE_MAGPIE=1`。

### 2.3 filebrowser 无法登录/看不到文件
- 密码与 dev 一致；scope=root`.`（相对），文件在 `/home/dev/data`；D18 前版本存在 scope 双重叠加 404（R13 已修）。

## 3. Tailscale 类

### 3.1 启动未自动登录
- 检查 key.txt 挂载（`/run/devbox/key.txt`，是**文件**不是目录）；日志应有「使用解密 auth key 登录」；
- state 卷存在但登录失效：`docker exec devbox tailscale logout` 后重启容器重走首启。

### 3.2 hostname 变成 devbox-1/-2
- tailnet 重名自动加后缀；管理台删旧设备后重启容器恢复 `devbox`（R19 修复后行为稳定）。

### 3.3 exit-node 不生效
- 需管理台 approve 本设备为 subnet/exit-node 路由（`--advertise-exit-node` 只广播）。

## 4. DSH/Magpie 插件类

### 4.1 插件面板为空/更新报错
- 确认镜像含 web-profile 播种（≥ M10/D26）；`docker exec devbox ls /home/dev/.dsh/profiles/web/node_modules`；
- 「声明了但没安装」：bundles 与 dependencies 不一致（R17，已由 jq 链同步剔除修复）。

### 4.2 pnpm「Switching to the store」
- 模板 `.npmrc` 已固定 store-dir（D27）；若仍出现，属 store 损坏，可 `rm -rf ~/.pnpm-store` 后重跑 pnpm install（全量重装，最后手段）。

### 4.3 插件版本匹配
- 容器内 `plugin-version-match.sh <插件名> --dsh <版本>`；批量升级走 `upgrade.sh`（通道 4）。

## 5. Magpie agent「不显示」专题（T13.9/D36 根因档案）

**现象**：Magpie 面板 Sessions/agent 列表长期为空，但 DSH 侧 LLM 供给正常。

**根因（M11 确诊）**：
1. 快照恢复的 cordis patch（llm-pi-ai）中 `maxTokensField` 字段值被快照脱敏替换成字面 `<REDACTED>`，不符合 schema 枚举（合法值仅 `max_completion_tokens`/`max_tokens`）→ patch 激活即 `ValidationError` → **面板注册层失败** → agent/provider 不显示；
2. **代理供给与面板注册是两条独立链路**：DSH 的模型请求直接指向 Magpie 网关 `http://127.0.0.1:3425/v1`（免网页认证，Caddy `/v1/*` 直通 + `MAGPIE_TRUST_PROXY=1`），不经过 patch 注册——这就是「agent 不显示却仍能代理」的原因；
3. M11 修正 `maxTokensField: "max_tokens"` 后 patch 激活；agent 记录的出现还需要**真实对话流量**（无会话=无记录，属正常）。

**自查顺序**：`docker logs devbox | grep -i validationerror` → 无报错即注册成功；`curl -s http://127.0.0.1:3425/v1/models` → 200 即供给链路正常；DSH 内发起一次对话后面板 Sessions 应出现记录。

## 6. 密码与凭证

- 忘记随机密码：`docker exec devbox cat /run/devbox/SERVICES.md`（生成时已写入）；
- 弱密码警告：日志「弱密码…放行」属 D30 设计（联调便利），公网部署请传 `-e DEV_PASSWORD=<强密码>`。

## 7. 升级失败

- `upgrade.sh` 某通道失败不影响其余通道（逐步 `|| warn`）；dsh/magpie 升级失败保留旧版本；
- 镜像级回滚：`docker run` 指定旧 tag（GHCR 保留全部 `YYYYMMDD-HHmm`）。

## 8. 修订历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-11-28 | 首版（含 Magpie agent 根因档案） |
