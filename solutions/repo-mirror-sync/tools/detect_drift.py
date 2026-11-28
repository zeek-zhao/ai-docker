# -*- coding: utf-8 -*-
"""detect_drift — 漂移检测器（阶段 3，FR-D1/IF-2，docs/01 §12.2）。

职责：以 out/inventory.json（唯一真相表）为输入，对每个仓库只比 sha 不下载内容：
上游真实 HEAD sha（GitHub API，受请求预算约束）vs mirror 侧 ``ls-remote``
HEAD sha（git 协议只读远端引用，不占 API 配额）。不一致则产出
``drift_detected`` 事件（白名单与节流唯一出处 config/policy.yaml，
由 tools/alert.py 校验构建 payload），并把观测到的 mirror sha 写回记录
``mirror_sha``（docs/01 §12.2）。

硬性约束（AGENTS §3）：
- 零策略常量：请求上限取 config/scan.yaml 的 ``scan.max_requests_per_run``；
- token 一律走环境变量（复用 scanner.make_github_fetcher），禁止入库与写日志；
- 与 scan_inventory 同属扫描子系统（docs/02 §4）：本模块是唯一调 GitHub
  API/git 的地方之一；测试通过注入假 fetcher/prober 覆盖行为，禁止真实网络
  调用（场景见 features/detect_drift.feature，SC-M6-01~06）。

需求映射：FR-D1 漂移检测（R15/ADR-002）；IF-2 git ls-remote 只读引用。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tools import scan_inventory as scanner

__all__ = ["detect", "build_event", "make_lsremote_prober", "main"]


def build_event(repo, upstream_sha, mirror_sha):
    """构建漂移事件（docs/01 §12.2：提示 repo sync --force-sync 或刷新 mirror）。

    事件 kind 必须在 config/policy.yaml ``alert.on`` 白名单内（drift_detected）；
    体积双数字段（estimated/actual_bytes）不适用，留空由 alert 层校验放行。
    """
    return {
        "kind": "drift_detected",
        "subject": repo,
        "summary": ("仓库 %s 漂移：上游 HEAD %s != mirror %s；"
                    "请执行 repo sync --force-sync 或刷新 mirror"
                    % (repo, upstream_sha, mirror_sha)),
        "upstream_sha": upstream_sha,
        "mirror_sha": mirror_sha,
    }


def detect(records, fetcher, mirror_prober, max_requests, now=None):
    """漂移检测主循环（FR-D1）。

    返回 ``{"records", "events", "stats", "cursor", "complete", "now"}``：
    - records: 14 字段记录列表（docs/01 §7.2）；已检仓库写回观测 mirror_sha
      并刷新 last_scanned（head_sha/head_sha_at 属扫描器职责，本模块不碰）；
    - events: drift_detected 事件列表（drifted 个）；
    - cursor: 预算耗尽时 {"remaining": [未检仓库名], "reason": …}，否则 None；
      未检仓库原样随行输出（与扫描器合并语义一致）；
    - fetcher(kind, repo=…, branch=…): 上游数据源（kind="head"，与扫描器同
      契约，每仓库消耗 1 次请求预算）；
    - mirror_prober(repo): mirror 侧只读探测（git 协议，不占 API 配额，IF-2）。
    """
    now = now or scanner.iso_now()
    budget = scanner.RequestBudget(max_requests)
    events, out_records = [], []
    stats = {"requests": 0, "repos": 0, "drifted": 0, "unchanged": 0}
    cursor = None
    index = 0
    try:
        for index, record in enumerate(records):
            budget.take()  # 上游真实 HEAD：每仓库 1 次 API
            upstream = fetcher("head", repo=record["repo"],
                               branch=record["default_branch"])["sha"]
            mirror = mirror_prober(record["repo"])     # git 协议，不计配额
            updated = dict(record)
            updated["mirror_sha"] = mirror              # 写回观测值（§12.2）
            updated["last_scanned"] = now
            out_records.append(updated)
            stats["repos"] += 1
            if upstream != mirror:
                stats["drifted"] += 1
                events.append(build_event(record["repo"], upstream, mirror))
            else:
                stats["unchanged"] += 1
    except scanner.BudgetExhausted:
        cursor = {"remaining": [r["repo"] for r in records[index:]],
                  "reason": "budget_exhausted"}
        out_records.extend(dict(r) for r in records[index:])  # 未检仓库随行
    stats["requests"] = budget.used
    return {"records": out_records, "events": events, "stats": stats,
            "cursor": cursor, "complete": cursor is None, "now": now}


def make_lsremote_prober(url_template="https://github.com/{repo}.git"):
    """git ls-remote 只读探测薄层（仅生产使用；测试注入假 prober）。

    只读远端引用（IF-2），不下载任何对象；mirror 地址模板由调用方注入
    （部署形态相关，非策略常量）。git 失败向上抛出，由调用方按 scan_error
    告警口径处置（FR-A1）。
    """

    def prober(repo):
        url = url_template.format(repo=repo)
        result = subprocess.run(
            ["git", "ls-remote", url, "HEAD"],
            capture_output=True, text=True, check=True)
        lines = result.stdout.strip().splitlines()
        return lines[0].split()[0] if lines else ""

    return prober


def main(argv=None):
    """CLI 入口：python3 tools/detect_drift.py [--inventory out/inventory.json] [--out out]。

    读 config/scan.yaml 取请求上限；把观测 mirror_sha 写回 inventory.json/csv；
    预算耗尽保存 out/drift-cursor.json 续跑；漂移事件落 out/drift_events.json
    （运行时产物，out/ 不入库），投递由调用方经 tools/alert.py 完成。
    """
    import argparse

    from tools import policy as policy_mod

    parser = argparse.ArgumentParser(description="漂移检测器（FR-D1）")
    parser.add_argument("--inventory", default="out/inventory.json",
                        help="唯一真相表输入（方案相对路径）")
    parser.add_argument("--out", default="out",
                        help="写回目录（inventory.json/csv 与游标/事件产物）")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    scan_cfg, _errors = policy_mod.load_scan(root)
    payload = json.loads(Path(args.inventory).read_text(encoding="utf-8"))
    result = detect(
        payload.get("repos", []),
        scanner.make_github_fetcher(),
        make_lsremote_prober(),
        scan_cfg["scan"]["max_requests_per_run"],
    )
    if result["cursor"]:
        cursor_path = Path(args.out) / "drift-cursor.json"
        cursor_path.parent.mkdir(parents=True, exist_ok=True)
        cursor_path.write_text(
            json.dumps(result["cursor"], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
    scanner.write_inventory(result["records"], args.out, now=result["now"])
    if result["events"]:
        events_path = Path(args.out) / "drift_events.json"
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text(
            json.dumps(result["events"], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
    print("漂移检测%s：仓库 %d，漂移 %d，请求 %d 次"
          % ("完成" if result["complete"] else "未完成（游标已保存）",
             result["stats"]["repos"], result["stats"]["drifted"],
             result["stats"]["requests"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
