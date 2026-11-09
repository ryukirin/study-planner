"""计算到期的提醒。纯函数，由 App 的后台线程定期调用。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any

from .plan_spec import Session
from .scheduler import Placement
from .timeutil import format_time, parse_time

LATE_LIMIT = timedelta(minutes=10)


@dataclass
class Reminder:
    key: str
    at: datetime
    title: str
    message: str
    kind: str  # timed / start / summary


def _describe(session: Session, placement: Placement) -> str:
    parts = [f"{format_time(placement.start)}-{format_time(placement.end)}", session.plan_name]
    if session.location:
        parts.append(session.location)
    return " · ".join(parts)


def _lead(session: Session, default: int) -> int:
    if isinstance(session.remind, int) and not isinstance(session.remind, bool):
        return session.remind
    return default


def due_reminders(ws: Any, settings: dict[str, Any], since: datetime, now: datetime, late_limit: timedelta = LATE_LIMIT) -> list[Reminder]:
    """返回 (since, now] 之间到期的提醒。早于 now - late_limit 的不再补发，已完成的任务不提醒。"""
    if now <= since:
        return []
    config = settings["reminders"]
    lower = max(since, now - late_limit)
    results: list[Reminder] = []

    def due(at: datetime) -> bool:
        return lower < at <= now

    days = sorted({since.date(), now.date(), now.date() + timedelta(days=1)})
    for day in days:
        midnight = datetime.combine(day, time())
        for placement in ws.layout(day).placed:
            session = placement.session
            if session.remind is False or ws.is_done(session.uid):
                continue
            start_at = midnight + timedelta(minutes=placement.start)
            lead = _lead(session, config["timed_lead"]) if session.is_fixed else 0
            if session.is_fixed and config["timed"]:
                at = start_at - timedelta(minutes=lead)
                title = f"{lead} 分钟后：{session.title}" if lead else f"现在开始：{session.title}"
                if due(at):
                    results.append(Reminder(f"timed|{session.uid}", at, title, _describe(session, placement), "timed"))
            covered = session.is_fixed and config["timed"] and lead == 0
            if config["task_start"] and not covered and due(start_at):
                results.append(Reminder(f"start|{session.uid}", start_at, f"现在开始：{session.title}", _describe(session, placement), "start"))
        if config["daily_summary"]:
            at = midnight + timedelta(minutes=parse_time(config["summary_time"]))
            if due(at):
                sessions = ws.sessions_on(day)
                overdue = ws.overdue(day)
                if sessions or overdue:
                    minutes = sum(session.minutes for session in sessions)
                    first = ws.layout(day).placed[:1]
                    message = f"{len(sessions)} 项任务，共 {minutes} 分钟"
                    if first:
                        message += f"，第一项 {format_time(first[0].start)} {first[0].session.title}"
                    if overdue:
                        message += f"。另有 {len(overdue)} 项逾期"
                    results.append(Reminder(f"summary|{day.isoformat()}", at, "今日安排", message, "summary"))
    return sorted(results, key=lambda item: item.at)
