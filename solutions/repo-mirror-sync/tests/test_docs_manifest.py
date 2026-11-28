# -*- coding: utf-8 -*-
"""TC-M*：文档与清单一致性用例（治理类测试，AGENTS §4/docs/04 §4）。

保证：manifest.yaml 与磁盘一致（delivered 必在、planned 必不在）；
docs 编号连续且含修订历史；文档头部版本与修订历史末行一致（SemVer 纪律）。
"""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import yaml_lite  # noqa: E402

MANIFEST = ROOT / "manifest.yaml"
DOCS = ROOT / "docs"


class TestDocsAndManifest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = yaml_lite.load_file(MANIFEST)

    def test_TC_M1_manifest_matches_disk(self):
        """TC-M1 manifest 与磁盘一致：delivered 必存在，planned 必不存在"""
        self.assertEqual(self.manifest["manifest_version"], 1)
        self.assertEqual(self.manifest["solution"], "repo-mirror-sync")
        violations = []
        for entry in self.manifest["entries"]:
            target = ROOT / entry["path"]
            state = entry["state"]
            if state == "delivered" and not target.is_file():
                violations.append("delivered 缺失：%s" % entry["path"])
            if state == "planned" and target.exists():
                violations.append("planned 却已存在（清单腐化）：%s" % entry["path"])
        self.assertEqual(violations, [])

    def test_TC_M2_docs_numbering_and_history(self):
        """TC-M2 文档编号自 01 起连续，均含修订历史节"""
        docs = sorted(DOCS.glob("*.md"))
        self.assertTrue(docs, "docs 目录为空")
        self.assertEqual(
            [p.name[:2] for p in docs],
            ["%02d" % n for n in range(1, len(docs) + 1)],
            "docs 编号不连续（docs/04 §4：新增顺延，禁止跳号）")
        for path in docs:
            text = path.read_text(encoding="utf-8")
            self.assertIn("修订历史", text, "%s 缺少修订历史" % path.name)

    def test_TC_M3_doc_ids_plan_series(self):
        """TC-M3 每篇文档含与序号对应的 DSH-PLAN-<NNN> 编号"""
        for path in sorted(DOCS.glob("*.md")):
            expect = "DSH-PLAN-%03d" % int(path.name[:2])
            text = path.read_text(encoding="utf-8")
            self.assertIn(expect, text,
                          "%s 缺少文档编号 %s" % (path.name, expect))

    def test_TC_M4_header_version_matches_last_revision(self):
        """TC-M4 文档头部版本与修订历史末行版本一致（SemVer 纪律，docs/04 §4）"""
        for path in sorted(DOCS.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            m_head = re.search(r"\|\s*版本\s*\|\s*(\d+\.\d+\.\d+)\s*\|", text)
            revisions = re.findall(
                r"^\|\s*(\d+\.\d+\.\d+)\s*\|\s*\d{4}-\d{2}-\d{2}\s*\|",
                text, flags=re.M)
            self.assertTrue(m_head, "%s 缺少头部版本" % path.name)
            self.assertTrue(revisions, "%s 缺少修订历史行" % path.name)
            self.assertEqual(
                m_head.group(1), revisions[-1],
                "%s 头部版本 %s 与修订历史末行 %s 不一致"
                % (path.name, m_head.group(1), revisions[-1]),
            )

    def test_TC_M5_governance_docs_revision_history(self):
        """TC-M5 治理文档修订历史完整（D-25 对策）：AGENT/test-report/根README 修订表单调递增且末行为最新；AGENT 进度表与 docs/06 里程碑表同步"""
        governance = [
            ROOT / "AGENT.md",
            ROOT / "reports" / "test-report.md",
            ROOT.parents[1] / "README.md",
        ]
        for path in governance:
            text = path.read_text(encoding="utf-8")
            versions = re.findall(
                r"^\|\s*(\d+\.\d+\.\d+)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|",
                text, flags=re.M)
            self.assertTrue(
                versions, "%s 缺少修订历史表" % path)
            keys = [tuple(int(x) for x in v[0].split(".")) for v in versions]
            self.assertEqual(
                keys, sorted(keys),
                "%s 修订历史版本非单调递增：%s" % (path, versions))
            self.assertEqual(
                keys[-1], max(keys),
                "%s 修订历史末行不是最新版本" % path)
        agent = (ROOT / "AGENT.md").read_text(encoding="utf-8")
        plan = (DOCS / "06-开发计划与里程碑.md").read_text(encoding="utf-8")
        agent_rows = re.findall(r"^\|\s*\d+\s+\|", agent, flags=re.M)
        plan_rows = re.findall(r"^\|\s*M\d+\s+\|", plan, flags=re.M)
        self.assertEqual(
            len(agent_rows), len(plan_rows),
            "AGENT.md 进度表（%d 行）与 docs/06 里程碑表（%d 行）不同步"
            % (len(agent_rows), len(plan_rows)))


if __name__ == "__main__":
    unittest.main()
