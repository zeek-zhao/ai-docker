# -*- coding: utf-8 -*-
"""bdd_steps_drift — features/detect_drift.feature 的步骤定义（SC-M6-01~06）。

只使用注入的 FakeUpstream/FakeMirrorProber，绝不访问网络（AGENTS §3.4）；
与既有 bdd_steps_* 共享 bdd_runner.MODULE_STEPS 注册表（docs/05 §3），
故本模块步骤措辞与其他里程碑步骤正则互不重叠。
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent          # tests/
_ROOT = _HERE.parent                             # solutions/repo-mirror-sync/
for _p in (str(_ROOT), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from bdd_runner import step                       # noqa: E402
from tools import alert as alert_mod              # noqa: E402
from tools import detect_drift as drifter         # noqa: E402


class FakeUpstream:
    """上游数据源替身：与 scanner.make_github_fetcher 同契约（kind="head"）。"""

    def __init__(self, fixtures):
        self.fixtures = {f["repo"]: f for f in fixtures}

    def __call__(self, kind, repo=None, branch=None, sha=None):
        if kind != "head":
            raise ValueError(kind)
        return {"sha": self.fixtures[repo]["head_sha"]}


class FakeMirrorProber:
    """mirror 侧 ls-remote 替身：返回配置的 HEAD sha（只读引用，无对象下载）。"""

    def __init__(self, sha_by_repo):
        self.sha_by_repo = dict(sha_by_repo)
        self.calls = []

    def __call__(self, repo):
        self.calls.append(repo)
        return self.sha_by_repo[repo]


def _record(repo, head_sha, branch, mirror_sha=""):
    """构造上一轮的 14 字段记录（docs/01 §7.2）。"""
    past = "2026-01-01T08:00:00+08:00"
    return {
        "repo": repo, "topics": [], "labels": [], "default_branch": branch,
        "size_kb": 100, "size_bytes_est": 100 * 1024, "lfs_bytes": 0,
        "head_sha": head_sha, "head_sha_at": past, "path_in_manifest": "",
        "shared_paths": [], "last_scanned": past, "scan_status": "ok",
        "mirror_sha": mirror_sha,
    }


def _find(records, repo):
    for record in records:
        if record["repo"] == repo:
            return record
    raise AssertionError("记录缺失：%s" % repo)


# ---------------------------------------------------------------- 假如/假设

@step("given", r'清单中 "([^"]+)" 的 head_sha 为 (\S+) 分支 (\S+) mirror_sha (\S+)')
def given_prev_with_mirror(ctx, repo, sha, branch, mirror):
    ctx.setdefault("prev", []).append(_record(repo, sha, branch, mirror))


@step("given", r'清单中 "([^"]+)" 的 head_sha 为 (\S+) 分支 (\S+)')
def given_prev(ctx, repo, sha, branch):
    ctx.setdefault("prev", []).append(_record(repo, sha, branch))


@step("given", r'上游 "([^"]+)" 的真实 HEAD 为 (\S+)')
def given_upstream(ctx, repo, sha):
    ctx.setdefault("fixtures", []).append({"repo": repo, "head_sha": sha})


@step("given", r'mirror 侧 "([^"]+)" 的 HEAD 为 (\S+)')
def given_mirror(ctx, repo, sha):
    ctx.setdefault("mirror", {})[repo] = sha


# ---------------------------------------------------------------- 当

@step("when", r"执行漂移检测 请求上限为 (\d+)")
def when_detect(ctx, max_requests):
    prober = FakeMirrorProber(ctx.get("mirror", {}))
    ctx["prober"] = prober
    ctx["result"] = drifter.detect(
        ctx["prev"], FakeUpstream(ctx.get("fixtures", [])), prober,
        int(max_requests))


# ---------------------------------------------------------------- 那么

@step("then", r"漂移事件数为 (\d+)")
def then_event_count(ctx, n_events):
    assert len(ctx["result"]["events"]) == int(n_events), \
        "事件数 %d != %s" % (len(ctx["result"]["events"]), n_events)


@step("then", r"清单记录 (\d+) 条 且消耗请求 (\d+) 次")
def then_records_requests(ctx, n_records, n_requests):
    assert len(ctx["result"]["records"]) == int(n_records), \
        "记录数 %d != %s" % (len(ctx["result"]["records"]), n_records)
    assert ctx["result"]["stats"]["requests"] == int(n_requests), \
        "请求次数 %d != %s" % (ctx["result"]["stats"]["requests"], n_requests)


@step("then", r'记录 "([^"]+)" 写回 mirror_sha (\S+)')
def then_mirror_written(ctx, repo, sha):
    assert _find(ctx["result"]["records"], repo)["mirror_sha"] == sha


@step("then", r'记录 "([^"]+)" 保留 head_sha (\S+)')
def then_head_kept(ctx, repo, sha):
    assert _find(ctx["result"]["records"], repo)["head_sha"] == sha


@step("then", r"事件 kind 为 (\S+)")
def then_event_kind(ctx, kind):
    assert ctx["result"]["events"][0]["kind"] == kind


@step("then", r'事件 subject 为 "([^"]+)"')
def then_event_subject(ctx, repo):
    assert ctx["result"]["events"][0]["subject"] == repo


@step("then", r'事件 summary 包含 "([^"]+)"')
def then_event_summary(ctx, phrase):
    assert phrase in ctx["result"]["events"][0]["summary"], \
        "summary 缺少 %r：%r" % (phrase, ctx["result"]["events"][0]["summary"])


@step("then", "检测未完成")
def then_incomplete(ctx):
    assert ctx["result"]["complete"] is False


@step("then", r"漂移游标剩余 \[([^\]]*)\]")
def then_cursor(ctx, raw):
    expected = [item.strip() for item in raw.split(",") if item.strip()]
    assert ctx["result"]["cursor"]["remaining"] == expected


@step("then", "事件通过告警白名单构建 payload 成功")
def then_payload(ctx):
    rules = alert_mod.load_alert_policy(str(_ROOT))
    ctx["payload"] = alert_mod.build_payload(ctx["result"]["events"][0], rules)


@step("then", r"事件 payload dedup_key 为 (\S+)")
def then_dedup(ctx, key):
    assert ctx["payload"]["dedup_key"] == key


@step("then", r"事件 payload channels 为 \[([^\]]*)\]")
def then_channels(ctx, raw):
    expected = [item.strip() for item in raw.split(",") if item.strip()]
    assert ctx["payload"]["channels"] == expected


@step("then", r"mirror 探测共 (\d+) 次")
def then_probes(ctx, n_probes):
    assert len(ctx["prober"].calls) == int(n_probes)
