# 语法约定见 docs/05-BDD总纲与场景目录.md；步骤定义见 tests/bdd_steps_dispatch.py
功能: 告警投递网络层与流水线接入（M9 阶段5，tools/notify.py + 三流水线）
  作为平台维护者
  我希望四类告警经 github-issue 与 feishu-webhook 真实投递（凭据仅环境变量注入，IF-5），
  且节流状态跨 CI run 持久化（FR-A1/H10），流水线按白名单事件触发通知
  （纯逻辑仍在 tools/alert.py：不导入网络库；真实 github-issue 投递属本轮实测，
  feishu 真实发送因 FEISHU_WEBHOOK_URL 未提供标注待执行，AGENTS §3.5。）

@SC-M9-01
场景: sender 工厂按环境变量构造且缺凭据即拒绝
  假如 已读取 tools/notify.py 源码
  那么 源码凭据仅取自环境变量
  而且 alert 纯逻辑模块仍不导入网络库
  当 在无凭据环境中构造 github-issue 投递器
  那么 抛出 AlertError
  当 在无凭据环境中构造 feishu 投递器
  那么 抛出 AlertError
  当 注入示例凭据后构造两类投递器
  那么 投递器均为可调用对象

@SC-M9-02
场景: 节流状态落盘且跨实例生效
  假如 准备临时产物目录
  当 节流器在 "0" 秒放行键 "budget_exceeded:scan-run" 并落盘
  当 新节流器从盘加载并在 "100" 秒再次放行同键
  那么 放行结果为 假
  当 新节流器从盘加载并在 "3600" 秒再次放行同键
  那么 放行结果为 真

@SC-M9-03
场景: 告警投递 CLI 端到端（无凭据通道 skipped 且产物落盘）
  假如 准备临时产物目录
  而且 事件文件含 budget_exceeded 事件 主题 "scan-run"
  当 运行告警投递 CLI（无凭据）
  那么 CLI 退出码为 "0"
  而且 投递报告含 "github-issue" 状态 "skipped"
  而且 投递报告含 "feishu-webhook" 状态 "skipped"
  而且 节流存储文件已生成

@SC-M9-04
场景: 三流水线告警与缓存治理接入静态断言
  假如 工作流文件 "scan.yml" 已存在
  而且 工作流文件 "build-block.yml" 已存在
  而且 工作流文件 "verify-fuse.yml" 已存在
  那么 流水线 "scan.yml" 含 "tools/notify.py"
  而且 流水线 "scan.yml" 含 "tools/detect_drift.py"
  而且 流水线 "scan.yml" 含 "alert-events.json"
  而且 流水线 "scan.yml" 含 "drift_events.json"
  而且 流水线 "scan.yml" 含 "secrets.MIRROR_SCAN_TOKEN"
  而且 流水线 "scan.yml" 含 "FEISHU_WEBHOOK_URL: ${{ secrets.FEISHU_WEBHOOK_URL }}"
  而且 流水线 "scan.yml" 含 "if: failure()"
  而且 流水线 "build-block.yml" 含 "tools/cache_gc.py"
  而且 流水线 "verify-fuse.yml" 含 "tools/cache_gc.py"
