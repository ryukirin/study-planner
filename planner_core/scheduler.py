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
    early: list[Session] = field(default_factory=list)  # 在这一天之前就完成的任务，不占这一天的时间

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


def layout_day(day: date, sessions: list[Session], windows: list[Window], buffer_minutes: int,
               manual: dict[int, list[str]] | None = None) -> DayLayout:
    """定时任务按 time 固定放置。其余任务按 计划优先级 → 计划 id → 原定日期 → 当天顺序，
    放入第一个 tag 匹配、放得下且不与定时任务重叠的时间段。改期的任务按原定日期排，
    从前面改过来的排在当天同一计划的任务之前，从后面提前的排在之后。

    manual 是手动排序：{时间段开始的分钟数: [任务 id]}。列出的任务先按列表顺序放进指定的时间段，不检查 tag。
    时间段不存在、任务不存在或放不下的条目被忽略，对应的任务按上面的规则自动安排。"""
    ordered_windows = sorted(windows, key=lambda item: item.start)
    cursors = [window.start for window in ordered_windows]
    placed: list[Placement] = []
    overflow: list[Session] = []
    busy: list[tuple[int, int]] = []
    ordered = sorted(sessions, key=lambda item: (item.priority, item.plan_id, item.moved_from or item.day, item.order))
    for session in ordered:
        if session.is_fixed:
            start = session.fixed_start
            placed.append(Placement(session, start, start + session.minutes, None))
            busy.append((start, start + session.minutes))
    movable = {session.uid: session for session in ordered if not session.is_fixed}
    pinned: set[str] = set()
    for index, window in enumerate(ordered_windows):
        for uid in (manual or {}).get(window.start, []):
            session = movable.get(uid)
            if session is None or uid in pinned:
                continue
            start = _first_free(cursors[index], window.end, session.minutes, busy, buffer_minutes)
            if start is None:
                continue
            placed.append(Placement(session, start, start + session.minutes, window))
            cursors[index] = start + session.minutes + buffer_minutes
            pinned.add(uid)
    for session in ordered:
        if session.is_fixed or session.uid in pinned:
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


def replan_day(base: DayLayout, at: int, buffer_minutes: int, done: dict[str, int | None],
               manual: dict[int, list[str]] | None = None) -> DayLayout:
    """从 at 时刻起重排一天里还没做的任务。

    base 是 layout_day 的结果。done 是已完成任务的完成时刻（当天的分钟数，不在当天完成的为 None）。

    - 定时任务不动。
    - 已完成的任务不再占用后面的时间。原来排在 at 之前、也在 at 之前完成的保持原位。
      提前完成的（原来排在 at 之后）和 at 之后才完成的，改为在完成时刻结束。
    - 没完成的任务全部重排：按 base 里的先后顺序，从 at 起放进时间段，避开定时任务和已完成任务占用的时间。
      能放进原来的时间段或 tag 匹配的时间段，取最早放得下的一个，都放不下进入未排入。
    - 原来未排入的任务排在最后重新尝试。
    - manual 是手动排序，格式和 layout_day 的一样。列出的没完成的任务排在前面，先试指定的时间段，不检查 tag。
      已完成的任务腾出了时间，所以 layout_day 里放不下的手动条目在这里可能放得下。"""
    frozen: list[Placement] = []
    waiting: list[tuple[Session, Window | None]] = []
    for item in base.placed:
        session = item.session
        if session.is_fixed:
            frozen.append(item)
        elif session.uid in done:
            minute = done[session.uid]
            if minute is None and item.end > at:
                minute = at
            if minute is not None and (minute > at or item.end > at):
                # 开始时刻按时长倒推。原来的开始时刻已经过了的，不早于原来的开始时刻
                start = max(minute - session.minutes, 0)
                if item.start < minute:
                    start = max(start, item.start)
                frozen.append(Placement(session, start, minute, item.window))
            else:
                frozen.append(item)
        else:
            waiting.append((session, item.window))
    overflow = [session for session in base.overflow if session.uid in done]
    waiting.extend((session, None) for session in base.overflow if session.uid not in done)
    undone = {session.uid: session for session, _ in waiting}
    queue: list[tuple[Session, Window | None, bool]] = []
    pinned: set[str] = set()
    for window in base.windows:
        for uid in (manual or {}).get(window.start, []):
            if uid in undone and uid not in pinned:
                queue.append((undone[uid], window, True))
                pinned.add(uid)
    queue.extend((session, home, False) for session, home in waiting if session.uid not in pinned)
    busy = [(item.start, item.end) for item in frozen]
    cursors = [max(window.start, at) for window in base.windows]
    placed = list(frozen)
    for session, home, home_first in queue:
        candidates = list(enumerate(base.windows))
        if home_first:
            candidates.sort(key=lambda pair: pair[1] is not home)
        for index, window in candidates:
            if window is not home and session.slot and session.slot != window.tag:
                continue
            start = _first_free(cursors[index], window.end, session.minutes, busy, buffer_minutes)
            if start is not None:
                placed.append(Placement(session, start, start + session.minutes, window))
                cursors[index] = start + session.minutes + buffer_minutes
                break
        else:
            overflow.append(session)
    placed.sort(key=lambda item: (item.start, item.session.priority))
    return DayLayout(day=base.day, windows=base.windows, placed=placed, overflow=overflow, early=base.early)


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


def feasibility(sessions_on: Callable[[date], list[Session]], profile: Profile, start: date, end: date,
                manual_on: Callable[[date], dict[int, list[str]]] | None = None) -> Feasibility:
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
        layout = layout_day(day, sessions, windows, profile.buffer_minutes, manual_on(day) if manual_on else None)
        week.available += layout.available_minutes
        week.required += sum(session.minutes for session in sessions)
        if layout.overflow:
            report.overflow.append((day, layout.overflow))
        report.overlaps.extend((day, a.session, b.session) for a, b in layout.fixed_overlaps())
        day += timedelta(days=1)
    return report
