# -*- coding: utf-8 -*-
# 缓存 LRU 治理（M9 阶段5，FR-A2/H1/ADR-007）。
# 清理参数唯一出处 config/scan.yaml limits 节（cache_gb/keep_blocks/keep_versions，AGENTS §3.3）；
# 加密层（*.age）属 FR-B4 交付物：仅告警，不删除、不计入体积；每项删除逐行落日志（验收可复核）。
from __future__ import annotations

import json
from pathlib import Path

from tools import policy as policy_mod


def _iter_blocks(cache_dir):
    """块 = cache_dir 下的子目录（目录名即块名），按名称稳定排序。"""
    return sorted((p for p in cache_dir.iterdir() if p.is_dir()), key=lambda p: p.name)


def _version_files(block_dir):
    """块内版本文件：非 .age 常规文件，按 mtime 新→旧。"""
    files = [p for p in block_dir.rglob("*") if p.is_file() and not p.name.endswith(".age")]
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def _age_warnings(cache_dir):
    """加密残留仅告警（FR-B4 制品不进缓存清理范围）。"""
    return ["警告：%s 为加密层（FR-B4），不删除、不计入缓存体积"
            % p.relative_to(cache_dir).as_posix()
            for p in sorted(cache_dir.rglob("*.age"))]


def clean(cache_dir, budget_bytes, keep_blocks, keep_versions):
    """LRU 清理：先块级（保留最近 keep_blocks 块），再版本级（每块保留最新 keep_versions 个），
    最后预算兜底（自最旧块删起至 ≤budget_bytes）。

    返回 {"deleted", "kept_blocks", "over_budget", "bytes_before", "bytes_after", "log"}。
    """
    cache_dir = Path(cache_dir)
    if not cache_dir.is_dir():
        raise NotADirectoryError("缓存目录不存在：%s" % cache_dir)
    for name, value in (("预算", budget_bytes), ("保留块数", keep_blocks), ("保留版本数", keep_versions)):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError("%s 必须为正整数：%r" % (name, value))

    log = list(_age_warnings(cache_dir))
    deleted = []
    blocks = {b: _version_files(b) for b in _iter_blocks(cache_dir)}
    bytes_before = sum(f.stat().st_size for files in blocks.values() for f in files)

    def _drop(path, reason):
        size = path.stat().st_size
        path.unlink()
        rel = path.relative_to(cache_dir).as_posix()
        deleted.append(rel)
        log.append("删除 %s（%d 字节，%s）" % (rel, size, reason))
        return size

    order = sorted(blocks, key=lambda b: max((f.stat().st_mtime for f in blocks[b]), default=0))
    evict = order[:-keep_blocks] if len(order) > keep_blocks else []
    kept = [b for b in order if b not in evict]

    for b in evict:  # 块级 LRU：整块删除
        for f in list(blocks[b]):
            _drop(f, "块级 LRU")
    for b in kept:  # 版本级 LRU：块内只留最新 keep_versions 个
        for f in blocks[b][keep_versions:]:
            _drop(f, "版本级 LRU")

    def _remaining():
        return sum(f.stat().st_size for b in kept for f in blocks[b] if f.is_file())

    total, i = _remaining(), 0
    while total > budget_bytes and i < len(kept):  # 预算兜底：自最旧块删起
        for f in blocks[kept[i]]:
            if f.is_file():
                total -= _drop(f, "预算超限")
        i += 1

    for b in evict + kept[:i]:  # 空目录壳一并移除（文件级删除后）
        try:
            b.rmdir()
        except OSError:
            pass

    bytes_after = _remaining()
    return {
        "deleted": deleted,
        "kept_blocks": len([b for b in kept if any(f.is_file() for f in blocks[b])]),
        "over_budget": bytes_before > budget_bytes,
        "bytes_before": bytes_before,
        "bytes_after": bytes_after,
        "log": log,
    }


def build_cache_pressure_event(result, budget_bytes):
    """FR-A2：超预算时产出 cache_pressure 事件（estimated=预算，actual=清理前峰值，NFR-6 成对）。"""
    return {
        "kind": "cache_pressure",
        "subject": "cache",
        "summary": "缓存超预算：已清理 %d 项释放 %d 字节（峰值 %d 字节）"
                   % (len(result["deleted"]),
                      result["bytes_before"] - result["bytes_after"],
                      result["bytes_before"]),
        "estimated_bytes": budget_bytes,
        "actual_bytes": result["bytes_before"],
    }


def main(argv=None):
    """CLI：--cache-dir 必填；预算与保留数读 config/scan.yaml limits（唯一出处）。"""
    import argparse

    parser = argparse.ArgumentParser(description="缓存 LRU 清理与预算审计（FR-A2）")
    parser.add_argument("--cache-dir", required=True)
    parser.add_argument("--out", default="out")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    cfg, errors = policy_mod.load_scan(root)
    if errors:
        print("config/scan.yaml 校验失败：%s" % errors)
        return 2
    limits = cfg["limits"]
    budget_bytes = int(limits["cache_gb"]) * 10 ** 9

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = Path(args.cache_dir)
    if not cache_dir.is_dir():
        (out_dir / "cache-gc.log").write_text("", encoding="utf-8")
        print("缓存目录不存在（%s）：零清理审计通过" % cache_dir)
        return 0

    result = clean(cache_dir, budget_bytes,
                   int(limits["keep_blocks"]), int(limits["keep_versions"]))
    (out_dir / "cache-gc.log").write_text(
        "".join(line + "\n" for line in result["log"]), encoding="utf-8")
    if result["over_budget"]:
        event = build_cache_pressure_event(result, budget_bytes)
        (out_dir / "cache-events.json").write_text(
            json.dumps([event], ensure_ascii=False, indent=2), encoding="utf-8")
    print("缓存清理：保留 %d 块，删除 %d 项（%d→%d 字节，预算 %d）"
          % (result["kept_blocks"], len(result["deleted"]),
             result["bytes_before"], result["bytes_after"], budget_bytes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
