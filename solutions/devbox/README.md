# zeek-ai-devbox —— 全栈随身开发容器工程

> 文档编号：RD-001 · 版本：v1.0 · 日期：2026-11-27 · 作者：zeek.zhao（AI 执行） · 评审：需求方已确认 · 状态：开发中
> 方案依据：PLAN.md（ZeekDevAI Container 全栈随身开发容器方案）

## 1. 项目简介

基于 Ubuntu 24.04 的自包含开发容器：多阶段分层镜像；Caddy 在单对外端口（默认 8080）按路径反向代理导航首页、Web 终端、文件共享、DSH、Magpie，并做统一登录态会话鉴权；SSH 映射 2222:22；age 加密配置按清单还原；只挂载 `devbox/` 数据目录。

## 2. 目录结构

```
solutions/devbox/
├── README.md                     # 本文档
├── PLAN.md                       # 方案文档（来源：需求方）
├── Dockerfile                    # 多阶段分层构建（base/toolchain-build/config/services/final）
├── docker-compose.yml            # 一键编排（端口/UID/GID 参数化）
├── entrypoint.sh                 # 启动入口：权限对齐/密码/解密还原/起服务
├── config/
│   ├── gitconfig                 # Git 身份预设
│   ├── zsh/                      # Oh My Zsh + powerlevel10k
│   ├── vim/                      # LazyVim 配置
│   ├── tmux/                     # oh-my-tmux 配置
│   ├── caddy/                    # Caddyfile + auth-gate 会话鉴权
│   └── homepage/                 # HomePage 导航清单
├── secrets/
│   ├── manifest.json             # 加密条目清单
│   └── README.md                 # 密钥与加解密流程说明（私钥不入库）
├── data/                         # 运行时挂载数据目录
├── scripts/
│   ├── build.sh                  # 分层构建
│   ├── run.sh                    # 启动示例（参数化）
│   ├── age-keygen.sh             # 生成/校验 age 密钥对
│   ├── encrypt.sh                # 按 manifest 加密目录/文件
│   ├── pack.sh                   # 打包密文+清单+还原脚本
│   ├── decrypt.sh                # 容器内按清单解密
│   └── restore.sh                # 解密+按目录还原+权限修复
└── docs/                         # ISO 风格过程文档
```

## 3. 快速开始

```bash
# 构建
docker build --target final -t zeek-ai-devbox:latest .
# 启动
./scripts/run.sh            # 等价 PLAN.md §10.2 示例，参数可覆盖
# 访问
#   Web:  http://<host>:8080/   （dev / 123，本地测试弱密码）
#   SSH:  ssh -p 2222 dev@<host>
```

## 4. 文档索引

| 编号 | 文档 | 说明 |
|------|------|------|
| TD-001 | docs/00-任务书.md | 任务范围与约束 |
| PL-001 | docs/01-落地计划.md | 里程碑与确认结论 |
| TR-001 | docs/02-里程碑与任务跟踪.md | 任务执行状态 |
| RK-001 | docs/03-风险登记.md | 风险与对策 |
| CH-001 | docs/04-变更记录.md | 变更历史 |
