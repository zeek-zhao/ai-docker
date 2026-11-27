# -*- coding: utf-8 -*-
"""bdd_steps_docker — features/docker_artifacts.feature 的步骤定义（SC-M2-01~04）。

静态结构校验：只读文件文本做形态断言，不执行 Docker 构建 / CI
（诚实性，AGENTS §3.5；实际构建属阶段 4，Linux 待执行）。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent          # tests/
_ROOT = _HERE.parent                             # solutions/repo-mirror-sync/
for _p in (str(_ROOT), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from bdd_runner import step                       # noqa: E402
from tools import policy as policy_mod            # noqa: E402

# ---------------------------------------------------------------- 假如/假设


def _read(rel_path):
    path = _ROOT / rel_path
    assert path.is_file(), "文件缺失：%s" % rel_path
    return path.read_text(encoding="utf-8")


@step("given", r'Dockerfile 文件 "([^"]+)" 已存在')
def given_dockerfile(ctx, rel_path):
    ctx.setdefault("dockerfiles", {})[rel_path] = _read(rel_path)
    ctx["current_file"] = rel_path


_REPO_ROOT = _ROOT.parents[1]


@step("given", r'工作流文件 "([^"]+)" 已存在')
def given_workflow(ctx, name):
    """ADR-012：工作流迁仓库根级，优先读根级 repo-mirror-sync-<name>，回退方案内旧路径。"""
    root_file = _REPO_ROOT / ".github" / "workflows" / ("repo-mirror-sync-%s" % name)
    legacy = _ROOT / ".github" / "workflows" / name
    target = root_file if root_file.is_file() else legacy
    assert target.is_file(), "工作流文件不存在：%s（根级与方案内均未找到）" % target
    ctx.setdefault("workflows", {})[name] = target.read_text(encoding="utf-8")
    ctx["current_workflow"] = name


# ---------------------------------------------------------------- 那么

_FROM_DIGEST_RE = re.compile(
    r"(?m)^FROM\s+\S+@(sha256:[0-9a-f]{64}|\$\{?[A-Z0-9_]*DIGEST\}?)")
_FROM_LATEST_RE = re.compile(r"(?m)^FROM\s+\S+:latest")


@step("then", "FROM 指令以 digest 固定基础镜像")
def then_from_digest(ctx):
    text = ctx["dockerfiles"][ctx["current_file"]]
    assert _FROM_DIGEST_RE.search(text), \
        "FROM 未以 digest 固定（sha256 或 DIGEST 构建参数）：%s" % ctx["current_file"]


@step("then", r"安装层覆盖 (.+?) 两类工具")
def then_tools(ctx, names):
    text = ctx["dockerfiles"][ctx["current_file"]]
    for name in names.split("、"):
        assert name in text, "工具 %s 未出现在安装层：%s" % (name, ctx["current_file"])


@step("then", r"FROM 基于 (\S+) (\S+) 基础镜像")
def then_from_base_image(ctx, image, tag):
    text = ctx["dockerfiles"][ctx["current_file"]]
    assert re.search(r"(?m)^FROM\s+%s:%s@" % (re.escape(image), re.escape(tag)), text), \
        "FROM 未基于 %s:%s 基础镜像 digest 固定：%s" % (image, tag, ctx["current_file"])


@step("then", "全文件不引用 latest 标签")
def then_no_latest(ctx):
    pool = list(ctx["dockerfiles"].values()) + list(ctx.get("workflows", {}).values())
    text = ctx["dockerfiles"].get(ctx["current_file"], "\n".join(pool))
    assert not _FROM_LATEST_RE.search(text), \
        "FROM 引用了 :latest 标签：%s" % ctx["current_file"]


@step("then", r"ARG 声明包含 (\S+)")
def then_arg(ctx, name):
    text = ctx["dockerfiles"][ctx["current_file"]]
    assert re.search(r"(?m)^ARG\s+\S*%s" % re.escape(name), text), \
        "缺少 ARG %s：%s" % (name, ctx["current_file"])


@step("then", "FROM 基于参数化工具链镜像")
def then_from_toolchain(ctx):
    text = ctx["dockerfiles"][ctx["current_file"]]
    assert re.search(r"(?m)^FROM\s+\$\{?TOOLCHAIN_IMAGE\}?", text), \
        "FROM 未参数化 TOOLCHAIN_IMAGE：%s" % ctx["current_file"]


@step("then", "FROM 不引用索引镜像 manifest-index")
def then_no_index_from(ctx):
    text = ctx["dockerfiles"][ctx["current_file"]]
    assert not re.search(r"(?m)^FROM\s+.*manifest-index", text), \
        "索引镜像进入了继承链（FR-B2 违约）：%s" % ctx["current_file"]


@step("then", "融合定义包含 lowerdir 挂载约定")
def then_lowerdir(ctx):
    assert "lowerdir" in ctx["dockerfiles"][ctx["current_file"]], \
        "融合定义缺少 lowerdir 约定：%s" % ctx["current_file"]


@step("then", "融合定义包含 manifest 软链约定")
def then_manifest_link(ctx):
    text = ctx["dockerfiles"][ctx["current_file"]]
    assert re.search(r"ln\s+-s\s+\S*manifest", text), \
        "融合定义缺少 manifest 软链：%s" % ctx["current_file"]


# ------------------------------------------------- SC-M2-04 三个工作流

@step("then", "scan 工作流 cron 与 config 扫描周期一致")
def then_cron_consistent(ctx):
    cfg, errors = policy_mod.load_scan(_ROOT)
    assert not errors, "config/scan.yaml 非法：%s" % errors
    every_days = cfg["scan"]["every_days"]
    stagger = cfg["scan"]["stagger_minute"]
    text = ctx["workflows"]["scan.yml"]
    m = re.search(r'cron:\s*"([^"]+)"', text)
    assert m, "scan.yml 缺少 cron 表达式"
    fields = m.group(1).split()
    assert len(fields) == 5, "cron 必须为五段式：%r" % m.group(1)
    assert fields[0] == str(stagger), \
        "cron 分钟 %s != config.stagger_minute %s" % (fields[0], stagger)
    assert fields[2] == "*/%d" % every_days, \
        "cron 日域 %s != */%d（config.every_days）" % (fields[2], every_days)


@step("then", "scan 工作流调用扫描器且凭据走环境变量")
def then_scanner_env(ctx):
    text = ctx["workflows"]["scan.yml"]
    assert "tools/scan_inventory.py" in text, "scan.yml 未调用扫描器"
    assert "GH_TOKEN:" in text and "secrets." in text, \
        "凭据必须经 env 引用 secrets（AGENTS §3.4）"


@step("then", "build-block 工作流按块参数化且产出绑定表")
def then_block_params(ctx):
    text = ctx["workflows"]["build-block.yml"]
    assert "workflow_call" in text, "build-block.yml 缺少 workflow_call 触发器"
    assert "block_id" in text and "BUILD_BLOCK" in text, "块参数缺失"
    assert "bindings.json" in text, "绑定表检查缺失（FR-B3）"


@step("then", "build-block 工作流含全层加密与 sha256 tag 规范")
def then_encrypt_sha(ctx):
    text = ctx["workflows"]["build-block.yml"]
    assert "age -encrypt" in text, "缺少 age 全层加密步骤（FR-B4）"
    assert "sha256" in text, "缺少 sha256 tag 规范步骤"


@step("then", "verify-fuse 工作流引用融合定义且解密凭据走环境变量")
def then_verify_fuse(ctx):
    text = ctx["workflows"]["verify-fuse.yml"]
    assert "docker/fused.Dockerfile" in text, "verify-fuse.yml 未引用融合定义"
    assert "AGE_KEY" in text and "secrets." in text, "解密凭据必须走 secrets 环境"
