@M1
功能: 体积清单扫描（tools/scan_inventory.py）
  作为镜像同步的唯一真相表来源
  扫描器以受控配额产出 docs/01 §7.2 定义的 14 字段 inventory，
  先比 head_sha 再算体积，配额耗尽保存 cursor 可续跑

  @SC-M1-01
  场景: 新仓库扫描产出完整 14 字段记录
    假如 配置加载自 config 且请求上限为 200
    而且 上一轮清单为空
    而且 仓库夹具 "acme/widget" 有 topics [k8s] 标签 [vendor] 头指针 sha111 分支 main 尺寸 2500000KB
    当 执行扫描
    那么 产出记录有 1 条 且消耗请求 3 次
    而且 记录字段集合与 docs/01 §7.2 的 14 字段完全一致
    而且 记录 "acme/widget" 的 size_bytes_est 等于 2560000000

  @SC-M1-02
  场景: head_sha 未变的仓库一次请求即跳过体积计算
    假如 配置加载自 config 且请求上限为 200
    而且 上一轮清单中 "acme/old" 的 head_sha 为 shaA1 分支 main 尺寸 1000KB
    而且 仓库夹具 "acme/old" 有 topics [edge] 标签 [self-dev] 头指针 shaA1 分支 main 尺寸 1000KB
    当 执行扫描
    那么 产出记录有 1 条 且消耗请求 1 次
    而且 记录 "acme/old" 的 head_sha_at 沿用上一轮 且 last_scanned 已刷新

  @SC-M1-03
  场景: 配额耗尽时保存 cursor 中断且不丢失进度
    假如 配置加载自 config 且请求上限为 3
    而且 上一轮清单为空
    而且 仓库夹具 "acme/a" 有 topics [k8s] 标签 [] 头指针 s1 分支 main 尺寸 1000KB
    而且 仓库夹具 "acme/b" 有 topics [edge] 标签 [] 头指针 s2 分支 main 尺寸 1000KB
    而且 仓库夹具 "acme/c" 有 topics [toolchain] 标签 [] 头指针 s3 分支 main 尺寸 1000KB
    当 执行扫描
    那么 扫描未完成
    而且 已产出记录 1 条
    而且 cursor 剩余 ["acme/b", "acme/c"]

  @SC-M1-04
  场景: 凭 cursor 续跑补齐剩余仓库且已扫仓库不丢失
    假如 配置加载自 config 且请求上限为 200
    而且 上一轮清单中 "acme/a" 的 head_sha 为 s1 分支 main 尺寸 1000KB
    而且 仓库夹具 "acme/a" 有 topics [k8s] 标签 [] 头指针 s1 分支 main 尺寸 1000KB
    而且 仓库夹具 "acme/b" 有 topics [edge] 标签 [] 头指针 s2 分支 main 尺寸 1000KB
    而且 仓库夹具 "acme/c" 有 topics [toolchain] 标签 [] 头指针 s3 分支 main 尺寸 1000KB
    当 以剩余 ["acme/b", "acme/c"] 的游标续跑
    那么 扫描完成 且已产出记录 3 条 且游标清空
    而且 记录 "acme/a" 仍在清单中

  @SC-M1-05
  场景: 单仓超确认预算时打 oversized 标记
    假如 配置加载自 config 且请求上限为 200
    而且 上一轮清单为空
    而且 仓库夹具 "acme/kernel" 有 topics [k8s] 标签 [] 头指针 s9 分支 main 尺寸 4500000KB
    当 执行扫描
    那么 记录 "acme/kernel" 的 scan_status 为 oversized
    而且 记录 "acme/kernel" 仍在清单中

  @SC-M1-06
  场景: 清单落盘 out 目录双格式且行数一致
    假如 配置加载自 config 且请求上限为 200
    而且 上一轮清单为空
    而且 仓库夹具 "acme/a" 有 topics [k8s] 标签 [] 头指针 s1 分支 main 尺寸 1000KB
    而且 仓库夹具 "acme/b" 有 topics [edge] 标签 [] 头指针 s2 分支 main 尺寸 2000KB
    当 执行扫描并落盘 out
    那么 out 目录生成 inventory.json 与 inventory.csv
    而且 inventory.json 记录数与 inventory.csv 数据行数一致且为 2

  @SC-M1-07
  场景: token 只走环境变量且绝不写入产物
    假如 配置加载自 config 且请求上限为 200
    而且 上一轮清单为空
    而且 仓库夹具 "acme/a" 有 topics [k8s] 标签 [] 头指针 s1 分支 main 尺寸 1000KB
    当 执行扫描并落盘 out（fetcher 持有示例密钥）
    那么 out 目录产物文本不包含 secret-token-xyz 也不包含 GH_TOKEN 键名

  @SC-M1-08
  场景: 元数据缺 head_sha 时以引用探测结果回填（F-9 回归）
    假如 配置加载自 config 且请求上限为 200
    而且 上一轮清单为空
    而且 仓库夹具 "acme/a" 元数据 head_sha 置空 头指针 s9 分支 main
    当 执行扫描
    那么 扫描完成 且已产出记录 1 条 且游标清空
    而且 记录 "acme/a" 的 head_sha 为 s9
    而且 记录 "acme/a" 的 scan_status 为 ok

  @SC-M1-09
  场景: 多 token 轮转唯一入口静态断言（FR-A3）
    假如 已读取 tools/scan_inventory.py 源码
    那么 源码支持 GH_TOKENS 逗号分隔轮转
    而且 源码保留 GH_TOKEN 单 token 回退
    而且 源码不含 token 字面量
