# 测试报告 — repo-mirror-sync 方案测试（DSH-PLAN-001~004）

> 测试入口：`python3 tests/run_tests.py`（方案目录相对路径，跨平台，仅标准库）。
> 机读结果：`reports/test-report.json`（每次执行覆盖写入，不入 manifest 校验）。

---

## 1. 概述

- **被测对象**：本方案已交付基础库与配置治理能力（阶段 0 产物）：
  `tools/yaml_lite.py`、`tools/policy.py`、`tools/budget.py`、`tools/overlay.py`、
  `tools/packing.py`，`config/scan.yaml`、`config/policy.yaml`、`manifest.yaml`
  与 `docs/` 文档族。
- **测试目标**：验证配置与确认参数（D1~D5）一致、预算与标签派生正确、
  选举规则与 docs/01 §13.3 一致、FFD 装箱满足 docs/01 §10 约束、清单与文档治理合格。
- **范围外**（未实现未测，诚实性 AGENTS §3.5）：阶段 4~5 的 `merge_guard.py`、
  告警通道；阶段 2 构建产物已于 M2 完成**静态结构**校验（SC-M2-01~04），
  实际 Docker 构建 / CI 运行仍属 Linux 待执行项（见 §7）；
  阶段 1 扫描器（§6）与阶段 3 求解器（§8）已实现并全绿。

## 2. 测试设计

35 个用例，按被测能力分六组（编号写入各用例 docstring 首行）：

| 组 | 文件 | 用例 | 设计依据 |
|---|---|---|---|
| Y 解析器 | `tests/test_yaml_lite.py` | TC-Y1~Y6 | scan/policy 实际语法：嵌套映射、列表、行内字典、注释、引号内 `#`、含冒号取值（`env:AGE_KEY`、`out/inventory.json`）、非法语法显式报错 |
| C 配置确认 | `tests/test_config_validation.py` | TC-C1~C8 | docs/01 §5 决策参数表 D1~D5；ADR-005/006/007/010；AGENTS §3.3（tools/ 禁硬编码策略常量，正则扫描 `4000000000`、`storage_gb: 5`、`every_days: 7` 等模式）；非法策略四形态必须被 `Policy.validate()` 拒绝 |
| B 预算标签 | `tests/test_budget.py` | TC-B1~B4 | docs/01 §8.1 预算公式 `(5−0.4)GB/1.25=3.68GB`；§9.1 size_class 严格不等式边界；D2 确认预算 4.0 GB ≥ 公式值 |
| O 选举融合 | `tests/test_overlay.py` | TC-O1~O7 | docs/01 §13.3 选举规则（D5）；`manifest/**` pin toolchain、`**/.gitmodules` pin self-dev、`**/build.sh` 前缀隔离（含根级命中）；Windows 反斜杠归一；未知层/空层显式报错；H9 lowerdir ≤ 8 |
| P 装箱求解 | `tests/test_packing.py` | TC-P1~P6 | docs/01 §10 FFD 约束（降序、bin ≤ 预算、单块不可跨 job）与 §17 示例；FR-P3/P4（超预算单仓标 oversized 不装箱）；确定性已知解；空输入 |
| M 清单治理 | `tests/test_docs_manifest.py` | TC-M1~M4 | docs/04 §4 文档纪律：manifest 与磁盘一致（delivered 必在、planned 必不在）；编号连续；DSH-PLAN-001~004；头部版本与修订历史末行一致（SemVer） |

设计原则：配置即用例数据（用例读 `config/*.yaml` 而非复写数值，策略变更时用例自动跟随）；
边界值优先（size_class 七点边界、预算上下界、lowerdir 8/9）；错误路径显式断言
（非法语法、未知层、悬空引用、缺失阈值必须抛错而非静默缺省）。

## 3. 执行结果

- **末次执行**：85/85 全部通过（回归 35 项 + BDD 场景 50 项，0 失败 0 错误 0 跳过，见 §6~§15）；
  机读详情见 `reports/test-report.json`（含每用例状态与耗时）。
- **执行环境**：Python 标准库 unittest；Windows 开发机与 Linux 目标服务器
  均可运行（无第三方依赖、路径自定位、统一 LF 行尾）。
- **首轮执行发现并已修复的缺陷**（诚实记录）：

| # | 缺陷 | 修复 |
|---|---|---|
| D-1 | `tools/yaml_lite.py` `_KV_RE` 漏写捕获组，解析任意键值对即抛 `IndexError: no such group` | 改为双捕获组（键允许引号形态），`_split_kv` 语义不变 |
| D-2 | 列表项以行内字典 `{ path: … }` 书写时被误判为 `key: value`，`policy.yaml` `path_rules` 解析损坏 | `_parse_list` 优先识别 `[`/`{` 开头的行内集合 |
| D-3 | `tools/budget.py` 模块 docstring 出现策略常量字面量，违反 AGENTS §3.3 并被 TC-C6 拦截 | docstring 改述口径，删除字面量 |
| D-4 | `**/build.sh` 在 fnmatch 语义下不命中根级 `build.sh`，与 gitignore 意图不符 | `match_rule` 对 `**/` 前缀追加「任意层级含根」匹配 |
| D-5 | TC-P4 用例 id 重复、TC-P5 期望分组写错（期望为用例错误，非实现错误） | 修正用例：id 唯一化；期望改为 FFD 实际解 `[9,1]+[5]` |

## 4. docs/01 §17 示例分组与 FFD 可行解的差异说明

docs/01 §17 端到端示例中「self + edge 同箱」为**示意分组**；FFD 按 size_class
降序实际产出 **[k8s] + [self, edge]**（k8s 2.6GB 独占一箱，self 1.8GB 与
edge 0.2GB 合箱 2.0GB）。两种分组均为满足「每 job ≤ 4.0 GB、合计 4.6 GB →
2 个 job」的可行解；TC-P1 只断言可行解约束（箱数 ≥ 2、各箱 ≤ 预算、全覆盖
不重复、无 oversized），不断言具体分组，与 FR-P3「FFD 或给差距说明」一致。

## 5. 结论与待执行事项

1. **结论**：阶段 0（规划 + 基础库 + 配置治理 + 文档/清单纪律）与阶段 1~5 全部
   里程碑（M1 扫描器 SC-M1-01~07、M2 构建产物静态结构 SC-M2-01~04、M3 求解器
   SC-M3-01~05、M4 融合守卫 SC-M4-01~04、M5 告警 SC-M5-01~04）、阶段 3 遗留项
   M6 漂移检测（SC-M6-01~06）、阶段 4 补充 M7 非特权融合校验（SC-M7-01~04）
   与 M8 CI 触发及还原验证（SC-M1-08 回归+CI 实测 V16~V18+还原 T1~T7）
   测试目标全部达成；
   十轮共发现 24 项缺陷（D-1~D-24）、1 项治理漏项补记（AGENT.md 修订历史缺 1.0.6
   行，见 §12.2 D-25）、M8 轮 6 项缺陷/平台约束（F-4~F-9，编号沿用验收记录，见 §13.2）
   与 M9 轮 5 项缺陷/治理漏项（F-10~F-14，见 §14.2），已全部修复或缓解并回归通过。
2. **待执行**（未实现未测，属实际构建/CI 运行，见 docs/06 §4 与 docs/03 §10）：
   M2 产物的实际 Docker 构建、Actions 触发与融合挂载、告警通道真实投递
   须在 Linux 服务器执行；各里程碑完成后按 docs/03 §10 验收准则补充场景并更新本报告。

## 6. M1 轮补充（BDD 场景，1.0.1）

- **新增**：BDD 场景 SC-M1-01~07（`features/scan_inventory.feature`，中文 Gherkin，
  步骤定义 `tests/bdd_steps_scan.py`，经 `tests/test_bdd_features.py` 桥接进统一套件），
  覆盖扫描器 FR-S1~S5：14 字段记录、sha 未变跳过、配额耗尽 cursor、续跑补齐、
  oversized 标记、out/ 双格式落盘、token/键名不泄漏。
- **执行结果**：回归 35 项 + 场景 7 项 = **42/42 通过**（0 失败 0 错误 0 跳过）。
- **本轮红灯发现并已修复的缺陷**（BDD「先场景后实现」如实记录）：

| # | 缺陷 | 修复 |
|---|---|---|
| D-6 | `tests/bdd_runner.py` 不认「功能:」后的自由叙述行，整个 BDD 套件加载失败 | `parse_feature` 允许叙述段（无未闭合场景时的自由文本行） |
| D-7 | TC-M3 动态编号误拼 `DSH-PLAN-01`（文档编号实为三位 `DSH-PLAN-001`） | 改 `%03d` 补零 |
| D-8 | `docs/06` 头部补修订表后文末旧修订节未删，TC-M4 判「末行版本 1.0.0」失败 | 删除文末重复节，改指回文首 |
| D-9 | `tools/scan_inventory.py` 续跑时上轮记录不随行——`write_inventory` 覆盖写会丢失已扫仓库（SC-M1-04 红灯暴露） | `scan()` 返回合并后的完整清单（不在本轮 order 的上轮记录原样随行）；场景改为模拟「首轮中断后的真实状态」 |

## 7. M2 轮补充（构建产物静态结构，1.0.2）

- **新增**：BDD 场景 SC-M2-01~04（`features/docker_artifacts.feature`，步骤定义
  `tests/bdd_steps_docker.py`），覆盖 FR-B1~B4 静态结构约束：
  toolchain digest 固定 + 工具链三件套、块镜像参数化且索引不进继承链、
  融合视图 lowerdir/manifest 软链约定、三工作流结构（cron 与 config 语义一致、
  凭据走环境变量、绑定表、age 全层加密 + sha256 tag）。
- **执行结果**：回归 35 项 + 场景 11 项 = **46/46 通过**（0 失败 0 错误 0 跳过）。
- **诚实边界**：本组用例为**静态结构校验**——实际 Docker 构建、Actions 触发、
  overlay 挂载验收属阶段 4，须在 Linux 服务器执行（AGENTS §3.5）。
- **本轮红灯发现并已修复的缺陷**：

| # | 缺陷 | 修复 |
|---|---|---|
| D-10 | `tests/bdd_steps_docker.py` `then_no_latest` 无条件访问 `ctx["workflows"]`，纯 Dockerfile 场景抛 `KeyError`（步骤定义缺陷，非实现缺陷） | 改 `ctx.get("workflows", {})` |

## 8. M3 轮补充（组合求解器，1.0.3）

- **新增**：BDD 场景 SC-M3-01~05（`features/plan.feature`，步骤定义
  `tests/bdd_steps_plan.py`），覆盖 FR-P1~P5：标签/topics 正交选块、
  FFD 装箱各 job ≤ 确认预算、单块不跨 job、超预算单仓降级 sparse
  （`--filter=blob:none --depth=1`）、plan.json 归档（generated/algo_version/
  inventory_snapshot/jobs）与同输入可复现、未知组合显式报错（PolicyError）。
- **执行结果**：回归 35 项 + 场景 16 项 = **51/51 通过**（0 失败 0 错误 0 跳过）。
- **诚实边界**：求解器为纯计算模块（无网络层，FR-P2 先计划后拉取）；
  plan.json 实际落盘 `out/`（不入库）；对接 inventory.json 全链路属阶段 4~5 集成。
- **本轮红灯发现并已修复的缺陷**：

| # | 缺陷 | 修复 |
|---|---|---|
| D-11 | `tools/plan.py` 与步骤定义对 `load_policy()` 返回值做二次 `Policy()` 包装，抛 `AttributeError: 'Policy' object has no attribute 'get'` | `load_policy` 已返回 Policy 实例（含结构校验），删除双重包装 |

## 9. M4 轮补充（融合守卫，1.0.4）

- **新增**：BDD 场景 SC-M4-01~04（`features/merge_guard.feature`，步骤定义
  `tests/bdd_steps_guard.py`），覆盖 FR-F1~F3：同名路径裁决与 overlay 一致
  （keep/pin 且 path_rules 压倒 precedence）、`**/build.sh` isolate 前缀隔离
  不产生胜出层（H6）、层数>8 建议两级融合且上限取自 policy（FR-F1/H9）、
  守卫源码静态断言委托 `tools.overlay.OverlayResolver` 且无第二套裁决表
  （FR-F3/AGENTS §3.6）。
- **执行结果**：回归 35 项 + 场景 20 项 = **55/55 通过**（0 失败 0 错误 0 跳过）。
- **诚实边界**：守卫为纯计算模块（不挂载、不联网）；两级融合仅产出建议，
  实际两级挂载属 Linux 阶段 4 验证。
- **本轮红灯发现并已修复的缺陷**（均为场景/步骤语法层，实现零改动）：

| # | 缺陷 | 修复 |
|---|---|---|
| D-12 | feature 首行使用功能级 tag「@M4 融合守卫」，运行器仅支持场景级 tag → BDD 套件加载失败 | 删除功能级 tag 行 |
| D-13 | feature 使用「背景:」块，运行器语法（docs/05）不含该关键字 → 「步骤出现在场景之外」 | 前置步骤内联到每个场景 |
| D-14 | 场景缺编号 tag 行（`@SC-M4-…`）→ 「场景缺少编号 tag」 | 每个场景补 tag 行 |
| D-15 | 「而且」后无空格，不满足运行器 `而且\s+` 关键字切分 → 「无法识别的行」 | 补空格（6 处） |
| D-16 | 步骤正则未容忍「为/路径」后的空格（6 个模式全匹配失败）→ 「无匹配步骤定义」 | 统一加 `\s*` |

## 10. M5 轮补充（告警，1.0.5）

- **新增**：BDD 场景 SC-M5-01~04（`features/alert.feature`，步骤定义
  `tests/bdd_steps_alert.py`），覆盖 FR-A1/NFR-6/H10：四类事件白名单生成
  payload 且未知类型拒绝、估算/实测双数成对校验（NFR-6）、节流窗口取自
  policy（1h=3600s 边界：3599s 抑制/3600s 放行）且按键独立、双通道渲染
  （github-issue 标题/标签、feishu 文本内容）且渲染结果不含凭据字段、
  源码静态断言（事件白名单字面量/节流时长常量零硬编码、不导入网络库、
  引用策略加载）。
- **执行结果**：回归 35 项 + 场景 24 项 = **59/59 通过**（0 失败 0 错误 0 跳过）。
- **诚实边界**：alert.py 为纯逻辑模块（不联网、默认不发送，dispatch 无 sender
  即 skipped）；真实 GitHub Issue/飞书 webhook 投递属 Linux 阶段 5 验证。
- **本轮红灯发现并已修复的缺陷**：

| # | 缺陷 | 修复 |
|---|---|---|
| D-17 | feature 场景缺编号 tag 行（`@SC-M5-…`）→ 「场景缺少编号 tag」 | 每个场景补 tag 行 |
| D-18 | 「那么」后无空格（那么抛出/那么放行，共 6 行）→ 「无法识别的行」 | 补空格 |
| D-19 | `load_alert_policy(None)` 把缺省 None 直接传给 `load_policy` → 「策略文件不存在：None\\config\policy.yaml」 | 缺省时按模块位置解析方案目录（`tools/` 上一级，仓库相对路径） |
| D-20 | 「再次放行同键」无匹配步骤定义 | 新增步骤并记录 `last_key`/`first_key` |
| D-21 | SC-M5-04 given 仅读源码未加载策略 → 断言 `KeyError: 'rules'` | given 同时 `load_alert_policy()` |

## 11. M6 轮补充（漂移检测，1.0.6）

- **新增**：BDD 场景 SC-M6-01~06（`features/detect_drift.feature`，步骤定义
  `tests/bdd_steps_drift.py`），覆盖 FR-D1/IF-2（docs/01 §12.2）：
  清单与 mirror 一致零事件且写回观测 sha、mirror 回退一个提交报漂移
  （FR-D1 验收行为，summary 提示 `repo sync --force-sync`）、mirror 领先上游
  同样判漂移（只比 sha 不比方向）、请求预算耗尽保存游标且未检仓库原样随行、
  事件过 policy 告警白名单构建 payload（dedup_key=`drift_detected:<repo>`，
  通道取自策略）、mirror 探测走 git 协议不消耗请求预算（IF-2，probes=1）。
- **执行结果**：回归 35 项 + 场景 30 项 = **65/65 通过**（0 失败 0 错误 0 跳过）。
- **诚实边界**：detect_drift 为纯逻辑模块（上游 HEAD 与 ls-remote 探测均经
  注入夹具 FakeUpstream/FakeMirrorProber 覆盖）；真实 ls-remote 端到端与
  「手动回退 mirror 一个 commit」实测属真实 mirror/Linux 环境待执行项。
- **本轮红灯发现并已修复的缺陷**：

| # | 缺陷 | 修复 |
|---|---|---|
| D-22 | `tests/test_bdd_features.py` 步骤模块守卫只捕 `ModuleNotFoundError`，而 `from tools import detect_drift` 在包缺子模块时抛 `ImportError`（cannot import name）→ 整套件加载失败而非逐场景红灯 | 守卫放宽为 `except ImportError`（`ModuleNotFoundError` 为其子类，向后兼容） |

## 12. M7 轮补充（非特权融合校验，1.0.7）

### 12.1 新增场景（SC-M7-01~04，features/fuse_verify.feature）

| 编号 | 能力 | 需求映射 |
|---|---|---|
| SC-M7-01 | 同名无规则路径按层序 keep，低层内容不泄漏 | FR-F1、ADR-011 |
| SC-M7-02 | pin（manifest/**、**/.gitmodules）与 isolate（**/build.sh）用户态物化 | FR-F2~F3、H6 |
| SC-M7-03 | 零特权依赖（无子进程/FUSE/挂载 token）且决策表落盘 | FR-F1~F3、ADR-011 |
| SC-M7-04 | 决策表与 overlay.py 独立重算同源、lowerdir 上限校验 | FR-F1~F3、H9 |

### 12.2 本轮缺陷与治理漏项

| 编号 | 现象 | 根因 | 修复 |
|---|---|---|---|
| D-23 | SC-M7-02 首轮失败：断言 k8s 层缺隔离副本 | 步骤对全部声明层断言副本，而 isolate 只属在场层（merge_guard 语义） | 步骤改为仅对含该路径的层断言 |
| D-24 | SC-M7-03 红灯阶段场景 KeyError | 场景缺「准备两层夹具」given（源码静态断言场景仍需运行实例） | 场景补 given 夹具 |
| D-25 | M6 轮方案 AGENT.md 修订历史漏加 1.0.6 行（人工治理漏项，本轮终检发现） | 修订历史完整性无自动化校验 | 本轮补记 1.0.6/1.0.7 两行；可在 TC-M1 族增修订历史完整性断言（待办） |

### 12.3 实测佐证（非 CI 部分）

- 真实 ubuntu:24.04 基座构建与块/融合镜像构建、fail-fast 双路径、运行时约定核验：
  V10~V15 见 `reports/acceptance-20261128-ubuntu24-fuse-verify.md`（digest 注入实测，非 stub）。
- ~~CI 运行（Actions 三工作流触发）仍属待执行~~ 已于 M8 轮完成（V16~V18，见 §13.3）。

## 13. M8 轮补充（CI 触发与还原验证，1.0.8）

### 13.1 场景

| 编号 | 内容 | 映射 | 结果 |
|---|---|---|---|
| SC-M1-08 | 元数据缺 head_sha 时以引用探测结果回填（F-9 回归） | FR-S3 | 绿 |

### 13.2 缺陷与平台约束（F 编号沿用验收记录）

| 编号 | 现象 | 处置 | 状态 |
|---|---|---|---|
| F-4 | workflow_dispatch 需工作流存在于默认分支（404） | push 触发（分支+paths）缓解；dispatch 待合 main | 缓解（约束留存） |
| F-5 | scan 失败：No module named 'tools' | 步骤加 PYTHONPATH=. | 已修复 |
| F-6 | artifact name 非法（${BLOCK_ID:-x}） | 改 GitHub 表达式兜底 | 已修复 |
| F-7 | 层树缺 scripts/build.sh（块内容在 /opt/block） | runner 侧合成 isolate 触发文件 | 已修复 |
| F-7b | verify-fuse startup_failure（YAML 缩进） | 块标量基准重排 | 已修复 |
| F-8 | MIRROR_SCAN_TOKEN 401（密钥值曾被视图掩码串污染） | secrets 重写+scan.yml 注记 | 已修复 |
| F-9 | 首次真实扫描 head_sha=""且 scan_status=ok（假 fetcher 掩盖真实适配层空串） | 探测值回填+SC-M1-08 回归；run4 复核 head_sha=d102e6f4…（main 真实 HEAD） | 已修复 |

### 13.3 实测佐证（CI 部分）

- 三流水线 push 触发全绿与制品本地还原（T1~T7：sha256/解密/加载/内容一致/融合复算/消费侧挂载自验/schema）见
  `reports/acceptance-20261128-ci-restore.md`（V16~V18 + T1~T7）；
- 离线回归 70/70（35 单测 + 35 BDD 场景）。

## 14. M9 轮补充（告警与治理，1.0.9）

### 14.1 场景

| 场景 | 能力 | 结果 |
|---|---|---|
| SC-M9-01~04（features/alert_dispatch.feature） | sender 工厂凭据拒绝与 alert 纯度、节流落盘跨实例、CLI 无凭据 skipped 降级与产物落盘、三流水线接入静态断言 | 绿 |
| SC-M9-05~08（features/cache_gc.feature） | 缓存 LRU（8 块×2 版本）、预算超限 cache_pressure 双数成对、.age 加密层豁免、limits 唯一出处静态断言 | 绿 |
| SC-M1-09（features/scan_inventory.feature） | GH_TOKENS 逗号分隔轮转唯一入口 + GH_TOKEN 回退 + 无 token 字面量（FR-A3） | 绿 |

回归：85/85 全绿（35 单测 + 50 BDD 场景，0 失败 0 错误）。

### 14.2 缺陷（F 编号沿用验收记录）

| 编号 | 缺陷 | 根因 | 修复 |
|---|---|---|---|
| F-10 | notify 调 render_all(payload, rules) 抛 TypeError | render_all 契约为单参（payload 自带 channels） | 改 render_all(payload)；红灯转绿前发现 |
| F-11 | dispatch 步骤 ctx 键名与 alert 步骤模块约定不一致（error/allowed） | 新步骤模块未对齐既有约定 | 键名统一 error/allowed |
| F-12 | bdd_steps_cache ROOT 未定义 + _synth size=100 使 SC-M9-06 预算场景不成立 | 步骤落盘笔误（1000 字节意图写为 100） | 改 _ROOT + size=1000（4000>1000 预算成立） |
| F-13 | cache_gc 文件级删除残留空目录壳（b01/b02 目录仍在） | clean 契约未含目录壳回收 | 整块删除后 rmdir 空壳（复验 b03~b10 剩余） |
| F-14 | docs/04 §3.1 目录树 toolchain 注释仍写 overlayfs（M7 ADR-011 治理漏项） | M7 轮文档同步未覆盖目录树注释行 | 本轮修正并补记 |
| F-15 | 验收记录凭据行误含真实 token（运行时占位符被宿主替换写入文档；M9 轮 test-report 漏登记，本轮补记） | heredoc 直写占位符文本触发替换机制 | Push Protection 拦截（未进远端）；改描述性文案+全库扫描确认仅 1 处；教训：入库文档禁写占位符形态文本 |
| F-16 | CI 漂移检测步骤 exit 1（run 46054269814） | 步骤漏注 GH_TOKEN，make_github_fetcher 拒绝无凭据调 API | 补 secrets 注入（b38aaf5）；本地真实形态冒烟+CI 复跑 46055114527 全绿，mirror_sha 首检基线写回 |

### 14.3 实测佐证

- github-issue 真发验收（FR-A1）：notify.py 内联 budget_exceeded 事件 → Issue #8（[mirror-sync][budget_exceeded] scan-run，双标签）一分钟内送达；同键立即重发 → throttled（1h 窗口抑制）；验收产物已评论并关闭（评论 201/关闭 200）；
- 缓存治理实测（FR-A2）：cache_gc CLI 合成 10 块×2 版本 → 块级 LRU 删 b01/b02（4 行日志）+ 空目录壳回收（剩余 b03~b10）；目录缺失 → 零清理审计通过；
- GH_TOKENS 轮转入口真实冒烟（FR-A3）：单枚 token 真实扫描 3 请求完成，head_sha=d102e6f4d72decc92c579c6eaf737f15b4a9c174（main HEAD）且未超限不产 alert-events.json；
- feishu-webhook：无 URL 通道 skipped 降级符合设计，真实发送待 FEISHU_WEBHOOK_URL 提供（**待执行**）；
- CI 端到端告警（M10 收口）：scan run 46054269814 真实失败 → 失败告警步骤 `scan_error:scanner → sent` 真发（FR-A1 无需人为制造）；F-16 修复后 run 46055114527 全绿，制品 alert-dispatch.json/inventory.json（head_sha==mirror_sha 首检基线写回）；
- GH_TOKENS 轮转 stub 离线实证：bad→403 依序轮转 good→200、耗尽 HTTPError 403 冒泡、GH_TOKENS 缺省回退 GH_TOKEN 单枚，三场景全过；
- 详见 `reports/acceptance-20261128-alert-dispatch.md`（E2E-1~11）。

## 15. M10 轮补充（合并裁决，FR-D2/Issue #3）

### 15.1 场景与红灯

| 场景 | 覆盖 | 结果 |
|---|---|---|
| SC-M10-01 | 基线一致 → drop 只记合并日志 | 绿 |
| SC-M10-02 | 基线不一致 → quarantine + published=False + manual_review | 绿 |
| SC-M10-03 | 顺序固定 order=[manifest_rebuild, drift_fetch] | 绿 |
| SC-M10-04 | 同路径同内容 → hardlink 去重计划 | 绿 |
| SC-M10-05 | 异内容 → 委托融合守卫（§13.2 矩阵）与独立重算一致 | 绿 |
| SC-M10-06 | 隔离区 notice.json（manual_review/published）落盘 | 绿 |

红灯：SC-M10-01 NotImplementedError（80=79+1 红）；中文 Gherkin 关键字后缺空格致 23 行不匹配（教训 D-27：关键字与内容间必须有空格）。

### 15.2 缺陷登记

| 编号 | 现象 | 根因 | 处置 |
|---|---|---|---|
| F-17 | CLI 静默退出无产物（E2E-12 首跑） | merge_arbitration.py 缺 `if __name__ == "__main__"` 入口，BDD 未覆盖 CLI 入口 | 补入口；E2E-12 复跑通过 |
| F-18 | suite 80=79+1（六场景仅产出 1 个用例，29 步串联假绿灯） | feature 场景缺独立 `@SC-` tag 行（SC 编号误写入标题行，违反 D-12/D-14） | 按规范格式补 6 个 tag 行；85/85 真绿灯（六场景独立执行仍全过，实现本身正确） |
| D-28 | dedupe 委托守卫抛 DecideError「在场层不在 precedence 中」 | 合并域称谓 [manifest,fetch] 非 precedence 层名 | 引入 ARBITRATION_LAYERS=(toolchain,self-dev) 映射后委托；独立重算步骤同步引用 |

### 15.3 实测佐证

- E2E-12 CLI 冒烟：drop 路径追加 merge-log.json（无隔离区）；quarantine 路径落 `quarantine/acme/a/{sha12}/notice.json`（manual_review=true、published=false）；
- 85/85 全绿（35 单测 + 50 BDD 场景）；FR-D1 全链已由 CI 真实跑通（head_sha==mirror_sha 首检基线写回，run 46055114527）；
- Issue #3（FR-D2 合并裁决）随本轮交付关闭评论。

## 16. 治理增强（D-25 待办划账）

- `tests/test_docs_manifest.py` 新增 **TC-M5**：AGENT.md / reports/test-report.md / 仓库根 README.md 三份治理文档的修订历史表必须存在、版本单调递增且末行为最新；AGENT.md 进度表行数与 docs/06 里程碑表行数强制同步（防「内容已更新而修订行漏加」类治理漏项复发，如 D-25 的 1.0.6 漏记与本轮 §15 修订行笔误）；
- 勘误：§15 修订行「M11 补充」→「M10 补充」（笔误，见 1.0.12 修订行）。

## 17. F-4 收口（方案合入 main 后）

- 快照同步（97b53ea）+ 本地合并推 main（03e838e，合并提交身份 zeek.zhao）+ PR #10 标记 merged；
- 三份 repo-mirror-sync-* 工作流注册 state=active；workflow_dispatch 实测三份全部 success（scan run#7 / build-block run#4 / verify-fuse run#5，ref=main）；
- schedule cron 已注册（scan.yml "17 3 */7 * *"），首次实际触发待观察；详见 `reports/acceptance-20261128-f4-closeout.md`（W1~W5/V19~V21）；Issue #7 划账关闭。

## 修订历史

| 版本 | 日期 | 修订说明 |
|---|---|---|
| 1.0.0 | 2026-11-27 | 首次发布：35 用例设计与执行结果（35/35 通过），含首轮 5 项缺陷修复记录与 §17 分组差异说明 |
| 1.0.1 | 2026-11-27 | M1 补充：BDD 场景 SC-M1-01~07（FR-S1~S5），42/42 全绿；红灯修复记录 D-6~D-9 |
| 1.0.2 | 2026-11-27 | M2 补充：BDD 场景 SC-M2-01~04（FR-B1~B4 静态结构），46/46 全绿；红灯修复记录 D-10；待执行项收敛至阶段 3~5 与实际构建 |
| 1.0.3 | 2026-11-27 | M3 补充：BDD 场景 SC-M3-01~05（FR-P1~P5），51/51 全绿；红灯修复记录 D-11；待执行项收敛至阶段 4~5 与实际构建 |
| 1.0.4 | 2026-11-27 | M4 补充：BDD 场景 SC-M4-01~04（FR-F1~F3），55/55 全绿；红灯修复记录 D-12~D-16（场景/步骤语法层）；待执行项收敛至阶段 5 与实际构建 |
| 1.0.5 | 2026-11-28 | M5 补充：BDD 场景 SC-M5-01~04（FR-A1/NFR-6/H10），59/59 全绿；红灯修复记录 D-17~D-21；M0~M5 全部达成，待执行项收敛至 Linux 实际构建/投递 |
| 1.0.6 | 2026-11-28 | M6 补充：BDD 场景 SC-M6-01~06（FR-D1/IF-2），65/65 全绿；红灯修复记录 D-22；待执行项收敛至真实 mirror/Linux 端到端实测与 FR-D2 合并裁决 |
| 1.0.7 | 2026-11-28 | M7 补充：BDD 场景 SC-M7-01~04（FR-F1~F3/ADR-011），69/69 全绿；缺陷 D-23~D-24 与治理漏项 D-25；实测佐证 ubuntu:24.04 基座与 harness 非特权端到端（验收记录 20261128-ubuntu24-fuse-verify） |
| 1.0.8 | 2026-11-28 | M8 补充：SC-M1-08（F-9 回归）70/70 全绿；CI 实测 V16~V18 与还原 T1~T7（验收记录 20261128-ci-restore）；缺陷/约束 F-4~F-9 登记（§13） |
| 1.0.9 | 2026-11-28 | M9 补充：SC-M9-01~08（告警投递网络层+缓存 LRU）与 SC-M1-09（GH_TOKENS 轮转）79/79 全绿；实测 E2E-1~8（github-issue 真发 Issue #8+节流抑制、cache LRU、GH_TOKENS 冒烟，验收记录 20261128-alert-dispatch）；缺陷/治理漏项 F-10~F-14 登记（§14） |
| 1.0.10 | 2026-11-28 | M10 收口补充：CI 端到端告警达成与 GH_TOKENS 轮转 stub 实证（§14.3）；F-15 补记+F-16 登记（§14.2） |
| 1.0.11 | 2026-11-28 | M10 补充：SC-M10-01~06（合并裁决 FR-D2）85/85 全绿（§15）；E2E-12 CLI 冒烟；F-17/F-18/D-28 登记；Issue #3 收口 |
| 1.0.12 | 2026-11-28 | 治理增强（D-25 待办划账）：TC-M5 治理文档修订历史完整性断言（§16）；勘误 §15 修订行 M11→M10 |
| 1.0.13 | 2026-11-28 | F-4 收口：方案合入 main（03e838e）后三流水线注册 active+dispatch 实测全绿（§17） |
