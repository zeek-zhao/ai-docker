"""budget — 体积预算与派生标签（size_class）计算。

依据：docs/01-方案总览.md §8（预算公式）、§9.1（size_class 阈值）；
ADR-003（单 job 预算 4.0 GB、k=1.25）。所有阈值与预算一律读
config/scan.yaml，禁止硬编码（AGENTS §3.3）。

口径约定：GB = 10^9 字节（十进制），与 config 的 ``budget.budget_bytes``
（4.0 GB）一致；MB 同理为 10^6 字节。具体数值只出现在 config，本模块不出现。
"""

from __future__ import annotations

GB = 10 ** 9  # 单位定义（十进制字节），非策略阈值

__all__ = ["budget_raw_bytes", "confirmed_budget_bytes", "size_class", "decide"]


def _num(value, name):
    if not isinstance(value, (int, float)):
        raise ValueError("limits.%s 缺失或非数值" % name)
    return float(value)


def budget_raw_bytes(limits):
    """预算公式 budget_raw = (limit − overhead) / k，返回字节数（docs/01 §8.1）。"""
    limit = _num(limits.get("storage_gb"), "storage_gb")
    overhead = _num(limits.get("overhead_gb"), "overhead_gb")
    k = _num(limits.get("safety_factor"), "safety_factor")
    return int((limit - overhead) * GB / k)


def confirmed_budget_bytes(scan):
    """读取需求方确认的单 job 预算（D2）budget.budget_bytes。"""
    value = (scan.get("budget") or {}).get("budget_bytes")
    if not isinstance(value, int) or value <= 0:
        raise ValueError("budget.budget_bytes 缺失或非法")
    return value


def size_class(size_bytes, thresholds):
    """按 docs/01 §9.1 阈值派生 size_class。

    边界语义与文档一致（严格不等式）：small(<small_max)、large(>large_min)、
    oversized(>oversized_min)，其余为 medium。阈值来自 scan.yaml 的
    ``size_class`` 节（十进制字节）。
    """
    small_max = thresholds.get("small_max_bytes")
    large_min = thresholds.get("large_min_bytes")
    oversized_min = thresholds.get("oversized_min_bytes")
    for name, value in (
        ("small_max_bytes", small_max),
        ("large_min_bytes", large_min),
        ("oversized_min_bytes", oversized_min),
    ):
        if not isinstance(value, int):
            raise ValueError("size_class.%s 缺失或非法" % name)
    if size_bytes > oversized_min:
        return "oversized"
    if size_bytes > large_min:
        return "large"
    if size_bytes < small_max:
        return "small"
    return "medium"


def decide(size_bytes, budget_bytes):
    """单块预算判定：'ok'（≤ 预算，可整块直拉）或 'split'（> 预算，必须切分/稀疏检出）。"""
    if size_bytes <= budget_bytes:
        return "ok"
    return "split"
