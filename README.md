# ai-docker · 多方案仓库

> 本仓库承载多个独立问题方案的规划、实现与测试，每个方案在
> `solutions/<方案ID>/` 下**目录隔离**。当前包含一个方案：
> repo 多仓库「分层镜像 + 低频探测 + 标签编排」同步（`repo-mirror-sync`）：
> 在 GitHub Actions 单次 5 GB 存储上限内，把 manifest 管理下的 N 个仓库按
> topic/标签切片成多个加密镜像块，既支持「只拉自己开发的那一块」，
> 又支持运行时把多个块 OverlayFS 融合为一个跨目录全量视图。

## 1. 全局规范

- [`AGENTS.md`](AGENTS.md)：Agent 全局工作规范，对本仓库所有 AI 会话生效（脚本边界、临时脚本治理、策略唯一来源、诚实性约束等）。
- [`.gitignore`](.gitignore)：版本控制边界（任意深度 `out/`、`local/`、`tmp/`、密钥永不入库）。

## 2. 方案索引

| 方案 ID | 路径 | 主题 | 状态 | 入口 |
|---|---|---|---|---|
| `repo-mirror-sync` | `solutions/repo-mirror-sync/` | repo 多仓分层镜像同步 | M0~M10 已交付（85/85 绿：基础库/扫描/构建产物静态结构/求解/融合守卫/告警/漂移检测/非特权融合校验/CI 触发与还原验证/告警投递与缓存治理/合并裁决）；toolchain 基座 ubuntu:24.04（ADR-011，实际构建 V10~V14）；CI 三流水线已实测（V16~V18，ADR-012）+ 制品还原 T1~T7；告警 github-issue 真发验收（Issue #8）+1h 节流抑制、缓存 LRU 治理（FR-A2）、GH_TOKENS 轮转（FR-A3）；合并裁决已交付（`tools/merge_arbitration.py`，FR-D2/Issue #3 收口）；待执行：feishu webhook、dispatch/schedule 收口（合 main 后，PR #10） | [solutions/repo-mirror-sync/AGENT.md](solutions/repo-mirror-sync/AGENT.md) |

每个方案目录内的固定结构（详细规则见该方案 `docs/04`）：

```
solutions/<方案ID>/
├── manifest.yaml        # 方案清单：全部文件与产物
├── AGENT.md             # AI 接手提示词（跨平台交接）
├── docs/                # ISO 规划文档族
├── config/              # 策略唯一来源（scan.yaml / policy.yaml）
├── tools/               # 脚本区（基础库 + 阶段实现）
├── tests/               # 测试用例与测试入口
├── reports/             # 测试报告与验收记录
├── docker/              # 镜像定义区（按阶段交付）
├── .github/workflows/   # 流水线区（按阶段交付）
├── local/               # 临时脚本区（不入库，7 天到期删除）
└── out/                 # 运行产物区（不入库）
```

## 3. 快速开始（任一方案）

```bash
cd solutions/repo-mirror-sync
python3 tests/run_tests.py            # 运行全部测试（纯标准库，Linux/Windows/macOS 通用）
```

## 4. 修订历史

| 版本 | 日期 | 说明 |
|---|---|---|
| 1.0.0 | 2026-11-27 | 初版：方案拆解、架构设计、需求规格、仓库规划、AGENTS.md、配置基线 |
| 1.1.0 | 2026-11-27 | 重构为多方案仓库：方案产出迁入 `solutions/repo-mirror-sync/`；新增 manifest、tests、reports、AGENT.md |
| 1.1.1 | 2026-11-28 | 方案状态更新：M6 漂移检测交付（`tools/detect_drift.py`，SC-M6-01~06 全绿，65/65）；待执行项收敛至 Linux 实际构建/CI 运行与 FR-D2 合并裁决 |
| 1.1.2 | 2026-11-28 | 方案状态更新：M7 非特权融合校验交付（`tools/fuse_verify.py`，SC-M7-01~04 全绿，69/69）；toolchain 基座换 ubuntu:24.04（ADR-011）；实际构建 V10~V14 已 Linux 实测，待执行项收敛至 CI 运行与 FR-D2 合并裁决 |
| 1.1.3 | 2026-11-28 | 方案状态更新：M8 CI 触发与还原验证交付（三流水线实测 V16~V18 全绿，ADR-012/013；制品还原 T1~T7；SC-M1-08 补 F-9 回归，70/70）；待执行项收敛至 dispatch/schedule 收口（合 main 后）与 FR-D2 合并裁决 |
| 1.1.4 | 2026-11-28 | 方案状态更新：M9 告警与治理交付（FR-A1 github-issue 真发验收 Issue #8+节流抑制；FR-A2 缓存 LRU；FR-A3 GH_TOKENS 轮转；SC-M9-01~08+SC-M1-09，79/79）；待执行项收敛至 feishu webhook、dispatch/schedule 收口（合 main 后）与 FR-D2 合并裁决 |
| 1.1.5 | 2026-11-28 | 方案状态更新：M10 合并裁决交付（`tools/merge_arbitration.py`，FR-D2/Issue #3 收口，SC-M10-01~06，85/85）；待执行项收敛至 feishu webhook 与 dispatch/schedule 收口（合 main 后，PR #10） |
