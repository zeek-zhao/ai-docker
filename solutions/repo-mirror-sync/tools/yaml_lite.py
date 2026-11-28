"""yaml_lite — 轻量 YAML 子集解析器（仅 Python 标准库，跨平台）。

目的：本仓库 config/*.yaml 的唯一解析入口。运行环境可能没有 PyYAML
（Windows 开发机与目标 Linux 服务器均不引入第三方依赖，见 AGENT.md §2），
故自带一个覆盖本仓库配置语法的子集解析器：

- 注释（整行 ``#`` 与行尾 `` #``，引号内 ``#`` 不裁剪）
- 嵌套映射（缩进 2 空格；制表符按 2 空格处理）
- 列表项 ``- <标量>`` / ``- <行内字典>`` / ``- key: v`` 后随同级缩进键值
- 行内字典 ``{ a: b, c: d }``、行内列表 ``[x, y, z]``
- 标量：带引号字符串、整数、浮点、布尔（true/false）、其余按字符串

明确不支持的语法会抛 ``ValueError``（显式失败，不做静默猜测）。
"""

from __future__ import annotations

import re

__all__ = ["parse", "YamlLiteError"]


class YamlLiteError(ValueError):
    """yaml_lite 解析失败（含行号定位）。"""


_INT_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?\d+\.\d*$")
_KV_RE = re.compile(r'^((?:"[^"]*")|(?:\'[^\']*\')|[^:\s][^:]*?):[ ]?(.*)$')


def _tokenize(text):
    """按行产出 (缩进, 去注释后的行内容, 行号)，跳过空行与纯注释行。"""
    tokens = []
    for no, raw in enumerate(text.splitlines(), 1):
        line = raw.replace("\t", "  ")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        content = _strip_comment(stripped)
        if content:
            tokens.append((indent, content, no))
    return tokens


def _strip_comment(s):
    """裁剪行尾注释：引号外且 ``#`` 前是空白（或行首）时截断。"""
    quote = None
    for i, ch in enumerate(s):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or s[i - 1] in " \t"):
            return s[:i].rstrip()
    return s.rstrip()


def _is_kv(s):
    """判断 ``key: value`` 形态（冒号后必须紧跟空格或行尾）。"""
    return bool(_KV_RE.match(s))


def _split_kv(s, no):
    m = _KV_RE.match(s)
    if not m:
        raise YamlLiteError("第 %d 行：无法解析键值对 %r" % (no, s))
    key = m.group(1).strip()
    if len(key) >= 2 and key[0] == key[-1] and key[0] in "\"'":
        key = key[1:-1]
    return key, m.group(2).strip()


def _split_top(s, sep):
    """按顶层分隔符切分（忽略引号与嵌套括号内的 sep）。"""
    parts, depth, quote, buf = [], 0, None, []
    for ch in s:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch in "[{":
            depth += 1
            buf.append(ch)
        elif ch in "]}":
            depth -= 1
            buf.append(ch)
        elif ch == sep and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return [p.strip() for p in parts]


def _parse_scalar(s, no):
    """解析标量 / 行内字典 / 行内列表。"""
    s = s.strip()
    if not s:
        return None
    if s == "{}":
        return {}
    if s == "[]":
        return []
    if s[0] == "{":
        if not s.endswith("}"):
            raise YamlLiteError("第 %d 行：行内字典未闭合：%r" % (no, s))
        result = {}
        for part in _split_top(s[1:-1], ","):
            if not part:
                continue
            if not _is_kv(part):
                raise YamlLiteError("第 %d 行：行内字典片段缺少冒号：%r" % (no, part))
            k, v = _split_kv(part, no)
            result[k] = _parse_scalar(v, no)
        return result
    if s[0] == "[":
        if not s.endswith("]"):
            raise YamlLiteError("第 %d 行：行内列表未闭合：%r" % (no, s))
        return [_parse_scalar(part, no) for part in _split_top(s[1:-1], ",") if part]
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    if s in ("true", "True"):
        return True
    if s in ("false", "False"):
        return False
    if s in ("null", "~", "None"):
        return None
    if _INT_RE.match(s):
        return int(s)
    if _FLOAT_RE.match(s):
        return float(s)
    return s


def _parse_block(tokens, i, indent):
    """解析从 tokens[i] 开始、缩进为 indent 的一个块（映射或列表）。"""
    if tokens[i][1].startswith("-"):
        return _parse_list(tokens, i, indent)
    return _parse_map(tokens, i, indent)


def _parse_map(tokens, i, indent):
    result = {}
    while i < len(tokens) and tokens[i][0] == indent and not tokens[i][1].startswith("-"):
        no = tokens[i][2]
        key, rest = _split_kv(tokens[i][1], no)
        i += 1
        if rest:
            result[key] = _parse_scalar(rest, no)
            continue
        if i < len(tokens) and tokens[i][0] > indent:
            result[key], i = _parse_block(tokens, i, tokens[i][0])
        else:
            result[key] = None
    return result, i


def _parse_list(tokens, i, indent):
    result = []
    while i < len(tokens) and tokens[i][0] == indent and tokens[i][1].startswith("-"):
        no = tokens[i][2]
        first = tokens[i][1][1:].strip()
        if not first:
            if i + 1 < len(tokens) and tokens[i + 1][0] > indent:
                item, i = _parse_block(tokens, i + 1, tokens[i + 1][0])
            else:
                item, i = None, i + 1
            result.append(item)
            continue
        if first[0] in "[{":
            # 行内字典 / 行内列表项（必须先于 key: value 分支判断）
            result.append(_parse_scalar(first, no))
            i += 1
            continue
        if _is_kv(first):
            # 行内首键值 + 后随同级缩进键值，构成一个映射项
            key, rest = _split_kv(first, no)
            entry = {key: _parse_scalar(rest, no) if rest else None}
            i += 1
            child_indent = None
            if i < len(tokens) and tokens[i][0] > indent and _is_kv(tokens[i][1]):
                child_indent = tokens[i][0]
                while (
                    i < len(tokens)
                    and tokens[i][0] == child_indent
                    and _is_kv(tokens[i][1])
                ):
                    k2, r2 = _split_kv(tokens[i][1], tokens[i][2])
                    i += 1
                    if r2:
                        entry[k2] = _parse_scalar(r2, no)
                    elif i < len(tokens) and tokens[i][0] > child_indent:
                        entry[k2], i = _parse_block(tokens, i, tokens[i][0])
                    else:
                        entry[k2] = None
            result.append(entry)
            continue
        result.append(_parse_scalar(first, no))
        i += 1
    return result, i


def parse(text):
    """解析 YAML 子集文本，返回 Python 数据。语法不符抛 YamlLiteError。"""
    tokens = _tokenize(text)
    if not tokens:
        return {}
    value, i = _parse_block(tokens, 0, tokens[0][0])
    if i != len(tokens):
        raise YamlLiteError(
            "第 %d 行附近存在无法归属的缩进（解析在 %d/%d 个有效行处停止）"
            % (tokens[i][2], i, len(tokens))
        )
    return value


def load_file(path):
    """从文件读取并解析（路径由调用方给定；本仓库内一律相对方案目录）。"""
    with open(path, "r", encoding="utf-8") as fh:
        return parse(fh.read())
