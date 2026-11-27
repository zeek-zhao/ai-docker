# AGENT.md — AI 接手提示词（solutions/repo-mirror-sync）

> **给 AI 的一句话**：你是本方案（多仓分层镜像同步，DSH-PLAN-001~004）的落地工程师。
> 目标环境是 **Linux 服务器**（bash + Python 3.8+，仅标准库起步）；
> 本文件告诉你环境约定、路径规则、硬性约束与从哪里继续。

---

## 1. 你在哪里、怎么跑命令

1. 本仓库可放在服务器任意目录（如 `~/work/ai-docker/`、`/srv/ai-docker/`）。
   **一切路径均为仓库相对路径**，不要假设任何绝对路径（不要假设 `D:\`、`C:\Users\...` 或 `/home/<某人>/...`）。
2. 先定位仓库根（含本文件上级两层的目录）：
   ```bash
   # 仓库根 = 本文件所在方案目录的上级
   REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-.}")" >/dev/null 2>&1; pwd)"
   # 直接进入工作区
   cd <仓库根>/solutions/repo-mirror-sync
   ```
   后文所有命令都假定你已 `cd` 到 `solutions/repo-mirror-sync/`（下称「方案目录」）。
3. 运行测试（唯一入口，纯标准库，无第三方依赖）：
   ```bash
   python3 tests/run_tests.py
   ```
   成功判据：退出码 0，且 `reports/test-report.json` 的 `totals.failed == totals.error == 0`。
4. 行尾约定：仓库统一 LF（见根级 `.gitattributes`）。若在 Windows 编辑，确保保存为 UTF-8 + LF。

## 2. 路径规则（可移植性硬规则）

1. 相对路径基准：**方案目录** `solutions/repo-mirror-sync/`。脚本统一用
   `Path(__file__).resolve().parents[1]` 自定位，禁止 `os.getcwd()` 依赖。
2. 分层基准：
   - 仓库根级文件（`AGENTS.md`、`README.md`、`.gitignore`、`.gitattributes`）在方案目录的 `../../`；
   - 方案内文件（`docs/`、`config/`、`tools/`、`tests/`、`reports/`、`docker/`、`.github/workflows/`）直接相对方案目录。
3. 禁止出现的内容：盘符（`D:\`、`C:\`）、`/Users/<名>`、`/home/<具体用户名>`、
   `C:\Users\zeek.zhao.ROLLINGWIRELESS\...` 等任何机器特定路径。参考材料路径只允许出现在
   `docs/01` §2 的「来源记录」里，且仅作为历史说明，代码永不引用。
4. 输出目录：`out/`（运行产物，不入库）；临时脚本：`local/`（不入库，7 天过期）。

## 3. 硬性约束（违反即返工，与根级 AGENTS.md 一致）

1. **脚本边界**：所有脚本必须位于仓库工作区内；禁止写仓库外路径。
2. **策略唯一来源**：体积阈值、扫描频率、请求上限、选举规则只在 `config/scan.yaml`
   与 `config/policy.yaml`；代码禁止硬编码（尤其禁止 `5 GB`、`4 GB`、`200 次请求`）。
3. **选举规则唯一实现**：同名路径裁决只允许调用 `tools/overlay.py` 读
   `config/policy.yaml` 的 `overlay.precedence` / `overlay.path_rules`；禁止第二套裁决逻辑。
4. **API 配额**：调 GitHub API 必须受 `scan.max_requests_per_run` 约束并支持 cursor 续跑；
   先比 `head_sha` 再算体积；token 走环境变量（如 `GH_TOKEN`、`AGE_KEY`），禁止入库与写日志。
5. **诚实性**：未执行的动作只能写「待执行」；`local/` 内容不得称为「已交付」；需求方未确认的决策标「待确认」。
6. **临时脚本治理**：`local/YYYYMMDD-<主题>.<ext>`，7 天后删除；转正式须改写进 `tools/`。
7. **文档纪律**：改 FR/NFR/ADR/策略 = 重大变更（先文档后实现）；所有文档改动追加修订历史（SemVer）；
   实现改动映射到 `docs/03-需求规格.md` 的 FR/NFR 编号。

## 4. 当前进度（接手前先读这一节）

| 阶段 | 状态 | 说明 |
|---|---|---|
| 0 规划 | ✅ 已完成 | docs/01~04 四份 ISO 文档 + config 双 YAML + 本 AGENT.md + manifest.yaml |
| 基础库 | ✅ 已完成 | tools/：yaml_lite、policy、budget、overlay、packing（纯标准库） |
| 测试 | ✅ 已完成 | tests/ 入口 `python3 tests/run_tests.py`、报告 `reports/`；BDD 场景（docs/05）随套件执行 |
| 1 扫描 | ✅ 已完成（M1） | `tools/scan_inventory.py`（14 字段清单、sha 跳过、配额+cursor、oversized；SC-M1-01~07 绿） |
| 2 构建块 | ✅ 已完成（M2，静态结构） | `docker/*.Dockerfile`×3、`.github/workflows/*`×3（SC-M2-01~04 绿；实际 Docker 构建/CI 运行待 Linux 阶段 4，AGENTS §3.5） |
| 3 求解 | ✅ 已完成（M3） | `tools/plan.py`（组合选块+FFD 装箱+超预算降级 sparse；SC-M3-01~05 绿） |
| 4 融合校验 | ✅ 已完成（M4） | `tools/merge_guard.py`（选举规则唯一入口=tools/overlay.py + lowerdir ≤8 校验；SC-M4-01~04 绿） |
| 5 告警 | ✅ 已完成（M5） | `tools/alert.py`（四类事件白名单+双通道渲染+按键节流，均取自 policy；SC-M5-01~04 绿） |
| 6 漂移检测 | ✅ 已完成（M6） | `tools/detect_drift.py`（上游 HEAD vs ls-remote 只比 sha、mirror_sha 写回、drift_detected 事件、预算/cursor；SC-M6-01~06 绿） |
| 7 非特权融合校验 | ✅ 已完成（M7） | `tools/fuse_verify.py`（用户态等价校验 harness，复用 overlay.py 裁决、决策表落盘；SC-M7-01~04 绿；ADR-011） |

> 开发方式为 BDD（docs/05 五步法），里程碑与任务清单见 docs/06；
> M0~M5 已在 `dev/repo-mirror-sync` 完成并合回 main（10db421），
> M6 起开发在 `repo-mirror-sync` 分支延续；M7 同分支交付（ADR-011：toolchain 换基 ubuntu:24.04 + 非特权融合校验）。

「待执行」意味着对应文件按 manifest.yaml 标注为 `planned`（测试会校验它**不存在**——
实现某阶段时：先写 feature 场景（红灯），再实现（绿灯），最后把 manifest 条目从
`planned` 改 `delivered` 并同步 docs/06 勾选）。

## 5. 接手第一步（标准动作）

```bash
cd <仓库根>/solutions/repo-mirror-sync
python3 tests/run_tests.py          # 1) 确认全绿，再动手
cat manifest.yaml                   # 2) 看清 delivered / planned 边界
cat docs/01-方案总览.md              # 3) 读懂方案与决策参数 D1~D5
```

然后按 `docs/01` §19 落地阶段表与 `docs/03` §10 阶段验收准则推进下一阶段；
每完成一项，更新 manifest 状态、文档修订历史与 `reports/` 验收记录。

## 6. 关键文档与术语速查

| 想知道什么 | 去哪里 |
|---|---|
| 方案结论、决策参数 D1~D5、示例推演 | `docs/01-方案总览.md` |
| 架构视图、ADR-001~010（含全层加密风险接受） | `docs/02-架构设计.md` |
| FR×23 / NFR×7 / 验收准则 | `docs/03-需求规格.md` |
| 目录/文档/提交/变更流程规范 | `docs/04-仓库规划与流程规范.md` |
| BDD 五步法、场景目录 | `docs/05-BDD总纲与场景目录.md` |
| 里程碑 M0~M7、任务清单、当前进度 | `docs/06-开发计划与里程碑.md` |
| 体积阈值、扫描周期、预算 | `config/scan.yaml` |
| 块定义、组合、加密、选举规则、告警 | `config/policy.yaml` |
| 全部文件清单与状态 | `manifest.yaml` |
| 测试怎么跑、结果在哪 | `tests/run_tests.py`、`reports/test-report.md` |

术语（block/combo/层/前缀融合/扁平融合/选举规则）定义见 `docs/01` §3。

## 修订历史

| 版本 | 日期 | 修订说明 |
|---|---|---|
| 1.0.0 | 2026-11-27 | 首次发布：Linux 目标环境、可移植路径规则、硬性约束、进度表与接手步骤 |
| 1.0.1 | 2026-11-27 | 进度表更新：阶段 1 扫描完成（M1，SC-M1-01~07 绿）；补充 BDD 开发方式与 docs/05/06 索引 |
| 1.0.2 | 2026-11-27 | 进度表更新：阶段 2 构建产物完成（M2，SC-M2-01~04 绿，静态结构校验；实际构建待 Linux） |
| 1.0.3 | 2026-11-27 | 进度表更新：阶段 3 求解器完成（M3，SC-M3-01~05 绿） |
| 1.0.4 | 2026-11-27 | 进度表更新：阶段 4 融合守卫完成（M4，SC-M4-01~04 绿） |
| 1.0.5 | 2026-11-28 | 进度表更新：阶段 5 告警完成（M5，SC-M5-01~04 绿）；M0~M5 全部完成，待合回 main |
| 1.0.6 | 2026-11-28 | 进度表更新：M6 漂移检测完成（`tools/detect_drift.py`，SC-M6-01~06 绿）；开发分支 repo-mirror-sync（本轮补记：该版本修订行在 M6 轮遗漏，见 test-report §12.2 D-25） |
| 1.0.7 | 2026-11-28 | 进度表更新：M7 非特权融合校验完成（`tools/fuse_verify.py`，SC-M7-01~04 绿，ADR-011）；toolchain 换基 ubuntu:24.04 |
