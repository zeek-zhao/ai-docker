"""policy — policy.yaml 的加载、校验与访问层（策略唯一出处的唯一读取口）。

依据：docs/02-架构设计.md ADR-001/005/006/007/010、docs/03-需求规格.md
FR-P/FR-F/FR-A。本模块只解析与校验策略，不做任何裁决之外的动作；
同名路径裁决语义见 tools/overlay.py（其规则数据一律取自本模块加载的配置）。
"""

from __future__ import annotations

import os

from . import yaml_lite

__all__ = ["PolicyError", "Policy", "load_config", "load_policy", "load_scan"]


class PolicyError(ValueError):
    """策略文件缺失、结构不符或取值非法。"""


_REQUIRED_SCAN = {
    "scan": ("every_days", "max_requests_per_run", "stagger_minute", "state_file"),
    "limits": ("storage_gb", "overhead_gb", "safety_factor", "cache_gb"),
    "budget": ("budget_bytes",),
}


def load_config(solution_dir, name):
    """读取方案目录内 config/<name>；不存在即抛错（不静默缺省）。"""
    path = os.path.join(str(solution_dir), "config", name)
    if not os.path.isfile(path):
        raise PolicyError("策略文件不存在：%s" % path)
    return yaml_lite.load_file(path)


def load_scan(solution_dir):
    """读取并校验 scan.yaml，返回 (data, errors)。errors 非空即视为无效。"""
    data = load_config(solution_dir, "scan.yaml")
    return data, validate_scan(data)


def load_policy(solution_dir):
    """读取并校验 policy.yaml，返回 Policy 对象（结构非法时抛 PolicyError）。"""
    data = load_config(solution_dir, "policy.yaml")
    policy = Policy(data)
    errors = policy.validate()
    if errors:
        raise PolicyError("policy.yaml 校验失败：%s" % "; ".join(errors))
    return policy


def validate_scan(data):
    """校验 scan.yaml 结构完整性；返回错误字符串列表（空即通过）。"""
    errors = []
    if not isinstance(data, dict):
        return ["scan.yaml 顶层必须是映射"]
    for section, keys in _REQUIRED_SCAN.items():
        sec = data.get(section)
        if not isinstance(sec, dict):
            errors.append("缺少节 %s" % section)
            continue
        for key in keys:
            if sec.get(key) is None:
                errors.append("%s.%s 缺失" % (section, key))
    scan = data.get("scan", {})
    limits = data.get("limits", {})
    if isinstance(limits.get("storage_gb"), (int, float)) and limits["storage_gb"] <= 0:
        errors.append("limits.storage_gb 必须为正数")
    if isinstance(limits.get("safety_factor"), (int, float)) and limits["safety_factor"] <= 0:
        errors.append("limits.safety_factor 必须为正数")
    if isinstance(scan.get("every_days"), int) and scan["every_days"] <= 0:
        errors.append("scan.every_days 必须为正整数")
    return errors


class Policy:
    """policy.yaml 的结构化视图（只读）。"""

    def __init__(self, data):
        self.raw = data
        self.blocks = data.get("blocks", [])
        self.combos = data.get("combos", [])
        self.encryption = data.get("encryption", {})
        self.overlay = data.get("overlay", {})
        self.alert = data.get("alert", {})

    # ---- 查询 ----

    def block_ids(self):
        return [b.get("id") for b in self.blocks if isinstance(b, dict)]

    def block(self, block_id):
        for b in self.blocks:
            if isinstance(b, dict) and b.get("id") == block_id:
                return b
        return None

    def combo(self, combo_id):
        for c in self.combos:
            if isinstance(c, dict) and c.get("id") == combo_id:
                return c
        return None

    def combo_blocks(self, combo_id):
        """返回组合引用的块列表；引用不存在的块即抛错（配置一致性由校验保证）。"""
        combo = self.combo(combo_id)
        if combo is None:
            raise PolicyError("未知组合：%s" % combo_id)
        resolved = []
        for ref in combo.get("blocks", []):
            block = self.block(ref)
            if block is None:
                raise PolicyError("组合 %s 引用了未定义的块 %s" % (combo_id, ref))
            resolved.append(block)
        return resolved

    @property
    def precedence(self):
        """同名路径裁决优先级（左高右低，唯一出处 overlay.precedence）。"""
        return list(self.overlay.get("precedence", []))

    @property
    def path_rules(self):
        return list(self.overlay.get("path_rules", []))

    @property
    def max_lowerdir(self):
        return self.overlay.get("max_lowerdir")

    # ---- 校验 ----

    def validate(self):
        """结构校验；返回错误列表（空即通过）。"""
        errors = []
        if not isinstance(self.raw, dict):
            return ["policy.yaml 顶层必须是映射"]
        if not self.block_ids():
            errors.append("blocks 不能为空")
        ids = self.block_ids()
        if len(ids) != len(set(ids)):
            errors.append("blocks.id 存在重复")
        for combo in self.combos:
            if not isinstance(combo, dict) or "id" not in combo:
                errors.append("combos 条目缺少 id")
                continue
            for ref in combo.get("blocks", []):
                if ref not in ids:
                    errors.append("组合 %s 引用未定义块 %s" % (combo.get("id"), ref))
        prec = self.precedence
        if not prec:
            errors.append("overlay.precedence 不能为空")
        elif len(prec) != len(set(prec)):
            errors.append("overlay.precedence 存在重复层")
        known = set(prec)
        for rule in self.path_rules:
            if not isinstance(rule, dict) or "path" not in rule:
                errors.append("overlay.path_rules 条目缺少 path")
                continue
            pin = rule.get("pin")
            if pin is not None and pin not in known:
                errors.append("path_rules %s 的 pin 层 %s 不在 precedence 内" % (rule.get("path"), pin))
            if pin is None and not rule.get("isolate"):
                errors.append("path_rules %s 既无 pin 也无 isolate" % rule.get("path"))
        mld = self.max_lowerdir
        if not isinstance(mld, int) or mld <= 0:
            errors.append("overlay.max_lowerdir 必须为正整数")
        enc = self.encryption
        if enc.get("mode") != "full-layer":
            errors.append("encryption.mode 必须为 full-layer（ADR-007 全层加密，变更须走 ADR）")
        if not enc.get("tool"):
            errors.append("encryption.tool 缺失")
        key_ref = enc.get("key_ref", "")
        if not str(key_ref).startswith("env:"):
            errors.append("encryption.key_ref 必须以 env: 开头（密钥严禁入库，AGENTS §3.4）")
        if not enc.get("tag_identity"):
            errors.append("encryption.tag_identity 缺失")
        layouts = self.overlay.get("layouts")
        if not isinstance(layouts, dict) or set(layouts.values()) - {"flat", "prefix"}:
            errors.append("overlay.layouts 取值只能是 flat/prefix")
        for key in ("channels", "on", "throttle"):
            if not self.alert.get(key):
                errors.append("alert.%s 缺失" % key)
        return errors
