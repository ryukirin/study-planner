"""日程页的手动调整，保存在 day_order.json。计划文件不记录这些调整。

- days：拖动任务后，那一天各空闲时间段里的任务顺序。
- moves：改期的任务和它的新日期（“排到明天”和“全部重排”）。
- replan：某一天从哪个时刻起按实际进度重排（“完成并重排”）。
- pulls：提前完成一项任务时，同一项重复任务后面各项的前移记录，取消完成时按它移回。
- snapshots：days、moves、pulls 里的计划任务在写入记录时的快照（标题、分钟数和类型）。

计划里的任务按“计划 id + 原定日期 + 模板位置”识别。计划文件修改以后，id 不再出现的任务的记录不起作用。
id 还在、但同一位置换成了标题、分钟数或类型不同的任务时（快照对不上），这个 id 的记录也不起作用，任务回到自动排程。
这个任务再次被拖动或改期时，旧记录被删除，按现在的任务记下快照。没有快照的旧记录照常生效。
临时任务的 id 不会换给别的任务，不记快照。
"""
from __future__ import annotations

import os

from .plan_spec import parse_date
from .storage import load_json, quarantine, write_json_atomic
from .timeutil import format_time, parse_time


class DayOrderStore:
    """days：{日期: {时间段开始时间 HH:MM: [任务 id]}}。moves：{任务 id: 日期}。replan：{日期: HH:MM}。
    snapshots：{任务 id: {"title": 标题, "minutes": 分钟数, "slot": 类型}}。"""

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
        snapshots = data.get("snapshots") if isinstance(data, dict) else None
        self.snapshots: dict[str, dict] = {uid: dict(item) for uid, item in (snapshots if isinstance(snapshots, dict) else {}).items()
                                           if _is_snapshot(item)}

    # ----- 拖动排序 -----

    def get(self, date_str: str) -> dict[int, list[str]]:
        """返回 {时间段开始的分钟数: [任务 id]}，没有手动排序时为空。"""
        return {parse_time(start): list(uids) for start, uids in self.days.get(date_str, {}).items()}

    def set(self, date_str: str, windows: dict[str, list[str]]) -> None:
        """记下这一天各时间段的任务顺序。任务的快照要先用 remember 记下。"""
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

    def clear(self, date_str: str) -> bool:
        """删除这一天的手动排序和重排时刻。改期的任务不受影响。"""
        removed = [self.days.pop(date_str, None), self.replan.pop(date_str, None)]
        if all(item is None for item in removed):
            return False
        self.save()
        return True

    # ----- 改期 -----

    def set_move(self, uid: str, date_str: str | None) -> None:
        """date_str 为 None 时取消改期。任务的快照要先用 remember 记下。"""
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

    # ----- 快照 -----

    def matches(self, uid: str, snapshot: dict | None) -> bool:
        """这个任务的记录是否对当前的任务起作用。没有快照的旧记录和临时任务（snapshot 为 None）都算对得上。"""
        stored = self.snapshots.get(uid)
        return stored is None or snapshot is None or stored == snapshot

    def remember(self, uid: str, snapshot: dict | None) -> None:
        """写入任务的记录之前，记下任务现在的快照。快照和已有的不同时，先删除这个任务原来的记录。不保存。"""
        if snapshot is None:
            return
        if not self.matches(uid, snapshot):
            self._forget(uid)
        self.snapshots[uid] = dict(snapshot)

    def _forget(self, uid: str) -> None:
        self.moves.pop(uid, None)
        for day in list(self.days):
            windows = {start: [item for item in uids if item != uid] for start, uids in self.days[day].items()}
            windows = {start: uids for start, uids in windows.items() if uids}
            if windows:
                self.days[day] = windows
            else:
                del self.days[day]
        self.pulls.pop(uid, None)
        for done_uid in list(self.pulls):
            self.pulls[done_uid].pop(uid, None)
            if not self.pulls[done_uid]:
                del self.pulls[done_uid]

    def save(self) -> None:
        # 只保留还有记录引用的任务的快照
        used = set(self.moves) | set(self.pulls)
        used.update(uid for windows in self.days.values() for uids in windows.values() for uid in uids)
        used.update(uid for record in self.pulls.values() for uid in record)
        self.snapshots = {uid: item for uid, item in self.snapshots.items() if uid in used}
        write_json_atomic(self.path, {"version": 1, "days": self.days, "moves": self.moves, "replan": self.replan,
                                      "pulls": self.pulls, "snapshots": self.snapshots})


def _is_time(value: object) -> bool:
    try:
        parse_time(value)  # type: ignore[arg-type]
    except ValueError:
        return False
    return True


def _is_snapshot(value: object) -> bool:
    return (isinstance(value, dict) and isinstance(value.get("title"), str) and isinstance(value.get("slot"), str)
            and isinstance(value.get("minutes"), int) and not isinstance(value.get("minutes"), bool))


def _is_date(value: object) -> bool:
    try:
        parse_date(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return True
