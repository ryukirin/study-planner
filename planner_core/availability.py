from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from . import jp_holidays
from .plan_spec import WEEK_KEYS, format_date, parse_date
from .storage import load_json, write_json_atomic
from .timeutil import format_time, parse_time

PROFILE_KEYS = {"version", "buffer_minutes", "weekly", "exceptions", "holidays", "holiday"}
HOLIDAY_CALENDARS = ("none", "jp")
WINDOW_KEYS = {"start", "end", "tag", "label"}
EXCEPTION_KEYS = {"date", "windows", "note"}
STANDARD_TAGS = ("focus", "commute", "light")
TAG_NAMES = {"focus": "整块学习", "commute": "通勤", "light": "轻任务"}


class ProfileError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("\n".join(errors))


@dataclass
class Window:
    start: int
    end: int
    tag: str = "focus"
    label: str = ""

    @property
    def minutes(self) -> int:
        return self.end - self.start

    def to_dict(self) -> dict[str, str]:
        return {"start": format_time(self.start), "end": format_time(self.end), "tag": self.tag, "label": self.label}

    def describe(self) -> str:
        name = self.label or TAG_NAMES.get(self.tag, self.tag)
        return f"{format_time(self.start)}-{format_time(self.end)} {name}[{self.tag}]"


@dataclass
class Profile:
    weekly: dict[str, list[Window]] = field(default_factory=lambda: {key: [] for key in WEEK_KEYS})
    exceptions: dict[date, list[Window]] = field(default_factory=dict)
    exception_notes: dict[date, str] = field(default_factory=dict)
    buffer_minutes: int = 5
    holidays: str = "none"
    # None 表示祝日沿用周六的时间段
    holiday: list[Window] | None = None

    def holiday_name(self, day: date) -> str | None:
        """开启日本祝日时返回祝日名称，否则返回 None。"""
        if self.holidays != "jp":
            return None
        return jp_holidays.holiday_name(day)

    def holiday_windows(self) -> list[Window]:
        return self.weekly["sat"] if self.holiday is None else self.holiday

    def uses_holiday_windows(self, day: date) -> bool:
        """周一至周五的祝日按祝日时间段排程。周末的祝日仍用当天的星期模板，例外日期优先。"""
        return day not in self.exceptions and day.weekday() < 5 and self.holiday_name(day) is not None

    def windows_for(self, day: date) -> list[Window]:
        if day in self.exceptions:
            return self.exceptions[day]
        if self.uses_holiday_windows(day):
            return self.holiday_windows()
        return self.weekly[WEEK_KEYS[day.weekday()]]

    def tags(self) -> set[str]:
        tags = {window.tag for windows in self.weekly.values() for window in windows}
        tags.update(window.tag for windows in self.exceptions.values() for window in windows)
        if self.holidays != "none" and self.holiday:
            tags.update(window.tag for window in self.holiday)
        return tags

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "version": 1,
            "buffer_minutes": self.buffer_minutes,
            "weekly": {key: [window.to_dict() for window in self.weekly[key]] for key in WEEK_KEYS},
            "holidays": self.holidays,
        }
        if self.holiday is not None:
            data["holiday"] = [window.to_dict() for window in self.holiday]
        data["exceptions"] = [
            {"date": format_date(day), "windows": [window.to_dict() for window in windows], "note": self.exception_notes.get(day, "")}
            for day, windows in sorted(self.exceptions.items())
        ]
        return data


def default_profile() -> Profile:
    profile = Profile()
    for key in WEEK_KEYS[:5]:
        profile.weekly[key] = [Window(parse_time("20:00"), parse_time("21:30"), "focus", "晚上")]
    for key in WEEK_KEYS[5:]:
        profile.weekly[key] = [Window(parse_time("14:00"), parse_time("16:00"), "focus", "下午")]
    return profile


def check_windows(windows: list[Window]) -> list[str]:
    """检查同一天的时间段：开始早于结束、互不重叠。"""
    problems = []
    for window in windows:
        if window.start >= window.end:
            problems.append(f"{format_time(window.start)}-{format_time(window.end)}：开始时间必须早于结束时间")
        if not window.tag.strip():
            problems.append(f"{format_time(window.start)}-{format_time(window.end)}：tag 不能为空")
    ordered = sorted(windows, key=lambda item: item.start)
    for previous, current in zip(ordered, ordered[1:]):
        if current.start < previous.end:
            problems.append(f"{previous.describe()} 和 {current.describe()} 时间重叠")
    return problems


def _parse_windows(raw: Any, path: str, errors: list[str]) -> list[Window]:
    if not isinstance(raw, list):
        errors.append(f"{path}：必须是时间段数组")
        return []
    windows = []
    for index, item in enumerate(raw):
        item_path = f"{path}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{item_path}：必须是对象")
            continue
        for key in item:
            if key not in WINDOW_KEYS:
                errors.append(f"{item_path}：未知字段 {key}")
        try:
            start = parse_time(item.get("start"))
            end = parse_time(item.get("end"))
        except ValueError as exc:
            errors.append(f"{item_path}：{exc}")
            continue
        tag = item.get("tag", "focus")
        label = item.get("label", "")
        if not isinstance(tag, str) or not isinstance(label, str):
            errors.append(f"{item_path}：tag 和 label 必须是字符串")
            continue
        windows.append(Window(start, end, tag.strip(), label))
    errors.extend(f"{path}：{problem}" for problem in check_windows(windows))
    return sorted(windows, key=lambda item: item.start)


def parse_profile(data: Any) -> Profile:
    errors: list[str] = []
    if not isinstance(data, dict):
        raise ProfileError(["profile.json 必须是 JSON 对象"])
    for key in data:
        if key not in PROFILE_KEYS:
            errors.append(f"未知字段 {key}")
    profile = Profile()
    buffer = data.get("buffer_minutes", 5)
    if not isinstance(buffer, int) or isinstance(buffer, bool) or not 0 <= buffer <= 60:
        errors.append("buffer_minutes：必须是 0 到 60 的整数")
    else:
        profile.buffer_minutes = buffer
    weekly = data.get("weekly", {})
    if not isinstance(weekly, dict):
        errors.append("weekly：必须是对象，键为 mon 到 sun")
        weekly = {}
    for key, raw in weekly.items():
        if key not in WEEK_KEYS:
            errors.append(f"weekly：未知键 {key}，只能用 {', '.join(WEEK_KEYS)}")
            continue
        profile.weekly[key] = _parse_windows(raw, f"weekly.{key}", errors)
    holidays = data.get("holidays")
    if holidays is None:
        holidays = "none"
    if holidays not in HOLIDAY_CALENDARS:
        errors.append('holidays：只能是 "jp"（按日本祝日排程）或 "none"（不处理祝日）')
    else:
        profile.holidays = holidays
    if data.get("holiday") is not None:
        profile.holiday = _parse_windows(data["holiday"], "holiday", errors)
    exceptions = data.get("exceptions", [])
    if not isinstance(exceptions, list):
        errors.append("exceptions：必须是数组")
        exceptions = []
    for index, raw in enumerate(exceptions):
        path = f"exceptions[{index}]"
        if not isinstance(raw, dict):
            errors.append(f"{path}：必须是对象")
            continue
        for key in raw:
            if key not in EXCEPTION_KEYS:
                errors.append(f"{path}：未知字段 {key}")
        try:
            day = parse_date(raw.get("date", ""))
        except (TypeError, ValueError):
            errors.append(f"{path}.date：格式应为 YYYY-MM-DD")
            continue
        if day in profile.exceptions:
            errors.append(f"{path}：日期 {format_date(day)} 重复")
            continue
        profile.exceptions[day] = _parse_windows(raw.get("windows", []), f"{path}.windows", errors)
        note = raw.get("note", "")
        if isinstance(note, str) and note:
            profile.exception_notes[day] = note
    if errors:
        raise ProfileError(errors)
    return profile


@dataclass
class ProfileLoad:
    profile: Profile
    is_default: bool
    errors: list[str]
    warning: str | None


def load_profile(path: str) -> ProfileLoad:
    """profile 不存在时用默认时间段。内容有错时也先用默认时间段，同时返回错误供界面提示。"""
    data, warning = load_json(path, lambda: None)
    if data is None:
        return ProfileLoad(default_profile(), True, [], warning)
    try:
        return ProfileLoad(parse_profile(data), False, [], warning)
    except ProfileError as exc:
        return ProfileLoad(default_profile(), True, exc.errors, warning)


def save_profile(path: str, profile: Profile) -> None:
    write_json_atomic(path, profile.to_dict())
