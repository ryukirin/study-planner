"""把工作区整理成界面需要的 JSON 结构。界面只负责渲染，不做计算。"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .availability import STANDARD_TAGS, TAG_NAMES, Window, format_time
from .scheduler import DayLayout
from .jp_holidays import holidays_between
from .levels import summary as level_summary
from .notes_check import task_spans
from .plan_spec import Session, format_date, parse_date, weekday_cn
from .tasks import TASKS_PLAN_ID
from .workspace import Workspace

OVERDUE_LIMIT = 100
RANGE_LIMIT = 42  # 月视图最多 6 周
UPCOMING_HOLIDAYS = 6


def window_payload(window: Window) -> dict[str, Any]:
    return {"start": format_time(window.start), "end": format_time(window.end), "tag": window.tag,
            "label": window.label, "minutes": window.minutes}


def session_payload(ws: Workspace, session: Session, start: int | None = None, end: int | None = None,
                    window: Window | None = None, unplaced: bool = False, early: bool = False) -> dict[str, Any]:
    """window 是任务所在的空闲时间段，unplaced 表示当天没排进空闲时间，early 表示在这一天之前就完成了。"""
    return {
        "uid": session.uid, "plan_id": session.plan_id, "plan_name": session.plan_name, "color": session.color,
        "title": session.title, "detail": session.detail, "minutes": session.minutes, "slot": session.slot,
        "phase": session.phase, "kind": session.kind, "date": session.date_str, "weekday": weekday_cn(session.day),
        "done": ws.is_done(session.uid), "done_at": ws.progress.done_at(session.uid), "uses": session.uses,
        "start": format_time(start) if start is not None else None,
        "end": format_time(end) if end is not None else None,
        "window": window_payload(window) if window is not None else None, "unplaced": unplaced, "early": early,
        "moved_from": format_date(session.moved_from) if session.moved_from else None,
        "moved_from_weekday": weekday_cn(session.moved_from) if session.moved_from else None,
        "fixed": session.is_fixed, "location": session.location, "links": session.links,
        "remind": session.remind, "focus_count": ws.progress.focus_count(session.uid),
        "focus_minutes": ws.progress.focus_minutes(session.uid),
        "is_task": session.plan_id == TASKS_PLAN_ID,
        "task_id": session.uid.split("|")[-1] if session.plan_id == TASKS_PLAN_ID else None,
    }


def banner_messages(ws: Workspace) -> list[dict[str, str]]:
    messages = [{"level": "error", "text": warning} for warning in ws.warnings]
    if ws.profile_errors:
        messages.append({"level": "error", "text": "空闲时间文件有错误，当前按默认时间段排程。详情见“空闲时间”页。", "view": "profile"})
    elif ws.profile_is_default:
        messages.append({"level": "info", "text": "还没有设置空闲时间，当前按默认时间段排程。", "view": "profile"})
    if ws.plan_errors:
        messages.append({"level": "error", "text": f"{len(ws.plan_errors)} 个计划文件读取失败。详情见“计划”页。", "view": "plans"})
    return messages


def milestone_payload(item: Any) -> dict[str, Any]:
    return {"date": format_date(item.day), "text": item.text, "note": item.note,
            "moved_from": format_date(item.moved_from) if item.moved_from else None,
            "done": item.done, "follows": item.follows}


def milestones_payload(ws: Workspace, day: date, today: date | None) -> list[dict[str, Any]]:
    return [{"plan_name": plan.name, "color": ws.color_of(plan.id), **milestone_payload(item)}
            for plan, item in ws.milestones_on(day, today or date.today())]


def actual_spans(plan: Any, sessions: list[Session], planned: list[tuple[date, date]]) -> list[tuple[date, date]]:
    """每个阶段的任务现在的起止日期，改期的任务按改期后的日期算。阶段内没有任务时用 planned 里的值。"""
    spans = []
    for phase, fallback in zip(plan.phases, planned):
        days = [session.day for session in sessions if phase.start <= (session.moved_from or session.day) <= phase.end]
        spans.append((min(days), max(days)) if days else fallback)
    return spans


def window_name(window: Window) -> str:
    return window.label or TAG_NAMES.get(window.tag, window.tag)


def overflow_reason(layout: DayLayout, session: Session, at: int | None) -> str:
    """任务没排进空闲时间的原因。at 是这一天的重排时刻，没有重排时为 None。"""
    windows = [window for window in layout.windows if not session.slot or window.tag == session.slot]
    if not windows:
        tag = TAG_NAMES.get(session.slot or "", session.slot or "")
        return f"这一天没有“{tag}”类型的空闲时间段" if session.slot else "这一天没有空闲时间段"
    if at is not None and all(window.end - max(window.start, at) < session.minutes for window in windows):
        names = "、".join(f"{window_name(window)} {format_time(window.start)}–{format_time(window.end)}" for window in windows)
        return f"{format_time(at)} 起重排时，{names} 剩下的时间不够 {session.minutes} 分钟"
    return f"可以放的时间段里剩下的时间不够 {session.minutes} 分钟"


def day_payload(ws: Workspace, day: date, today: date | None = None) -> dict[str, Any]:
    layout = ws.layout(day)
    at = ws.day_order.replan_at(format_date(day))
    groups = []
    for window in layout.windows:
        items = [item for item in layout.placed if item.window is window]
        groups.append({
            "window": window_payload(window),
            "tasks": [session_payload(ws, item.session, item.start, item.end, window) for item in items],
            "free": window.end - (items[-1].end if items else window.start),
            # 重排时已经过去的时间段，不再放没做的任务
            "passed": at is not None and window.end <= at,
        })
    sessions = ws.sessions_on(day)
    uids = {session.uid for session in sessions}
    history = [
        {"plan_name": record.get("plan_name") or record.get("plan_id", ""), "title": record.get("title", ""), "minutes": record.get("minutes", 0)}
        for uid, record in ws.progress.for_date(format_date(day)) if uid not in uids
    ]
    exception_note = ws.profile.exception_notes.get(day, "") if day in ws.profile.exceptions else None
    return {
        "date": format_date(day),
        "weekday": weekday_cn(day),
        "is_exception": day in ws.profile.exceptions,
        "exception_note": exception_note,
        "holiday": ws.profile.holiday_name(day),
        "holiday_windows": ws.profile.uses_holiday_windows(day),
        "manual_order": ws.day_order.has(format_date(day)),
        "groups": groups,
        "fixed": [session_payload(ws, item.session, item.start, item.end) for item in layout.fixed],
        "overflow": [{**session_payload(ws, session, unplaced=True),
                      "reason": None if ws.is_done(session.uid) else overflow_reason(layout, session, at)}
                     for session in layout.overflow],
        "early": [session_payload(ws, session, early=True) for session in layout.early],
        "replan_at": format_time(at) if at is not None else None,
        "milestones": milestones_payload(ws, day, today),
        "history": history,
        "total": len(sessions),
        "done": sum(1 for session in sessions if ws.is_done(session.uid)),
        "minutes": sum(session.minutes for session in sessions),
        "done_minutes": sum(session.minutes for session in sessions if ws.is_done(session.uid)),
        "focus_count": len(ws.progress.focus_on(format_date(day))),
        "focus_minutes": sum(item.get("minutes", 0) for item in ws.progress.focus_on(format_date(day))),
    }


def day_brief(ws: Workspace, day: date, today: date | None = None) -> dict[str, Any]:
    """周视图和月视图里的一天：提前完成的任务在最前，其余按开始时间排列，没排进空闲时间的排在最后。"""
    layout = ws.layout(day)
    tasks = [session_payload(ws, session, early=True) for session in layout.early]
    tasks += [session_payload(ws, item.session, item.start, item.end, item.window) for item in layout.placed]
    tasks += [session_payload(ws, session, unplaced=True) for session in layout.overflow]
    return {
        "date": format_date(day), "weekday": weekday_cn(day), "holiday": ws.profile.holiday_name(day),
        "is_exception": day in ws.profile.exceptions, "tasks": tasks,
        "milestones": milestones_payload(ws, day, today),
        "total": len(tasks), "done": sum(1 for task in tasks if task["done"]),
        "minutes": sum(task["minutes"] for task in tasks),
        "done_minutes": sum(task["minutes"] for task in tasks if task["done"]),
    }


def range_payload(ws: Workspace, start: date, days: int, today: date | None = None) -> list[dict[str, Any]]:
    """从 start 起连续 days 天，最多 RANGE_LIMIT 天。"""
    return [day_brief(ws, start + timedelta(days=offset), today) for offset in range(max(0, min(days, RANGE_LIMIT)))]


def calendar_marks(ws: Workspace, today: date) -> dict[str, str]:
    """每天的状态：done 全部完成，overdue 过去且有未完成，todo 有任务。"""
    marks: dict[str, str] = {}
    days = {day for expansion in ws.iter_expansions() for day in expansion.by_date}
    for day in days:
        sessions = ws.sessions_on(day)
        if all(ws.is_done(session.uid) for session in sessions):
            marks[format_date(day)] = "done"
        elif day < today:
            marks[format_date(day)] = "overdue"
        else:
            marks[format_date(day)] = "todo"
    return marks


def events_payload(ws: Workspace, plan: Any) -> list[dict[str, Any]]:
    """计划里的单次任务。任务 id 中的 e 序号按当天顺序编号，和 expand_plan 一致。"""
    result = []
    per_day: dict[date, int] = {}
    for event in plan.events:
        index = per_day.get(event.day, 0)
        per_day[event.day] = index + 1
        uid = f"{plan.id}|{format_date(event.day)}|e{index}"
        session = ws.session_by_uid(uid)
        day = session.day if session else event.day
        result.append({
            "date": format_date(day), "time": format_time(event.task.time) if event.task.time is not None else None,
            "title": event.task.title, "location": event.task.location,
            "moved_from": format_date(event.day) if day != event.day else None,
            "done": ws.is_done(uid),
        })
    return sorted(result, key=lambda item: (item["date"], item["time"] or ""))


def plans_payload(ws: Workspace, today: date) -> list[dict[str, Any]]:
    result = []
    for plan in ws.plans:
        status = ws.plan_status(plan, today)
        sessions = ws.expansions[plan.id].all_sessions()
        spans = actual_spans(plan, sessions, task_spans(plan, ws.expansions[plan.id]))
        undone = [session.day for session in sessions if not ws.is_done(session.uid)]
        result.append({
            "id": plan.id, "name": plan.name, "goal": plan.goal, "category": plan.category,
            "color": ws.color_of(plan.id), "priority": plan.priority,
            "state": status.state, "file": plan.source_path,
            "start": format_date(plan.start), "end": format_date(plan.end),
            "deadline": format_date(plan.deadline) if plan.deadline else None,
            "days_total": (plan.end - plan.start).days + 1,
            "days_elapsed": min(max((today - plan.start).days, 0), (plan.end - plan.start).days + 1),
            "current_phase": status.current_phase.name if status.current_phase else None,
            "percent": round(status.percent, 1),
            "done_sessions": status.done_sessions, "total_sessions": status.total_sessions,
            "done_minutes": status.done_minutes, "total_minutes": status.total_minutes,
            "overdue_count": len(status.overdue), "overdue_minutes": status.overdue_minutes, "extra_days": status.extra_days,
            "history_records": status.history_records,
            "moved_count": sum(1 for session in sessions if session.moved_from is not None),
            "last_task": format_date(max(undone)) if undone else None,
            "phases": [
                {"name": phase.name, "goal": phase.goal, "focus": phase.focus, "start": format_date(phase.start),
                 "end": format_date(phase.end), "days": (phase.end - phase.start).days + 1,
                 "task_start": format_date(span[0]), "task_end": format_date(span[1]),
                 "current": phase.start <= today <= phase.end, "past": phase.end < today}
                for phase, span in zip(plan.phases, spans)
            ],
            "milestones": [{**milestone_payload(item), "past": item.done or (not item.follows and item.day < today)}
                           for item in ws.plan_milestones(plan, today)],
            "sequences": [
                {"name": seq.name, "title": plan.sequences[seq.name].title or seq.name, "total": seq.total,
                 "done": len(seq.done_items), "next": seq.remaining_items[:3]}
                for seq in status.sequences
            ],
            "resources": plan.resources,
            "events": events_payload(ws, plan),
            "notes": plan.notes,
        })
    return result


def profile_payload(ws: Workspace, today: date) -> dict[str, Any]:
    data = ws.profile.to_dict()
    data.setdefault("holiday", None)
    upcoming = holidays_between(today, today + timedelta(days=365))[:UPCOMING_HOLIDAYS]
    data.update({
        "path": ws.profile_path, "is_default": ws.profile_is_default, "errors": ws.profile_errors,
        "standard_tags": [{"tag": tag, "name": TAG_NAMES[tag]} for tag in STANDARD_TAGS],
        "upcoming_holidays": [{"date": format_date(day), "weekday": weekday_cn(day), "name": name} for day, name in upcoming],
    })
    return data


def build_state(ws: Workspace, selected: date, today: date) -> dict[str, Any]:
    overdue = ws.overdue(today)
    active = [plan for plan in ws.plans if plan.start <= today <= plan.end]
    return {
        "today": format_date(today),
        "selected": format_date(selected),
        "home": ws.home,
        "plans_dir": ws.plans_dir,
        "banner": banner_messages(ws),
        "day": day_payload(ws, selected, today),
        "overdue": [session_payload(ws, session) for session in overdue[:OVERDUE_LIMIT]],
        "overdue_total": len(overdue),
        "overdue_minutes": sum(session.minutes for session in overdue),
        "moved_total": ws.moved_count(),
        "active_plans": len(active),
        "calendar": calendar_marks(ws, today),
        "plans": plans_payload(ws, today),
        "plan_errors": [{"file": item.path, "errors": item.errors} for item in ws.plan_errors],
        "profile": profile_payload(ws, today),
        "archived": ws.archived(),
        "settings": ws.settings,
        "level": level_summary(ws.progress.focus_total(), ws.settings["levels"]),
    }


def find_session(ws: Workspace, uid: str) -> Session | None:
    return ws.session_by_uid(uid) if isinstance(uid, str) else None
