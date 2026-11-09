from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable

from .availability import Profile, Window
from .plan_spec import Session


@dataclass
class Placement:
    session: Session
    start: int
    end: int
    window: Window | None  # 定时任务不属于任何空闲时间段，为 None


@dataclass
class DayLayout:
    day: date
    windows: list[Window]
    placed: list[Placement]
    overflow: list[Session]

    @property
    def available_minutes(self) -> int:
        return sum(window.minutes for window in self.windows)

    @property
    def planned_minutes(self) -> int:
        return sum(item.session.minutes for item in self.placed) + sum(session.minutes for session in self.overflow)

    @property
    def fixed(self) -> list[Placement]:
        return [item for item in self.placed if item.window is None]

    def fixed_overlaps(self) -> list[tuple[Placement, Placement]]:
        items = sorted(self.fixed, key=lambda item: item.start)
        return [(a, b) for i, a in enumerate(items) for b in items[i + 1:] if b.start < a.end]


def _first_free(start: int, end: int, minutes: int, busy: list[tuple[int, int]], buffer_minutes: int) -> int | None:
    """在 [start, end] 里找第一个能放下 minutes 且不与 busy 重叠的位置。"""
    position = start
    while position + minutes <= end:
        conflict = next((block for block in busy if block[0] < position + minutes and position < block[1]), None)
        if conflict is None:
            return position
        position = conflict[1] + buffer_minutes
    return None


def layout_day(day: date, sessions: list[Session], windows: list[Window], buffer_minutes: int) -> DayLayout:
    """定时任务按 time 固定放置。其余任务按 计划优先级 → 计划 id → 当天顺序，
    放入第一个 tag 匹配、放得下且不与定时任务重叠的时间段。"""
    ordered_windows = sorted(windows, key=lambda item: item.start)
    cursors = [window.start for window in ordered_windows]
    placed: list[Placement] = []
    overflow: list[Session] = []
    busy: list[tuple[int, int]] = []
    ordered = sorted(sessions, key=lambda item: (item.priority, item.plan_id, item.order))
    for session in ordered:
        if session.is_fixed:
            start = session.fixed_start
            placed.append(Placement(session, start, start + session.minutes, None))
            busy.append((start, start + session.minutes))
    for session in ordered:
        if session.is_fixed:
            continue
        for index, window in enumerate(ordered_windows):
            if session.slot and session.slot != window.tag:
                continue
            start = _first_free(cursors[index], window.end, session.minutes, busy, buffer_minutes)
            if start is not None:
                placed.append(Placement(session, start, start + session.minutes, window))
                cursors[index] = start + session.minutes + buffer_minutes
                break
        else:
            overflow.append(session)
    placed.sort(key=lambda item: (item.start, item.session.priority))
    return DayLayout(day=day, windows=ordered_windows, placed=placed, overflow=overflow)


@dataclass
class WeekLoad:
    week_start: date
    required: int = 0
    available: int = 0

    @property
    def ratio(self) -> float:
        return self.required / self.available if self.available else (float("inf") if self.required else 0.0)


@dataclass
class Feasibility:
    start: date
    end: date
    overflow: list[tuple[date, list[Session]]] = field(default_factory=list)
    weeks: list[WeekLoad] = field(default_factory=list)
    overlaps: list[tuple[date, Session, Session]] = field(default_factory=list)

    @property
    def overflow_count(self) -> int:
        return sum(len(items) for _, items in self.overflow)


def feasibility(sessions_on: Callable[[date], list[Session]], profile: Profile, start: date, end: date) -> Feasibility:
    report = Feasibility(start=start, end=end)
    week: WeekLoad | None = None
    day = start
    while day <= end:
        week_start = day - timedelta(days=day.weekday())
        if week is None or week.week_start != week_start:
            week = WeekLoad(week_start=week_start)
            report.weeks.append(week)
        windows = profile.windows_for(day)
        sessions = sessions_on(day)
        layout = layout_day(day, sessions, windows, profile.buffer_minutes)
        week.available += layout.available_minutes
        week.required += sum(session.minutes for session in sessions)
        if layout.overflow:
            report.overflow.append((day, layout.overflow))
        report.overlaps.extend((day, a.session, b.session) for a, b in layout.fixed_overlaps())
        day += timedelta(days=1)
    return report
