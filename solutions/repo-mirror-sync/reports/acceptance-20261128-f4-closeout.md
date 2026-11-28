# F-4 收口验收记录（dispatch/schedule 在默认分支启用）

| 文档编号 | DSH-PLAN-013 |
|---|---|
| 版本 | 1.0.0 |
| 日期 | 2026-11-28 |
| 状态 | 已发布 |
| 关联 | docs/01 §18、Issue #7、PR #10、ADR-012 |

## 1 范围
记录 F-4（workflow_dispatch 要求工作流存在于默认分支）随方案合入 main 后的收口验证：工作流注册、dispatch 实测、schedule 注册状态。

## 2 规范性引用
- docs/01-方案总览.md §18（阶段表）
- docs/02-架构设计.md ADR-012（工作流根级化）
- 根 AGENTS.md §3.1（脚本边界与诚实性）

## 3 术语和定义
沿用 docs/01 §2。

## 4 验收记录

| 项 | 内容 | 结果 |
|---|---|---|
| W1 | 快照分支 pr/repo-mirror-sync 同步至 398b2e6（force push 031cbd1→97b53ea） | 完成 |
| W2 | 本地合并推 main（--allow-unrelated-histories -X theirs，合并提交 03e838e，作者/提交者均 zeek.zhao） | 完成 |
| W3 | PR #10 标记 merged（GitHub 自动检测 + 服务端确认） | 完成 |
| W4 | workflows 注册核验：三份 repo-mirror-sync-* state=active | 通过 |
| V19 | workflow_dispatch 实测 scan（ref=main，204） | run#7 success |
| V20 | workflow_dispatch 实测 build-block（block_id=verify-block，204） | run#4 success |
| V21 | workflow_dispatch 实测 verify-fuse（combo_id=full-reading，204） | run#5 success |
| W5 | schedule cron 注册（scan.yml cron "17 3 */7 * *"） | 已注册（active），首次实际触发待观察 |

## 5 结论
F-4 收口达成：三流水线在 main 可 dispatch 且实测全绿；Issue #7 划账关闭。轮询教训：`/actions/runs?event=...&branch=...` 组合过滤存在列表延迟，按 `/actions/workflows/<wf>/runs` 端点核查更可靠。

## 6 待执行
- scan 周级 cron 首次实际触发待观察（已注册，无法即时验证）。
- feishu webhook 真发验收（URL 未提供，维持待执行）。

## 7 修订历史

| 版本 | 日期 | 修订说明 |
|---|---|---|
| 1.0.0 | 2026-11-28 | 首版：W1~W5/V19~V21 记录，F-4 收口结论 |
