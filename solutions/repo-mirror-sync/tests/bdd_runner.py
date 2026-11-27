# -*- coding: utf-8 -*-
"""bdd_runner — 极简 Gherkin（中文子集）解析与执行器（仅标准库）。

约定见 docs/05-BDD总纲与场景目录.md §5：
- feature 文件在 ``features/``，中文关键字：功能/场景/假如/假设/当/那么/而且/并且/但是；
- 场景首行 tag ``@SC-Mn-NN`` 为场景编号，编号必须存在；
- 步骤定义在 ``tests/bdd_steps_*.py``，以 ``@given/@when/@then`` 注册正则；
- 运行器把每个场景变成一个 unittest 用例（docstring 首行 = 场景编号），
  由 ``tests/run_tests.py`` 统一发现执行并写入 reports/test-report.json。
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

__all__ = ["BddError", "Steps", "step", "parse_feature", "load_features",
           "run_scenario", "build_suite"]

_ROOT = Path(__file__).resolve().parents[1]
FEATURES_DIR = _ROOT / "features"

_FEATURE_RE = re.compile(r"^(?:功能|Feature)\s*[:：]\s*(.+)$")
_SCENARIO_RE = re.compile(r"^(?:场景|Scenario)\s*[:：]\s*(.+)$")
_STEP_RES = (
    ("given", re.compile(r"^(?:假如|假设|Given)\s+(.+)$")),
    ("when", re.compile(r"^(?:当|When)\s+(.+)$")),
    ("then", re.compile(r"^(?:那么|Then)\s+(.+)$")),
    ("given", re.compile(r"^(?:而且|并且|And|But)\s+(.+)$")),  # And/But 沿用上一段
)
_TAG_RE = re.compile(r"^@([\w\-]+)$")


class BddError(ValueError):
    """feature 文件语法错误或步骤无法匹配（含场景编号定位）。"""


class Steps:
    """步骤注册表：kind ∈ {given, when, then} → 编译正则 → 函数。"""

    def __init__(self):
        self._registry = {"given": [], "when": [], "then": []}

    def _register(self, kind, pattern, func):
        self._registry[kind].append((re.compile(pattern), func))

    def given(self, pattern):
        return lambda func: (self._register("given", pattern, func), func)[1]

    def when(self, pattern):
        return lambda func: (self._register("when", pattern, func), func)[1]

    def then(self, pattern):
        return lambda func: (self._register("then", pattern, func), func)[1]

    def dispatch(self, kind, text, ctx, scenario_id):
        for regex, func in self._registry[kind]:
            m = regex.fullmatch(text)
            if m:
                return func(ctx, *m.groups())
        raise BddError("场景 %s：无匹配步骤定义（%s：%s）" % (scenario_id, kind, text))


def step(kind, pattern):
    """模块级装饰器：把函数注册到模块级共享注册表 ``MODULE_STEPS``。"""
    def deco(func):
        MODULE_STEPS._register(kind, pattern, func)
        return func
    return deco


MODULE_STEPS = Steps()  # 各 bdd_steps_*.py 通过 @step 装饰器注册到这里


def parse_feature(text, source="<feature>"):
    """解析 feature 文件文本 → {"name":…, "scenarios":[{id,name,steps:[(kind,text)]}]}。"""
    feature_name, scenarios, scn, last_kind = None, [], None, None
    for no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _TAG_RE.match(line)
        if m:
            if scn is not None and scn["name"] is not None:
                # 上一个场景已命名，本 tag 开启新场景
                scn = {"id": None, "name": None, "steps": []}
            if scn is None:
                scn = {"id": None, "name": None, "steps": []}
            scn["id"] = m.group(1)
            continue
        m = _FEATURE_RE.match(line)
        if m:
            feature_name = m.group(1).strip()
            continue
        m = _SCENARIO_RE.match(line)
        if m:
            if scn is None:
                scn = {"id": None, "name": None, "steps": []}
            if not scn["id"]:
                raise BddError("%s:%d 场景缺少编号 tag（@SC-…）" % (source, no))
            scn["name"] = m.group(1).strip()
            scenarios.append(scn)
            continue
        for kind, regex in _STEP_RES:
            m = regex.match(line)
            if m:
                if scn is None or scn["name"] is None:
                    raise BddError("%s:%d 步骤出现在场景之外" % (source, no))
                if line.startswith(("而且", "并且", "And", "But")):
                    kind = last_kind or kind
                scn["steps"].append((kind, m.group(1).strip()))
                last_kind = kind
                break
        else:
            if feature_name is not None and (scn is None or scn["name"] is None):
                continue  # 功能叙述段（功能: 与首个场景: 之间的自由文本）
            raise BddError("%s:%d 无法识别的行：%r" % (source, no, line))
    if feature_name is None:
        raise BddError("%s 缺少 功能: 定义" % source)
    for scn in scenarios:
        if not scn["steps"]:
            raise BddError("%s 场景 %s 无步骤" % (source, scn["id"]))
    return {"name": feature_name, "source": source, "scenarios": scenarios}


def load_features(features_dir=None):
    """读取目录下全部 .feature 文件（UTF-8）。"""
    directory = Path(features_dir) if features_dir else FEATURES_DIR
    features = []
    for path in sorted(directory.glob("*.feature")):
        features.append(parse_feature(
            path.read_text(encoding="utf-8"), source=path.name))
    if not features:
        raise BddError("features 目录为空：%s" % directory)
    return features


def run_scenario(scn, steps=None, ctx=None):
    """执行单个场景：按顺序分派步骤；断言失败/异常向上抛（红灯）。"""
    registry = steps if steps is not None else MODULE_STEPS
    context = {} if ctx is None else ctx
    for kind, text in scn["steps"]:
        registry.dispatch(kind, text, context, scn["id"])
    return context


def build_suite(features_dir=None, registries=None):
    """把全部场景桥接为 unittest 测试套件（用例 docstring 首行 = 场景编号）。"""
    registry_map = registries if registries is not None else {"*": MODULE_STEPS}
    suite = unittest.TestSuite()
    for feature in load_features(features_dir):
        registry = registry_map.get("*") or registry_map.get(feature["name"])
        if registry is None:
            raise BddError("feature %r 无对应步骤注册表" % feature["name"])
        methods = {}
        for scn in feature["scenarios"]:
            def make(scn=scn, registry=registry):
                def test(self):
                    run_scenario(scn, registry)
                test.__doc__ = "%s %s" % (scn["id"], scn["name"])
                return test
            methods["test_%s" % scn["id"]] = make()
        cls = type(
            "Bdd_%s" % re.sub(r"\W", "_", feature["name"])[:40],
            (unittest.TestCase,),
            dict(methods),
        )
        for name in methods:
            suite.addTest(cls(name))
    return suite
