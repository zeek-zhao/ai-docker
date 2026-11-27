功能: 融合守卫 merge_guard
  作为镜像融合流程的守门人，
  我希望同名路径裁决与融合层数约束都经由唯一守卫入口完成，
  以便选举规则与层数上限只来自 config/policy.yaml 与 tools/overlay.py
  （FR-F1~FR-F3；ADR-005、ADR-001/ADR-008；AGENTS §3.6）。
  本组场景为纯计算守卫：不执行挂载、不访问网络（FR-P2 先计划后拉取）。
  每个场景的前置条件：策略文件已加载并注入守卫。

  @SC-M4-01
  场景: 同名路径冲突裁决与 overlay 一致且 path_rules 压倒优先级
    假如 策略文件已加载并注入守卫
    假设 以下层在场：self-dev、k8s、edge
    当 守卫裁决路径 "etc/config.yaml"
    那么 裁决 action 为 keep
    而且 胜出层为 self-dev
    而且 被遮蔽层为 k8s、edge
    假设 路径 "manifest/toolchain.lock" 在场层为 k8s、edge
    当 守卫裁决该路径
    那么 裁决 action 为 pin
    而且 胜出层为 toolchain
    假设 路径 ".gitmodules" 在场层为 toolchain、self-dev
    当 守卫裁决该路径
    那么 裁决 action 为 pin
    而且 胜出层为 self-dev

  @SC-M4-02
  场景: build.sh 前缀隔离且不产生胜出层
    假如 策略文件已加载并注入守卫
    假设 以下层在场：self-dev、k8s
    当 守卫裁决路径 "scripts/build.sh"
    那么 裁决 action 为 isolate
    而且 不产生胜出层
    而且 隔离建议包含独立前缀 "/mnt/self-dev/scripts/build.sh" 与 "/mnt/k8s/scripts/build.sh"

  @SC-M4-03
  场景: 融合层数超上限建议两级融合且上限取自策略
    假如 策略文件已加载并注入守卫
    当 执行层数守卫，层数为 9
    那么 层数守卫 ok 为 假
    而且 two_stage 为 真
    而且 max_lowerdir 取自策略为 8
    而且 建议包含 "两级融合"
    当 执行层数守卫，层数为 8
    那么 层数守卫 ok 为 真
    而且 two_stage 为 假

  @SC-M4-04
  场景: 守卫实现委托 overlay 不含第二套裁决逻辑
    假如 策略文件已加载并注入守卫
    当 审查 tools/merge_guard.py 源码
    那么 源码从 tools/overlay 导入 OverlayResolver
    而且 源码不含独立裁决表赋值（precedence/path_rules）
