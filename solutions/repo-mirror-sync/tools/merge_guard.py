# -*- coding: utf-8 -*-
"""merge_guard — 融合守卫（阶段 4，FR-D1~FR-D4）。

职责边界（docs/01 §13；docs/02 ADR-005、ADR-008；AGENTS §3.6）：
1. 同名路径裁决唯一应用入口：全部委托 tools/overlay.OverlayResolver，
   选举规则唯一出处 config/policy.yaml 的 overlay 节；
   本模块禁止实现第二套裁决逻辑（FR-D1 / AGENTS §3.6）；
2. 融合层数守卫：上限唯一出处 overlay.max_lowerdir（H9 对策），
   超限给出两级融合建议（ADR-008），本模块只给建议、不执行挂载；
3. 隔离建议：path_rules isolate 命中时，为每个在场层生成独立挂载前缀，
   各层保留自有副本互不覆盖（H6 对策）。

本模块为纯计算守卫：不执行挂载、不访问网络、不落盘。
"""

from __future__ import annotations

from tools.overlay import OverlayResolver

__all__ = ["MergeGuard", "GuardError"]

ISOLATE_PREFIX_TPL = "/mnt/{layer}/{path}"


class GuardError(Exception):
    """守卫输入非法或策略缺失。"""


class MergeGuard:
    """融合前置守卫：裁决编排 + 层数校验 + 隔离建议。

    resolver 必须是 tools.overlay.OverlayResolver 实例（唯一裁决入口，
    isinstance 校验失败即拒绝，防止绕过 overlay 私接第二套实现）。
    """

    def __init__(self, resolver):
        if not isinstance(resolver, OverlayResolver):
            raise GuardError("必须注入 tools.overlay.OverlayResolver（唯一裁决入口）")
        self.resolver = resolver

    # ---- 同名路径裁决（FR-D1~FR-D4，委托 overlay）----

    def arbitrate(self, path, present_layers):
        """裁决同名路径并生成融合处置建议。

        返回 dict：
          pin/keep → {"path", "action", "layer", "shadowed"}（shadowed 为被遮蔽层，按输入序去重）
          isolate  → {"path", "action", "prefixes", "note"}（各层独立前缀，不产生胜出层）
        裁决本身完全由 resolver.decide 完成；本方法不覆盖其结果。
        """
        decision = self.resolver.decide(path, present_layers)
        result = {"path": path, "action": decision["action"]}
        if decision["action"] == "isolate":
            posix_path = str(path).replace("\\", "/").lstrip("/")
            ordered_layers = list(dict.fromkeys(present_layers))
            result["prefixes"] = [
                ISOLATE_PREFIX_TPL.format(layer=lay, path=posix_path)
                for lay in ordered_layers
            ]
            result["note"] = "各层保留自有副本，互不覆盖（H6 对策）"
            return result
        winner = decision.get("layer")
        result["layer"] = winner
        result["shadowed"] = [
            lay for lay in dict.fromkeys(present_layers) if lay != winner
        ]
        return result

    # ---- 融合层数守卫（FR-D2 / H9，上限唯一出处 policy）----

    def check_stack(self, count):
        """校验单次融合层数并给出两级融合建议。

        返回 dict：{"count", "max_lowerdir", "ok", "two_stage", "advice"}。
        ok 为 False（即 two_stage 为 True）时调用方必须两级融合后再挂载。
        """
        if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
            raise GuardError("层数必须为正整数，收到：%r" % (count,))
        max_lowerdir = getattr(self.resolver, "max_lowerdir", None)
        if not isinstance(max_lowerdir, int) or max_lowerdir <= 0:
            raise GuardError("overlay.max_lowerdir 未配置或非法（唯一出处 config/policy.yaml）")
        ok = self.resolver.check_lowerdir(count)
        two_stage = not ok
        if two_stage:
            advice = (
                "在场合计 %d 层，超出单次融合上限 %d 层；"
                "建议两级融合：先融合低位层为中间视图，再叠加高位层（H9 对策）"
                % (count, max_lowerdir)
            )
        else:
            advice = "层数在上限内，可单次融合"
        return {
            "count": count,
            "max_lowerdir": max_lowerdir,
            "ok": ok,
            "two_stage": two_stage,
            "advice": advice,
        }
