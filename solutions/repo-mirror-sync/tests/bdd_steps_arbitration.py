# -*- coding: utf-8 -*-
"""bdd_steps_arbitration — 合并裁决 BDD 步骤（SC-M10，阶段 3 补全）。

夹具约定：manifest_entry={"repo","rev"}；fetch={"repo","sha","source"}；
文件内容用 mark 字节串便于断言。步骤措辞与其他模块正则不重叠。
"""
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT))

from bdd_runner import step
from tools import merge_arbitration

MODULE_STEPS = {}


def _guard():
    from tools.merge_guard import MergeGuard
    from tools.overlay import OverlayResolver
    from tools.policy import load_policy
    return MergeGuard(OverlayResolver(load_policy(_ROOT)))


@step("given", r'^manifest 指定仓库 "(.+)" 基线 rev "(.+)"$')
def _given_manifest(ctx, repo, rev):
    ctx["manifest"] = {"repo": repo, "rev": rev}


@step("given", r'^漂移补拉包仓库 "(.+)" 补拉 sha "(.+)"$')
def _given_fetch(ctx, repo, sha):
    ctx["fetch"] = {"repo": repo, "sha": sha, "source": "drift"}


@step("given", r'^manifest 侧文件 "(.+)" 内容 "(.+)"$')
def _given_file_a(ctx, path, content):
    ctx.setdefault("files_a", {})[path] = content.encode("utf-8")


@step("given", r'^补拉侧文件 "(.+)" 内容 "(.+)"$')
def _given_file_b(ctx, path, content):
    ctx.setdefault("files_b", {})[path] = content.encode("utf-8")


@step("when", r"^执行合并裁决$")
def _when_arbitrate(ctx):
    ctx["result"] = merge_arbitration.arbitrate(ctx["manifest"], ctx["fetch"])


@step("when", r"^执行内容级去重$")
def _when_dedupe(ctx):
    ctx["decisions"] = merge_arbitration.dedupe(
        ctx["files_a"], ctx["files_b"], guard=_guard())


@step("when", r"^执行合并裁决落盘$")
def _when_write(ctx):
    ctx["result"] = merge_arbitration.arbitrate(ctx["manifest"], ctx["fetch"])
    ctx["tmp"] = tempfile.TemporaryDirectory()
    ctx["notice"] = merge_arbitration.write_quarantine(
        ctx["result"], ctx["tmp"].name)


@step("then", r"^裁决结果为丢弃补拉包$")
def _then_drop(ctx):
    assert ctx["result"]["action"] == "drop", ctx["result"]


@step("then", r'^合并日志包含仓库 "(.+)" 与补拉 sha "(.+)"$')
def _then_log(ctx, repo, sha):
    log = ctx["result"]["log"]
    assert log["repo"] == repo and log["fetch_sha"] == sha, log


@step("then", r"^裁决结果为降级隔离区$")
def _then_quarantine(ctx):
    assert ctx["result"]["action"] == "quarantine", ctx["result"]


@step("then", r'^隔离目录为 "(.+)"$')
def _then_dir(ctx, expect):
    assert ctx["result"]["quarantine_dir"] == expect, ctx["result"]


@step("then", r"^补拉包不进入发布镜像$")
def _then_not_published(ctx):
    assert ctx["result"]["published"] is False, ctx["result"]


@step("then", r"^隔离结果标记待人工确认$")
def _then_review(ctx):
    assert ctx["result"]["manual_review"] is True, ctx["result"]


@step("then", r"^处理顺序为 manifest 重建先于漂移补拉$")
def _then_order(ctx):
    assert ctx["result"]["order"] == ["manifest_rebuild", "drift_fetch"], ctx["result"]


@step("then", r'^路径 "(.+)" 裁决为硬链接去重$')
def _then_hardlink(ctx, path):
    match = [d for d in ctx["decisions"] if d["path"] == path]
    assert match and match[0]["action"] == "hardlink", ctx["decisions"]


@step("then", r'^路径 "(.+)" 裁决为隔离各层保留副本$')
def _then_isolate(ctx, path):
    match = [d for d in ctx["decisions"] if d["path"] == path]
    assert match and match[0]["action"] == "isolate", ctx["decisions"]
    assert match[0]["prefixes"], ctx["decisions"]


@step("then", r"^裁决结果与融合守卫独立重算一致$")
def _then_consistent(ctx):
    from tools.merge_guard import MergeGuard
    from tools.overlay import OverlayResolver
    from tools.policy import load_policy
    ref = MergeGuard(OverlayResolver(load_policy(_ROOT))).arbitrate(
        "scripts/build.sh", list(merge_arbitration.ARBITRATION_LAYERS))
    mine = [d for d in ctx["decisions"] if d["path"] == "scripts/build.sh"][0]
    assert mine["action"] == ref["action"], (mine, ref)
    assert mine["prefixes"] == ref["prefixes"], (mine, ref)


@step("then", r"^隔离区清单已写入且标记人工确认$")
def _then_notice(ctx):
    notice = Path(ctx["notice"])
    assert notice.is_file(), notice
    import json
    data = json.loads(notice.read_text(encoding="utf-8"))
    assert data["manual_review"] is True and data["published"] is False, data
