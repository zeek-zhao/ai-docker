"""overlay — 同名路径权威裁决与融合层数校验。

依据：docs/01 §13（运行时融合与选举规则，D5 确认）、docs/02 ADR-005。
规则唯一出处：config/policy.yaml 的 ``overlay.precedence`` 与
``overlay.path_rules``（AGENTS §3.6：任何代码不得私自实现第二套裁决逻辑，
本模块是唯一实现，且规则数据一律由 tools/policy.py 从配置加载）。

裁决语义：
1. ``path_rules`` 优先于 ``precedence``（显式 pin / isolate 压倒层级）；
2. 无规则命中时按 precedence 从左到右取第一个「在场层」胜出；
3. ``pin`` 路径在融合前软链指向唯一权威层；``isolate`` 路径走前缀隔离；
4. 单次融合层数不得超过 ``overlay.max_lowerdir``（H9），超出需两级融合。
"""

from __future__ import annotations

import fnmatch

__all__ = ["OverlayResolver", "DecideError"]


class DecideError(ValueError):
    """无法完成裁决（如 pin 层不在场、规则指向未知层）。"""


def _norm(path):
    """统一为 posix 风格相对路径（Windows 反斜杠视为分隔符）。"""
    return str(path).replace("\\", "/").lstrip("/")


class OverlayResolver:
    """基于 policy.yaml 的同名路径裁决器（纯函数式，无副作用）。"""

    def __init__(self, policy):
        self.precedence = policy.precedence
        self.path_rules = policy.path_rules
        self.max_lowerdir = policy.max_lowerdir

    # ---- path_rules（优先于 precedence）----

    def match_rule(self, path):
        """返回第一条命中的 path_rules 条目；无命中返回 None。

        通配采用 fnmatch 语义（``*`` 可跨越 ``/``），并对 ``**/`` 前缀追加
        gitignore 式「任意层级含根」语义：``**/build.sh`` 同时命中根级
        ``build.sh`` 与任意子目录同名文件（docs/01 §13.3 的意图）。
        """
        p = _norm(path)
        for rule in self.path_rules:
            pattern = rule.get("path")
            if not pattern:
                continue
            if fnmatch.fnmatchcase(p, pattern):
                return rule
            if pattern.startswith("**/") and fnmatch.fnmatchcase(
                p, pattern[3:]
            ):
                return rule
        return None

    # ---- 裁决 ----

    def decide(self, path, present_layers):
        """裁决同名路径归属。

        path: 相对路径（posix 风格）。
        present_layers: 在场层名集合（如 {toolchain, k8s, edge}）。
        返回 dict：
          {"action": "pin", "layer": <层>}     — path_rules pin，融合前软链指向唯一权威层
          {"action": "isolate"}                — path_rules isolate，走前缀隔离
          {"action": "keep", "layer": <层>}    — 按 precedence 胜出层保留
        """
        present = set(present_layers)
        unknown = present - set(self.precedence)
        if unknown:
            raise DecideError("在场层不在 precedence 中：%s" % sorted(unknown))
        rule = self.match_rule(path)
        if rule is not None:
            if rule.get("pin") is not None:
                pin = rule["pin"]
                if pin not in self.precedence:
                    raise DecideError("pin 指向未知层 %s（路径 %s）" % (pin, path))
                return {"action": "pin", "layer": pin}
            if rule.get("isolate"):
                return {"action": "isolate"}
        for layer in self.precedence:
            if layer in present:
                return {"action": "keep", "layer": layer}
        raise DecideError("无任何在场层可裁决路径 %s" % path)

    # ---- 融合层数（H9）----

    def check_lowerdir(self, count):
        """校验单次融合层数；合法返回 True，超限返回 False（调用方须两级融合）。"""
        if not isinstance(self.max_lowerdir, int) or self.max_lowerdir <= 0:
            raise DecideError("overlay.max_lowerdir 未配置或非法")
        return count <= self.max_lowerdir
