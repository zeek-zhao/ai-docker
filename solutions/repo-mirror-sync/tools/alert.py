"""告警 payload 生成与节流状态机（阶段 5，FR-A1/NFR-6/H10，ADR-010）。

纯逻辑模块：不导入任何网络库，也不包含事件白名单与节流时长常量——
两者唯一出处为 config/policy.yaml 的 ``alert.on`` 与 ``alert.throttle``（AGENTS §3.3/§3.6）。
实际投递由调用方注入 sender（薄封装）；本模块的渲染与节流不产生网络行为，
真实通道连通性属 Linux 阶段 5 验证（AGENTS §3.5，待执行）。

需求映射：FR-A1 四类告警双通道+节流；NFR-6 估算/实测双数成对；H10 按键节流防风暴。
"""
import os
import re

from tools.policy import load_policy

__all__ = [
    "AlertError",
    "AlertThrottle",
    "build_payload",
    "load_alert_policy",
    "parse_duration",
    "render_all",
    "render_channel",
]

_DURATION_RE = re.compile(r"^(\d+)([smh])$")
_DURATION_UNITS = {"s": 1, "m": 60, "h": 60 * 60}
_CREDENTIALED_CHANNELS = frozenset({"github-issue", "feishu-webhook"})


class AlertError(Exception):
    """告警策略非法、事件未知、双数不成对或节流参数非法。"""


def parse_duration(text):
    """把 ``<数字><s|m|h>`` 形式的时长解析为秒数；非法输入抛 AlertError。"""
    m = _DURATION_RE.match(str(text).strip())
    if not m:
        raise AlertError("无法解析节流时长：%r（期望 <数字><s|m|h>）" % (text,))
    return int(m.group(1)) * _DURATION_UNITS[m.group(2)]


def load_alert_policy(solution_dir=None):
    """从 config/policy.yaml 读取告警节并校验，返回 {channels,on,throttle_seconds}。

    白名单与节流时长一律取自策略文件，本函数不提供任何默认值。
    solution_dir 缺省时按模块位置解析（<方案目录>/tools/alert.py 的上一级），
    仓库相对路径，跨平台可移植。
    """
    if solution_dir is None:
        solution_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    policy = load_policy(solution_dir)
    alert = policy.raw.get("alert") or {}
    if not alert:
        raise AlertError("config/policy.yaml 缺少 alert 节")
    channels = alert.get("channels") or []
    kinds = alert.get("on") or []
    throttle_text = alert.get("throttle")
    if not channels or not isinstance(channels, list):
        raise AlertError("alert.channels 必须为非空列表")
    if not kinds or not isinstance(kinds, list):
        raise AlertError("alert.on 必须为非空列表")
    if not throttle_text:
        raise AlertError("alert.throttle 必填（防告警风暴，H10）")
    seconds = parse_duration(throttle_text)
    if seconds <= 0:
        raise AlertError("alert.throttle 必须为正时长")
    unknown_channel = [c for c in channels if c not in _CREDENTIALED_CHANNELS]
    if unknown_channel:
        raise AlertError("alert.channels 含未支持的通道：%s" % ", ".join(unknown_channel))
    return {"channels": list(channels), "on": list(kinds), "throttle_seconds": seconds}


class AlertThrottle:
    """按键独立的节流状态机：窗口内同键抑制，过期放行并刷新时间戳。"""

    def __init__(self, window_seconds):
        if isinstance(window_seconds, bool) or not isinstance(window_seconds, (int, float)):
            raise AlertError("节流窗口必须为正数秒")
        if window_seconds <= 0:
            raise AlertError("节流窗口必须为正数秒")
        self.window_seconds = window_seconds
        self._last = {}

    def allow(self, key, now):
        """键在窗口内未被发送或已过期时放行（并记录时间戳），否则抑制。"""
        if not isinstance(key, str) or not key:
            raise AlertError("节流键必须为非空字符串")
        if isinstance(now, bool) or not isinstance(now, (int, float)):
            raise AlertError("时间戳必须为数值")
        prev = self._last.get(key)
        if prev is not None and now < prev + self.window_seconds:
            return False
        self._last[key] = now
        return True

    def snapshot(self):
        """导出纯数据快照（落盘/跨进程恢复用，H10；不含凭据）。"""
        return {"window_seconds": self.window_seconds, "last": dict(self._last)}

    def restore(self, state):
        """从 snapshot() 数据恢复；结构非法即拒绝（防半截文件静默生效）。"""
        if not isinstance(state, dict):
            raise AlertError("节流快照必须为对象")
        window = state.get("window_seconds")
        last = state.get("last", {})
        if isinstance(window, bool) or not isinstance(window, (int, float)) or window <= 0:
            raise AlertError("节流快照窗口非法")
        if not isinstance(last, dict):
            raise AlertError("节流快照键表非法")
        clean = {}
        for key, stamp in last.items():
            if isinstance(key, str) and key and not isinstance(stamp, bool) \
                    and isinstance(stamp, (int, float)):
                clean[key] = stamp
        self.window_seconds = window
        self._last = clean


def build_payload(event, rules):
    """按策略白名单构建告警事件 payload；未知事件类型抛 AlertError。

    NFR-6（判断保真）：估算/实测双数必须成对出现，缺一即拒绝——
    保证体积类通知不出现单边数字。
    """
    if not isinstance(event, dict):
        raise AlertError("事件必须为字典")
    kind = event.get("kind")
    subject = event.get("subject")
    if not isinstance(kind, str) or not kind:
        raise AlertError("事件缺少 kind")
    if kind not in rules["on"]:
        raise AlertError("未知事件类型：%s（白名单见 config/policy.yaml alert.on）" % kind)
    if not isinstance(subject, str) or not subject:
        raise AlertError("事件缺少 subject")
    estimated = event.get("estimated_bytes")
    actual = event.get("actual_bytes")
    if (estimated is None) != (actual is None):
        raise AlertError("估算/实测双数必须成对提供（NFR-6）")
    for name, value in (("estimated_bytes", estimated), ("actual_bytes", actual)):
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
            raise AlertError("%s 必须为非负整数" % name)
    return {
        "kind": kind,
        "subject": subject,
        "summary": str(event.get("summary") or "%s %s" % (kind, subject)),
        "estimated_bytes": estimated,
        "actual_bytes": actual,
        "dedup_key": "%s:%s" % (kind, subject),
        "channels": list(rules["channels"]),
    }


def _size_line(payload):
    if payload["estimated_bytes"] is None:
        return None
    return "估算体积 %d 字节 / 实测体积 %d 字节" % (
        payload["estimated_bytes"],
        payload["actual_bytes"],
    )


def render_channel(channel, payload):
    """把 payload 渲染为通道负载；未支持通道抛 AlertError。仅渲染，不发送。"""
    if channel not in _CREDENTIALED_CHANNELS:
        raise AlertError("未支持的告警通道：%s" % channel)
    title = "[mirror-sync][%s] %s" % (payload["kind"], payload["subject"])
    body_lines = [payload["summary"]]
    size_line = _size_line(payload)
    if size_line:
        body_lines.append(size_line)
    if channel == "github-issue":
        return {
            "channel": channel,
            "title": title,
            "body": "\n".join(body_lines),
            "labels": ["mirror-sync", payload["kind"]],
        }
    return {
        "channel": channel,
        "msg_type": "text",
        "content": {"text": "\n".join([title] + body_lines)},
    }


def render_all(payload):
    """按 payload.channels 顺序渲染全部通道负载。"""
    return [render_channel(channel, payload) for channel in payload["channels"]]


def dispatch(rendered, senders):
    """薄封装投递：senders 为 {通道名: 可调用(渲染负载)}；默认不发送、无网络行为。

    未提供 sender 的通道跳过并在结果中标记 skipped，交由调用方决定如何处置。
    """
    if not isinstance(senders, dict):
        raise AlertError("senders 必须为 {通道名: 可调用} 字典")
    results = []
    for item in rendered:
        channel = item.get("channel")
        sender = senders.get(channel)
        if sender is None:
            results.append({"channel": channel, "status": "skipped"})
            continue
        results.append({"channel": channel, "status": "sent", "result": sender(item)})
    return results
