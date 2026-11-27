# 阶段5 告警投递与缓存治理实测验收记录

| 项 | 内容 |
|---|---|
| 文档编号 | ACC-M9-20261128 |
| 版本 | 1.0.0 |
| 状态 | 已发布 |
| 所属分支 | repo-mirror-sync |
| 方案 | repo-mirror-sync（ai-docker） |

## 1 范围

本记录承载 M9 里程碑（阶段 5：告警与治理，FR-A1~A3）的实测验收结果：

- FR-A1 告警投递：github-issue 通道真实发送验收（含 1 分钟内送达与 1h 节流抑制）；feishu-webhook 因未提供 URL 仅完成渲染与 skipped 降级验证；
- FR-A2 缓存治理：cache_gc LRU 清理（块级/版本级/预算兜底）合成目录实测；
- FR-A3 多 token 轮转：GH_TOKENS 唯一入口静态断言 + 单枚 token 真实冒烟。

## 2 引用

- docs/01-方案总览.md §18（阶段 5 行）
- docs/03-功能需求与验收标准.md §5.6（FR-A1~A3）、§10（验收清单）
- docs/05-BDD总纲与场景目录.md（SC-M9-01~08、SC-M1-09）
- docs/06-开发计划与里程碑.md §4（M9）
- reports/test-report.md §14（M9 轮补充）

## 3 术语

| 术语 | 含义 |
|---|---|
| dedup_key | 告警去重键（kind:subject） |
| skipped | 通道凭据缺失时的降级状态（不投递、不告警失败） |
| throttled | 1h 节流窗口内被抑制的事件状态 |
| LRU | 最近最少使用（块级整块删除 → 版本级留最新 N → 预算兜底） |

## 4 实测结果

### 4.1 环境与前置

- 宿主：jenkins@10.22.67.213（Docker 26.1.0；Python 3.10.12；age 工具位于 local/20261128-age-bin，临时区 7 天过期）
- 凭据：GitHub token 经运行时占位符机制内联注入（真实值不入库、不入任何文档，见根 AGENTS §3.1）；FEISHU_WEBHOOK_URL 未提供（决策①）
- 基线：79/79 全绿（35 单测 + 44 BDD 场景，含 SC-M9-01~08、SC-M1-09）

### 4.2 E2E 实测

| 编号 | 场景 | 操作 | 期望 | 结果 |
|---|---|---|---|---|
| E2E-1 | github-issue 真发（FR-A1 验收） | notify.py 内联 budget_exceeded 事件（estimated=1000/actual=4321） | 一分钟内收到单条可行动通知 | ✅ Issue #8「[mirror-sync][budget_exceeded] scan-run」送达，双标签（mirror-sync、budget_exceeded），正文含 dedup_key 与 estimated/actual |
| E2E-2 | 节流抑制 | 同 dedup_key 立即重发 | 1h 窗口内二次投递被抑制 | ✅ events 状态=throttled，results 空 |
| E2E-3 | 验收产物处置 | 对 Issue #8 评论验收产物并关闭 | 评论成功+状态 closed | ✅ 评论 HTTP 201 / 关闭 HTTP 200 |
| E2E-4 | cache_gc LRU（FR-A2） | 合成 10 块×2 版本×1KB，keep_blocks=8/keep_versions=2 | 删 b01/b02 整块（含版本级日志 4 行），剩余 b03~b10 | ✅ 删除 4 行日志、空目录壳回收（F-13 修复后复验） |
| E2E-5 | cache_gc 目录缺失 | cache-dir 指向不存在目录 | 零清理审计通过 exit 0 | ✅ |
| E2E-6 | cache_gc 预算兜底 | 预算 1000 字节、4 块×1 版本 | 超限→cache_pressure 双数成对（estimated=1000/actual=4000）、删至 ≤ 预算 | ✅（SC-M9-06 绿灯覆盖） |
| E2E-7 | GH_TOKENS 冒烟（FR-A3） | 单枚 token 经 GH_TOKENS 真实扫描（scan.yaml 最小集） | 完成扫描、未超限不产 alert-events.json | ✅ 3 请求完成，head_sha=d102e6f4d72decc92c579c6eaf737f15b4a9c174（main HEAD） |
| E2E-8 | feishu-webhook 降级 | 无 FEISHU_WEBHOOK_URL 投递 | feishu 通道 skipped、github-issue 正常 | ✅（符合决策①；真实发送待执行） |

### 4.3 结论

- FR-A1：github-issue 通道验收达成（E2E-1/2/3）；feishu-webhook 待 URL（待执行）。
- FR-A2：cache LRU 三级清理与预算审计验收达成（E2E-4~6）。
- FR-A3：GH_TOKENS 轮转入口唯一性与单枚回退验收达成（SC-M1-09 + E2E-7）；多 token 403/429 切换分支待真实限流场景（待执行）。
- 三流水线接线静态断言通过（SC-M9-04）；CI 端到端告警待下次真实 run 触发（待执行）。

## 5 缺陷记录（F 编号续）

| 编号 | 缺陷 | 根因 | 处置 |
|---|---|---|---|
| F-10 | notify 调 render_all(payload, rules) 抛 TypeError | render_all 契约为单参（payload 自带 channels） | 修复并登记；红灯转绿前发现 |
| F-11 | dispatch 步骤 ctx 键名与 alert 步骤约定不一致 | 新步骤模块未对齐既有约定（error/allowed） | 键名统一 |
| F-12 | bdd_steps_cache ROOT 未定义 + size=100 笔误 | 步骤落盘笔误（意图 1000 字节） | 改 _ROOT + size=1000 |
| F-13 | cache_gc 文件级删除残留空目录壳 | clean 契约未含目录壳回收 | 整块删除后 rmdir 空壳 |
| F-14 | docs/04 §3.1 目录树 toolchain 注释仍写 overlayfs | M7 轮（ADR-011）治理漏项 | 本轮修正并补记 docs/04 1.0.3 |
| F-15 | 验收记录 4.1 凭据行误含真实 token（运行时占位符被宿主替换写入文档） | 文档 heredoc 直写占位符文本触发替换机制 | GitHub Push Protection 拦截（未进远端）；改为描述性文案并全库扫描确认仅此 1 处；教训：入库文档禁写占位符形态文本 |

## 6 待执行事项

- [待执行] feishu-webhook 真实发送验收（待 FEISHU_WEBHOOK_URL 提供，建议经 repo secrets 注入）
- [待执行] GH_TOKENS 多 token 403/429 真实切换分支验收（待限流场景）
- [待执行] CI 端到端告警验收（待 scan 流水线真实 run 触发）
- [待执行] 阶段5 剩余：导出 manifest 仓库列表维护、FR-D2 合并裁决（Issue #3）、dispatch/cron 收口（Issue #7，待合 main）

## 7 清理记录

- out/m9-e2e、out/m9-scan-smoke 实测目录已删除；临时产物未入库（out/** 为 gitignore）。
- age 工具与 key 保留于 local/20261128-age-bin（临时区 7 天过期，密钥不入库）。

## 8 修订历史

| 版本 | 日期 | 说明 |
|---|---|---|
| 1.0.0 | 2026-11-28 | 首版：M9 阶段5 告警投递与缓存治理实测验收（E2E-1~8、F-10~F-14） |
| 1.0.1 | 2026-11-28 | 修正 4.1 凭据描述误含运行时替换 token（F-15；Push Protection 拦截于本地，未进远端）；缺陷表增至 F-15 |
