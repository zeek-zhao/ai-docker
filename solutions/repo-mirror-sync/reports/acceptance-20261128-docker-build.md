# 实际构建验证记录 — repo-mirror-sync（2026-11-28）

> 性质：阶段 4「实际构建/运行验证」的**执行记录**（AGENTS §3.5 诚实性：未执行项
> 一律标注「待执行」并收录 Issue）。测试行为验证见 `reports/test-report.md`。
> 环境：Linux 服务器（jenkins@10.22.67.213），Docker 26.1.0（overlay2），
> 代码基线 repo-mirror-sync 分支 `1986809`（M6 交付后）。
> 关联 Issue：#4（实际构建验证遗留，本记录 findings 的跟踪入口）、
> #3（FR-D2 合并裁决，非本记录范围，仅关联提及）。

## 1 验证范围与方法

对 `docker/` 三个镜像定义做**真实构建验证**（区别于 SC-M2-01~04 的静态结构
校验）。方法：`docker build` 实跑；上游 HEAD 与探测均不经本记录涉及；
因 L0 工具链构建失败（见 §2），block/fused 采用 **stub 基座**验证机制——
即 `docker tag debian:bookworm-slim repo-mirror-sync/toolchain:L0` 后构建，
只验证 Dockerfile 自身逻辑（参数化、COPY、fail-fast、软链、ENV），
不验证工具链内容。构建夹具（bindings.json、placeholder.txt）放
`local/20261128-docker-ctx*`（不入库，验证后即删，AGENTS §3.2）。

## 2 结果

| # | 验证项 | 结果 | 证据/说明 |
|---|---|---|---|
| V1 | 基础镜像拉取与 digest 实测 | ✅ | `debian:bookworm-slim@sha256:e67eeead736ff7bbe258ef088bff683635c561b1fcfefad0806c1df4ab49ce0e`（运行时自 registry 取得，非杜撰；构建参数 DEBIAN_DIGEST 仍待维护者正式固定入库） |
| V2 | toolchain.L0 真实构建 | ❌ **失败** | `RUN apt-get install … overlayfs-tools` exit 100：`debian:bookworm-slim` 仓库**无 `overlayfs-tools` 包**（`git`、`age` 均有候选，apt-cache 证实）。属阶段 4 预告的「包名以目标发行版实际可用为准」校正项 → 跟踪 Issue #4 |
| V3 | block.Dockerfile 参数化构建 | ✅ | `--build-arg BUILD_BLOCK=verify-block` 构建成功（stub 基座，标签镜像 sha256:16f87c…） |
| V4 | block fail-fast·路径一（整块目录缺失） | ✅ | COPY checksum 阶段失败：`"/blocks/verify-block": not found`——目录不存在时在 COPY 即失败，**不会**走到 RUN 报错分支 |
| V5 | block fail-fast·路径二（目录在、缺 bindings.json） | ✅ | RUN 分支精确触发设计报错：`bindings.json 缺失：块 verify-block 未生成绑定表（FR-B3）`，exit 1 |
| V6 | fused.Dockerfile 构建 | ✅ | 构建成功（stub 基座，sha256:703622…） |
| V7 | fused 运行时软链与 ENV | ✅ | `docker run` 实测：`readlink /workspace/manifest` → `/mnt/manifest`；`LOWERDIR=/mnt/layers/toolchain:/mnt/layers/self-dev`；`MOUNT_POINT=/workspace/merged`（符合 docs/01 §13 与 manifest 软链约定） |
| V8 | overlay 实际挂载与两级融合 | 待执行 | 需特权容器 + 内核 overlayfs；属 CI `verify-fuse.yml` 特权步骤（Issue #4 第 5 项） |
| V9 | Actions 三工作流触发运行 | 待执行 | `scan.yml` / `build-block.yml` / `verify-fuse.yml` 实际触发（Issue #4 第 4 项） |

## 3 发现与处置

1. **F-1（构建阻断）**：`overlayfs-tools` 在 `debian:bookworm-slim` 无包，
   V2 失败。处置：本轮**不擅自改镜像定义**（替换工具属 FR-B1/SC-M2-01 设计
   决策，按 docs/06 §5 规则 3 须先改文档再实现），候选方案（fuse-overlayfs 包 /
   源码编译 / 去除工具改用内核原生挂载校验）已列 Issue #4 待裁决。
2. **F-2（行为澄清）**：V4/V5 证明 fail-fast 有两条触发路径——块目录整体缺失
   在 COPY 阶段失败（BuildKit 报 not found），目录存在但缺 bindings.json 才
   触发 Dockerfile 内的中文报错分支。两路径均达成「缺失即构建失败（fail-fast）」
   设计意图，无需改码。
3. **F-3（stub 边界）**：V3~V7 基于 stub 基座，验证的是 Dockerfile 机制而非
   工具链内容；真实基座复验列为 Issue #4 第 3 项。

## 4 清理

构建夹具（`local/20261128-docker-ctx*`）已删除；验证镜像
（block:verify / fused:verify / stub toolchain:L0 标签）已 `docker rmi`；
工作树验证后无残留（`git status` 干净）。

## 修订历史

| 版本 | 日期 | 修订说明 |
|---|---|---|
| 1.0.0 | 2026-11-28 | 首次记录：V1~V7 已执行、V8~V9 待执行（Issue #4）；发现 F-1 工具链缺包、F-2 fail-fast 双路径、F-3 stub 边界 |
