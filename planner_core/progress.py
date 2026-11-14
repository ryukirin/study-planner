from __future__ import annotations

import os
from datetime import datetime

from .plan_spec import Session
from .storage import load_json, quarantine, write_json_atomic


class ProgressStore:
    """完成记录和专注记录。

    records：键为任务 id（计划id|日期|模板位置），值保存任务快照，只保存已完成的任务。
    focus_log：每次完成的番茄钟专注。
    """

    def __init__(self, path: str) -> None:
        self.path = path
        data, self.warning = load_json(path, lambda: {"version": 1, "records": {}, "focus_log": []})
        records = data.get("records") if isinstance(data, dict) else None
        if not isinstance(records, dict):
            records = {}
            if os.path.exists(path):
                moved = quarantine(path)
                self.warning = f"{path} 结构不对，已改名为 {moved}"
        focus_log = data.get("focus_log", []) if isinstance(data, dict) else []
        self.records: dict[str, dict] = records
        self.focus_log: list[dict] = [item for item in focus_log if isinstance(item, dict)] if isinstance(focus_log, list) else []

    def is_done(self, uid: str) -> bool:
        return uid in self.records

    def set_done(self, session: Session, done: bool, now: datetime | None = None) -> None:
        if done:
            self.records[session.uid] = {
                "plan_id": session.plan_id,
                "plan_name": session.plan_name,
                "date": session.date_str,
                "title": session.title,
                "minutes": session.minutes,
                "uses": session.uses,
                "done_at": (now or datetime.now()).isoformat(timespec="seconds"),
            }
        else:
            self.records.pop(session.uid, None)
        self.save()

    def add_focus(self, minutes: int, task: dict | None, now: datetime | None = None) -> None:
        ended = now or datetime.now()
        self.focus_log.append({
            "date": ended.strftime("%Y-%m-%d"), "ended_at": ended.isoformat(timespec="seconds"), "minutes": minutes,
            "uid": (task or {}).get("uid"), "title": (task or {}).get("title", ""), "plan_id": (task or {}).get("plan_id"),
        })
        self.save()

    def remove_plan(self, plan_id: str) -> int:
        uids = [uid for uid, record in self.records.items() if record.get("plan_id") == plan_id]
        for uid in uids:
            del self.records[uid]
        if uids:
            self.save()
        return len(uids)

    def save(self) -> None:
        write_json_atomic(self.path, {"version": 1, "records": self.records, "focus_log": self.focus_log})

    def for_date(self, date_str: str) -> list[tuple[str, dict]]:
        return [(uid, record) for uid, record in self.records.items() if record.get("date") == date_str]

    def for_plan(self, plan_id: str) -> list[tuple[str, dict]]:
        return [(uid, record) for uid, record in self.records.items() if record.get("plan_id") == plan_id]

    def focus_on(self, date_str: str) -> list[dict]:
        return [item for item in self.focus_log if item.get("date") == date_str]

    def focus_total(self) -> int:
        """所有完成的专注的累计分钟数，用来计算等级。"""
        return sum(item["minutes"] for item in self.focus_log
                   if isinstance(item.get("minutes"), int) and not isinstance(item.get("minutes"), bool) and item["minutes"] > 0)

    def focus_count(self, uid: str) -> int:
        return sum(1 for item in self.focus_log if item.get("uid") == uid)

    def focus_minutes(self, uid: str) -> int:
        return sum(item.get("minutes", 0) for item in self.focus_log if item.get("uid") == uid)

    def done_at(self, uid: str) -> str | None:
        return self.records.get(uid, {}).get("done_at")
