# DevBox 文档索引

> 维护人：zeek.zhao · 更新：2026-11-28（M12 重组）

## 目录结构

```
docs/
├── guides/            # 使用与维护手册（GD 编号）
│   ├── usage.md       # GD-001 整体使用方法
│   ├── upgrade.md     # GD-002 升级流程（DSH/Magpie/组件 ARG 化）
│   └── maintenance.md # GD-003 维护指南（含 Tailscale 密钥管理取舍）
├── architecture/      # 架构设计（AD 编号）
│   └── design.md      # AD-001 总体架构与决策索引
├── issues/            # 问题记录（R 编号索引 + 专项排障报告）
├── plans/             # 计划与任务书归档（TD/PL/原始需求 PLAN）
├── reports/           # 验收记录与截图
└── NN-*.md            # 过程文档（任务书/计划/里程碑/风险/变更，编号顺延）
```

## 快速入口

- 第一次用 → [guides/usage.md](guides/usage.md)
- 升级 DSH/Magpie → [guides/upgrade.md](guides/upgrade.md)
- 密钥/轮换/排障 → [guides/maintenance.md](guides/maintenance.md)
- 架构与决策 → [architecture/design.md](architecture/design.md)

## 过程文档编号规则

`NN-任务书-TD-00X.md` / `NN-落地计划-PL-00X.md` 成对顺延；里程碑状态在 `02-里程碑与任务跟踪.md`（TR-001），风险在 `03-风险登记.md`（RK-001），变更在 `04-变更记录.md`（CH-001）。问题记录（R 编号）索引见 `issues/README.md`。

### docs/plans 补充
19-任务书-TD-010.md（M15 八项）
20-落地计划-PL-010.md（M15）
21-测试计划-BTS-001.md（Bats 冒烟测试计划）
22-任务书-TD-011.md（M16 清理/文档/Tailscale/Bats）
