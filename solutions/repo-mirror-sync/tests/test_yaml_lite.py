# -*- coding: utf-8 -*-
"""TC-Y*：yaml_lite 配置解析器用例（被测对象 tools/yaml_lite.py）。

覆盖：真实 config/*.yaml 结构与类型、注释与冒号处理、行内字典/列表、
错误语法显式失败。对应 FR-S2（清单与配置解析）、docs/04 §3 配置基线。
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import yaml_lite  # noqa: E402

CONFIG = ROOT / "config"


def _walk_scalars(node):
    if isinstance(node, dict):
        for v in node.values():
            yield from _walk_scalars(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_scalars(v)
    else:
        yield node


class TestYamlLite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scan = yaml_lite.load_file(CONFIG / "scan.yaml")
        cls.policy = yaml_lite.load_file(CONFIG / "policy.yaml")

    def test_TC_Y1_scan_structure_and_types(self):
        """TC-Y1 scan.yaml 结构与类型解析"""
        self.assertEqual(self.scan["version"], 1)
        self.assertIsInstance(self.scan["version"], int)
        self.assertEqual(self.scan["scan"]["every_days"], 7)
        self.assertEqual(self.scan["scan"]["max_requests_per_run"], 200)
        self.assertIsInstance(self.scan["limits"]["overhead_gb"], float)
        self.assertEqual(self.scan["limits"]["overhead_gb"], 0.4)
        self.assertIsInstance(self.scan["budget"]["budget_bytes"], int)
        self.assertEqual(self.scan["budget"]["budget_bytes"], 4000000000)
        self.assertEqual(self.scan["size_class"]["small_max_bytes"], 200000000)

    def test_TC_Y2_policy_nested_and_lists(self):
        """TC-Y2 policy.yaml 嵌套映射与列表解析"""
        blocks = self.policy["blocks"]
        self.assertIsInstance(blocks, list)
        self.assertEqual(len(blocks), 3)
        self.assertEqual(blocks[0]["id"], "block-self")
        self.assertEqual(blocks[0]["match"], {"label": "self-dev"})
        self.assertEqual(blocks[1]["mode"], "split-by-repo")
        combos = self.policy["combos"]
        self.assertEqual(combos[0]["blocks"], ["block-self", "block-k8s", "block-edge"])
        rules = self.policy["overlay"]["path_rules"]
        self.assertEqual(rules[0], {"path": "manifest/**", "pin": "toolchain"})
        self.assertEqual(rules[2], {"path": "**/build.sh", "isolate": True})

    def test_TC_Y3_comments_and_colon_values(self):
        """TC-Y3 注释裁剪与含冒号取值（env:AGE_KEY、out/inventory.json）"""
        self.assertEqual(self.scan["scan"]["state_file"], "out/inventory.json")
        self.assertEqual(self.policy["encryption"]["key_ref"], "env:AGE_KEY")
        self.assertEqual(self.policy["alert"]["throttle"], "1h")
        for value in _walk_scalars(self.scan):
            if isinstance(value, str):
                self.assertNotIn("#", value)
        for value in _walk_scalars(self.policy):
            if isinstance(value, str):
                self.assertNotIn("#", value)

    def test_TC_Y4_quoted_hash_kept(self):
        """TC-Y4 引号内 # 与注释语义"""
        data = yaml_lite.parse('a: "x # y"   # 行尾注释\nb: 2\n')
        self.assertEqual(data["a"], "x # y")
        self.assertEqual(data["b"], 2)

    def test_TC_Y5_errors_are_explicit(self):
        """TC-Y5 非法语法显式报错（YamlLiteError）"""
        with self.assertRaises(yaml_lite.YamlLiteError):
            yaml_lite.parse("a: { b: 1\n")          # 行内字典未闭合
        with self.assertRaises(yaml_lite.YamlLiteError):
            yaml_lite.parse("a: 1\n  b: 2\n")       # 悬空缩进无法归属
        with self.assertRaises(yaml_lite.YamlLiteError):
            yaml_lite.parse("[1, 2\n")              # 行内列表未闭合

    def test_TC_Y6_scalar_forms(self):
        """TC-Y6 标量形态：整数/浮点/布尔/字符串"""
        data = yaml_lite.parse(
            "i: 42\nf: 1.25\nyes: true\nno: false\ns: hello-world\n"
        )
        self.assertEqual(data, {
            "i": 42, "f": 1.25, "yes": True, "no": False, "s": "hello-world",
        })


if __name__ == "__main__":
    unittest.main()
