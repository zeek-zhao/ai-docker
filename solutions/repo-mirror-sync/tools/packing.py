"""packing — 组合求解（带上界的装箱，FFD 启发式）。

依据：docs/01 §10（组合求解）、docs/03 FR-P3（size_class 降序 FFD；
单块不可跨 job）；预算上限一律来自 config（budget.budget_bytes），禁止硬编码。

算法：按体积降序 first-fit-decreasing。两条硬约束：
1. 单块不可跨 job——每块完整放入一个 bin（算法保证）；
2. 单块自身超过预算 → 不放入任何 bin，标记 oversized（FR-P4 降级：
   blob:none 浅克隆 + sparse-checkout，全量历史留 mirror 冷备）。
"""

from __future__ import annotations

__all__ = ["first_fit_decreasing"]


def first_fit_decreasing(items, budget_bytes):
    """FFD 装箱。

    items: [{"id": str, "size_bytes": int}, ...]（顺序无关）。
    budget_bytes: 单 bin（单 job）体积上限。
    返回 (bins, unplaced)：
      bins = [{"items": [块id...], "used": int}, ...]（每 bin ≤ 预算）
      unplaced = [{"id", "size_bytes", "reason": "oversized"}, ...]
    """
    bins = []
    unplaced = []
    ordered = sorted(
        (dict(it) for it in items),
        key=lambda it: (-int(it["size_bytes"]), str(it["id"])),
    )
    for item in ordered:
        size = int(item["size_bytes"])
        if size > budget_bytes:
            unplaced.append(
                {"id": item["id"], "size_bytes": size, "reason": "oversized"}
            )
            continue
        placed = False
        for bin_ in bins:
            if bin_["used"] + size <= budget_bytes:
                bin_["items"].append(item["id"])
                bin_["used"] += size
                placed = True
                break
        if not placed:
            bins.append({"items": [item["id"]], "used": size})
    return bins, unplaced
