# 验收记录：V2 修复轮（ubuntu:24.04 基座 + 非特权融合校验）

| 项目 | 内容 |
|---|---|
| 版本 | 1.0.0 |
| 日期 | 2026-11-28 |
| 状态 | 已发布（V10~V15 已执行；CI 运行待执行） |
| 关联 | ADR-011（docs/02）、FR-B1 与 §10 阶段 4（docs/03）、M7（docs/06）、Issue #3/#4、验收记录 acceptance-20261128-docker-build.md（V1~V9） |
| 分支 | repo-mirror-sync |

## 1 范围

记录 2026-11-28 V2 阻断修复轮的全部实测：①toolchain 基础镜像换基 ubuntu:24.04 并以真实 digest 构建；②非特权用户态等价校验工具 `tools/fuse_verify.py` 的端到端验证；③块/融合镜像运行时约定复验。内核 OverlayFS 实际挂载（上一轮 V8）不在本轮范围（ADR-011：挂载属消费侧运行时语义，不作 CI 门禁）。

## 2 规范性引用文件

docs/01 §3/§13.1/§18、docs/02 ADR-011、docs/03 FR-B1/§10、docs/05 §6（SC-M7）、docs/06 §3/§4（M7）、根 AGENTS.md §3.5。

## 3 术语和定义

沿用 docs/01 §3；「用户态等价校验」为本轮新义：在不调用 mount/FUSE/特权能力的普通进程内，按 `tools/overlay.py` 唯一裁决物化融合视图并落盘决策表（decisions.json），用于验收内容可见性与选举语义。

## 4 验证项（基线：上一轮 V1~V9）

| 编号 | 验证内容 | 命令要点 | 结果 | 佐证 |
|---|---|---|---|---|
| V10 | L0 工具链镜像（ubuntu:24.04）真实构建 | `docker build --build-arg UBUNTU_DIGEST=sha256:562111b88caa79c71391c0c4d3c2114a7d5c35915c20561fd893cb1e07929e6b -f docker/toolchain.Dockerfile .` | PASS：image sha256:10f5b7709da6…；容器内 git 2.43.0、age 1.1.1、`/opt/.toolchain-baseline` 存在；`dpkg -s overlayfs-tools` 确认无此包（ADR-011 预期） | 宿主 Docker 26.1.0/overlay2 |
| V11 | block 镜像正向构建（`--build-arg TOOLCHAIN_IMAGE=repo-mirror-sync/toolchain:L0`） | 临时构建上下文含 bindings.json + repo/README | PASS | 上下文在 local/（已删） |
| V12 | fail-fast 路径一：块目录在而 bindings.json 缺失 | 同 V11 去绑定表 | PASS：exit=1，中文报错「bindings.json 缺失：块 verify-block 未生成绑定表（FR-B3）」 | 复验上轮 V5 |
| V13 | fail-fast 路径二：/blocks/verify-block 整目录缺失 | 同 V11 去目录 | PASS：exit=1，COPY 报 "/blocks/verify-block": not found | 复验上轮 V4 |
| V14 | fused 镜像构建与运行时约定 | `docker build -f docker/fused.Dockerfile --build-arg TOOLCHAIN_IMAGE=…`；运行取 readlink/ENV | PASS：`readlink /workspace/manifest`=/mnt/manifest；`LOWERDIR`=/mnt/layers/toolchain:/mnt/layers/self-dev；`MOUNT_POINT`=/workspace/merged | 复验上轮 V6~V7，基座为真实 ubuntu（非 stub） |
| V15 | 非特权 harness 端到端（普通用户 jenkins，无 sudo/privileged） | `python3 tools/fuse_verify.py --layers toolchain=<tmp> --layers self-dev=<tmp> --out out/fuse-verify-e2e` | PASS：exit=0；passed=true；lowerdir={count:2,max:8,ok:true}；materialized=5；pin 软链 manifest/index→toolchain 层、.gitmodules→self-dev 层；keep opt/README=toolchain 内容；isolate mnt/{toolchain,self-dev}/scripts/build.sh 互不覆盖；decisions.json 4 条与 overlay.py 裁决一致 | ADR-011 主验收 |

## 5 结论与上轮发现项处置

1. F-1（debian:bookworm-slim 无 overlayfs-tools 包导致 V2 构建阻断）→ **关闭**：ADR-011 裁定 L0=git/age，内核挂载由消费侧承担；换基 ubuntu:24.04 后实测同样无该包（V10），与 ADR 结论一致。
2. 上轮 V3~V7 使用 debian stub 假扮基座的边界（F-3）→ 本轮 V10~V14 以真实 ubuntu:24.04 基座全链复验，无 stub。
3. SC-M2-01 场景与 `tests/bdd_steps_docker.py` 已同步「安装层覆盖 git、age 两类工具」及「FROM 基于 ubuntu 24.04 基础镜像」断言（静态结构层）。

## 6 待执行

1. CI 运行时验证（上轮 V9）：Actions 三工作流（scan/build-block/verify-fuse）真实触发；verify-fuse 的非特权校验步骤依赖制品解包出的层目录（out/layers/*，由 build-block 制品链提供），待 CI 链路联通后验证（Issue #4 跟踪）。
2. 内核 OverlayFS 实际挂载（上轮 V8）：属消费侧部署环境语义，不在 CI 门禁（ADR-011）。
3. FR-D2 合并裁决实现（Issue #3，docs/01 §12.3）。

## 7 清理记录

临时构建上下文 `local/20261128-docker-ctx2/3/4`、验证镜像（block:verify、fused-view:verify）、e2e 输出目录与 /tmp 日志均已删除；toolchain:L0 镜像保留（image 10f5b7709da6）。工作树仅含本轮交付文件。

## 修订历史

| 版本 | 日期 | 修订说明 |
|---|---|---|
| 1.0.0 | 2026-11-28 | 首次发布：V10~V15 实测记录、F-1 关闭、V8/V9 待执行边界（ADR-011） |
