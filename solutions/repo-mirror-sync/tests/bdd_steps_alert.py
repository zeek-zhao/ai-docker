"""SC-M5-01~04 步骤定义：告警 payload 生成与节流状态机（FR-A1/NFR-6/H10）。

静态断言策略：事件白名单字面量不出现在本文件或 tools/alert.py——
步骤直接以 config/policy.yaml 的 alert.on 值作为测试数据（唯一出处，AGENTS §3.3）。
"""
import json
import os
import re
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tools.alert import AlertError, AlertThrottle, build_payload, load_alert_policy, render_all  # noqa: E402
from bdd_runner import step  # noqa: E402

_NET_RE = re.compile(r"^\s*(?:import|from)\s+(requests|urllib3?|http|socket|httplib)\b", re.M)
_THROTTLE_LIT_RE = re.compile(r"3600|[\"']1h[\"']")


def _num(text):
    return None if text == "-" else int(text)


@step("given", r"^策略文件已加载并构建告警器$")
def given_rules(ctx):
    ctx["rules"] = load_alert_policy()


@step("when", r'^提交事件 "([^"]+)" 主题 "([^"]+)" 估算 "([^"]*)" 实测 "([^"]*)"$')
def when_submit(ctx, kind, subject, est, act):
    event = {"kind": kind, "subject": subject, "summary": "%s %s" % (kind, subject)}
    if est != "-":
        event["estimated_bytes"] = int(est)
    if act != "-":
        event["actual_bytes"] = int(act)
    try:
        ctx["payload"] = build_payload(event, ctx["rules"])
        ctx["error"] = None
    except AlertError as exc:
        ctx["payload"] = None
        ctx["error"] = exc


@step("when", r'^提交未知事件 "([^"]+)"$')
def when_submit_unknown(ctx, kind):
    try:
        build_payload({"kind": kind, "subject": "x"}, ctx["rules"])
        ctx["error"] = None
    except AlertError as exc:
        ctx["error"] = exc


@step("then", r'^payload kind 为 "([^"]+)"$')
def then_kind(ctx, kind):
    assert ctx["payload"] is not None and ctx["payload"]["kind"] == kind


@step("then", r'^payload 去重键为 "([^"]+)"$')
def then_dedup(ctx, key):
    assert ctx["payload"]["dedup_key"] == key


@step("then", r"^payload 含估算实测双数$")
def then_pair(ctx):
    p = ctx["payload"]
    assert p["estimated_bytes"] is not None and p["actual_bytes"] is not None


@step("then", r"^抛出 AlertError$")
def then_alert_error(ctx):
    assert ctx["error"] is not None and isinstance(ctx["error"], AlertError)


@step("then", r'^节流窗口取自策略为 "(\d+)" 秒$')
def then_window(ctx, sec):
    assert ctx["rules"]["throttle_seconds"] == int(sec)


@step("when", r'^节流器在 "(\d+)" 秒放行键 "([^"]+)"$')
def when_allow(ctx, sec, key):
    thr = ctx.setdefault("throttle", AlertThrottle(ctx["rules"]["throttle_seconds"]))
    ctx.setdefault("first_key", key)
    ctx["last_key"] = key
    ctx["allowed"] = thr.allow(key, int(sec))


@step("when", r'^节流器在 "(\d+)" 秒再次放行同键$')
def when_allow_same(ctx, sec):
    thr = ctx.setdefault("throttle", AlertThrottle(ctx["rules"]["throttle_seconds"]))
    ctx["allowed"] = thr.allow(ctx["last_key"], int(sec))


@step("when", r'^节流器在 "(\d+)" 秒再次放行首键$')
def when_allow_first(ctx, sec):
    thr = ctx.setdefault("throttle", AlertThrottle(ctx["rules"]["throttle_seconds"]))
    ctx["allowed"] = thr.allow(ctx["first_key"], int(sec))


@step("then", r"^放行结果为 (真|假)$")
def then_allowed(ctx, flag):
    assert ctx["allowed"] is (flag == "真")


@step("when", r'^渲染事件 "([^"]+)" 主题 "([^"]+)" 为全部通道$')
def when_render(ctx, kind, subject):
    payload = build_payload(
        {"kind": kind, "subject": subject, "summary": "%s %s" % (kind, subject)},
        ctx["rules"],
    )
    ctx["payload"] = payload
    ctx["rendered"] = render_all(payload)


@step("then", r'^渲染结果含 "(\d+)" 个通道$')
def then_channels(ctx, n):
    rendered = ctx["rendered"]
    assert len(rendered) == int(n)
    assert [r["channel"] for r in rendered] == ctx["rules"]["channels"]


@step("then", r'^github-issue 渲染含标签 "([^"]+)"$')
def then_issue(ctx, label):
    item = next(r for r in ctx["rendered"] if r["channel"] == "github-issue")
    assert label in item["labels"] and item["title"].startswith("[mirror-sync]")


@step("then", r"^feishu 渲染为文本内容$")
def then_feishu(ctx):
    item = next(r for r in ctx["rendered"] if r["channel"] == "feishu-webhook")
    assert item["msg_type"] == "text" and item["content"]["text"]


@step("then", r"^渲染结果不含凭据字段$")
def then_no_credential(ctx):
    text = json.dumps(ctx["rendered"], ensure_ascii=False).lower()
    for word in ("token", "secret", "password", "authorization", "hook_url", "https://"):
        assert word not in text, "渲染结果泄漏凭据字段：%s" % word


@step("given", r"^已读取 tools/alert.py 源码$")
def given_src(ctx):
    ctx["rules"] = load_alert_policy()
    with open(os.path.join(_HERE, "..", "tools", "alert.py"), "r", encoding="utf-8") as fh:
        ctx["alert_src"] = fh.read()


@step("then", r"^源码不含事件白名单字面量$")
def then_no_whitelist(ctx):
    for kind in ctx["rules"]["on"]:
        assert kind not in ctx["alert_src"], "alert.py 硬编码事件名：%s" % kind


@step("then", r"^源码不含硬编码节流时长$")
def then_no_throttle_lit(ctx):
    assert _THROTTLE_LIT_RE.search(ctx["alert_src"]) is None


@step("then", r"^源码不导入网络库$")
def then_no_net(ctx):
    assert _NET_RE.search(ctx["alert_src"]) is None


@step("then", r"^源码引用策略加载$")
def then_policy_ref(ctx):
    assert "load_policy" in ctx["alert_src"]
