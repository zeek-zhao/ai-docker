# -*- coding: utf-8 -*-
"""merge_arbitration — 合并裁决（阶段 3 补全，docs/01 §12.3）。

顺序固定，不做「谁后到谁赢」：
1. 先按 manifest 重建（基线 = manifest 指定 rev/sha）；
2. 再漂移补拉：补拉 sha 与基线一致 → 丢弃补拉包只记合并日志；
   不一致（mirror 落后于 manifest 指定 rev）→ 以 manifest 为准，
   补拉包降级 ``quarantine/`` 隔离区待人工确认，不进入发布镜像；
3. 内容级去重：同路径 sha256 一致 → 硬链接去重计划；不一致 →
   委托 tools/merge_guard.MergeGuard（唯一裁决实现，§13.2 矩阵），
   不悄悄覆盖。

纯计算层（arbitrate/dedupe）不落盘不网络；write_quarantine 落隔离区
清单；CLI 追加合并日志并按需落隔离区。
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.merge_guard import MergeGuard

__all__ = ["arbitrate", "dedupe", "write_quarantine", "main"]

# 合并裁决域到 precedence 层名的映射：manifest 域权威 → toolchain，
# 漂移补拉域 → self-dev。委托 §13.2 矩阵（MergeGuard/OverlayResolver
# 唯一裁决实现）时必须使用 precedence 层名，present_layers 校验才可通过。
ARBITRATION_LAYERS = ("toolchain", "self-dev")

TZ = timezone(timedelta(hours=8))
QUARANTINE_DIR_TPL = "quarantine/{repo}/{sha12}"


def _iso_now():
    return datetime.now(TZ).isoformat(timespec="seconds")


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def arbitrate(manifest_entry, fetch, now=None):
    """合并裁决（§12.3 顺序 1~2）。

    manifest_entry: {"repo", "rev"}（manifest 指定基线）；
    fetch: {"repo", "sha"}（漂移补拉包）。
    返回 dict（含 order/baseline/fetch_sha/log；drop→published=True，
    quarantine→published=False + quarantine_dir + manual_review=True）。
    """
    if not isinstance(manifest_entry, dict) or "repo" not in manifest_entry or "rev" not in manifest_entry:
        raise ValueError("manifest_entry 需含 repo/rev（manifest 指定基线）")
    if not isinstance(fetch, dict) or "repo" not in fetch or "sha" not in fetch:
        raise ValueError("fetch 需含 repo/sha（漂移补拉包）")
    repo = manifest_entry["repo"]
    if fetch.get("repo") != repo:
        raise ValueError(
            "补拉仓库与 manifest 仓库不一致：%r vs %r" % (fetch.get("repo"), repo))
    rev = manifest_entry["rev"]
    fsha = fetch["sha"]
    result = {
        "repo": repo,
        "order": ["manifest_rebuild", "drift_fetch"],
        "baseline": rev,
        "fetch_sha": fsha,
    }
    if fsha == rev:
        result["action"] = "drop"
        result["published"] = True
        result["log"] = {
            "repo": repo,
            "fetch_sha": fsha,
            "action": "drop",
            "reason": "补拉 sha 与 manifest 基线一致，丢弃补拉包只记合并日志（§12.3 顺序 2）",
            "at": now or _iso_now(),
        }
        return result
    sha12 = str(fsha).replace("/", "")[:12] or "unknown"
    result["action"] = "quarantine"
    result["published"] = False
    result["quarantine_dir"] = QUARANTINE_DIR_TPL.format(repo=repo, sha12=sha12)
    result["manual_review"] = True
    result["log"] = {
        "repo": repo,
        "fetch_sha": fsha,
        "action": "quarantine",
        "reason": "补拉 sha 与 manifest 基线不一致，以 manifest 为准，补拉包降级隔离区待人工确认（§12.3 顺序 2）",
        "at": now or _iso_now(),
    }
    return result


def dedupe(files_a, files_b, guard=None):
    """内容级去重（§12.3 顺序 3）。

    files_a/files_b: {path: bytes}（manifest 侧 / 补拉侧）。
    同路径双份：sha256 一致 → hardlink；不一致 → 委托
    MergeGuard.arbitrate(path, ["manifest","fetch"])（唯一裁决实现）；
    单侧存在 → keep。
    """
    if guard is not None and not isinstance(guard, MergeGuard):
        raise ValueError("guard 必须是 tools.merge_guard.MergeGuard（唯一裁决入口）")
    decisions = []
    for path in sorted(set(files_a) | set(files_b)):
        a = files_a.get(path)
        b = files_b.get(path)
        if a is not None and b is not None:
            if _sha256(a) == _sha256(b):
                decisions.append({
                    "path": path,
                    "action": "hardlink",
                    "note": "两份内容一致，硬链接去重（§12.3 顺序 3）",
                })
                continue
            if guard is None:
                raise ValueError("内容不一致需注入 MergeGuard（唯一裁决实现）")
            verdict = dict(guard.arbitrate(path, list(ARBITRATION_LAYERS)))
            verdict["note"] = "内容不一致，按 §13.2 矩阵由融合守卫裁决，不悄悄覆盖"
            decisions.append(verdict)
        elif a is not None:
            decisions.append({"path": path, "action": "keep", "source": "manifest"})
        else:
            decisions.append({"path": path, "action": "keep", "source": "fetch"})
    return decisions


def write_quarantine(result, out_dir):
    """隔离区清单落盘（quarantine/…/notice.json），返回路径；drop 返回 None。"""
    if result.get("action") != "quarantine":
        return None
    notice_dir = Path(out_dir) / Path(result["quarantine_dir"])
    notice_dir.mkdir(parents=True, exist_ok=True)
    notice = notice_dir / "notice.json"
    payload = {
        "repo": result["repo"],
        "fetch_sha": result["fetch_sha"],
        "baseline": result["baseline"],
        "manual_review": True,
        "published": False,
        "reason": result["log"]["reason"],
        "at": result["log"]["at"],
    }
    notice.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(notice)


def main(argv=None):
    parser = argparse.ArgumentParser(description="合并裁决 CLI（docs/01 §12.3）")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--manifest-rev", required=True)
    parser.add_argument("--fetch-sha", required=True)
    parser.add_argument("--out", default="out/merge")
    args = parser.parse_args(argv)
    result = arbitrate(
        {"repo": args.repo, "rev": args.manifest_rev},
        {"repo": args.repo, "sha": args.fetch_sha},
    )
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    log_path = out / "merge-log.json"
    logs = []
    if log_path.is_file():
        try:
            logs = json.loads(log_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            logs = []
    logs.append(result["log"])
    log_path.write_text(
        json.dumps(logs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    notice = write_quarantine(result, out)
    print(json.dumps({
        "action": result["action"],
        "log": str(log_path),
        "notice": notice,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
