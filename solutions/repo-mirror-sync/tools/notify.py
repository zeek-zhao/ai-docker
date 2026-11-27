# -*- coding: utf-8 -*-
# 告警投递网络层（M9 阶段5，FR-A1/IF-5/H10）。
# 纯逻辑在 tools/alert.py（不导入网络库，SC-M5-04）；本模块是告警链路唯一网络点，
# 凭据仅经环境变量注入（AGENTS §3.4），任何报告/日志不得回显凭据。
from __future__ import annotations

import json
import os
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.alert import (AlertError, AlertThrottle, build_payload, dispatch,
                         load_alert_policy, render_all)


def _now():
    """+08:00 时区 ISO 时间戳（与方案其余产物一致）。"""
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).isoformat(timespec="seconds")


def make_github_issue_sender(token_env="GH_TOKEN", api_base="https://api.github.com"):
    """构造 github-issue 投递器；凭据缺失当场拒绝（防御在工厂，不延迟到发网）。"""
    token = os.environ.get(token_env)
    if not token:
        raise AlertError("环境变量 %s 未设置，github-issue 通道不可用" % token_env)

    def _send(item):
        repo = os.environ.get("GITHUB_REPOSITORY")
        if not repo:
            raise AlertError("环境变量 GITHUB_REPOSITORY 未设置，无法定位 Issue 目标仓库")
        body = json.dumps({
            "title": item["title"],
            "body": item["body"],
            "labels": item["labels"],
        }).encode("utf-8")
        request = urllib.request.Request(
            api_base + "/repos/%s/issues" % repo, data=body, method="POST",
            headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            })
        with urllib.request.urlopen(request) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return {"issue_url": data.get("html_url", "")}

    return _send


def make_feishu_sender(url_env="FEISHU_WEBHOOK_URL"):
    """构造 feishu-webhook 投递器；URL 缺失当场拒绝。"""
    url = os.environ.get(url_env)
    if not url:
        raise AlertError("环境变量 %s 未设置，feishu-webhook 通道不可用" % url_env)

    def _send(item):
        body = json.dumps({
            "msg_type": item["msg_type"],
            "content": item["content"],
        }).encode("utf-8")
        request = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request) as resp:
            return json.loads(resp.read().decode("utf-8"))

    return _send


def build_senders(rules, token_env="GH_TOKEN", feishu_env="FEISHU_WEBHOOK_URL"):
    """按策略通道装配投递器；工厂凭据拒绝 → 该通道记 None（dispatch 判 skipped）。"""
    factories = {
        "github-issue": lambda: make_github_issue_sender(token_env),
        "feishu-webhook": lambda: make_feishu_sender(feishu_env),
    }
    senders = {}
    for channel in rules["channels"]:
        factory = factories.get(channel)
        if factory is None:
            senders[channel] = None
            continue
        try:
            senders[channel] = factory()
        except AlertError:
            senders[channel] = None
    return senders


def save_throttle(path, throttle):
    """节流状态落盘（H10 跨 CI run 持久化；纯数据快照，不含凭据）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(throttle.snapshot(), ensure_ascii=False), encoding="utf-8")


def load_throttle(path, fallback_seconds=None):
    """从盘恢复节流器；文件缺失且无回退窗口时拒绝（调用方决定默认值）。"""
    p = Path(path)
    if not p.is_file():
        if fallback_seconds is None:
            raise AlertError("节流快照缺失且未提供回退窗口：%s" % p)
        return AlertThrottle(fallback_seconds)
    try:
        state = json.loads(p.read_text(encoding="utf-8"))
        seed = fallback_seconds if fallback_seconds is not None else 1
        throttle = AlertThrottle(seed)
        throttle.restore(state)
        return throttle
    except (ValueError, AlertError):
        # 半截/非法快照：按回退窗口重建（宁可重发不可崩溃，H10 韧性）
        if fallback_seconds is None:
            raise AlertError("节流快照损坏且未提供回退窗口：%s" % p)
        return AlertThrottle(fallback_seconds)


def collect_events(event_files, inline=None):
    """合并事件源：--events 文件（缺失即忽略，供 if: always() 场景）+ 内联单事件。"""
    events = []
    for name in event_files:
        p = Path(name)
        if not p.is_file():
            continue
        loaded = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            loaded = [loaded]
        events.extend(loaded)
    if inline is not None:
        events.append(inline)
    return events


def run(events, rules, senders, throttle, throttle_path, dry_run=False):
    """节流→渲染→投递→报告（编排层；网络行为只发生在 sender 内部）。"""
    now = time.time()
    results, event_rows = [], []
    for event in events:
        payload = build_payload(event, rules)
        if not throttle.allow(payload["dedup_key"], now):
            event_rows.append({"dedup_key": payload["dedup_key"], "status": "throttled"})
            continue
        rendered = render_all(payload)
        delivered = []
        pending = []
        for item in rendered:
            if senders.get(item["channel"]) is None:
                delivered.append({"channel": item["channel"], "status": "skipped"})
            elif dry_run:
                delivered.append({"channel": item["channel"], "status": "dry-run"})
            else:
                pending.append(item)
        if pending:
            delivered.extend(dispatch(pending, senders))
        results.extend(delivered)
        statuses = {row["channel"]: row["status"] for row in delivered}
        if "sent" in statuses.values():
            status = "sent"
        elif "dry-run" in statuses.values():
            status = "dry-run"
        else:
            status = "skipped"
        event_rows.append({"dedup_key": payload["dedup_key"], "status": status})
    report = {"generated": _now(), "results": results, "events": event_rows}
    save_throttle(throttle_path, throttle)
    return report


def main(argv=None):
    """CLI：--events 可重复（缺失忽略）；或内联 --kind/--subject 单事件；--dry-run 只渲染。"""
    import argparse

    parser = argparse.ArgumentParser(description="告警投递（FR-A1，唯一网络点）")
    parser.add_argument("--events", action="append", default=[],
                        help="事件 JSON 文件（可重复；文件缺失时忽略）")
    parser.add_argument("--kind", help="内联事件 kind")
    parser.add_argument("--subject", help="内联事件主题")
    parser.add_argument("--summary", default="", help="内联事件摘要")
    parser.add_argument("--estimated-bytes", type=int, default=None)
    parser.add_argument("--actual-bytes", type=int, default=None)
    parser.add_argument("--out", default="out", help="产物目录（报告/节流存储）")
    parser.add_argument("--dry-run", action="store_true", help="只渲染与审计，不真实投递")
    parser.add_argument("--token-env", default="GH_TOKEN")
    parser.add_argument("--feishu-env", default="FEISHU_WEBHOOK_URL")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "alert-dispatch.json"

    try:
        rules = load_alert_policy(root)
    except AlertError as exc:
        print("告警策略加载失败：%s" % exc)
        return 2

    inline = None
    if args.kind or args.subject:
        if not (args.kind and args.subject):
            print("--kind 与 --subject 必须成对提供")
            return 2
        inline = {"kind": args.kind, "subject": args.subject, "summary": args.summary}
        if (args.estimated_bytes is None) != (args.actual_bytes is None):
            print("--estimated-bytes 与 --actual-bytes 必须成对（NFR-6）")
            return 2
        if args.estimated_bytes is not None:
            inline["estimated_bytes"] = args.estimated_bytes
            inline["actual_bytes"] = args.actual_bytes

    events = collect_events(args.events, inline)
    if not events:
        report = {"generated": _now(), "results": [], "events": []}
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("无事件需要投递")
        return 0

    senders = build_senders(rules, args.token_env, args.feishu_env)
    throttle_path = out_dir / "alert-throttle.json"
    throttle = load_throttle(throttle_path, rules["throttle_seconds"])
    report = run(events, rules, senders, throttle, throttle_path, dry_run=args.dry_run)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for row in report["events"]:
        print("%s → %s" % (row["dedup_key"], row["status"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
