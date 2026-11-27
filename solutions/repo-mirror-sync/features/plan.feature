@M3
功能: 组合求解器（tools/plan.py：inventory → 组合选块 → FFD 装箱 → plan.json）
  作为镜像同步的计划入口，求解器按 config/policy.yaml 的块/组合定义
  与 config/scan.yaml 的确认预算，先输出计划再拉代码（FR-P2，ADR-001）；
  求解为纯计算：本里程碑不引入任何网络层（诚实性，AGENTS §3.5）

  @SC-M3-01
  场景: 组合求解按标签与 topics 正交命中三块（FR-P1/P2）
    假如 仓库夹具 "acme/self-a" 标签 [self-dev] topics [] 尺寸 1800MB
    而且 仓库夹具 "acme/k8s-a" 标签 [] topics [k8s] 尺寸 1600MB
    而且 仓库夹具 "acme/k8s-b" 标签 [] topics [k8s] 尺寸 1000MB
    而且 仓库夹具 "acme/edge-a" 标签 [] topics [edge] 尺寸 200MB
    当 以组合 "full-reading" 求解
    那么 计划引用组合 "full-reading"
    而且 块覆盖 [block-self, block-k8s, block-edge]
    而且 全部仓库入选且记录命中块与预估体积

  @SC-M3-02
  场景: FFD 装箱产出 job 列表且各 job 不超确认预算（FR-P3）
    假如 仓库夹具 "acme/self-a" 标签 [self-dev] topics [] 尺寸 1800MB
    而且 仓库夹具 "acme/k8s-a" 标签 [] topics [k8s] 尺寸 1600MB
    而且 仓库夹具 "acme/k8s-b" 标签 [] topics [k8s] 尺寸 1000MB
    而且 仓库夹具 "acme/edge-a" 标签 [] topics [edge] 尺寸 200MB
    当 以组合 "full-reading" 求解
    那么 job 数量至少 2 且每个 job 体积不超确认预算
    而且 所有入选块均入 job 且单块不跨 job

  @SC-M3-03
  场景: 单仓超确认预算降级稀疏检出（FR-P4/FR-B5）
    假如 仓库夹具 "acme/kernel-huge" 标签 [] topics [k8s] 尺寸 4500MB
    而且 仓库夹具 "acme/k8s-b" 标签 [] topics [k8s] 尺寸 1000MB
    而且 仓库夹具 "acme/self-a" 标签 [self-dev] topics [] 尺寸 1800MB
    而且 仓库夹具 "acme/edge-a" 标签 [] topics [edge] 尺寸 200MB
    当 以组合 "full-reading" 求解
    那么 记录 "acme/kernel-huge" 降级为 sparse 且 flags 含 --filter=blob:none 与 --depth=1
    而且 其余仓库正常装箱不受降级影响

  @SC-M3-04
  场景: plan.json 归档含快照与算法版本且同输入可复现（FR-P5/H11）
    假如 仓库夹具 "acme/self-a" 标签 [self-dev] topics [] 尺寸 1800MB
    而且 仓库夹具 "acme/k8s-a" 标签 [] topics [k8s] 尺寸 1600MB
    而且 仓库夹具 "acme/edge-a" 标签 [] topics [edge] 尺寸 200MB
    当 以组合 "full-reading" 求解并落盘 out
    那么 out/plan.json 含 generated、algo_version、inventory_snapshot 与 jobs 字段
    而且 同输入重跑得到相同 job 划分

  @SC-M3-05
  场景: 未知组合显式报错且不产出计划（FR-P2 前置校验）
    假如 仓库夹具 "acme/self-a" 标签 [self-dev] topics [] 尺寸 1800MB
    当 以未知组合 "not-exist" 求解
    那么 显式抛出 PolicyError 且未产出任何计划
