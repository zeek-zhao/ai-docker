# -*- coding: utf-8 -*-
"""测试入口：发现并运行本目录全部 test_*.py，输出 reports/test-report.json。

用法（Linux / Windows / macOS 通用，仅标准库）：
    python3 tests/run_tests.py        # 仓库相对路径，与工作目录无关
退出码：0 全部通过；1 存在 failed/error。
"""

import json
import platform
import sys
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports"
TZ = timezone(timedelta(hours=8))  # 本仓库约定时区 +08:00（AGENTS §1）


class CaseCollector(unittest.TestResult):
    """逐用例收集结果，含用例编号（docstring 首行 TC-xx）。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cases = []

    def _record(self, test, status, err=None):
        doc = (getattr(test, "_testMethodDoc", "") or "").strip().splitlines()
        case_id = doc[0].strip() if doc else ""
        message = ""
        if err is not None:
            message = "%s: %s" % (type(err[1]).__name__, err[1])
        self.cases.append({
            "id": case_id,
            "test": test.id(),
            "status": status,
            "message": message[:500],
        })

    def addSuccess(self, test):
        super().addSuccess(test)
        self._record(test, "passed")

    def addError(self, test, err):
        super().addError(test, err)
        self._record(test, "error", err)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._record(test, "failed", err)

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._record(test, "skipped")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    started = time.monotonic()
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(ROOT / "tests"), pattern="test_*.py")
    runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=2,
                                     resultclass=CaseCollector)
    result = runner.run(suite)
    duration = round(time.monotonic() - started, 3)

    report = {
        "generated": datetime.now(TZ).isoformat(timespec="seconds"),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "solution": "repo-mirror-sync",
        "runner": "tests/run_tests.py (unittest, stdlib only)",
        "totals": {
            "run": result.testsRun,
            "passed": len(result.cases and [c for c in result.cases if c["status"] == "passed"]),
            "failed": len([c for c in result.cases if c["status"] == "failed"]),
            "error": len([c for c in result.cases if c["status"] == "error"]),
            "skipped": len([c for c in result.cases if c["status"] == "skipped"]),
        },
        "duration_s": duration,
        "cases": result.cases,
    }
    REPORT_DIR.mkdir(exist_ok=True)
    report_path = REPORT_DIR / "test-report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("\n===== 汇总 =====")
    print("总计 %d | 通过 %d | 失败 %d | 错误 %d | 跳过 %d | 用时 %.3fs"
          % (result.testsRun, report["totals"]["passed"],
             report["totals"]["failed"], report["totals"]["error"],
             report["totals"]["skipped"], duration))
    print("报告：%s" % report_path.relative_to(ROOT))
    return 0 if (report["totals"]["failed"] == 0
                 and report["totals"]["error"] == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
