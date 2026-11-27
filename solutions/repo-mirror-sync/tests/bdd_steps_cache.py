# -*- coding: utf-8 -*-
# SC-M9-05~08 步骤定义：缓存 LRU 清理（合成目录库级调用，无网络行为）。
import json
import os
import sys
import tempfile

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from bdd_runner import step  # noqa: E402
import tools.cache_gc as cache_gc_mod  # noqa: E402



def _synth(ctx, blocks, versions, size=1000):
    root = tempfile.mkdtemp(prefix="bdd-cache-")
    for b in range(1, blocks + 1):
        block_id = "b%02d" % b
        bdir = os.path.join(root, block_id)
        os.makedirs(bdir)
        for v in range(1, versions + 1):
            with open(os.path.join(bdir, "block-%s-%d.tar" % (block_id, v)), "wb") as fh:
                fh.write(b"x" * size)
    ctx["cache_dir"] = root
    return root


@step("given", r'合成缓存目录含 "(\d+)" 块每块 "(\d+)" 版本')
def given_synth(ctx, blocks, versions):
    _synth(ctx, int(blocks), int(versions))


@step("given", r'合成缓存目录含 ".age" 加密残留')
def given_synth_age(ctx):
    root = _synth(ctx, 2, 1)
    with open(os.path.join(root, "b01", "block-b01-1.tar.age"), "wb") as fh:
        fh.write(b"age")


@step("when", r'运行缓存清理（库级 keep_blocks "(\d+)" keep_versions "(\d+)" 预算充足）')
def when_gc_keep(ctx, keep_blocks, keep_versions):
    ctx["gc"] = cache_gc_mod.clean(ctx["cache_dir"], budget_bytes=10 ** 12,
                                   keep_blocks=int(keep_blocks), keep_versions=int(keep_versions))


@step("when", r'运行缓存清理（库级 预算 "(\d+)" 字节）')
def when_gc_budget(ctx, budget):
    ctx["gc"] = cache_gc_mod.clean(ctx["cache_dir"], budget_bytes=int(budget),
                                   keep_blocks=8, keep_versions=2)


@step("then", r'删除清单含 "([^"]+)" 与 "([^"]+)"')
def then_deleted(ctx, a, b):
    deleted = " ".join(ctx["gc"]["deleted"])
    assert a in deleted and b in deleted, "删除清单缺 %s/%s：%r" % (a, b, ctx["gc"]["deleted"])


@step("then", r'保留块数为 "(\d+)"')
def then_kept(ctx, n):
    assert ctx["gc"]["kept_blocks"] == int(n), "保留块数 %r" % ctx["gc"]["kept_blocks"]


@step("then", r'清理日志有 "(\d+)" 行')
def then_log_lines(ctx, n):
    assert len(ctx["gc"]["log"]) == int(n), "日志行数 %r" % (ctx["gc"]["log"],)


@step("then", r"^清理结果标记预算超限$")
def then_over_budget(ctx):
    assert ctx["gc"]["over_budget"] is True


@step("then", r"^cache_pressure 事件双数成对$")
def then_pair(ctx):
    event = cache_gc_mod.build_cache_pressure_event(ctx["gc"], budget_bytes=1000)
    assert event["kind"] == "cache_pressure"
    assert (event["estimated_bytes"] is None) == (event["actual_bytes"] is None)
    assert event["estimated_bytes"] is not None
    ctx["pressure_event"] = event


@step("then", r"^删除后体积在预算内$")
def then_within(ctx):
    assert ctx["gc"]["bytes_after"] <= 1000, "清理后仍超预算：%r" % ctx["gc"]["bytes_after"]


@step("then", r"^加密残留文件仍在缓存目录$")
def then_age_kept(ctx):
    p = os.path.join(ctx["cache_dir"], "b01", "block-b01-1.tar.age")
    assert os.path.isfile(p), ".age 加密残留被误删"


@step("then", r"^清理日志含加密层告警$")
def then_age_warn(ctx):
    assert any(".age" in line for line in ctx["gc"]["log"]), "日志缺加密层告警"


@step("given", r"^已读取 tools/cache_gc\.py 源码$")
def given_gc_src(ctx):
    ctx["gc_src"] = open(os.path.join(_ROOT, "tools", "cache_gc.py"), encoding="utf-8").read()


@step("then", r"^源码不含保留块数硬编码$")
def then_no_hardcode(ctx):
    src = ctx["gc_src"]
    assert "keep_blocks=8" not in src and "keep_blocks: 8" not in src, "cache_gc.py 硬编码保留块数"


@step("then", r"^源码引用 limits 配置$")
def then_limits_ref(ctx):
    assert 'limits' in ctx["gc_src"] and 'load_scan' in ctx["gc_src"], "cache_gc.py 未引用 limits 配置"


@step("then", r'limits 配置含 keep_blocks "(\d+)" 与 keep_versions "(\d+)"')
def then_limits_values(ctx, blocks, versions):
    from tools.policy import load_scan
    cfg, _errors = load_scan(_ROOT)
    limits = cfg["limits"]
    assert limits["keep_blocks"] == int(blocks) and limits["keep_versions"] == int(versions)
