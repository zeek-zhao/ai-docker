# -*- coding: utf-8 -*-
"""TC-P*：组合求解（FFD 装箱）用例（被测对象 tools/packing.py）。

依据：docs/01 §10（FFD：size_class 降序、单 bin ≤ 预算、单块不可跨 job）、
§17 端到端示例（full-reading 合计 4.6GB > 4.0GB 预算 → 2 job）、
docs/03 FR-P3/P4（FFD 与人工最优一致或给差距说明；超预算单仓降级稀疏检出）。
预算上限取 config（D2=4.0e9）；合成用例的预算为测试夹具，非策略常量。
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import packing, policy as policy_mod  # noqa: E402


class TestPacking(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        scan, _ = policy_mod.load_scan(ROOT)
        cls.budget_bytes = scan["budget"]["budget_bytes"]  # 4.0e9（D2）

    def test_TC_P1_full_reading_scenario(self):
        """TC-P1 docs §17 场景：三块合计 4.6GB > 4.0GB → ≥2 个 job 且均 ≤ 预算"""
        items = [
            {"id": "block-self", "size_bytes": 1_800_000_000},
            {"id": "block-k8s", "size_bytes": 2_600_000_000},
            {"id": "block-edge", "size_bytes": 200_000_000},
        ]
        self.assertEqual(sum(i["size_bytes"] for i in items), 4_600_000_000)
        bins, unplaced = packing.first_fit_decreasing(items, self.budget_bytes)
        self.assertEqual(unplaced, [])               # 每块自身 ≤ 预算，全部可装箱
        self.assertGreaterEqual(len(bins), 2)        # 合计超预算 → 至少 2 job
        for bin_ in bins:
            self.assertLessEqual(bin_["used"], self.budget_bytes)
        placed = [iid for bin_ in bins for iid in bin_["items"]]
        self.assertEqual(sorted(placed), sorted(i["id"] for i in items))

    def test_TC_P2_ffd_known_answer(self):
        """TC-P2 FFD 确定性已知解：预算10、块[7,6,4,2,1] → [7,2,1]+[6,4]"""
        items = [{"id": str(v), "size_bytes": v} for v in (7, 6, 4, 2, 1)]
        bins, unplaced = packing.first_fit_decreasing(items, 10)
        self.assertEqual(unplaced, [])
        self.assertEqual([sorted(b["items"]) for b in bins],
                         [["1", "2", "7"], ["4", "6"]])
        self.assertEqual([b["used"] for b in bins], [10, 10])

    def test_TC_P3_oversized_never_packed(self):
        """TC-P3 单块 > 预算 → 标记 oversized 不装箱（FR-P4 降级稀疏检出）"""
        items = [
            {"id": "kernel-huge", "size_bytes": 4_500_000_000},
            {"id": "small", "size_bytes": 100_000_000},
        ]
        bins, unplaced = packing.first_fit_decreasing(items, self.budget_bytes)
        self.assertEqual(unplaced,
                         [{"id": "kernel-huge", "size_bytes": 4_500_000_000,
                           "reason": "oversized"}])
        self.assertEqual(len(bins), 1)
        self.assertEqual(bins[0]["items"], ["small"])

    def test_TC_P4_item_never_split_across_jobs(self):
        """TC-P4 单块不可跨 job（同一 id 只出现在一个 bin，docs/01 §10 约束 1）"""
        items = [{"id": "b%d" % i, "size_bytes": v * 100_000_000}
                 for i, v in enumerate((3, 3, 3, 2))]
        bins, _ = packing.first_fit_decreasing(items, self.budget_bytes)
        seen = [iid for bin_ in bins for iid in bin_["items"]]
        self.assertEqual(len(seen), len(set(seen)))

    def test_TC_P5_decreasing_order_independent(self):
        """TC-P5 输入顺序无关：乱序输入得到与降序一致的装箱（FR-P3 FFD 语义）"""
        a = [{"id": "x", "size_bytes": 1}, {"id": "big", "size_bytes": 9},
             {"id": "mid", "size_bytes": 5}]
        b = list(reversed(a))
        for items in (a, b):
            bins, _ = packing.first_fit_decreasing(items, 10)
            # FFD：9 开箱后 5 放不下新开一箱，1 回填第一箱 → [9,1] + [5]
            self.assertEqual([sorted(x["items"]) for x in bins],
                             [["big", "x"], ["mid"]])

    def test_TC_P6_empty_input(self):
        """TC-P6 空输入 → 无 bin 无 unplaced"""
        bins, unplaced = packing.first_fit_decreasing([], self.budget_bytes)
        self.assertEqual((bins, unplaced), ([], []))


if __name__ == "__main__":
    unittest.main()
