# -*- coding: utf-8 -*-
"""bdd_steps_plan — features/plan.feature 的步骤定义（SC-M3-01~05）。

纯计算求解：不访问网络（AGENTS §3.4）；落盘目录固定在仓库相对路径
out/bdd/（.gitignore 已忽略 **/out/**）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent          # tests/
_ROOT = _HERE.parent                             # solutions/repo-mirror-sync/
for _p in (str(_ROOT), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from bdd_runner import step                       # noqa: E402
from tools import plan as planner                 # noqa: E402
from tools.policy import PolicyError, load_policy, load_scan  # noqa: E402

_OUT_DIR = _ROOT / "out" / "bdd"


def _parse_list(raw):
    return [item.strip().strip('"') for item in raw.split(",") if item.strip()]


def _confirmed_budget():
    cfg, errors = load_scan(_ROOT)
    assert not errors, "config/scan.yaml 非法：%s" % errors
    return cfg["budget"]["budget_bytes"]


# ---------------------------------------------------------------- 假如/假设

@step("given", r'仓库夹具 "([^"]+)" 标签 \[([^\]]*)\] topics \[([^\]]*)\] 尺寸 (\d+)MB')
def given_fixture(ctx, repo, labels, topics, size_mb):
    ctx.setdefault("fixtures", []).append({
        "repo": repo,
        "labels": _parse_list(labels),
        "topics": _parse_list(topics),
        "size_bytes_est": int(size_mb) * 10 ** 6,   # MB=十进制（docs/01 §8 口径）
    })


# ---------------------------------------------------------------- 当

def _solve(ctx, combo_id):
    ctx["plan"] = planner.build_plan(
        ctx["fixtures"], load_policy(_ROOT), _confirmed_budget(),
        combo_id=combo_id)


@step("when", r'以组合 "([^"]+)" 求解并落盘 out')
def when_solve_dump(ctx, combo_id):
    _solve(ctx, combo_id)
    planner.write_plan(ctx["plan"], _OUT_DIR)


@step("when", r'以组合 "([^"]+)" 求解')
def when_solve(ctx, combo_id):
    _solve(ctx, combo_id)


@step("when", r'以未知组合 "([^"]+)" 求解')
def when_solve_unknown(ctx, combo_id):
    ctx["plan"] = None
    try:
        _solve(ctx, combo_id)
        ctx["error"] = None
    except PolicyError as exc:
        ctx["error"] = exc


# ---------------------------------------------------------------- 那么

@step("then", r'计划引用组合 "([^"]+)"')
def then_combo_ref(ctx, combo_id):
    assert ctx["plan"]["combo"] == combo_id


@step("then", r"块覆盖 \[([^\]]*)\]")
def then_blocks_covered(ctx, raw):
    assert {b["id"] for b in ctx["plan"]["blocks"]} == set(_parse_list(raw))


@step("then", "全部仓库入选且记录命中块与预估体积")
def then_all_selected(ctx):
    selected = {entry["repo"]: entry for entry in ctx["plan"]["repos"]}
    for fixture in ctx["fixtures"]:
        entry = selected.get(fixture["repo"])
        assert entry is not None, "仓库未入选：%s" % fixture["repo"]
        assert entry["block"] and entry["size_bytes_est"] == fixture["size_bytes_est"]
    assert ctx["plan"]["unassigned"] == [], "存在未匹配仓库"


@step("then", r"job 数量至少 (\d+) 且每个 job 体积不超确认预算")
def then_jobs_within_budget(ctx, min_jobs):
    budget = _confirmed_budget()
    jobs = ctx["plan"]["jobs"]
    assert len(jobs) >= int(min_jobs), "job 数 %d < %s" % (len(jobs), min_jobs)
    for job in jobs:
        assert job["size_bytes_est"] <= budget, \
            "job %s 超确认预算：%s" % (job["job"], job["size_bytes_est"])


@step("then", "所有入选块均入 job 且单块不跨 job")
def then_blocks_packed(ctx):
    planned_blocks = {b["id"] for b in ctx["plan"]["blocks"]}
    seen = []
    for job in ctx["plan"]["jobs"]:
        seen.extend(job["blocks"])
    assert set(seen) == planned_blocks, "块覆盖不一致"
    assert len(seen) == len(planned_blocks), "单块跨 job（docs/01 §10 约束 1）"


@step("then", r'记录 "([^"]+)" 降级为 (\S+) 且 flags 含 (\S+) 与 (\S+)')
def then_degraded(ctx, repo, strategy, flag1, flag2):
    hits = [d for d in ctx["plan"]["degraded"] if d["repo"] == repo]
    assert hits, "仓库未降级：%s" % repo
    entry = hits[0]
    assert entry["strategy"] == strategy
    assert flag1 in entry["flags"] and flag2 in entry["flags"], \
        "降级 flags 不符：%s" % entry["flags"]


@step("then", "其余仓库正常装箱不受降级影响")
def then_rest_packed(ctx):
    assert ctx["plan"]["jobs"], "无任何 job 产出"
    assert ctx["plan"]["unplaced"] == [], "出现不应有的块超预算"
    degraded_repos = {d["repo"] for d in ctx["plan"]["degraded"]}
    for fixture in ctx["fixtures"]:
        if fixture["repo"] not in degraded_repos:
            assert any(fixture["repo"] == r["repo"] for r in ctx["plan"]["repos"])


@step("then", r"out/plan\.json 含 (\S+)、(\S+)、(\S+) 与 (\S+) 字段")
def then_plan_json_fields(ctx, *fields):
    payload = json.loads((_OUT_DIR / "plan.json").read_text(encoding="utf-8"))
    for name in fields:
        assert name in payload, "plan.json 缺字段：%s" % name


@step("then", "同输入重跑得到相同 job 划分")
def then_reproducible(ctx):
    again = planner.build_plan(
        ctx["fixtures"], load_policy(_ROOT), _confirmed_budget(),
        combo_id=ctx["plan"]["combo"])
    assert again["jobs"] == ctx["plan"]["jobs"], "同输入 job 划分不可复现"


@step("then", r"显式抛出 (\S+) 且未产出任何计划")
def then_policy_error(ctx, exc_name):
    assert ctx["error"] is not None, "未报错（静默缺省）"
    assert type(ctx["error"]).__name__ == exc_name, \
        "异常类型不符：%s" % type(ctx["error"]).__name__
    assert ctx["plan"] is None
