# DevBox（zeek-ai-devbox）—— 全栈随身开发容器工程

> 文档编号：RD-001 · 版本：v1.1 · 日期：2026-11-28 · 作者：zeek.zhao（AI 执行） · 评审：需求方已确认 · 状态：已发布
> 原始需求：`docs/plans/PLAN-original.md`（ZeekDevAI Container 全栈随身开发容器方案）

## 1. 项目简介

基于 Ubuntu 24.04 的自包含开发容器：多阶段分层镜像；Caddy 在单对外端口（默认 8080）按路径反向代理导航首页、Web 终端、文件共享、DSH、Magpie，并做统一登录态会话鉴权；SSH 映射 2222:22；age 加密配置按清单还原；Tailscale 持久连接（state 卷免重登录，D29）；只挂载 `data/` 数据目录。

- 镜像：`ghcr.io/zeek-zhao/devbox:<YYYYMMDD-HHmm>`（`latest` 恒指最新；CI 随 push 自动构建）
- 使用 → `docs/guides/usage.md`；升级 → `docs/guides/upgrade.md`；维护/密钥 → `docs/guides/maintenance.md`；架构 → `docs/architecture/design.md`

## 2. 目录结构

```
solutions/devbox/
├── README.md                     # 本文档
├── Dockerfile                    # 多阶段分层构建（ARG 参数化，升级只改这里）
├── docker-compose.yml            # 一键编排（name: devbox；state 卷 devbox-tailscale）
├── entrypoint.sh                 # 启动入口：权限对齐/密码/解密还原/Tailscale/起服务
├── config/                       # caddy(Caddyfile+authgate)/dsh/magpie/zsh/vim/tmux/homepage/gitconfig/tools
├── secrets/
│   ├── manifest.json             # 加密条目清单
│   ├── tailscale-authkey.age     # Tailscale auth key 密文（D29：允许入库/入镜像，私钥须本地）
│   └── README.md                 # 密钥与加解密流程说明（私钥 key.txt 不入库）
├── scripts/                      # build/run/age-keygen/encrypt/pack/decrypt/restore
├── tools/                        # plugin-version-match.sh 等
└── docs/                         # 文档体系（见 docs/README.md 索引）
    ├── guides/                   # GD：使用/升级/维护
    ├── architecture/             # AD：架构设计
    ├── issues/                   # 问题记录（R 编号索引）
    ├── plans/                    # 计划归档（含原始需求 PLAN-original.md）
    └── reports/                  # 验收记录与截图
```

## 3. 快速开始

```bash
WEB_PORT=8080 SSH_PORT=2222 ENABLE_DSH=1 ENABLE_MAGPIE=1 docker compose -p devbox up -d
# 访问 http://<宿主>:8080/（dev / 123）
```

## 4. 修订历史

| 版本 | 日期 | 说明 |
|---|---|---|
| v1.1 | 2026-11-28 | M12：DevBox 更名/文档体系重组/Tailscale 持久化（D29）/升级 ARG 化 |
| v1.0 | 2026-11-27 | 首版（M1） |
