# GD-004 Tailscale 访问各服务说明

> 文档编号：GD-004 · 版本：v1.0 · 日期：2026-11-28 · 适用：ENABLE_TAILSCALE=1 且设备已连接

## 1. 前提

1. 容器以 `-e ENABLE_TAILSCALE=1` 启动，启动日志出现「Tailscale 已连接」或 `tailscale status` 含本机 IP（100.x.x.x）。
2. 管理台已 approve 本设备（hostname 固定为 `devbox`，可用 `TS_HOSTNAME` 覆盖）。
3. 客户端设备（手机/笔记本）已登录**同一 tailnet**。

## 2. 服务访问入口（`<TS_IP>` 为容器设备的 100.x.x.x 地址）

| 服务 | Tailscale 入口 | 与宿主端口入口的差别 |
|------|----------------|----------------------|
| 首页 | `http://<TS_IP>/` | 同一 Caddy 入口，全部路由一致 |
| Web 终端 | `http://<TS_IP>/term/` | 不经宿主端口映射，出网即可用 |
| 文件共享 | `http://<TS_IP>/file-share/` | 同上 |
| DSH | `http://<TS_IP>/dsh/` | token 链接以首次登录输出为准；`DSH_PUBLIC_URL` 需设置为 `http://<TS_IP>/dsh/` 才能免 401 |
| Magpie | `http://<TS_IP>/magpie/?k=<key>` | `MAGPIE_WEB_URL` 同理设 `http://<TS_IP>/magpie/` |
| SSH | `ssh -p 2222 dev@<TS_IP>` | 走容器 22 端口（tailnet 内无需宿主映射） |
| exit-node | 设备侧开启 exit-node 并选本容器 | 需管理台 approve `--advertise-exit-node` |

> 注意：`DSH_PUBLIC_URL`/`MAGPIE_WEB_URL` 决定 fence 信任域与回跳链接。经 Tailscale 入口访问时请把这两个 env 设为 `<TS_IP>` 形态（或保留宿主形态并从宿主入口兑换一次 token）。Cookie 均绑定当前访问的 Host。

## 3. 常用操作

```bash
docker exec devbox tailscale status          # 连接状态与设备列表
docker exec devbox tailscale ip -4           # 本机 tailnet IP
docker exec devbox tailscale ping <对端>      # 连通性
```

## 4. 免重登录机制（D29）

- state 持久化于命名卷 `devbox-tailscale` → 重启容器免登录；
- 认证 Key 以 age 加密随镜像分发（`/usr/local/share/devbox/secrets/tailscale-authkey.age`），私钥只在宿主（挂载 `/run/devbox/key.txt`）；
- 换机部署：复制私钥文件+启动容器即可自动登录。

## 5. 修订历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-11-28 | 首版 |
