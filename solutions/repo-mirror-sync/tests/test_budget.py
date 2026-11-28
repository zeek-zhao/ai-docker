# -*- coding: utf-8 -*-
"""TC-B*：体积预算与 size_class 用例（被测对象 tools/budget.py）。

依据：docs/01 §8.1 预算公式 budget_raw=(limit−overhead)/k、§9.1 size_class
阈值（small<200MB / large>1.5GB / oversized>3.5GB）、ADR-003（D2 确认
4.0 GB）。阈值全部取自 config/scan.yaml（TC-C 已核对一致性）。
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import budget, policy as policy_mod  # noqa: E402

GB = 10 ** 9  # 与 tools/budget.py 相同的十进制单位定义


class TestBudget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scan, _ = policy_mod.load_scan(ROOT)
        cls.limits = cls.scan["limits"]
        cls.thresholds = cls.scan["size_class"]
        cls.confirmed = budget.confirmed_budget_bytes(cls.scan)

    def test_TC_B1_formula_and_confirmed_budget(self):
        """TC-B1 预算公式 (5−0.4)/1.25=3.68GB；确认预算 4.0GB≥公式值"""
        raw = budget.budget_raw_bytes(self.limits)
        self.assertEqual(raw, int((5 - 0.4) * GB / 1.25))
        self.assertEqual(raw, 3680000000)
        self.assertEqual(self.confirmed, 4000000000)     # D2
        self.assertGreaterEqual(self.confirmed, raw)     # 确认值含取整冗余

    def test_TC_B2_size_class_boundaries(self):
        """TC-B2 size_class 边界语义与 docs/01 §9.1 严格不等式一致"""
        self.assertEqual(budget.size_class(199_999_999, self.thresholds), "small")
        self.assertEqual(budget.size_class(200_000_000, self.thresholds), "medium")
        self.assertEqual(budget.size_class(999_999_999, self.thresholds), "medium")
        self.assertEqual(budget.size_class(1_500_000_000, self.thresholds), "medium")
        self.assertEqual(budget.size_class(1_500_000_001, self.thresholds), "large")
        self.assertEqual(budget.size_class(3_500_000_000, self.thresholds), "large")
        self.assertEqual(budget.size_class(3_500_000_001, self.thresholds), "oversized")

    def test_TC_B3_decide_ok_or_split(self):
        """TC-B3 单块预算判定：≤预算 ok，>预算 split（超限必须切分/稀疏检出）"""
        self.assertEqual(budget.decide(3_999_999_999, self.confirmed), "ok")
        self.assertEqual(budget.decide(4_000_000_000, self.confirmed), "ok")
        self.assertEqual(budget.decide(4_000_000_001, self.confirmed), "split")

    def test_TC_B4_missing_thresholds_raise(self):
        """TC-B4 阈值缺失显式报错（不静默缺省）"""
        with self.assertRaises(ValueError):
            budget.budget_raw_bytes({})
        with self.assertRaises(ValueError):
            budget.size_class(1, {"small_max_bytes": 1})
        with self.assertRaises(ValueError):
            budget.confirmed_budget_bytes({"budget": {}})


if __name__ == "__main__":
    unittest.main()
