"""日程页的手动调整，保存在 day_order.json。计划文件不记录这些调整。

- days：拖动任务后，那一天各空闲时间段里的任务顺序。
- moves：改期的任务和它的新日期（“排到明天”和“全部重排”）。
- replan：某一天从哪个时刻起按实际进度重排（“完成并重排”）。
- pulls：提前完成一项任务时，同一项重复任务后面各项的前移记录，取消完成时按它移回。

计划重排后任务 id 变了的条目自动失效，对应的任务回到自动排程。
"""
from __future__ import annotations

import os

from .plan_spec import parse_date
from .storage import load_json, quarantine, write_json_atomic
from .timeutil import format_time, parse_time


class DayOrderStore:
    """days：{日期: {时间段开始时间 HH:MM: [任务 id]}}。moves：{任务 id: 日期}。replan：{日期: HH:MM}。"""

    def __init__(self, path: str) -> None:
        self.path = path
        data, self.warning = load_json(path, lambda: {"version": 1, "days": {}})
        raw = data.get("days") if isinstance(data, dict) else None
        if not isinstance(raw, dict):
            raw = {}
            if os.path.exists(path):
                moved = quarantine(path)
                self.warning = f"{path} 结构不对，已改名为 {moved}"
                data = {}
        self.days: dict[str, dict[str, list[str]]] = {}
        for day, windows in raw.items():
            if not isinstance(windows, dict):
                continue
            cleaned = {start: [uid for uid in uids if isinstance(uid, str)]
                       for start, uids in windows.items() if _is_time(start) and isinstance(uids, list)}
            if cleaned:
                self.days[day] = cleaned
        moves = data.get("moves") if isinstance(data, dict) else None
        self.moves: dict[str, str] = {uid: day for uid, day in (moves if isinstance(moves, dict) else {}).items()
                                      if isinstance(uid, str) and _is_date(day)}
        replan = data.get("replan") if isinstance(data, dict) else None
        self.replan: dict[str, str] = {day: at for day, at in (replan if isinstance(replan, dict) else {}).items()
                                       if _is_date(day) and _is_time(at)}
        pulls = data.get("pulls") if isinstance(data, dict) else None
        # {提前完成的任务 id: {前移的任务 id: [前移前的日期, 前移后的日期]}}
        self.pulls: dict[str, dict[str, list[str]]] = {}
        for done_uid, record in (pulls if isinstance(pulls, dict) else {}).items():
            if isinstance(record, dict):
                self.pulls[done_uid] = {uid: list(pair) for uid, pair in record.items()
                                        if isinstance(pair, list) and len(pair) == 2 and all(_is_date(day) for day in pair)}

    # ----- 拖动排序 -----

    def get(self, date_str: str) -> dict[int, list[str]]:
        """返回 {时间段开始的分钟数: [任务 id]}，没有手动排序时为空。"""
        return {parse_time(start): list(uids) for start, uids in self.days.get(date_str, {}).items()}

    def set(self, date_str: str, windows: dict[str, list[str]]) -> None:
        windows = {start: list(uids) for start, uids in windows.items() if uids}
        if windows:
            self.days[date_str] = windows
        else:
            self.days.pop(date_str, None)
        self.save()

    # ----- 重排时刻 -----

    def replan_at(self, date_str: str) -> int | None:
        at = self.replan.get(date_str)
        return parse_time(at) if at else None

    def set_replan(self, date_str: str, minute: int) -> None:
        self.replan[date_str] = format_time(minute)
        self.save()

    # ----- 一天的调整 -----

    def has(self, date_str: str) -> bool:
        return date_str in self.days or date_str in self.replan

    def clear(self, date_str: str) -> bool:
        """删除这一天的手动排序和重排时刻。改期的任务不受影响。"""
        removed = [self.days.pop(date_str, None), self.replan.pop(date_str, None)]
        if all(item is None for item in removed):
            return False
        self.save()
        return True

    # ----- 改期 -----

    def set_move(self, uid: str, date_str: str | None) -> None:
        """date_str 为 None 时取消改期。"""
        if date_str is None:
            if self.moves.pop(uid, None) is None:
                return
        else:
            self.moves[uid] = date_str
        self.save()

    def clear_moves(self) -> int:
        """取消所有改期，返回取消的条数。"""
        count = len(self.moves)
        if count or self.pulls:
            self.moves = {}
            self.pulls = {}
            self.save()
        return count

    def save(self) -> None:
        write_json_atomic(self.path, {"version": 1, "days": self.days, "moves": self.moves, "replan": self.replan, "pulls": self.pulls})


def _is_time(value: object) -> bool:
    try:
        parse_time(value)  # type: ignore[arg-type]
    except ValueError:
        return False
    return True


def _is_date(value: object) -> bool:
    try:
        parse_date(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return True
