@M10
功能: 合并裁决（阶段 3 补全，docs/01 §12.3；顺序固定，不做「谁后到谁赢」）

@SC-M10-01
场景: 补拉 sha 与 manifest 基线一致时丢弃补拉包只记合并日志
  假如 manifest 指定仓库 "acme/a" 基线 rev "r2"
  而且 漂移补拉包仓库 "acme/a" 补拉 sha "r2"
  当 执行合并裁决
  那么 裁决结果为丢弃补拉包
  而且 合并日志包含仓库 "acme/a" 与补拉 sha "r2"

@SC-M10-02
场景: 补拉 sha 不一致时以 manifest 为准降级隔离区
  假如 manifest 指定仓库 "acme/a" 基线 rev "r2"
  而且 漂移补拉包仓库 "acme/a" 补拉 sha "r1"
  当 执行合并裁决
  那么 裁决结果为降级隔离区
  而且 隔离目录为 "quarantine/acme/a/r1"
  而且 补拉包不进入发布镜像
  而且 隔离结果标记待人工确认

@SC-M10-03
场景: 裁决顺序固定 manifest 重建先于漂移补拉
  假如 manifest 指定仓库 "acme/a" 基线 rev "r2"
  而且 漂移补拉包仓库 "acme/a" 补拉 sha "r1"
  当 执行合并裁决
  那么 处理顺序为 manifest 重建先于漂移补拉

@SC-M10-04
场景: 同路径内容一致时生成硬链接去重计划
  假如 manifest 侧文件 "scripts/build.sh" 内容 "A"
  而且 补拉侧文件 "scripts/build.sh" 内容 "A"
  当 执行内容级去重
  那么 路径 "scripts/build.sh" 裁决为硬链接去重

@SC-M10-05
场景: 同路径内容不一致时委托融合守卫裁决
  假如 manifest 侧文件 "scripts/build.sh" 内容 "A"
  而且 补拉侧文件 "scripts/build.sh" 内容 "B"
  当 执行内容级去重
  那么 路径 "scripts/build.sh" 裁决为隔离各层保留副本
  而且 裁决结果与融合守卫独立重算一致

@SC-M10-06
场景: 隔离区落盘待人工确认清单
  假如 manifest 指定仓库 "acme/a" 基线 rev "r2"
  而且 漂移补拉包仓库 "acme/a" 补拉 sha "r1"
  当 执行合并裁决落盘
  那么 隔离区清单已写入且标记人工确认
