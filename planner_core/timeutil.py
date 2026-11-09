from __future__ import annotations

import re

TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


def parse_time(value: str) -> int:
    """HH:MM 转为当天的分钟数，允许 24:00。"""
    match = TIME_RE.match(value.strip()) if isinstance(value, str) else None
    if not match:
        raise ValueError(f"时间 {value!r} 格式不对，应为 HH:MM")
    hour, minute = int(match.group(1)), int(match.group(2))
    if minute >= 60 or hour > 24 or (hour == 24 and minute > 0):
        raise ValueError(f"时间 {value!r} 超出范围")
    return hour * 60 + minute


def format_time(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"
