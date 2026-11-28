# -*- coding: utf-8 -*-
"""fuse_verify — 非特权用户态融合校验（ADR-011，docs/01 §13.1）。

背景：官方 debian:bookworm-slim 与 ubuntu:24.04 仓库均无 overlayfs-tools 包
（2026-11-28 实测，Issue #4 V2）；特权内核挂载不可进 CI 门禁。本工具以纯
用户态文件操作物化融合视图，校验两级融合语义（H6 同名隔离、H9 层数上限），
并落盘决策表供审计；内核 OverlayFS 挂载属消费侧运行时语义，不在职责内。

裁决唯一来源（AGENTS §3.6）：config/policy.yaml → tools/overlay.py；
处置建议唯一来源：tools/merge_guard.MergeGuard.arbitrate（含 isolate
前缀模板 /mnt/{layer}/{path}）。本模块不实现第二套裁决逻辑，只做物化
（copy/symlink）与审计（决策表落盘）；零子进程、零特权能力（ADR-011）。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.merge_guard import ISOLATE_PREFIX_TPL, MergeGuard      # noqa: E402
from tools.overlay import DecideError, OverlayResolver            # noqa: E402
from tools.policy import load_policy                              # noqa: E402

__all__ = ["verify", "main"]


def _collect(root):
    """枚举层目录内全部文件：[(posix 相对路径, 绝对路径)]，稳定排序。"""
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            full = Path(dirpath) / name
            found.append((full.relative_to(root).as_posix(), full))
    return found


def verify(layers, solution_dir=None, out_dir=None):
    """对有序层做非特权融合校验，返回报告并按需物化。

    layers: {层名: 层目录}；dict 序即提交顺序（模拟 lowerdir 靠左优先）。
    返回 {passed, decisions, lowerdir:{count,max,ok}, layers, errors,
    materialized}；out_dir 给定时物化 merged 树并写 decisions.json。
    """
    if not layers:
        raise DecideError("未提供任何层")
    solution_dir = Path(solution_dir) if solution_dir else _ROOT
    policy = load_policy(solution_dir)
    resolver = OverlayResolver(policy)
    guard = MergeGuard(resolver)

    inventory = {}  # 相对路径 -> [(层名, 文件绝对路径)]（按提交顺序）
    for name, root in layers.items():
        for rel, full in _collect(root):
            inventory.setdefault(rel, []).append((name, full))

    decisions, targets, errors = [], {}, []
    for rel in sorted(inventory):
        occurrences = inventory[rel]
        present = [name for name, _ in occurrences]
        try:
            arb = guard.arbitrate(rel, present)
        except DecideError as exc:
            errors.append("路径 %s 裁决失败：%s" % (rel, exc))
            continue
        entry = dict(arb)
        if arb["action"] in ("keep", "pin"):
            src = next((full for name, full in occurrences
                        if name == arb["layer"]), None)
            if src is None:
                errors.append("路径 %s 权威层 %s 不在场，融合将失败"
                              % (rel, arb["layer"]))
                continue
            entry["target"] = rel
            targets[rel] = (src, arb["action"])
        else:  # isolate：各层保留自有副本（H6），物化到运行时前缀布局
            entry["targets"] = []
            for name, full in occurrences:
                target = ISOLATE_PREFIX_TPL.format(layer=name, path=rel).lstrip("/")
                entry["targets"].append(target)
                targets[target] = (full, arb["action"])
        decisions.append(entry)

    report = {
        "passed": not errors,
        "decisions": decisions,
        "lowerdir": {
            "count": len(layers),
            "max": policy.max_lowerdir,
            "ok": resolver.check_lowerdir(len(layers)),
        },
        "layers": list(layers.keys()),
        "errors": errors,
        "materialized": [],
    }

    if out_dir is not None:
        out_dir = Path(out_dir)
        for target, (src, action) in sorted(targets.items()):
            dest = out_dir / "merged" / target
            if dest.exists() or dest.is_symlink():
                errors.append("物化冲突：%s" % target)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            if action == "pin":  # pin：软链指向唯一权威层（docs/01 §13.2）
                os.symlink(os.path.relpath(src, dest.parent), dest)
            else:  # keep/isolate：内容副本
                shutil.copyfile(src, dest)
            report["materialized"].append(target)
        report["passed"] = not errors
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "decisions.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="非特权用户态融合校验（ADR-011）；复用 overlay.py 唯一裁决")
    parser.add_argument("--layers", action="append", required=True,
                        metavar="名称=目录",
                        help="提交顺序的层（可重复；先声明=更靠左=更高优先）")
    parser.add_argument("--solution-dir", default=str(_ROOT),
                        help="方案目录（读 config/policy.yaml）")
    parser.add_argument("--out", default=None,
                        help="融合视图物化与决策表输出目录")
    args = parser.parse_args(argv)
    layers = {}
    for item in args.layers:
        if "=" not in item:
            parser.error("--layers 需为 名称=目录 形式：%s" % item)
        name, _, path = item.partition("=")
        if name in layers:
            parser.error("层名重复：%s" % name)
        layers[name] = path
    report = verify(layers, solution_dir=args.solution_dir, out_dir=args.out)
    print(json.dumps({k: report[k]
                      for k in ("passed", "layers", "lowerdir", "errors")},
                     ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
