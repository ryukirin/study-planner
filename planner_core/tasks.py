"""临时任务：一次性的小任务，保存在 tasks.json，由 App 或 CLI 添加。"""
from __future__ import annotations

import secrets
from datetime import date, datetime
from typing import Any

from .plan_spec import (MAX_TASK_MINUTES, Expansion, Plan, Session, format_date, parse_date, parse_task_extras)
from .storage import load_json, write_json_atomic
from .timeutil import format_time, parse_time

TASKS_PLAN_ID = "_tasks"
TASKS_PLAN_NAME = "临时任务"
TASKS_COLOR = "#7c7f8c"
TASK_FIELDS = {"title", "date", "time", "minutes", "detail", "location", "links", "remind"}
STORED_FIELDS = TASK_FIELDS | {"id", "created_at"}


class TaskError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("\n".join(errors))


def validate_task(data: Any) -> dict[str, Any]:
    """校验并规范化一条临时任务（不含 id）。"""
    errors: list[str] = []
    if not isinstance(data, dict):
        raise TaskError(["任务必须是对象"])
    for key in data:
        if key not in STORED_FIELDS:
            errors.append(f"未知字段 {key}")
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        errors.append("title：标题不能为空")
    try:
        day = parse_date(data.get("date", ""))
    except (TypeError, ValueError):
        errors.append("date：日期格式应为 YYYY-MM-DD")
        day = None
    minutes = data.get("minutes", 30)
    if not isinstance(minutes, int) or isinstance(minutes, bool) or not 1 <= minutes <= MAX_TASK_MINUTES:
        errors.append(f"minutes：必须是 1 到 {MAX_TASK_MINUTES} 的整数")
    detail = data.get("detail", "")
    if not isinstance(detail, str):
        errors.append("detail：必须是字符串")
    extra = parse_task_extras(data, "任务", errors)
    if errors:
        raise TaskError(errors)
    return {
        "title": title.strip(), "date": format_date(day), "time": format_time(extra["time"]) if extra["time"] is not None else None,
        "minutes": minutes, "detail": detail.strip(), "location": extra["location"], "links": extra["links"], "remind": extra["remind"],
    }


class TaskStore:
    def __init__(self, path: str) -> None:
        self.path = path
        data, self.warning = load_json(path, lambda: {"version": 1, "tasks": []})
        raw = data.get("tasks") if isinstance(data, dict) else None
        self.tasks: list[dict[str, Any]] = []
        self.errors: list[str] = []
        for index, item in enumerate(raw if isinstance(raw, list) else []):
            try:
                task = validate_task({k: v for k, v in item.items() if k not in ("id", "created_at")} if isinstance(item, dict) else item)
            except TaskError as exc:
                self.errors.append(f"tasks[{index}]：" + "，".join(exc.errors))
                continue
            task["id"] = item.get("id") or self._new_id()
            task["created_at"] = item.get("created_at", "")
            self.tasks.append(task)

    @staticmethod
    def _new_id() -> str:
        return datetime.now().strftime("%Y%m%d%H%M%S") + secrets.token_hex(2)

    def save(self) -> None:
        write_json_atomic(self.path, {"version": 1, "tasks": self.tasks})

    def get(self, task_id: str) -> dict[str, Any] | None:
        return next((task for task in self.tasks if task["id"] == task_id), None)

    def add(self, data: dict[str, Any]) -> dict[str, Any]:
        task = validate_task(data)
        task["id"] = self._new_id()
        task["created_at"] = datetime.now().isoformat(timespec="seconds")
        self.tasks.append(task)
        self.save()
        return task

    def update(self, task_id: str, data: dict[str, Any]) -> dict[str, Any]:
        current = self.get(task_id)
        if current is None:
            raise TaskError([f"任务 {task_id} 不存在"])
        task = validate_task(data)
        current.update(task)
        self.save()
        return current

    def delete(self, task_id: str) -> bool:
        before = len(self.tasks)
        self.tasks = [task for task in self.tasks if task["id"] != task_id]
        if len(self.tasks) != before:
            self.save()
            return True
        return False

    def expansion(self) -> Expansion | None:
        """把临时任务包装成一个内置计划的展开结果，和普通计划一起排程。"""
        if not self.tasks:
            return None
        days = [parse_date(task["date"]) for task in self.tasks]
        plan = Plan(
            id=TASKS_PLAN_ID, name=TASKS_PLAN_NAME, goal="", color=TASKS_COLOR, priority=0, start=min(days), end=max(days),
            deadline=None, resources=[], sequences={}, phases=[], events=[], milestones=[],
        )
        by_date: dict[date, list[Session]] = {}
        for task in sorted(self.tasks, key=lambda item: (item["date"], item["time"] or "99:99", item["created_at"])):
            day = parse_date(task["date"])
            sessions = by_date.setdefault(day, [])
            sessions.append(Session(
                uid=f"{TASKS_PLAN_ID}|{task['date']}|{task['id']}", plan_id=TASKS_PLAN_ID, plan_name=TASKS_PLAN_NAME,
                color=TASKS_COLOR, priority=0, day=day, order=len(sessions), title=task["title"], detail=task["detail"],
                minutes=task["minutes"], slot=None, phase="", kind="task",
                fixed_start=parse_time(task["time"]) if task["time"] else None, location=task["location"],
                links=list(task["links"]), remind=task["remind"],
            ))
        return Expansion(plan=plan, by_date=by_date, usage={})
