# -*- coding: utf-8 -*-
"""plan — 组合求解器：inventory → 组合选块 → FFD 装箱 → plan.json。

依据：docs/01 §10（装箱）/§17（端到端）、docs/03 FR-P1~P5、ADR-001（先计划
后拉取）、ADR-009（超大单仓降级）。纯计算模块：不引入任何网络层（FR-P2）。

策略唯一出处 config/*.yaml（AGENTS §3.3 / TC-C6）：
- 块定义与组合引用：config/policy.yaml（经 tools.policy.Policy 读入）；
- 确认预算：config/scan.yaml budget.budget_bytes（由调用方传入）。
本文件不硬编码任何体积阈值。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.packing import first_fit_decreasing        # noqa: E402
from tools.policy import load_policy, load_scan       # noqa: E402
from tools.scan_inventory import iso_now              # noqa: E402

__all__ = ["ALGO_VERSION", "SPARSE_FLAGS", "match_block", "build_plan",
           "write_plan", "main"]

ALGO_VERSION = "ffd-1"  # 算法版本（非策略常量），写入 plan.json 供复现审计（FR-P5）

# FR-P4 / ADR-009 降级检出参数（行为约定，见 docs/03 FR-P4 验收准则）
SPARSE_FLAGS = ["--filter=blob:none", "--depth=1"]


def match_block(record, block):
    """按 policy.yaml blocks[].match 语义判定记录归属。

    标签（人工）与 topics（GitHub）两个正交维度（FR-P1，ADR-001）；
    size_class 为派生维度，随 size_bytes_est 一并参与后续预算判定。
    匹配规则只读自 policy.yaml，不在代码中复写。
    """
    match = block.get("match") or {}
    label = match.get("label")
    if label and label in (record.get("labels") or []):
        return True
    topic = match.get("topic")
    if topic and topic in (record.get("topics") or []):
        return True
    return False


def build_plan(records, policy, confirmed_budget, combo_id=None, now=None,
               snapshot_ref=None):
    """组合求解：选块 → 预算判定 → FFD 装箱 → 计划字典。

    records: 14 字段清单记录列表（out/inventory.json 的 repos）；
    policy: tools.policy.Policy 实例；
    confirmed_budget: 确认预算字节数（config/scan.yaml budget.budget_bytes）。
    返回 dict（写入 plan.json 的结构，FR-P5：输入快照引用、算法版本、
    切分结果、超限/降级原因齐备）。
    """
    if combo_id:
        # 未知组合/悬空引用显式报错（FR-P2 前置校验，TC-C8 同源语义）
        blocks = policy.combo_blocks(combo_id)
    else:
        blocks = [b for b in policy.blocks if isinstance(b, dict)]

    selected, degraded, unassigned = [], [], []
    for record in records:
        hit = next((b for b in blocks if match_block(record, b)), None)
        if hit is None:
            unassigned.append({
                "repo": record["repo"],
                "reason": "未命中组合内任何块的匹配规则",
            })
            continue
        entry = {
            "repo": record["repo"],
            "block": hit["id"],
            "size_bytes_est": int(record["size_bytes_est"]),
        }
        if entry["size_bytes_est"] > int(confirmed_budget):
            # FR-P4 / FR-B5：超预算单仓降级 sparse，不入装箱、不静默失败
            degraded.append({
                **entry,
                "strategy": "sparse",
                "flags": list(SPARSE_FLAGS),
                "reason": "size_bytes_est 超过确认预算（FR-P4/FR-B5，ADR-009）",
            })
        else:
            selected.append(entry)

    # 块粒度聚合（装箱单位 = 块，docs/01 §10）
    by_block = {}
    for entry in selected:
        by_block.setdefault(entry["block"], []).append(entry)
    items = [
        {"id": block_id,
         "size_bytes": sum(e["size_bytes_est"] for e in members)}
        for block_id, members in by_block.items()
    ]

    bins, unplaced = first_fit_decreasing(items, int(confirmed_budget))
    jobs = [
        {"job": i + 1, "blocks": bin_["items"], "size_bytes_est": bin_["used"]}
        for i, bin_ in enumerate(bins)
    ]
    unplaced = [
        {"block": item["id"], "size_bytes_est": item["size_bytes"],
         "reason": "块体积超确认预算（两级融合/再切分，docs/01 §10）"}
        for item in unplaced
    ]

    return {
        "generated": now or iso_now(),
        "algo_version": ALGO_VERSION,
        "combo": combo_id,
        "inventory_snapshot": {"ref": snapshot_ref, "repos": len(records)},
        "blocks": [{"id": it["id"], "size_bytes_est": it["size_bytes"]}
                   for it in items],
        "repos": selected,   # 逐仓选择明细（命中块 + 预估体积，审计可回溯）
        "jobs": jobs,
        "unplaced": unplaced,
        "degraded": degraded,
        "unassigned": unassigned,
    }


def write_plan(plan, out_dir):
    """归档 plan.json（FR-P5：历史可复现决策依据；out/ 不入库）。"""
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "plan.json"
    path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    return path


def main(argv=None):
    """CLI：--inventory <inventory.json> --combo <id> --out <dir>。"""
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="组合求解器（先计划后拉取）")
    parser.add_argument("--inventory", default="out/inventory.json")
    parser.add_argument("--combo", default=None)
    parser.add_argument("--out", default="out")
    args = parser.parse_args(argv)

    inventory_path = Path(args.inventory)
    payload = json.loads(inventory_path.read_text(encoding="utf-8"))
    records = payload["repos"]

    policy = load_policy(root)   # 已返回 Policy 实例（含结构校验）
    scan_cfg, errors = load_scan(root)
    if errors:
        raise ValueError("config/scan.yaml 非法：%s" % errors)
    confirmed = scan_cfg["budget"]["budget_bytes"]

    plan = build_plan(records, policy, confirmed, combo_id=args.combo,
                      snapshot_ref=str(inventory_path))
    path = write_plan(plan, args.out)
    print("plan.json 已生成：%s" % path)
    print("jobs=%d degraded=%d unplaced=%d unassigned=%d" % (
        len(plan["jobs"]), len(plan["degraded"]),
        len(plan["unplaced"]), len(plan["unassigned"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
