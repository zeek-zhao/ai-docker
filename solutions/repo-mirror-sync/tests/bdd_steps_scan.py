# -*- coding: utf-8 -*-
"""bdd_steps_scan — features/scan_inventory.feature 的步骤定义（SC-M1-01~07）。

只使用注入的 FakeFetcher，绝不访问网络（AGENTS §3.4）；
落盘目录固定在仓库相对路径 out/bdd/（.gitignore 已忽略 **/out/**）。
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent          # tests/
_ROOT = _HERE.parent                             # solutions/repo-mirror-sync/
for _p in (str(_ROOT), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from bdd_runner import step                       # noqa: E402
from tools import policy as policy_mod            # noqa: E402
from tools import scan_inventory as scanner       # noqa: E402

_OUT_DIR = _ROOT / "out" / "bdd"


class FakeFetcher:
    """数据源替身：与 scanner.make_github_fetcher 同契约（kind head/repo/tree）。

    secret 槽位模拟「fetcher 内部持有 token」——产物文本断言它绝不泄漏。
    """

    def __init__(self, fixtures, secret=None):
        self.fixtures = {f["full_name"]: f for f in fixtures}
        self.secret = secret
        self.calls = []

    def __call__(self, kind, repo=None, branch=None, sha=None):
        self.calls.append((kind, repo))
        fixture = self.fixtures[repo]
        if kind == "head":
            return {"sha": fixture["head_sha"]}
        if kind == "repo":
            meta = dict(fixture)
            if fixture.get("meta_head_sha_empty"):
                meta["head_sha"] = ""  # 模拟 make_github_fetcher 真实形态（F-9）
            return meta
        if kind == "tree":
            return {"size_kb": fixture["size_kb"], "lfs_bytes": fixture.get("lfs_bytes", 0)}
        raise ValueError(kind)


# ---- SC-M1-09 多 token 轮转静态断言（FR-A3；步骤追加） ----

@step("given", r"^已读取 tools/scan_inventory\.py 源码$")
def given_scanner_src(ctx):
    ctx["scanner_src"] = (_ROOT / "tools" / "scan_inventory.py").read_text(encoding="utf-8")


@step("then", r"^源码支持 GH_TOKENS 逗号分隔轮转$")
def then_rotation(ctx):
    assert "GH_TOKENS" in ctx["scanner_src"], "scan_inventory.py 缺 GH_TOKENS 轮转"


@step("then", r"^源码保留 GH_TOKEN 单 token 回退$")
def then_fallback(ctx):
    assert 'os.environ.get(token_env)' in ctx["scanner_src"], "缺 GH_TOKEN 回退读取"


@step("then", r"^源码不含 token 字面量$")
def then_no_literal(ctx):
    src = ctx["scanner_src"]
    assert "ghp_" not in src and "github_pat_" not in src, "源码含 token 字面量"


def _parse_list(raw):
    """解析 `[a, b]` 形式的步骤参数 → Python 列表。"""
    return [item.strip().strip('"') for item in raw.split(",") if item.strip()]


def _find(records, repo):
    for record in records:
        if record["repo"] == repo:
            return record
    raise AssertionError("记录缺失：%s" % repo)


def _prev_record(repo, sha, branch, size_kb):
    """构造上一轮的 14 字段记录（时间取固定过去值，便于断言沿用/刷新）。"""
    past = "2026-01-01T08:00:00+08:00"
    return {
        "repo": repo, "topics": [], "labels": [], "default_branch": branch,
        "size_kb": int(size_kb), "size_bytes_est": int(size_kb) * 1024,
        "lfs_bytes": 0, "head_sha": sha, "head_sha_at": past,
        "path_in_manifest": "", "shared_paths": [], "last_scanned": past,
        "scan_status": "ok", "mirror_sha": "",
    }


# ---------------------------------------------------------------- 假如/假设

@step("given", r"配置加载自 config 且请求上限为 (\d+)")
def given_config(ctx, max_requests):
    cfg, errors = policy_mod.load_scan(_ROOT)
    assert not errors, "config/scan.yaml 非法：%s" % errors
    ctx["scan_cfg"] = cfg
    ctx["max_requests"] = int(max_requests)
    ctx["confirmed"] = cfg["budget"]["budget_bytes"]


@step("given", "上一轮清单为空")
def given_prev_empty(ctx):
    ctx["prev"] = []


@step("given", r'上一轮清单中 "([^"]+)" 的 head_sha 为 (\S+) 分支 (\S+) 尺寸 (\d+)KB')
def given_prev_repo(ctx, repo, sha, branch, size_kb):
    ctx.setdefault("prev", []).append(_prev_record(repo, sha, branch, size_kb))


@step("given", r'仓库夹具 "([^"]+)" 元数据 head_sha 置空 头指针 (\S+) 分支 (\S+)')
def given_fixture_no_meta_sha(ctx, repo, sha, branch):
    """F-9 回归夹具：head 探测返回真实 sha，repo 元数据 head_sha 为空串。"""
    ctx.setdefault("fixtures", []).append({
        "full_name": repo, "topics": [], "labels": [], "default_branch": branch,
        "head_sha": sha, "size_kb": 100, "meta_head_sha_empty": True,
    })


@step("given", r'仓库夹具 "([^"]+)" 有 topics \[([^\]]*)\] 标签 \[([^\]]*)\] '
               r'头指针 (\S+) 分支 (\S+) 尺寸 (\d+)KB')
def given_fixture(ctx, repo, topics, labels, sha, branch, size_kb):
    ctx.setdefault("fixtures", []).append({
        "full_name": repo,
        "topics": _parse_list(topics),
        "labels": _parse_list(labels),
        "default_branch": branch,
        "head_sha": sha,
        "size_kb": int(size_kb),
    })


# ---------------------------------------------------------------- 当

def _execute_scan(ctx):
    ctx["now"] = scanner.iso_now()
    fetcher = FakeFetcher(ctx["fixtures"])
    ctx["fetcher"] = fetcher
    ctx["result"] = scanner.scan(
        ctx["fixtures"], fetcher, ctx["max_requests"],
        prev_records=ctx["prev"], now=ctx["now"],
        confirmed_budget=ctx["confirmed"])


@step("when", "执行扫描")
def when_scan(ctx):
    _execute_scan(ctx)


@step("when", r"执行扫描并落盘 out（fetcher 持有示例密钥）")
def when_scan_dump_secret(ctx):
    _execute_scan(ctx)
    _dump(ctx)


@step("when", r"执行扫描并落盘 out")
def when_scan_dump(ctx):
    _execute_scan(ctx)
    _dump(ctx)


def _dump(ctx):
    for name in ("inventory.json", "inventory.csv"):
        path = _OUT_DIR / name
        if path.exists():
            path.unlink()
    scanner.write_inventory(ctx["result"]["records"], _OUT_DIR, now=ctx["now"])
    ctx["out_dir"] = str(_OUT_DIR)


@step("when", r"以剩余 \[([^\]]*)\] 的游标续跑")
def when_continue(ctx, raw):
    # 模拟首轮中断后的续跑：上轮清单已持久化（ctx["prev"]），cursor 剩余列表
    # 来自 out/cursor.json；scan() 返回合并后的完整清单（已扫仓库随行不丢失）
    ctx["now"] = scanner.iso_now()
    fetcher = FakeFetcher(ctx["fixtures"])
    ctx["fetcher"] = fetcher
    ctx["result"] = scanner.scan(
        ctx["fixtures"], fetcher, ctx["max_requests"],
        prev_records=ctx["prev"],
        cursor={"remaining": _parse_list(raw)},
        now=ctx["now"], confirmed_budget=ctx["confirmed"])


# ---------------------------------------------------------------- 那么

@step("then", r"产出记录有 (\d+) 条 且消耗请求 (\d+) 次")
def then_records_and_requests(ctx, n_records, n_requests):
    assert len(ctx["result"]["records"]) == int(n_records), \
        "记录数 %d != %s" % (len(ctx["result"]["records"]), n_records)
    assert ctx["result"]["stats"]["requests"] == int(n_requests), \
        "请求次数 %d != %s" % (ctx["result"]["stats"]["requests"], n_requests)


@step("then", r"记录字段集合与 docs/01 §7\.2 的 14 字段完全一致")
def then_fields(ctx):
    for record in ctx["result"]["records"]:
        assert set(record) == set(scanner.FIELDS), \
            "字段集合不一致：%s" % (set(record) ^ set(scanner.FIELDS))


@step("then", r'记录 "([^"]+)" 的 (\w+) 等于 (\d+)')
def then_field_equals(ctx, repo, field, value):
    assert _find(ctx["result"]["records"], repo)[field] == int(value)


@step("then", r'记录 "([^"]+)" 的 head_sha_at 沿用上一轮 且 last_scanned 已刷新')
def then_sha_at_kept(ctx, repo):
    record = _find(ctx["result"]["records"], repo)
    prev = _find(ctx["prev"], repo)
    assert record["head_sha_at"] == prev["head_sha_at"], "head_sha_at 被刷新"
    assert record["last_scanned"] == ctx["now"], "last_scanned 未刷新"
    assert record["last_scanned"] != prev["last_scanned"]


@step("then", "扫描未完成")
def then_incomplete(ctx):
    assert ctx["result"]["complete"] is False


@step("then", r"已产出记录 (\d+) 条")
def then_record_count(ctx, n_records):
    assert len(ctx["result"]["records"]) == int(n_records)


@step("then", r"cursor 剩余 \[([^\]]*)\]")
def then_cursor_remaining(ctx, raw):
    assert ctx["result"]["cursor"]["remaining"] == _parse_list(raw)


@step("then", r"扫描完成 且已产出记录 (\d+) 条 且游标清空")
def then_complete(ctx, n_records):
    assert ctx["result"]["complete"] is True
    assert ctx["result"]["cursor"] is None
    assert len(ctx["result"]["records"]) == int(n_records)


@step("then", r'记录 "([^"]+)" 的 (\w+) 为 (\S+)')
def then_field_is(ctx, repo, field, value):
    assert _find(ctx["result"]["records"], repo)[field] == value


@step("then", r'记录 "([^"]+)" 仍在清单中')
def then_present(ctx, repo):
    _find(ctx["result"]["records"], repo)


@step("then", "out 目录生成 inventory.json 与 inventory.csv")
def then_out_files(ctx):
    for name in ("inventory.json", "inventory.csv"):
        path = Path(ctx["out_dir"]) / name
        assert path.is_file() and path.stat().st_size > 0, "产物缺失：%s" % name


@step("then", r"inventory\.json 记录数与 inventory\.csv 数据行数一致且为 (\d+)")
def then_out_rows(ctx, n_records):
    payload = json.loads((Path(ctx["out_dir"]) / "inventory.json").read_text(encoding="utf-8"))
    with open(Path(ctx["out_dir"]) / "inventory.csv", encoding="utf-8") as fh:
        csv_rows = sum(1 for _ in csv.reader(fh)) - 1  # 去表头
    assert len(payload["repos"]) == csv_rows == int(n_records)


@step("then", r"out 目录产物文本不包含 (\S+) 也不包含 (\S+) 键名")
def then_no_leak(ctx, secret, key_name):
    # 模拟 fetcher 内部持有 token：赋值后再断言产物文本不泄漏
    ctx["fetcher"].secret = secret
    texts = "".join(
        path.read_text(encoding="utf-8")
        for path in Path(ctx["out_dir"]).iterdir() if path.is_file())
    assert secret not in texts, "产物泄漏密钥内容"
    assert key_name not in texts, "产物泄漏键名 %s" % key_name
