# -*- coding: utf-8 -*-
"""bdd_steps_fuse — features/fuse_verify.feature 的步骤定义（SC-M7-01~04）。

非特权融合校验（ADR-011）：夹具层目录由本模块在临时目录构建，内容标记
「<层名>::<相对路径>」便于断言来源；策略数据一律读 config/policy.yaml
（AGENTS §3.6 唯一出处）。不发起网络与特权操作；临时目录随场景存续于
ctx，由测试进程退出时系统回收（local/ 纪律不受影响）。
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent          # tests/
_ROOT = _HERE.parent                             # solutions/repo-mirror-sync/
for _p in (str(_ROOT), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from bdd_runner import step                       # noqa: E402

from tools import fuse_verify                     # noqa: E402
from tools.overlay import OverlayResolver         # noqa: E402
from tools.policy import load_policy              # noqa: E402

MODULE_STEPS = {}


def _mark(layer, rel):
    """夹具内容标记：来源可断言（<层名>::<相对路径>）。"""
    return "%s::%s\n" % (layer, rel)


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _merged_root(ctx):
    return Path(ctx["fuse"]["out"]) / "merged"


def _decision(ctx, rel):
    entry = next(d for d in ctx["fuse_report"]["decisions"] if d["path"] == rel)
    return entry


def _assert_pin(ctx, rel, layer):
    content = (_merged_root(ctx) / rel).read_text(encoding="utf-8")
    assert content.startswith(layer + "::"), \
        "融合视图 %s 内容非 %s 层：%r" % (rel, layer, content)
    entry = _decision(ctx, rel)
    assert entry["action"] == "pin" and entry["layer"] == layer, \
        "决策非 pin@%s：%r" % (layer, entry)


# ---------------------------------------------------------------- 假如/假设


@step("given", r"准备两层夹具 (\S+) 与 (\S+) 且同名路径内容不同")
def given_two_layers(ctx, layer_a, layer_b):
    tmp = Path(tempfile.mkdtemp(prefix="fuse-m7-"))
    layers = {}
    for name in (layer_a, layer_b):
        root = tmp / name
        _write(root / "opt/README", _mark(name, "opt/README"))
        layers[name] = str(root)
    ctx["fuse"] = {"tmp": tmp, "layers": layers, "out": tmp / "fuse-verify"}


@step("given", r"准备包含 manifest 索引、gitmodules 与 build 脚本的多层夹具")
def given_multi_layers(ctx):
    tmp = Path(tempfile.mkdtemp(prefix="fuse-m7-"))
    layout = {
        "toolchain": ["manifest/index", "opt/README", "scripts/build.sh"],
        "self-dev": ["manifest/index", ".gitmodules", "scripts/build.sh"],
        "k8s": ["manifest/index", "k8s/chart.yaml"],
    }
    layers = {}
    for name, files in layout.items():
        root = tmp / name
        for rel in files:
            _write(root / rel, _mark(name, rel))
        layers[name] = str(root)
    ctx["fuse"] = {"tmp": tmp, "layers": layers, "out": tmp / "fuse-verify"}


@step("given", r"已加载 tools/fuse_verify.py 源码")
def given_fuse_source(ctx):
    ctx["fuse_src"] = (_ROOT / "tools" / "fuse_verify.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------- 当


@step("when", r"运行非特权融合校验")
def when_fuse_verify(ctx):
    f = ctx["fuse"]
    ctx["fuse_report"] = fuse_verify.verify(
        f["layers"], solution_dir=_ROOT, out_dir=str(f["out"]))


# ---------------------------------------------------------------- 那么


@step("then", r"融合视图中同名路径内容来自 (\S+) 层")
def then_keep_content(ctx, layer):
    content = (_merged_root(ctx) / "opt/README").read_text(encoding="utf-8")
    assert content.startswith(layer + "::"), \
        "融合视图 opt/README 内容非 %s 层：%r" % (layer, content)


@step("then", r"决策表对该路径动作记录为 keep")
def then_keep_action(ctx):
    entry = _decision(ctx, "opt/README")
    assert entry["action"] == "keep", "动作非 keep：%r" % entry


@step("then", r"(\S+) 层同名内容不出现在融合视图")
def then_layer_absent(ctx, layer):
    for path in _merged_root(ctx).rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert not text.startswith(layer + "::"), \
                "%s 层内容泄漏进融合视图：%s" % (layer, path)


@step("then", r"manifest 索引在融合视图内容来自 (\S+) 层（pin）")
def then_pin_manifest(ctx, layer):
    _assert_pin(ctx, "manifest/index", layer)


@step("then", r"gitmodules 在融合视图内容来自 (\S+) 层（pin）")
def then_pin_gitmodules(ctx, layer):
    _assert_pin(ctx, ".gitmodules", layer)


@step("then", r"build 脚本在融合视图按层前缀隔离且互不覆盖")
def then_isolate_build(ctx):
    entry = _decision(ctx, "scripts/build.sh")
    assert entry["action"] == "isolate", "动作非 isolate：%r" % entry
    for name, root in ctx["fuse"]["layers"].items():
        if not (Path(root) / "scripts/build.sh").is_file():
            continue  # isolate 副本只属在场层（merge_guard 语义）
        target = _merged_root(ctx) / "mnt" / name / "scripts/build.sh"
        assert target.is_file(), "缺隔离副本：%s" % target
        expected = "%s::scripts/build.sh" % name
        assert target.read_text(encoding="utf-8").startswith(expected), \
            "隔离副本来源错误：%s" % target
    assert not (_merged_root(ctx) / "scripts/build.sh").exists(), \
        "隔离路径被物化到融合根（违反 H6）"


@step("then", r"实现不调用 mount、FUSE 设备或特权能力")
def then_no_privilege(ctx):
    src = ctx["fuse_src"]
    for pattern in (r"\bsubprocess\b", r"os\.system", r"os\.popen",
                    r"/dev/fuse", r"\bctypes\b", r"\bcap_add\b",
                    r"\bprivileged\b", r"\bmount\b", r"\bfuse\b"):
        assert not re.search(pattern, src), \
            "fuse_verify 源码含特权/子进程 token：%s" % pattern


@step("then", r"校验器运行于普通进程且决策表落盘输出目录")
def then_plain_process(ctx):
    report = ctx["fuse_report"]
    decisions_path = Path(ctx["fuse"]["out"]) / "decisions.json"
    assert decisions_path.is_file(), "决策表未落盘：%s" % decisions_path
    payload = json.loads(decisions_path.read_text(encoding="utf-8"))
    assert payload["passed"] == report["passed"], "决策表与报告不一致"
    if hasattr(os, "getuid"):  # 普通（非 setuid）进程内执行
        assert os.getuid() == os.geteuid()


@step("then", r"抽样路径决策与 OverlayResolver 独立重算一致")
def then_decision_replay(ctx):
    report = ctx["fuse_report"]
    resolver = OverlayResolver(load_policy(_ROOT))
    present_by_rel = {}
    for name, root in ctx["fuse"]["layers"].items():
        for dirpath, _dirs, files in os.walk(root):
            for fn in files:
                rel = Path(dirpath, fn).relative_to(root).as_posix()
                present_by_rel.setdefault(rel, []).append(name)
    for entry in report["decisions"]:
        arb = resolver.decide(entry["path"], present_by_rel[entry["path"]])
        assert arb["action"] == entry["action"], \
            "重算不一致 %s：%r vs %r" % (entry["path"], arb, entry)
        if arb["action"] in ("pin", "keep"):
            assert arb["layer"] == entry["layer"], \
                "权威层不一致 %s：%r vs %r" % (entry["path"], arb, entry)


@step("then", r"决策表含 lowerdir 层数与 max_lowerdir 校验结果")
def then_lowerdir_fields(ctx):
    low = ctx["fuse_report"]["lowerdir"]
    assert low["count"] == len(ctx["fuse"]["layers"]), "层数统计错误：%r" % low
    assert low["max"] >= low["count"] and low["ok"] is True, \
        "max_lowerdir 校验结果异常：%r" % low
