# -*- coding: utf-8 -*-
"""TC-C*：策略配置与需求方确认参数用例（被测对象 config/*.yaml + tools/policy.py）。

确认参数出处：docs/01 §5 决策表（D1~D5，需求方 2026-11-27 确认）、
docs/02 ADR-002/003/005/006/007/010。本组用例保证「配置与已确认决策一致」
以及「策略校验器能拒绝非法策略」（AGENTS §3.3/§3.6，docs/03 FR-P1/FR-F1）。
"""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import policy as policy_mod  # noqa: E402


class TestConfirmedParams(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scan, cls.scan_errors = policy_mod.load_scan(ROOT)
        cls.pol = policy_mod.load_policy(ROOT)  # 结构非法会抛 PolicyError

    def test_TC_C1_scan_confirmed_values(self):
        """TC-C1 scan.yaml 与确认参数 D1/D2 一致（docs/01 §5）"""
        self.assertEqual(self.scan_errors, [])
        scan = self.scan["scan"]
        self.assertEqual(scan["every_days"], 7)                 # D1 扫描周期
        self.assertEqual(scan["max_requests_per_run"], 200)     # 单次请求上限
        self.assertEqual(scan["stagger_minute"], 17)            # 错开整点
        self.assertEqual(scan["state_file"], "out/inventory.json")
        limits = self.scan["limits"]
        self.assertEqual(limits["storage_gb"], 5)               # 平台上限（配置项）
        self.assertEqual(limits["overhead_gb"], 0.4)
        self.assertEqual(limits["safety_factor"], 1.25)         # ADR-003 k 值
        self.assertEqual(limits["cache_gb"], 10)
        self.assertEqual(self.scan["budget"]["budget_bytes"], 4000000000)  # D2 4.0GB

    def test_TC_C2_precedence_and_path_rules(self):
        """TC-C2 选举规则与 D5 一致且唯一出处（ADR-005，AGENTS §3.6）"""
        self.assertEqual(self.pol.precedence, ["toolchain", "self-dev", "k8s", "edge"])
        rules = {r["path"]: r for r in self.pol.path_rules}
        self.assertEqual(rules["manifest/**"]["pin"], "toolchain")
        self.assertEqual(rules["**/.gitmodules"]["pin"], "self-dev")
        self.assertTrue(rules["**/build.sh"]["isolate"])
        self.assertEqual(self.pol.max_lowerdir, 8)              # H9 对策

    def test_TC_C3_encryption_full_layer(self):
        """TC-C3 加密策略与 D3 一致（ADR-007 全层加密，密钥仅环境变量）"""
        enc = self.pol.encryption
        self.assertEqual(enc["mode"], "full-layer")
        self.assertEqual(enc["tool"], "age")
        self.assertEqual(enc["key_ref"], "env:AGE_KEY")
        self.assertEqual(enc["tag_identity"], "plain-content-sha256")
        self.assertEqual(enc["cache_policy"], "artifacts-only")  # H1 对策

    def test_TC_C4_combos_and_layouts(self):
        """TC-C4 组合与混合布局与 D4 一致，块引用可解析（ADR-006）"""
        combos = {c["id"]: c for c in self.pol.combos}
        self.assertEqual(combos["full-reading"]["blocks"],
                         ["block-self", "block-k8s", "block-edge"])
        self.assertEqual(combos["full-reading"]["layout"], "prefix")
        self.assertEqual(combos["self-dev-flat"]["blocks"], ["block-self"])
        self.assertEqual(combos["self-dev-flat"]["layout"], "flat")
        resolved = self.pol.combo_blocks("full-reading")
        self.assertEqual([b["id"] for b in resolved],
                         ["block-self", "block-k8s", "block-edge"])
        self.assertEqual(self.pol.overlay["layouts"],
                         {"self-dev": "flat", "combo": "prefix"})

    def test_TC_C5_alert_channels_and_throttle(self):
        """TC-C5 告警四类事件 + 1h 节流（ADR-010，H10 对策）"""
        alert = self.pol.alert
        self.assertIn("github-issue", alert["channels"])
        self.assertIn("feishu-webhook", alert["channels"])
        self.assertEqual(set(alert["on"]), {
            "budget_exceeded", "scan_error", "drift_detected", "cache_pressure",
        })
        self.assertEqual(alert["throttle"], "1h")

    def test_TC_C6_no_hardcoded_strategy_in_tools(self):
        """TC-C6 tools/ 源码无策略常量硬编码（AGENTS §3.3：5GB/4GB 只在 config）"""
        forbidden = [
            re.compile(r"4000000000|4_000_000_000"),
            re.compile(r"\bstorage_gb\s*[:=]\s*5\b"),
            re.compile(r"\bevery_days\s*[:=]\s*7\b"),
            re.compile(r"\bbudget_bytes\s*=\s*\d"),
        ]
        tools_dir = ROOT / "tools"
        for py in sorted(tools_dir.glob("*.py")):
            if py.name == "__init__.py":
                continue
            src = py.read_text(encoding="utf-8")
            for pattern in forbidden:
                self.assertIsNone(
                    pattern.search(src),
                    "%s 中疑似硬编码策略常量（命中 %s）" % (py.name, pattern.pattern),
                )

    def test_TC_C7_invalid_policy_rejected(self):
        """TC-C7 校验器拒绝非法策略（pin 指向未知层/组合悬空引用/加密降级/密钥入库）"""
        base = {
            "blocks": [{"id": "b1", "match": {"topic": "x"}, "mode": "whole"}],
            "combos": [{"id": "c1", "blocks": ["b1"], "layout": "flat"}],
            "encryption": {"mode": "full-layer", "tool": "age",
                           "key_ref": "env:AGE_KEY", "tag_identity": "sha"},
            "overlay": {
                "layouts": {"combo": "prefix"},
                "precedence": ["toolchain"],
                "path_rules": [],
                "max_lowerdir": 8,
            },
            "alert": {"channels": ["github-issue"], "on": ["scan_error"],
                      "throttle": "1h"},
        }
        self.assertEqual(policy_mod.Policy(base).validate(), [])

        bad_pin = dict(base)
        bad_pin["overlay"] = dict(base["overlay"], path_rules=[
            {"path": "x/**", "pin": "ghost-layer"}])
        errors = policy_mod.Policy(bad_pin).validate()
        self.assertTrue(any("pin" in e for e in errors))

        bad_combo = dict(base)
        bad_combo["combos"] = [{"id": "c1", "blocks": ["nope"], "layout": "flat"}]
        self.assertTrue(any("nope" in e
                            for e in policy_mod.Policy(bad_combo).validate()))

        bad_enc = dict(base)
        bad_enc["encryption"] = dict(base["encryption"], mode="final-layer-only")
        self.assertTrue(any("full-layer" in e
                            for e in policy_mod.Policy(bad_enc).validate()))

        bad_key = dict(base)
        bad_key["encryption"] = dict(base["encryption"], key_ref="file:secret.key")
        self.assertTrue(any("env:" in e
                            for e in policy_mod.Policy(bad_key).validate()))

    def test_TC_C8_unknown_combo_raises(self):
        """TC-C8 未知组合名显式报错（先计划后拉取，FR-P2）"""
        with self.assertRaises(policy_mod.PolicyError):
            self.pol.combo_blocks("not-exist")


if __name__ == "__main__":
    unittest.main()
