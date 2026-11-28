# DevBox 维护指南（含 Tailscale 密钥管理与取舍）

> 文档编号：GD-003 · 版本：v1.0 · 日期：2026-11-28 · 作者：zeek.zhao · 状态：已发布 · 维护章节：维护

## 1 范围

日常维护操作、凭证/密钥管理方案与取舍、故障排查入口。

## 2 Tailscale 密钥管理：建议与取舍（D29）

### 2.1 采用方案（本工程落地）

**reusable Auth Key + age 加密（密文入库/入镜像，私钥仅本地）+ state 命名卷持久化**。

| 层 | 物件 | 位置 | 保护 |
|---|---|---|---|
| 凭证 | Tailscale auth key（明文） | 仅本地环境变量，用后即弃 | 不落盘、不入库 |
| 密文 | `secrets/tailscale-authkey.age` | 仓库 + 公开镜像 | age(X25519) 加密，公开无密钥不可解 |
| 私钥 | `secrets/key.txt`（0600） | 仅本地 + compose 挂载 | gitignore/dockerignore 双排除 |
| 状态 | `tailscaled.state`（机器身份/节点密钥） | 命名卷 `devbox-tailscale` | 不入镜像；卷即持久 |

### 2.2 取舍说明

| 方案 | 优点 | 缺点 | 结论 |
|---|---|---|---|
| **Auth Key+age（采用）** | 单容器最简；密文可入库随镜像走；轮换=重加密一份文件 | auth key 泄漏面=该 key 可登录新设备（选 reusable+过期时间可控） | ✔ 推荐 |
| OAuth Client | 自动化批量发 key，适合多实例 | 单容器过重；secret 同样需加密，链路更长 | 多实例再评估 |
| 已登录 state 迁移 | 最接近"免登录"（含机器身份） | state 含节点私钥，泄漏影响面最大；换宿主/网卡漂移易失效 | ✘ 不采用 |
| 明文 key 环境变量（现状 TS_AUTHKEY） | 零改造 | 明文进 compose/日志风险 | 保留为兼容入口，非默认 |

### 2.3 轮换与吊销

1. Tailscale 管理台 revoke 旧 auth key（并按需移除旧设备）；
2. 生成新 key → `printf '%s' "<新key>" | age -R <(age-keygen -y secrets/key.txt) -o secrets/tailscale-authkey.age`；
3. 提交新密文 → CI → 重建容器；`docker volume rm devbox-tailscale` 可强制走首启链路（同时获得新机器身份）。

## 3 日常维护

| 事项 | 命令/位置 |
|---|---|
| 服务健康 | `docker logs devbox`（entrypoint 六步日志）＋六端口 LISTEN（22/3000/3081/3430/8080/9090） |
| 鉴权网关 | auth-gate cookie secret 持久于 `/var/lib/devbox/cookie-secret`（重建后登录态保留需挂载或接受重新登录） |
| DSH 登录链接 | `docker exec devbox cat /run/devbox/dsh/url.txt` |
| 插件版本匹配 | `/usr/local/share/devbox/tools/plugin-version-match.sh` |
| 备份 | `data/`（bind）+ `docker volume`（tailscale state）＋ secrets/key.txt（本地妥善保管，丢失=密文不可解，需轮换重加密） |

## 4 故障排查入口

- Web 路由/反代问题 → `config/caddy/Caddyfile`（D15/D16/D17/D18 fence 同源化注释）
- DSH/Magpie 启动 → `entrypoint.sh` start_dsh/start_magpie（D12 时序、D26 web-profile 播种）
- 构建失败 → `docs/issues/`（R1~R18 排障记录索引）＋ CI 日志
- 插件不加载 → dsh-web.log（profile bundles/依赖校验，TD-006/TD-007 结论）

## 5 修订历史

| 版本 | 日期 | 说明 |
|---|---|---|
| v1.0 | 2026-11-28 | 首版发布（M12，含 D29 密钥方案） |
