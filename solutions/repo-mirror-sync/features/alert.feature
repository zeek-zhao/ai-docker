# 语法约定见 docs/05-BDD总纲与场景目录.md；步骤定义见 tests/bdd_steps_alert.py
功能: 告警 payload 生成与节流状态机（M5，tools/alert.py）
  作为平台维护者
  我希望四类告警按 config/policy.yaml 白名单生成可行动 payload，并按「事件类型+主题」节流
  以便防告警风暴（H10）且体积类通知同时携带估算/实测双数（NFR-6）
  （FR-A1；ADR-010。事件白名单与节流时长唯一出处为 config/policy.yaml；
  本模块为纯逻辑：不导入网络库、默认不发送，实际投递由调用方注入 sender
  薄封装，真实通道连通性属 Linux 阶段 5 验证，AGENTS §3.5。）

@SC-M5-01
场景: 四类事件生成 payload，未知事件与不成对双数被拒绝
  假如 策略文件已加载并构建告警器
  当 提交事件 "budget_exceeded" 主题 "self-dev" 估算 "1000" 实测 "1200"
  那么 payload kind 为 "budget_exceeded"
  而且 payload 去重键为 "budget_exceeded:self-dev"
  而且 payload 含估算实测双数
  当 提交事件 "budget_exceeded" 主题 "self-dev" 估算 "1000" 实测 "-"
  那么 抛出 AlertError
  当 提交事件 "scan_error" 主题 "scanner" 估算 "-" 实测 "-"
  那么 payload kind 为 "scan_error"
  当 提交未知事件 "unknown_kind"
  那么 抛出 AlertError

@SC-M5-02
场景: 节流窗口取自策略并按键独立生效
  假如 策略文件已加载并构建告警器
  那么 节流窗口取自策略为 "3600" 秒
  当 节流器在 "0" 秒放行键 "drift_detected:acme/a"
  那么 放行结果为 真
  当 节流器在 "3599" 秒再次放行同键
  那么 放行结果为 假
  当 节流器在 "3599" 秒放行键 "drift_detected:acme/b"
  那么 放行结果为 真
  当 节流器在 "3600" 秒再次放行首键
  那么 放行结果为 真

@SC-M5-03
场景: payload 渲染为两类通道且不含凭据
  假如 策略文件已加载并构建告警器
  当 渲染事件 "cache_pressure" 主题 "cache" 为全部通道
  那么 渲染结果含 "2" 个通道
  而且 github-issue 渲染含标签 "mirror-sync"
  而且 feishu 渲染为文本内容
  而且 渲染结果不含凭据字段

@SC-M5-04
场景: 事件白名单与节流时长唯一出处静态断言
  假如 已读取 tools/alert.py 源码
  那么 源码不含事件白名单字面量
  而且 源码不含硬编码节流时长
  而且 源码不导入网络库
  而且 源码引用策略加载
