# -*- coding: utf-8 -*-
"""test_bdd_features — BDD 场景桥接：features/*.feature → unittest 套件。

经 ``load_tests`` 协议接入 tests/run_tests.py 的统一发现机制；
docstring 首行为场景编号（SC-…），供 CaseCollector 写入测试报告。
尚未实现的里程碑步骤模块缺席时静默跳过（当前全部已实现），
对应 feature 目录尚无场景文件，不影响现有用例全绿。
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
for _p in (str(_ROOT), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bdd_runner  # noqa: E402

# 里程碑顺序导入步骤定义（注册进 bdd_runner.MODULE_STEPS）
for _mod in ("bdd_steps_scan", "bdd_steps_plan", "bdd_steps_guard",
             "bdd_steps_alert", "bdd_steps_docker", "bdd_steps_drift",
             "bdd_steps_fuse"):
    try:
        __import__(_mod)
    except ImportError:
        pass  # 对应里程碑未开始（docs/06 §4 任务计划）；from 包 import 名 抛 ImportError


def load_tests(loader, tests, pattern):
    """unittest 发现协议：返回全部场景构成的套件。"""
    return bdd_runner.build_suite()
