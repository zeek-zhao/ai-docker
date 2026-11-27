# AGENTS.md —— 仓库开发工作流规范

> 文档编号：AG-000 · 版本：v1.0 · 生效日期：2026-11-28 · 适用范围：本仓库全部分支 · 维护人：zeek.zhao

## 1. 仓库定位

本仓库（zeek-zhao/ai-docker）为 **zeek-ai-devbox 全栈随身开发容器**的多分支开发仓库。主要交付物位于 `solutions/devbox/`（方案依据 PLAN.md：多阶段分层镜像、Caddy 单端口反代统一会话鉴权、age 加密配置还原）。

## 2. 分支规范（多分支开发）

| 分支 | 用途 |
|------|------|
| `main` | 默认分支，承载仓库级规范与稳定基线 |
| `ai-devbox` | devbox 容器工程开发分支 |
| `ai-devbox-<suffix>` | 允许的变体分支（feature 后缀），如 `ai-devbox-mvp` |

规则：
1. 提交 Issue 时必须在标题或正文中**标注所属分支**。
2. 不得随意跨分支操作；仅在当前分支上工作。
3. 变体分支一律基于其宿主分支创建，禁止跨系重基底。

## 3. 提交规范

1. 提交人身份**仅允许** `zeek.zhao` / `zeek.zhao@foxmail.com`，且必须为**仓库局部配置**（`git config` 不带 `--global`）；合并提交（merge commit）同样受此约束——采用本地 merge 后推送，避免平台侧合并身份漂移。
2. 提交信息格式：`<type>(<scope>): <subject>`，type ∈ docs|feat|fix|chore|refactor|test；subject 使用中文短句。
3. 每个里程碑至少一次独立提交，便于追溯。

## 4. 凭据与安全

1. 一切凭据/令牌仅本地临时注入环境变量或本地密钥文件，**严禁**写入仓库、镜像或全局配置。
2. 禁止 `git config --global`；提交人信息只做仓库局部配置。
3. age 私钥及一切明文密钥严禁入库；`secrets/` 目录只允许密文与清单。

## 5. 工作流（强制顺序）

任务书 → 落地计划 → 风险评审并与需求方确认 → 按里程碑执行 → 验证 → 交付。

执行原则：文档先行、里程碑驱动、临时脚本用完即删、开发使用 RTK 压缩上下文。

## 6. 文档规范

`solutions/devbox/docs/` 内文档采用 ISO 风格元数据（文档编号/版本/日期/作者/评审/状态）。问题、解决方案与 AI 操作记录均须落档，禁止只做不留痕。

## 7. 目录约定

```
AGENTS.md             # 本规范（仓库级，main 基线）
solutions/devbox/     # devbox 容器工程（唯一开发落点）
solutions/devbox/docs # 过程文档（任务书/计划/里程碑/风险/变更）
```
