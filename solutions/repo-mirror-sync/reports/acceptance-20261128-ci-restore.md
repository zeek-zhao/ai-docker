# 验收记录：CI 触发与产物还原恢复测试（M8 轮）

| 版本 | 1.0.0 |
| 日期 | 2026-11-28 |
| 状态 | 生效（CI 三流水线实测通过；本地还原测试 T1~T7 全过；70/70 回归绿） |

---

## 1 范围

本记录固化 M8 轮「CI 触发 → 制品拉取 → 本地还原/恢复测试」的实测证据：
分支 `repo-mirror-sync` 上三条流水线（scan / build-block / verify-fuse）的触发、
修复与通过记录，以及 CI 制品在本地环境的全类型还原验证（解密、镜像加载、
融合校验复算、消费侧挂载自验、清单 schema 校验）。

## 2 规范性引用文件

- `docs/01-方案总览.md` §18（阶段表）；§11.3（绑定表契约）
- `docs/02-架构设计.md` ADR-011（融合验收非特权化）、ADR-012（工作流根级化）、ADR-013（scan.repos 唯一出处）
- `docs/03-需求规格.md` FR-B1~B4、FR-S3（14 字段 head_sha 真相）
- `reports/acceptance-20261128-ubuntu24-fuse-verify.md`（V10~V15 前置实测）
- 根 `AGENTS.md` §2.1/§2.2（根级 workflows 区，ADR-012）

## 3 术语和定义

| 术语 | 定义 |
|---|---|
| CI 制品 | Actions run 产出的 upload-artifact zip（block.tar.age / decisions.json / inventory.json 等） |
| 还原测试 | 用本地工具链把 CI 制品恢复为可用形态并校验内容一致性的测试（T1~T7） |
| V 编号 | CI/构建实测步骤编号（承接 V1~V15，本轮 V16~V18） |
| T 编号 | 本地还原/恢复测试编号（T1~T7） |
| F 编号 | 本轮发现的缺陷与平台约束编号（F-4~F-9） |

## 4 CI 实测记录（V16~V18）

| 编号 | 工作流 | run | 触发 | 结果 | 证据要点 |
|---|---|---|---|---|---|
| V16 | repo-mirror-sync-scan.yml | run4（id 46048132808） | push（paths：tools/scan_inventory.py） | success | inventory.json head_sha=d102e6f4d72decc92c579c6eaf737f15b4a9c174（main 真实 HEAD，40hex）且 scan_status=ok；run3 与 secrets 重写竞态失败后经 rerun API 重跑通过 |
| V17 | repo-mirror-sync-build-block.yml | run2 | push（paths：docker/**） | success | 验证块 verify-block 构建；bindings.json 镜像内 fail-fast 检查过；block.tar.age + sha256 清单产出 |
| V18 | repo-mirror-sync-verify-fuse.yml | run3 | push（paths：docker/**、tools/fuse_verify.py） | success | 层树导出→fused 构建→fuse_verify 通过（out/fuse-verify.passed）→加密往返 cmp 一致→decisions.json 落盘 |

触发方式说明：`workflow_dispatch` 需工作流存在于默认分支才被 Actions 注册
（F-4 平台约束），本轮以 push 触发（branches=[repo-mirror-sync]）完成实测；
dispatch 触发保留待合 main 后启用（待执行，阶段 5 收口）。

## 5 本地还原/恢复测试（T1~T7）

| 编号 | 内容 | 结果 |
|---|---|---|
| T1 | sha256 清单比对：build-block 与 verify-fuse 两份 block.tar.age 的 sha256 与 CI 清单一致（ac3406ad…/354086c4…） | 通过 |
| T2 | age 解密：本地 age v1.3.2 + keypair（local/20261128-age-bin/，7 天过期）解出 block.tar | 通过 |
| T3 | docker load：两份镜像分别载入 block-verify-block:2 / :3 | 通过 |
| T4 | 镜像内容抽验：/opt/block/bindings.json 与 CI 构建输入一致（manifest_rev=ci-verify-2 / fuse-verify-3 随 run_number 区分） | 通过 |
| T5 | 融合校验复算：从 CI 还原镜像重建层树后本地复跑 fuse_verify——passed=true，decisions/materialized 与 CI 制品逐条一致（opt/.toolchain-baseline keep toolchain、opt/** keep self-dev、scripts/build.sh isolate） | 通过 |
| T6 | 消费侧挂载自验：--privileged 容器（宿主 docker 组）内核 overlay 挂载 lowerdir=toolchain:self-dev，merged 并集含权威文件+块内容+isolate 的 build.sh（ADR-011 不变：挂载属消费侧运行时语义，本地自验非 CI 门禁） | 通过 |
| T7 | 清单 schema 校验：CI inventory.json 14 字段齐备、CSV 表头与 FIELDS 一致；首次真实扫描暴露 F-9 缺陷（head_sha 空串），修复后 run4 复核通过 | 通过 |

## 6 缺陷与平台约束（F-4~F-9）

| 编号 | 现象 | 根因 | 处置 | 状态 |
|---|---|---|---|---|
| F-4 | workflow_dispatch 对新工作流 404 | Actions 仅注册默认分支工作流 | 三工作流加 push 触发（分支+paths 限定）；dispatch 待合 main（Issue 跟踪） | 缓解（约束留存） |
| F-5 | scan run 失败：No module named 'tools' | 脚本执行 sys.path[0]=tools/ | 步骤加 PYTHONPATH=. | 已修复（c8f1f74） |
| F-6 | build-block artifact name 非法 | `${BLOCK_ID:-x}` 冒号非法且 name 不经 shell | 改 `${{ inputs.block_id || 'verify-block' }}` | 已修复（c8f1f74） |
| F-7 | verify-fuse 层树缺 scripts/build.sh | 块镜像无 /scripts（内容在 /opt/block） | runner 侧合成 isolate 触发文件 | 已修复（c8f1f74） |
| F-7b | verify-fuse run2 startup_failure（jobs=0） | 插入行缩进早于 run: | 块标量基准重排 | 已修复（0afa759） |
| F-8 | MIRROR_SCAN_TOKEN 401 | 密钥值曾被视图掩码串污染（教训：密钥占位符只能取规则原文） | secrets 重写；scan.yml 注释登记 | 已修复（0afa759+重写） |
| F-9 | 首次真实扫描 head_sha=""且 scan_status=ok | scan() 已探测 head["sha"] 但建记录取 meta["head_sha"]（真实适配层为空串，假 fetcher 掩盖缝隙） | 探测值回填+SC-M1-08 回归；run4 复核 head_sha=d102e6f4… | 已修复（1f31315） |

## 7 结论与待执行事项

1. **结论**：三流水线在本分支全绿；CI 制品全类型还原通过（T1~T7）；离线回归 70/70。
   M8 轮目标达成，V9（CI 运行时）遗留项在本分支语义下收口。
2. **待执行**（阶段 5 / 合 main 后）：
   - workflow_dispatch 触发与 schedule（scan 每周 cron）依赖合 main 后的平台注册（F-4）；
   - 消费侧挂载的 CI 门禁化（当前为本地自验，ADR-011 语义不变）；
   - FR-D2 合并裁决（Issue #3）与 scan.repos 真实仓库清单维护（首版最小集）。

## 8 清理记录

- 三份 CI 制品（out/ci-artifacts/，gitignored）验证后删除；
- 本地验证镜像 block-verify-block:2/:3、层树与 /tmp 缓存已删；
- age 工具与 keypair 留存 `local/20261128-age-bin/`（临时区 7 天过期，密钥不入库）；
- 工作树干净，本轮提交均已推送 origin repo-mirror-sync。

## 9 修订历史

| 版本 | 日期 | 说明 |
|---|---|---|
| 1.0.0 | 2026-11-28 | 首版：CI 三流水线实测（V16~V18）与本地还原测试（T1~T7）全过；缺陷 F-4~F-9 登记；F-9 修复并复核 |
