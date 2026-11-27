# -*- coding: utf-8 -*-
"""scan_inventory — 体积清单扫描器（阶段 1，docs/01 §7）。

职责：以受控配额产出唯一真相表 out/inventory.json（docs/01 §7.2 的 14 字段）
与人读版 out/inventory.csv；先比 head_sha 再算体积；配额耗尽保存 cursor 续跑。

硬性约束（AGENTS §3）：
- 一切阈值来自 config/scan.yaml，本模块零策略常量；
- GitHub token 一律走环境变量，禁止入库与写日志；
- 请求次数受 scan.max_requests_per_run 约束（RequestBudget 强制）；
- 本模块只含纯逻辑与薄适配层，测试通过注入假 fetcher 覆盖行为
  （场景见 features/scan_inventory.feature，SC-M1-01~07）。
"""

from __future__ import annotations

import csv
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools import budget as budget_mod

__all__ = [
    "FIELDS", "RequestBudget", "BudgetExhausted", "iso_now", "build_record",
    "scan", "write_inventory", "save_cursor", "load_cursor",
    "make_github_fetcher", "main",
]

TZ = timezone(timedelta(hours=8))

# docs/01 §7.2 表结构唯一真相：14 字段，顺序即 CSV 列序
FIELDS = [
    "repo", "topics", "labels", "default_branch", "size_kb", "size_bytes_est",
    "lfs_bytes", "head_sha", "head_sha_at", "path_in_manifest", "shared_paths",
    "last_scanned", "scan_status", "mirror_sha",
]


class BudgetExhausted(RuntimeError):
    """请求预算耗尽（调用方须保存 cursor 续跑）。"""


class RequestBudget:
    """单次运行的请求预算（max_requests 来自 config/scan.yaml）。"""

    def __init__(self, max_requests):
        if not isinstance(max_requests, int) or max_requests <= 0:
            raise ValueError("max_requests 必须为正整数")
        self.max_requests = max_requests
        self.used = 0

    def take(self, n=1):
        if self.used + n > self.max_requests:
            raise BudgetExhausted(
                "请求预算耗尽（已用 %d / 上限 %d）" % (self.used, self.max_requests))
        self.used += n


def iso_now():
    """当前时间（ISO 8601，+08:00，AGENTS §1）。"""
    return datetime.now(TZ).isoformat(timespec="seconds")


def build_record(meta, tree, prev, now):
    """由仓库元数据 + 树统计构建 14 字段记录（docs/01 §7.2）。"""
    record = {
        "repo": meta["full_name"],
        "topics": list(meta.get("topics", [])),
        "labels": list(meta.get("labels", [])),
        "default_branch": meta["default_branch"],
        "size_kb": int(tree["size_kb"]),
        "size_bytes_est": int(tree["size_kb"]) * 1024,
        "lfs_bytes": int(tree.get("lfs_bytes", 0)),
        "head_sha": meta["head_sha"],
        "head_sha_at": now,
        "path_in_manifest": meta.get("path_in_manifest", ""),
        "shared_paths": list(meta.get("shared_paths", [])),
        "last_scanned": now,
        "scan_status": "ok",
        "mirror_sha": (prev or {}).get("mirror_sha", ""),
    }
    if sorted(record) != sorted(FIELDS):
        raise RuntimeError("记录字段与 docs/01 §7.2 不一致")
    return record


def scan(repos, fetcher, max_requests, prev_records=None, cursor=None,
         now=None, confirmed_budget=None):
    """扫描主循环：返回 {"records", "cursor", "stats", "complete"}。

    repos: 夹具/上游提供的仓库描述列表（full_name、head_sha、size_kb 等）；
    fetcher(kind, repo=…, branch=…, sha=…): 数据源适配（测试注入假实现）；
    先比 head_sha：未变仓库仅消耗 1 次请求（docs/01 §7.3）。
    返回的 records 为合并后的完整清单：上轮记录中不在本轮 order 的仓库
    原样随行（cursor 续跑时已扫仓库不丢失），本轮处理的仓库重建/沿用。
    """
    now = now or iso_now()
    prev = {r["repo"]: r for r in (prev_records or [])}
    fixture = {r["full_name"]: r for r in repos}
    order = list(cursor["remaining"]) if cursor else [r["full_name"] for r in repos]
    in_order = set(order)
    records = [dict(r) for r in (prev_records or []) if r["repo"] not in in_order]
    budget = RequestBudget(max_requests)
    stats = {"requests": 0, "scanned": 0, "skipped": 0}
    remaining = None
    try:
        for index, name in enumerate(order):
            prev_rec = prev.get(name)
            if prev_rec is not None:
                budget.take()  # 1 次：比 sha
                head = fetcher("head", repo=name, branch=prev_rec["default_branch"])
                if head["sha"] == prev_rec["head_sha"]:
                    record = dict(prev_rec)          # 未变：沿用上轮记录
                    record["last_scanned"] = now     # head_sha_at 不刷新
                    records.append(record)
                    stats["skipped"] += 1
                    continue
                budget.take()
                meta = fetcher("repo", repo=name)
                budget.take()
                tree = fetcher("tree", repo=name, sha=head["sha"])
            else:
                budget.take()
                meta = fetcher("repo", repo=name)
                budget.take()
                head = fetcher("head", repo=name, branch=meta["default_branch"])
                budget.take()
                tree = fetcher("tree", repo=name, sha=head["sha"])
            meta["head_sha"] = head["sha"]  # F-9 回填：以引用探测值覆盖元数据缺省（真实适配层 meta 不含 head_sha）
            record = build_record(meta, tree, prev_rec, now)
            if confirmed_budget is not None and budget_mod.decide(
                record["size_bytes_est"], confirmed_budget
            ) == "split":
                record["scan_status"] = "oversized"   # docs/01 §7.2 枚举
            records.append(record)
            stats["scanned"] += 1
    except BudgetExhausted:
        remaining = {"remaining": order[index:], "reason": "budget_exhausted"}
    stats["requests"] = budget.used
    return {
        "records": records,
        "cursor": remaining,
        "stats": stats,
        "complete": remaining is None,
    }


def write_inventory(records, out_dir, now=None):
    """落盘 out/inventory.json 与 out/inventory.csv（docs/01 §7.3）。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    now = now or iso_now()
    payload = {"generated": now, "repos": records}
    (out_dir / "inventory.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    with open(out_dir / "inventory.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for record in records:
            row = dict(record)
            for key in ("topics", "labels", "shared_paths"):
                row[key] = ";".join(row[key])
            writer.writerow(row)
    return out_dir


def save_cursor(path, cursor):
    """保存 cursor（docs/01 §7.3：预算耗尽保存中断点）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cursor, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def load_cursor(path):
    """读取 cursor；文件不存在返回 None。"""
    path = Path(path)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_tokens(token_env="GH_TOKEN"):
    """FR-A3：GH_TOKENS（逗号分隔多 token 轮转）优先，回退单 GH_TOKEN。"""
    raw = os.environ.get("GH_TOKENS", "")
    tokens = [part.strip() for part in raw.split(",") if part.strip()]
    if not tokens:
        single = os.environ.get(token_env)
        if single:
            tokens = [single]
    return tokens


def make_github_fetcher(token_env="GH_TOKEN", api_base="https://api.github.com"):
    """GitHub REST 适配薄层（仅生产使用；测试注入假 fetcher）。

    token 只从环境变量读取（AGENTS §3.4），任何响应内容不回显 token。
    GH_TOKENS 多 token 轮转（FR-A3）：遇 403/429 依序切换下一枚，全部耗尽再抛错。
    """
    tokens = _resolve_tokens(token_env)
    if not tokens:
        raise RuntimeError("环境变量 %s 未设置（ refusing to call GitHub API）" % token_env)
    _idx = 0

    def _get(path):
        nonlocal _idx
        request = urllib.request.Request(
            api_base + path,
            headers={
                "Authorization": "Bearer " + tokens[_idx],
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            })
        try:
            with urllib.request.urlopen(request) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429) and _idx + 1 < len(tokens):
                _idx += 1  # 轮转到下一枚 token（FR-A3），不回显任何凭据
                return _get(path)
            raise

    def fetch(kind, repo=None, branch=None, sha=None):
        if kind == "head":
            return {"sha": _get("/repos/%s/branches/%s" % (repo, branch))["commit"]["sha"]}
        if kind == "repo":
            data = _get("/repos/" + repo)
            return {
                "full_name": data["full_name"],
                "topics": data.get("topics", []),
                "labels": [],
                "default_branch": data["default_branch"],
                "head_sha": "",
                "size_kb": int(data.get("size", 0)),
                "lfs_bytes": 0,
            }
        if kind == "tree":
            data = _get("/repos/%s/git/trees/%s?recursive=1" % (repo, sha))
            if data.get("truncated"):
                raise RuntimeError("tree 响应被截断：%s（需分页实现）" % repo)
            total = sum(int(b.get("size", 0)) for b in data.get("tree", [])
                        if b.get("type") == "blob")
            return {"size_kb": max(1, total // 1024), "lfs_bytes": 0}
        raise ValueError("未知 fetch kind：%s" % kind)

    return fetch


def main(argv=None):
    """CLI 入口：--repos <json 夹具文件> [--out out]（首版全量扫描）。"""
    import argparse
    from tools import policy as policy_mod

    parser = argparse.ArgumentParser(description="体积清单扫描器")
    parser.add_argument("--repos", required=True, help="仓库描述 JSON 文件（夹具同构）")
    parser.add_argument("--out", default="out", help="产物目录（仓库相对路径）")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    scan_cfg, _errors = policy_mod.load_scan(root)
    repos = json.loads(Path(args.repos).read_text(encoding="utf-8"))
    prev_path = Path(args.out) / "inventory.json"
    prev_records = []
    if prev_path.is_file():
        prev_records = json.loads(prev_path.read_text(encoding="utf-8")).get("repos", [])
    cursor = load_cursor(Path(args.out) / "cursor.json")
    result = scan(
        repos, make_github_fetcher(),
        scan_cfg["scan"]["max_requests_per_run"],
        prev_records=prev_records, cursor=cursor,
        confirmed_budget=scan_cfg["budget"]["budget_bytes"],
    )
    if result["cursor"]:
        save_cursor(Path(args.out) / "cursor.json", result["cursor"])
    write_inventory(result["records"], args.out)
    if not result["complete"]:
        # FR-A1：预算耗尽产出 budget_exceeded 事件（NFR-6 双数成对），notify 步骤投递
        actual_bytes = sum(int(r.get("size_bytes_est", 0)) for r in result["records"])
        budget_event = {
            "kind": "budget_exceeded",
            "subject": "scan-run",
            "summary": "本轮扫描未完成：确认体积超预算，游标已保存待续跑",
            "estimated_bytes": scan_cfg["budget"]["budget_bytes"],
            "actual_bytes": actual_bytes,
        }
        (Path(args.out) / "alert-events.json").write_text(
            json.dumps([budget_event], ensure_ascii=False, indent=2), encoding="utf-8")
    print("扫描%s：仓库 %d，请求 %d 次"
          % ("完成" if result["complete"] else "未完成（cursor 已保存）",
             len(result["records"]), result["stats"]["requests"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
