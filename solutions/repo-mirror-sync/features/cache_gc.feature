# 语法约定见 docs/05-BDD总纲与场景目录.md；步骤定义见 tests/bdd_steps_cache.py
功能: 缓存 LRU 治理（M9 阶段5，tools/cache_gc.py，FR-A2/H1/ADR-007）
  作为平台维护者
  我希望缓存按 cache_gb 预算与「最近 N 块 × 2 版本」LRU 规则自动清理并留日志，
  超限触发 cache_pressure 可行动告警，加密层永不进缓存清理范围
  （清理参数唯一出处 config/scan.yaml limits 节，AGENTS §3.3/§3.6。）

@SC-M9-05
场景: LRU 只保留最近 8 块且每块 2 版本
  假如 合成缓存目录含 "10" 块每块 "2" 版本
  当 运行缓存清理（库级 keep_blocks "8" keep_versions "2" 预算充足）
  那么 删除清单含 "b01" 与 "b02"
  而且 保留块数为 "8"
  而且 清理日志有 "4" 行

@SC-M9-06
场景: 预算超限触发 cache_pressure 事件且删除至预算内
  假如 合成缓存目录含 "4" 块每块 "1" 版本
  当 运行缓存清理（库级 预算 "1000" 字节）
  那么 清理结果标记预算超限
  而且 cache_pressure 事件双数成对
  而且 删除后体积在预算内

@SC-M9-07
场景: 加密层不进缓存清理范围（.age 仅告警不删除）
  假如 合成缓存目录含 ".age" 加密残留
  当 运行缓存清理（库级 keep_blocks "8" keep_versions "2" 预算充足）
  那么 加密残留文件仍在缓存目录
  而且 清理日志含加密层告警

@SC-M9-08
场景: 清理参数唯一出处静态断言
  假如 已读取 tools/cache_gc.py 源码
  那么 源码不含保留块数硬编码
  而且 源码引用 limits 配置
  而且 limits 配置含 keep_blocks "8" 与 keep_versions "2"
