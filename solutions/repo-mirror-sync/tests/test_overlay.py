# -*- coding: utf-8 -*-
"""TC-O*：同名路径裁决与融合层数用例（被测对象 tools/overlay.py）。

依据：docs/01 §13.3 选举规则（D5：toolchain > self-dev > k8s > edge；
manifest/** pin toolchain；**/.gitmodules pin self-dev；**/build.sh 前缀隔离）、
§15 H9（单次融合 ≤8 层）。规则数据全部读 config/policy.yaml（AGENTS §3.6
唯一出处）；FR-F1/F2（运行时融合，优先级可控）。
"""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import overlay, policy as policy_mod  # noqa: E402


class TestOverlayResolution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pol = policy_mod.load_policy(ROOT)
        cls.resolver = overlay.OverlayResolver(cls.pol)

    def test_TC_O1_precedence_order(self):
        """TC-O1 优先级顺序与在场层胜出（左高右低）"""
        self.assertEqual(self.resolver.precedence,
                         ["toolchain", "self-dev", "k8s", "edge"])
        got = self.resolver.decide("k8s/charts/app.yaml", {"k8s", "edge"})
        self.assertEqual(got, {"action": "keep", "layer": "k8s"})
        got = self.resolver.decide("edge/daemon/conf.toml", {"edge"})
        self.assertEqual(got, {"action": "keep", "layer": "edge"})
        got = self.resolver.decide("src/main.c", {"toolchain", "self-dev", "k8s"})
        self.assertEqual(got, {"action": "keep", "layer": "toolchain"})

    def test_TC_O2_manifest_pinned_to_toolchain(self):
        """TC-O2 manifest/** 永远 pin toolchain（压倒 precedence）"""
        got = self.resolver.decide(
            "manifest/default.xml",
            {"toolchain", "self-dev", "k8s", "edge"},
        )
        self.assertEqual(got, {"action": "pin", "layer": "toolchain"})
        got = self.resolver.decide("manifest/groups/k8s.xml", {"k8s", "edge"})
        self.assertEqual(got, {"action": "pin", "layer": "toolchain"})

    def test_TC_O3_gitmodules_pinned_to_self_dev(self):
        """TC-O3 **/.gitmodules pin self-dev（同路径不同内容，B 类冲突）"""
        got = self.resolver.decide(
            "k8s/sub/.gitmodules", {"self-dev", "k8s", "edge"})
        self.assertEqual(got, {"action": "pin", "layer": "self-dev"})

    def test_TC_O4_build_sh_isolated(self):
        """TC-O4 **/build.sh 前缀隔离（各 topic 自有脚本不打架，H6 对策）"""
        got = self.resolver.decide("build.sh", {"toolchain", "k8s"})
        self.assertEqual(got, {"action": "isolate"})
        got = self.resolver.decide("topic-k8s/scripts/build.sh", {"k8s", "edge"})
        self.assertEqual(got, {"action": "isolate"})

    def test_TC_O5_windows_path_normalized(self):
        """TC-O5 Windows 反斜杠路径归一后裁决一致（跨平台）"""
        got = self.resolver.decide("manifest\\default.xml", {"k8s", "edge"})
        self.assertEqual(got, {"action": "pin", "layer": "toolchain"})

    def test_TC_O6_unknown_layer_rejected(self):
        """TC-O6 在场层不在 precedence 中显式报错（AGENTS §3.6 一致性）"""
        with self.assertRaises(overlay.DecideError):
            self.resolver.decide("x/y", {"unknown-topic"})
        with self.assertRaises(overlay.DecideError):
            self.resolver.decide("x/y", set())

    def test_TC_O7_lowerdir_limit_h9(self):
        """TC-O7 单次融合层数上限 8（H9：超出须两级融合）"""
        self.assertTrue(self.resolver.check_lowerdir(8))
        self.assertFalse(self.resolver.check_lowerdir(9))
        broken = SimpleNamespace(precedence=["a"], path_rules=[], max_lowerdir=None)
        with self.assertRaises(overlay.DecideError):
            overlay.OverlayResolver(broken).check_lowerdir(1)


if __name__ == "__main__":
    unittest.main()
