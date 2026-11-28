# -*- coding: utf-8 -*-
"""SC-M4-01~04 步骤定义：融合守卫 merge_guard。

契约：裁决唯一入口 tools/overlay.OverlayResolver；规则唯一出处
config/policy.yaml（AGENTS §3.6）。本文件只做编排断言。
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))          # tests/
_ROOT = os.path.dirname(_HERE)                              # solutions/repo-mirror-sync/
for _p in (_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tools.overlay import OverlayResolver                   # noqa: E402
from tools.policy import load_policy                        # noqa: E402
from tools.merge_guard import MergeGuard                    # noqa: E402

from bdd_runner import step                                 # noqa: E402

ROOT = _ROOT


def _layers(text):
    return [part.strip() for part in text.replace("，", "、").split("、") if part.strip()]


# ---- 背景 ----


@step("given", r"^策略文件已加载并注入守卫$")
def given_policy_loaded(ctx):
    policy = load_policy(ROOT)
    ctx["guard"] = MergeGuard(OverlayResolver(policy))


# ---- given：在场层 ----


@step("given", r"^以下层在场：(.+)$")
def given_layers(ctx, text):
    ctx["layers"] = _layers(text)


@step("given", r'^路径\s*"([^"]+)"\s*在场层为(.+)$')
def given_path_layers(ctx, path, text):
    ctx["path"] = path
    ctx["layers"] = _layers(text)


# ---- when：裁决与守卫 ----


@step("when", r'^守卫裁决路径 "([^"]+)"$')
def when_arbitrate_path(ctx, path):
    ctx["path"] = path
    ctx["decision"] = ctx["guard"].arbitrate(path, ctx["layers"])


@step("when", r"^守卫裁决该路径$")
def when_arbitrate_same(ctx):
    ctx["decision"] = ctx["guard"].arbitrate(ctx["path"], ctx["layers"])


@step("when", r"^执行层数守卫，层数为\s*(\d+)$")
def when_check_stack(ctx, count):
    ctx["stack"] = ctx["guard"].check_stack(int(count))


@step("when", r"^审查 tools/merge_guard\.py 源码$")
def when_read_source(ctx):
    with open(os.path.join(ROOT, "tools", "merge_guard.py"), "r", encoding="utf-8") as fh:
        ctx["source"] = fh.read()


# ---- then：裁决结果 ----


@step("then", r"^裁决 action 为\s*(\w+)$")
def then_action(ctx, action):
    assert ctx["decision"]["action"] == action, ctx["decision"]


@step("then", r"^胜出层为\s*(\S+)$")
def then_layer(ctx, layer):
    assert ctx["decision"].get("layer") == layer, ctx["decision"]


@step("then", r"^被遮蔽层为\s*(.+)$")
def then_shadowed(ctx, text):
    expect = _layers(text)
    assert sorted(ctx["decision"].get("shadowed", [])) == sorted(expect), ctx["decision"]


@step("then", r"^不产生胜出层$")
def then_no_winner(ctx):
    assert "layer" not in ctx["decision"], ctx["decision"]


@step("then", r'^隔离建议包含独立前缀 "([^"]+)" 与 "([^"]+)"$')
def then_prefixes(ctx, first, second):
    prefixes = ctx["decision"].get("prefixes", [])
    assert first in prefixes and second in prefixes, ctx["decision"]


# ---- then：层数守卫 ----


@step("then", r"^层数守卫 ok 为\s*(真|假)$")
def then_stack_ok(ctx, word):
    expect = word == "真"
    assert ctx["stack"]["ok"] is expect, ctx["stack"]


@step("then", r"^two_stage 为\s*(真|假)$")
def then_two_stage(ctx, word):
    expect = word == "真"
    assert ctx["stack"]["two_stage"] is expect, ctx["stack"]


@step("then", r"^max_lowerdir 取自策略为\s*(\d+)$")
def then_max_lowerdir(ctx, value):
    assert ctx["stack"]["max_lowerdir"] == int(value), ctx["stack"]


@step("then", r'^建议包含 "([^"]+)"$')
def then_advice_contains(ctx, text):
    assert text in ctx["stack"]["advice"], ctx["stack"]


# ---- then：唯一裁决出处（静态）----


@step("then", r"^源码从 tools/overlay 导入 OverlayResolver$")
def then_source_import(ctx):
    assert "from tools.overlay import OverlayResolver" in ctx["source"], "守卫未委托 overlay"


@step("then", r"^源码不含独立裁决表赋值（precedence/path_rules）$")
def then_source_no_second_table(ctx):
    import re

    for banned in (r"\bprecedence\s*=", r"\bpath_rules\s*="):
        assert re.search(banned, ctx["source"]) is None, "发现第二套裁决逻辑：%s" % banned
