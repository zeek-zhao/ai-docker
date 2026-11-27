# -*- coding: utf-8 -*-
# SC-M9-01~04 步骤定义：投递网络层/节流持久化/CLI 端到端/流水线接入静态断言。
# 纯离线：sender 工厂仅验证构造契约与凭据拒绝；CLI 以库级调用 main(argv) 执行，
# 环境变量注入后恢复；无凭据环境下不产生任何网络行为。
import importlib
import json
import os
import sys
import tempfile

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from bdd_runner import step  # noqa: E402
from tools.alert import AlertError, AlertThrottle  # noqa: E402
import tools.notify as notify_mod  # noqa: E402



@step("given", r"^已读取 tools/notify\.py 源码$")
def given_notify_src(ctx):
    ctx["notify_src"] = open(os.path.join(_ROOT, "tools", "notify.py"), encoding="utf-8").read()


@step("then", r"^源码凭据仅取自环境变量$")
def then_src_env_only(ctx):
    src = ctx["notify_src"]
    assert "os.environ" in src, "notify.py 未从环境变量读取凭据"
    assert "secrets." not in src, "notify.py 不得内嵌 secrets 字面量"


@step("then", r"^alert 纯逻辑模块仍不导入网络库$")
def then_alert_pure(ctx):
    src = open(os.path.join(_ROOT, "tools", "alert.py"), encoding="utf-8").read()
    assert "urllib" not in src and "requests" not in src, "alert.py 必须保持纯逻辑（无网络库）"


def _pop_cred_env():
    saved = {}
    for key in ("GH_TOKEN", "FEISHU_WEBHOOK_URL", "GITHUB_REPOSITORY"):
        if key in os.environ:
            saved[key] = os.environ.pop(key)
    return saved


def _restore_env(saved):
    os.environ.update(saved)


@step("when", r"^在无凭据环境中构造 github-issue 投递器$")
def when_make_issue_sender(ctx):
    saved = _pop_cred_env()
    try:
        notify_mod.make_github_issue_sender()
        ctx["error"] = None
    except AlertError as exc:
        ctx["error"] = exc
    finally:
        _restore_env(saved)


@step("when", r"^在无凭据环境中构造 feishu 投递器$")
def when_make_feishu_sender(ctx):
    saved = _pop_cred_env()
    try:
        notify_mod.make_feishu_sender()
        ctx["error"] = None
    except AlertError as exc:
        ctx["error"] = exc
    finally:
        _restore_env(saved)


@step("when", r"^注入示例凭据后构造两类投递器$")
def when_make_senders_with_creds(ctx):
    os.environ["GH_TOKEN"] = "gh_example_token_for_construction_only"
    os.environ["FEISHU_WEBHOOK_URL"] = "https://open.feishu.cn/example"
    try:
        ctx["issue_sender"] = notify_mod.make_github_issue_sender()
        ctx["feishu_sender"] = notify_mod.make_feishu_sender()
    finally:
        for key in ("GH_TOKEN", "FEISHU_WEBHOOK_URL"):
            os.environ.pop(key, None)


@step("then", r"^投递器均为可调用对象$")
def then_senders_callable(ctx):
    assert callable(ctx["issue_sender"]) and callable(ctx["feishu_sender"])


@step("given", r"^准备临时产物目录$")
def given_tmp_out(ctx):
    ctx["tmpdir"] = tempfile.mkdtemp(prefix="bdd-dispatch-")


@step("when", r'节流器在 "(\d+)" 秒放行键 "([^"]+)" 并落盘')
def when_allow_and_save(ctx, sec, key):
    th = AlertThrottle(3600)
    ctx["allowed"] = th.allow(key, int(sec))
    notify_mod.save_throttle(os.path.join(ctx["tmpdir"], "alert-throttle.json"), th)


@step("when", r'新节流器从盘加载并在 "(\d+)" 秒再次放行同键')
def when_reload_allow(ctx, sec):
    th = notify_mod.load_throttle(os.path.join(ctx["tmpdir"], "alert-throttle.json"))
    ctx["allowed"] = th.allow("budget_exceeded:scan-run", int(sec))


@step("given", r'事件文件含 budget_exceeded 事件 主题 "([^"]+)"')
def given_events_file(ctx, subject):
    event = {
        "kind": "budget_exceeded", "subject": subject,
        "summary": "本轮扫描未完成，游标已保存待续跑",
        "estimated_bytes": 4000000000, "actual_bytes": 4100000000,
    }
    path = os.path.join(ctx["tmpdir"], "alert-events.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump([event], fh, ensure_ascii=False)
    ctx["events_path"] = path


@step("when", r"^运行告警投递 CLI（无凭据）$")
def when_run_notify_cli(ctx):
    saved = _pop_cred_env()
    try:
        argv = ["--events", ctx["events_path"], "--out", ctx["tmpdir"], "--dry-run"]
        ctx["cli_exit"] = notify_mod.main(argv)
    finally:
        _restore_env(saved)
    ctx["report_path"] = os.path.join(ctx["tmpdir"], "alert-dispatch.json")


@step("then", r'CLI 退出码为 "(\d+)"')
def then_cli_exit(ctx, code):
    assert ctx["cli_exit"] == int(code), "CLI 退出码 %r != %s" % (ctx["cli_exit"], code)


@step("then", r'投递报告含 "([^"]+)" 状态 "([^"]+)"')
def then_report_status(ctx, channel, status):
    report = json.load(open(ctx["report_path"], encoding="utf-8"))
    statuses = [r["status"] for r in report["results"] if r.get("channel") == channel]
    assert statuses and statuses[0] == status, "通道 %s 状态 %r != %s" % (channel, statuses, status)


@step("then", r"^节流存储文件已生成$")
def then_throttle_file(ctx):
    assert os.path.isfile(os.path.join(ctx["tmpdir"], "alert-throttle.json"))


@step("then", r'流水线 "([^"]+)" 含 "([^"]+)"')
def then_workflow_contains(ctx, name, needle):
    text = ctx["workflows"][name]
    assert needle in text, "流水线 %s 不含 %r" % (name, needle)
