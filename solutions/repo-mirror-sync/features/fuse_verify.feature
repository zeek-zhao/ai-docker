@M7
功能: 非特权融合校验（tools/fuse_verify.py 用户态等价，ADR-011）
  作为融合验收的 CI 可执行替代
  无特权条件下完成两级融合语义校验并产出可审计决策表；
  内核 OverlayFS 挂载属消费侧运行时语义（docs/01 §13.1，ADR-011）

  @SC-M7-01
  场景: 同名无规则路径按层序 keep 且低层内容不出现
    假如 准备两层夹具 toolchain 与 self-dev 且同名路径内容不同
    当 运行非特权融合校验
    那么 融合视图中同名路径内容来自 toolchain 层
    而且 决策表对该路径动作记录为 keep
    而且 self-dev 层同名内容不出现在融合视图

  @SC-M7-02
  场景: 策略裁决路径在融合视图按 pin 与 isolate 物化
    假如 准备包含 manifest 索引、gitmodules 与 build 脚本的多层夹具
    当 运行非特权融合校验
    那么 manifest 索引在融合视图内容来自 toolchain 层（pin）
    而且 gitmodules 在融合视图内容来自 self-dev 层（pin）
    而且 build 脚本在融合视图按层前缀隔离且互不覆盖

  @SC-M7-03
  场景: 校验器零特权依赖且决策表落盘
    假如 准备两层夹具 toolchain 与 self-dev 且同名路径内容不同
    而且 已加载 tools/fuse_verify.py 源码
    当 运行非特权融合校验
    那么 实现不调用 mount、FUSE 设备或特权能力
    而且 校验器运行于普通进程且决策表落盘输出目录

  @SC-M7-04
  场景: 决策表与 overlay.py 裁决同源可审计
    假如 准备包含 manifest 索引、gitmodules 与 build 脚本的多层夹具
    当 运行非特权融合校验
    那么 抽样路径决策与 OverlayResolver 独立重算一致
    而且 决策表含 lowerdir 层数与 max_lowerdir 校验结果
