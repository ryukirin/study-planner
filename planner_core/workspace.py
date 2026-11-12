from __future__ import annotations

import math
import os
import re
import shutil
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from typing import Any, Iterator

from . import paths
from .availability import Profile, load_profile, save_profile
from .day_order import DayOrderStore
from .plan_spec import DEFAULT_COLORS, Expansion, Milestone, Phase, Plan, PlanError, Session, expand_plan, format_date, load_plan_file
from .notes_check import phase_table_issues
from .progress import ProgressStore
from .scheduler import DayLayout, Feasibility, feasibility, layout_day, replan_day
from .settings import load_settings, save_settings
from .tasks import TASK_FIELDS, TASKS_PLAN_ID, TaskStore
from .timeutil import format_time


REPLAN_EXTRA_DAYS = 28  # 全部重排时，最后一个任务之后还可以往后排的天数


@dataclass
class PlanFileError:
    path: str
    errors: list[str]


@dataclass
class SequenceStatus:
    name: str
    total: int
    done_items: list[str]
    remaining_items: list[str]
    scheduled: int
    skipped: int
    exhausted_on: date | None


@dataclass
class PlanStatus:
    plan: Plan
    state: str
    current_phase: Phase | None
    total_sessions: int
    done_sessions: int
    total_minutes: int
    done_minutes: int
    overdue: list[Session]
    overdue_minutes: int
    extra_days: int
    upcoming_milestones: list[Milestone]
    sequences: list[SequenceStatus]
    history_records: int

    @property
    def percent(self) -> float:
        return self.done_sessions / self.total_sessions * 100 if self.total_sessions else 0.0


class WorkspaceError(ValueError):
    pass


class Workspace:
    """一次性读取数据目录里的空闲时间、计划、临时任务、设置和完成记录，供 App 和 CLI 使用。"""

    def __init__(self, home: str | None = None) -> None:
        self.home = os.path.abspath(home) if home else paths.data_home()
        self.reload()

    @property
    def plans_dir(self) -> str:
        return paths.plans_dir(self.home)

    @property
    def archive_dir(self) -> str:
        return paths.archive_dir(self.home)

    @property
    def profile_path(self) -> str:
        return paths.profile_path(self.home)

    @property
    def progress_path(self) -> str:
        return paths.progress_path(self.home)

    @property
    def tasks_path(self) -> str:
        return paths.tasks_path(self.home)

    @property
    def settings_path(self) -> str:
        return paths.settings_path(self.home)

    @property
    def day_order_path(self) -> str:
        return paths.day_order_path(self.home)

    # ---------- 读取 ----------

    def reload(self) -> None:
        paths.ensure_home(self.home)
        self.warnings: list[str] = []
        loaded = load_profile(self.profile_path)
        self.profile: Profile = loaded.profile
        self.profile_is_default = loaded.is_default
        self.profile_errors = loaded.errors
        if loaded.warning:
            self.warnings.append(loaded.warning)
        self.progress = ProgressStore(self.progress_path)
        if self.progress.warning:
            self.warnings.append(self.progress.warning)
        self.tasks = TaskStore(self.tasks_path)
        if self.tasks.warning:
            self.warnings.append(self.tasks.warning)
        self.warnings.extend(f"tasks.json {error}" for error in self.tasks.errors)
        self.day_order = DayOrderStore(self.day_order_path)
        if self.day_order.warning:
            self.warnings.append(self.day_order.warning)
        self.settings, problems = load_settings(self.settings_path)
        self.warnings.extend(problems)
        self.plans: list[Plan] = []
        self.plan_errors: list[PlanFileError] = []
        for name in sorted(os.listdir(self.plans_dir)):
            path = os.path.join(self.plans_dir, name)
            if not name.lower().endswith(".md") or not os.path.isfile(path):
                continue
            try:
                plan = load_plan_file(path)
            except PlanError as exc:
                self.plan_errors.append(PlanFileError(path, exc.errors))
                continue
            except (OSError, UnicodeDecodeError) as exc:
                self.plan_errors.append(PlanFileError(path, [f"读取失败：{exc}"]))
                continue
            if plan.id == TASKS_PLAN_ID:
                self.plan_errors.append(PlanFileError(path, [f"id {TASKS_PLAN_ID} 是临时任务专用的，请换一个 id"]))
                continue
            duplicate = self.plan_by_id(plan.id)
            if duplicate:
                self.plan_errors.append(PlanFileError(path, [f"id {plan.id} 和 {duplicate.source_path} 重复，这个文件被忽略"]))
                continue
            self.plans.append(plan)
        self._expand_all()

    def _expand_all(self) -> None:
        self.plans.sort(key=lambda plan: (plan.priority, plan.id))
        self.expansions: dict[str, Expansion] = {}
        for index, plan in enumerate(self.plans):
            self.expansions[plan.id] = expand_plan(plan, DEFAULT_COLORS[index % len(DEFAULT_COLORS)])
        self.task_expansion = self.tasks.expansion()
        self._apply_moves()
        self._layout_cache: dict[date, DayLayout] = {}
        self._milestone_cache: dict[str, tuple[int, list[Milestone]]] = {}

    def _apply_moves(self) -> None:
        """把改期的任务从原定日期挪到新日期。任务 id 不变，完成记录跟着任务走。"""
        self._sessions: dict[str, Session] = {
            session.uid: session for expansion in self.iter_expansions() for session in expansion.all_sessions()}
        for uid, target_text in self.day_order.moves.items():
            session = self._sessions.get(uid)
            if session is None or session.plan_id == TASKS_PLAN_ID:
                continue
            target = date.fromisoformat(target_text)
            if target == session.day:
                continue
            by_date = self.expansions[session.plan_id].by_date
            by_date[session.day].remove(session)
            if not by_date[session.day]:
                del by_date[session.day]
            siblings = by_date.setdefault(target, [])
            session.moved_from, session.day = session.day, target
            siblings.append(session)

    def session_by_uid(self, uid: str) -> Session | None:
        return self._sessions.get(uid)

    def iter_expansions(self) -> Iterator[Expansion]:
        if self.task_expansion:
            yield self.task_expansion
        yield from (self.expansions[plan.id] for plan in self.plans)

    def use_draft(self, plan: Plan) -> bool:
        """把草稿计划加入工作区（同 id 时替换），返回是否替换了已有计划。"""
        replaced = self.plan_by_id(plan.id) is not None
        self.plans = [item for item in self.plans if item.id != plan.id] + [plan]
        self._expand_all()
        return replaced

    def fingerprint(self) -> tuple:
        """计划文件夹、profile、临时任务和手动排序的修改时间，用于检测外部改动。"""
        entries = []
        candidates = [self.profile_path, self.tasks_path, self.day_order_path] + [os.path.join(self.plans_dir, name) for name in sorted(os.listdir(self.plans_dir))]
        for path in candidates:
            try:
                stat = os.stat(path)
                entries.append((path, stat.st_mtime_ns, stat.st_size))
            except OSError:
                entries.append((path, None, None))
        return tuple(entries)

    # ---------- 查询 ----------

    def plan_by_id(self, plan_id: str) -> Plan | None:
        return next((plan for plan in self.plans if plan.id == plan_id), None)

    def color_of(self, plan_id: str) -> str:
        expansion = self.expansions.get(plan_id)
        if expansion and expansion.plan.color:
            return expansion.plan.color
        index = next((i for i, plan in enumerate(self.plans) if plan.id == plan_id), 0)
        return DEFAULT_COLORS[index % len(DEFAULT_COLORS)]

    def sessions_on(self, day: date) -> list[Session]:
        sessions: list[Session] = []
        for expansion in self.iter_expansions():
            sessions.extend(expansion.by_date.get(day, []))
        return sessions

    def milestones_on(self, day: date, today: date) -> list[tuple[Plan, Milestone]]:
        return [(plan, item) for plan in self.plans for item in self.plan_milestones(plan, today) if item.day == day]

    def plan_milestones(self, plan: Plan, today: date) -> list[Milestone]:
        """计划的里程碑，日期按它跟随的任务推算。

        跟随的任务：计划里按周重复、原定日期不晚于里程碑的任务中，和里程碑相关的那些。
        里程碑写了 tasks 时，任务模板的标题包含其中一个词或使用其中一个序列就相关。
        没写时，任务模板标题的开头（第一个花括号或冒号之前）出现在里程碑的 text 里，或任务使用的序列标题出现在 text 里就相关。
        一个相关的任务也没有时，跟随全部按周重复的任务。

        每项任务的完成日期：已完成的按完成的那天，没完成的按现在排的日期，逾期的按今天。
        - 全部完成：里程碑已达成，日期是最后一项完成的那天。
        - 没有全部完成：里程碑和最后一项原定的任务保持原来的间隔，日期 = 原定日期 + (最晚的完成日期 - 最后一项任务原定的日期)。
        没有任务可以跟随时，里程碑不动。"""
        key = (len(self.progress.records), today)
        cached = self._milestone_cache.get(plan.id)
        if cached and cached[0] == key:
            return cached[1]
        sessions = [session for session in self.expansions[plan.id].all_sessions() if session.kind == "task"]
        result = []
        for item in plan.milestones:
            before = [session for session in sessions if (session.moved_from or session.day) <= item.day]
            related, follows = self._milestone_tasks(plan, item, before)
            if not related:
                result.append(item)
                continue
            finishes = []
            for session in related:
                if self.progress.is_done(session.uid):
                    moment = self._done_moment(session.uid)
                    finishes.append(moment.date() if moment else session.day)
                else:
                    finishes.append(max(session.day, today))
            done = all(self.progress.is_done(session.uid) for session in related)
            last = max(finishes)
            day = last if done else item.day + (last - max(session.moved_from or session.day for session in related))
            result.append(Milestone(day=day, text=item.text, note=item.note, tasks=item.tasks,
                                    moved_from=item.day if day != item.day else None, done=done, follows=follows))
        result.sort(key=lambda item: item.day)
        self._milestone_cache[plan.id] = (key, result)
        return result

    @staticmethod
    def _milestone_tasks(plan: Plan, milestone: Milestone, sessions: list[Session]) -> tuple[list[Session], list[str]]:
        """和里程碑相关的任务，以及用来判断的关键词。没有相关的任务时返回全部任务和空的关键词。"""
        related: list[Session] = []
        follows: list[str] = []
        for session in sessions:
            planned = session.moved_from or session.day
            phase = plan.phase_for(planned)
            slot = re.fullmatch(r"([a-z]+)(\d+)", session.uid.split("|")[-1])
            if phase is None or slot is None or slot.group(1) not in phase.week:
                continue
            templates = phase.week[slot.group(1)]
            if int(slot.group(2)) >= len(templates):
                continue
            template = templates[int(slot.group(2))]
            sequence = plan.sequences.get(template.uses) if template.uses else None
            if milestone.tasks:
                hits = [word for word in milestone.tasks
                        if word in template.title or word == template.uses or (sequence and word == sequence.title)]
            else:
                head = re.split(r"[{：:（(，,]", template.title)[0].strip()
                hits = [word for word in (head, sequence.title if sequence else "") if len(word) >= 2 and word in milestone.text]
            if hits:
                related.append(session)
                follows.extend(word for word in hits if word not in follows)
        if related:
            return related, follows
        return sessions, []

    def layout(self, day: date) -> DayLayout:
        if day not in self._layout_cache:
            self._layout_cache[day] = self._compute_layout(day, self.manual_order(day))
        return self._layout_cache[day]

    def _compute_layout(self, day: date, manual: dict[int, list[str]]) -> DayLayout:
        """按手动排序排一天。这一天设了重排时刻时，再从那个时刻起重排还没做的任务。"""
        return self._arrange(day, self.sessions_on(day), manual, self.day_order.replan_at(format_date(day)))

    def _arrange(self, day: date, sessions: list[Session], manual: dict[int, list[str]], at: int | None) -> DayLayout:
        """排一天的任务。在这一天之前就完成的任务不占时间，其余任务按空出的时间排。at 是重排时刻。"""
        done_at = {session.uid: self._done_moment(session.uid) for session in sessions if self.progress.is_done(session.uid)}
        early = [session for session in sessions if done_at.get(session.uid) and done_at[session.uid].date() < day]
        skipped = {session.uid for session in early}
        rest = [session for session in sessions if session.uid not in skipped]
        layout = layout_day(day, rest, self.profile.windows_for(day), self.profile.buffer_minutes, manual)
        if at is not None:
            done = {uid: moment.hour * 60 + moment.minute if moment and moment.date() == day else None
                    for uid, moment in done_at.items() if uid not in skipped}
            layout = replan_day(layout, at, self.profile.buffer_minutes, done, manual)
        layout.early = early
        return layout

    def _done_moment(self, uid: str) -> datetime | None:
        """任务的完成时刻。旧版本的完成记录没有时刻，返回 None。"""
        try:
            return datetime.fromisoformat(self.progress.done_at(uid) or "")
        except ValueError:
            return None

    def manual_order(self, day: date) -> dict[int, list[str]]:
        """这一天的手动排序：{时间段开始的分钟数: [任务 id]}，没有时为空。"""
        return self.day_order.get(format_date(day))

    def date_range(self) -> tuple[date, date] | None:
        expansions = list(self.iter_expansions())
        if not expansions:
            return None
        return min(item.plan.start for item in expansions), max(item.plan.end for item in expansions)

    def is_done(self, uid: str) -> bool:
        return self.progress.is_done(uid)

    def set_done(self, session: Session, done: bool, now: datetime | None = None) -> int:
        """标记或取消完成。返回跟着改了日期的任务数。

        提前完成（完成的日期早于任务的日期）按周重复的任务时，同一项重复任务后面没做的各项依次前移一格：
        下一项移到这一天，再下一项移到下一项原来的日期。取消完成时按记录移回。"""
        self.progress.set_done(session, done, now)
        self._layout_cache.pop(session.day, None)  # 重排过的日子，排程跟完成情况有关
        self._milestone_cache = {}
        if done:
            return self._pull_followers(session, (now or datetime.now()).date())
        return self._undo_pull(session)

    def _is_weekly(self, session: Session) -> bool:
        """计划里按周重复、没有固定开始时间的任务。只有这类任务会被自动改期。"""
        return session.plan_id != TASKS_PLAN_ID and session.kind == "task" and not session.is_fixed

    @staticmethod
    def _series(session: Session) -> tuple[str, str, str]:
        """同一项重复任务：同一个计划、同一个阶段、周模板里的同一个位置。"""
        return session.plan_id, session.phase, session.uid.split("|")[-1]

    def _pull_followers(self, session: Session, today: date) -> int:
        if session.day <= today or not self._is_weekly(session):
            return 0
        key = self._series(session)
        followers = sorted(
            (item for item in self._sessions.values()
             if item.day > session.day and self._is_weekly(item) and self._series(item) == key and not self.progress.is_done(item.uid)),
            key=lambda item: (item.day, item.moved_from or item.day, item.order))
        if not followers:
            return 0
        targets = [session.day] + [item.day for item in followers[:-1]]
        record: dict[str, list[str]] = {}
        for item, target in zip(followers, targets):
            record[item.uid] = [format_date(item.day), format_date(target)]
            self._set_move(item, target)
        self.day_order.pulls[session.uid] = record
        self.day_order.save()
        self._expand_all()
        return len(followers)

    def _undo_pull(self, session: Session) -> int:
        record = self.day_order.pulls.pop(session.uid, None)
        if record is None:
            return 0
        count = 0
        for uid, (previous, moved_to) in record.items():
            item = self._sessions.get(uid)
            # 前移之后又被改过日期或已经完成的任务不动
            if item is None or format_date(item.day) != moved_to or self.progress.is_done(uid):
                continue
            self._set_move(item, date.fromisoformat(previous))
            count += 1
        self.day_order.save()
        self._expand_all()
        return count

    def _set_move(self, session: Session, target: date) -> None:
        """在 day_order 里记下任务的新日期，不保存、不重新展开。target 等于原定日期时取消改期。"""
        if target == (session.moved_from or session.day):
            self.day_order.moves.pop(session.uid, None)
        else:
            self.day_order.moves[session.uid] = format_date(target)

    def overdue(self, today: date) -> list[Session]:
        items = []
        for expansion in self.iter_expansions():
            for day, sessions in expansion.by_date.items():
                if day < today:
                    items.extend(session for session in sessions if not self.progress.is_done(session.uid))
        return sorted(items, key=lambda session: (session.day, session.priority, session.plan_id, session.order))

    # ---------- 修改：空闲时间、设置、临时任务 ----------

    def save_profile(self, profile: Profile) -> None:
        save_profile(self.profile_path, profile)
        self.profile = profile
        self.profile_is_default = False
        self.profile_errors = []
        self._layout_cache = {}

    def save_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        self.settings = save_settings(self.settings_path, data)
        return self.settings

    def add_task(self, data: dict[str, Any]) -> dict[str, Any]:
        task = self.tasks.add(data)
        self._expand_all()
        return task

    def update_task(self, task_id: str, data: dict[str, Any]) -> dict[str, Any]:
        old = self.tasks.get(task_id)
        old_uid = f"{TASKS_PLAN_ID}|{old['date']}|{task_id}" if old else None
        task = self.tasks.update(task_id, data)
        new_uid = f"{TASKS_PLAN_ID}|{task['date']}|{task_id}"
        if old_uid and old_uid != new_uid and old_uid in self.progress.records:
            # 改了日期时，完成状态跟着任务走
            record = self.progress.records.pop(old_uid)
            record["date"] = task["date"]
            self.progress.records[new_uid] = record
            self.progress.save()
        self._expand_all()
        return task

    def delete_task(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        deleted = self.tasks.delete(task_id)
        if deleted and task:
            self.progress.records.pop(f"{TASKS_PLAN_ID}|{task['date']}|{task_id}", None)
            self.progress.save()
        self._expand_all()
        return deleted

    # ---------- 修改：手动排序 ----------

    def move_session(self, session: Session, window_start: int, index: int) -> bool:
        """把任务放到当天某个空闲时间段的第 index 个位置（只数非定时任务），并记下这一天各时间段的任务顺序。

        返回排程是否有变化。目标时间段放不下，或会把别的任务挤出原来的时间段时抛出 WorkspaceError，不保存。"""
        if session.is_fixed:
            raise WorkspaceError("定时任务的开始时间是固定的，不能拖动")
        day = session.day
        before = self.layout(day)
        target = next((window for window in before.windows if window.start == window_start), None)
        if target is None:
            raise WorkspaceError("找不到这个时间段，空闲时间可能刚被修改，请刷新后再试")
        order = {window.start: [item.session.uid for item in before.placed if item.window is window and item.session.uid != session.uid]
                 for window in before.windows}
        uids = order[target.start]
        uids.insert(max(0, min(index, len(uids))), session.uid)
        after = self._compute_layout(day, order)
        where = {item.session.uid: item for item in after.placed}
        name = f"{format_time(target.start)}–{format_time(target.end)} 的时间段"
        if session.uid not in where or where[session.uid].window is None or where[session.uid].window.start != target.start:
            raise WorkspaceError(f"{name}放不下这个任务（{session.minutes} 分钟）")
        for item in before.placed:
            if item.window is None or item.session.uid == session.uid:
                continue
            moved = where.get(item.session.uid)
            if moved is None or moved.window is None or moved.window.start != item.window.start:
                raise WorkspaceError(f"{name}放不下，“{item.session.title}”会被挤出去")
        if [(item.session.uid, item.start) for item in after.placed] == [(item.session.uid, item.start) for item in before.placed]:
            return False
        self.day_order.set(format_date(day), {format_time(start): uids for start, uids in order.items()})
        self._layout_cache.pop(day, None)
        return True

    def set_replan(self, day: date, minute: int) -> None:
        """这一天还没做的任务从 minute 时刻起重排。"""
        self.day_order.set_replan(format_date(day), minute)
        self._layout_cache.pop(day, None)

    def move_session_to_day(self, session: Session, target: date) -> Session:
        """把任务改到 target 那天，返回改期后的任务。计划里的任务记在 day_order.json，临时任务直接改日期。

        target 等于原定日期时取消改期。"""
        if session.plan_id == TASKS_PLAN_ID:
            task_id = session.uid.split("|")[-1]
            current = self.tasks.get(task_id)
            if current is None:
                raise WorkspaceError("找不到这个临时任务")
            data = {key: current[key] for key in TASK_FIELDS if key in current and current[key] is not None}
            data["date"] = format_date(target)
            self.update_task(task_id, data)
            return self._sessions[f"{TASKS_PLAN_ID}|{format_date(target)}|{task_id}"]
        origin = session.moved_from or session.day
        self.day_order.set_move(session.uid, None if target == origin else format_date(target))
        self._expand_all()
        return self._sessions[session.uid]

    def replan_all(self, today: date, minute: int, pull: bool) -> dict[str, int]:
        """从 today 的 minute 时刻起，重新安排所有没做的任务的日期。结果记在 day_order.json，计划文件不变。

        参与的是计划里按周重复的任务。定时任务、单次任务和临时任务留在原来的日期，照常占用时间。
        任务按原定日期、计划优先级、当天顺序排队，每个任务放到最早放得下的一天：
        - pull 为 True 时可以提前，最早到今天，且不早于所在阶段的开始日期。
        - pull 为 False 时只往后排，不早于任务现在的日期。
        - 同一个内容序列、同一个周模板位置的任务保持先后顺序。同一天里，同一计划的任务按原定日期排。
        - 放得下的标准和当天排程一致：任务排进了时间段，且没有把别的任务挤到未排入。
        - 找不到放得下的日期时留在原定日期。

        返回 moved（日期有变化的任务数）、beyond（排到计划结束日期之后的任务数）、unplaced（找不到日期的任务数）。"""
        def movable(session: Session) -> bool:
            return (session.plan_id != TASKS_PLAN_ID and session.kind == "task" and not session.is_fixed
                    and not self.progress.is_done(session.uid))

        current = {session.uid: session.day for session in self._sessions.values() if movable(session)}
        old_moves = dict(self.day_order.moves)
        try:
            # 先让参与的任务回到原定日期，拿到原来的当天顺序，再从这个状态开始安排
            for uid in current:
                self.day_order.moves.pop(uid, None)
            self._expand_all()
            queue = sorted((self._sessions[uid] for uid in current),
                           key=lambda session: (session.day, session.priority, session.plan_id, session.order))
            last_day = max((session.day for session in self._sessions.values()), default=today)
            horizon = max(last_day, today) + timedelta(days=REPLAN_EXTRA_DAYS)
            pool: dict[date, list[Session]] = {}
            over: dict[date, set[str]] = {}

            def arrange(day: date, sessions: list[Session]) -> DayLayout:
                at = minute if day == today else self.day_order.replan_at(format_date(day))
                return self._arrange(day, sessions, self.manual_order(day), at)

            def staying(day: date) -> list[Session]:
                if day not in pool:
                    pool[day] = [session for session in self.sessions_on(day) if session.uid not in current]
                    over[day] = {session.uid for session in arrange(day, pool[day]).overflow}
                return pool[day]

            moves: dict[str, str] = {}
            floors: dict[tuple, date] = {}
            unplaced = beyond = 0
            for session in queue:
                plan = self.plan_by_id(session.plan_id)
                origin = session.day
                phase = plan.phase_for(origin)
                floor = max(today, phase.start if phase else plan.start) if pull else max(today, current[session.uid])
                key = (session.plan_id, "seq", session.uses["seq"]) if session.uses else (session.plan_id, session.phase, session.uid.split("|")[-1])
                day = max(floor, floors.get(key, floor))
                while day <= horizon:
                    candidate = session if day == origin else replace(session, day=day, moved_from=origin)
                    layout = arrange(day, staying(day) + [candidate])
                    if (any(item.session.uid == session.uid for item in layout.placed)
                            and {item.uid for item in layout.overflow} <= over[day]):
                        break
                    day += timedelta(days=1)
                else:
                    unplaced += 1
                    if origin >= today:
                        staying(origin).append(session)
                        over[origin].add(session.uid)
                    continue
                pool[day].append(candidate)
                floors[key] = day
                if day != origin:
                    moves[session.uid] = format_date(day)
                if day > plan.end:
                    beyond += 1
        except Exception:
            self.day_order.moves = old_moves
            self._expand_all()
            raise
        self.day_order.moves.update(moves)
        self.day_order.pulls = {}
        self.day_order.replan[format_date(today)] = format_time(minute)
        self.day_order.save()
        self._expand_all()
        moved = sum(1 for uid, day in current.items() if self._sessions[uid].day != day)
        return {"moved": moved, "beyond": beyond, "unplaced": unplaced}

    def restore_all_days(self) -> int:
        """取消所有改期，任务回到原定日期。返回取消的条数。"""
        count = self.day_order.clear_moves()
        self._expand_all()
        return count

    def moved_count(self) -> int:
        return sum(1 for session in self._sessions.values() if session.moved_from is not None)

    def reset_day_order(self, day: date) -> bool:
        """删除这一天的手动排序和重排时刻，回到自动排程。改期的任务不受影响。"""
        changed = self.day_order.clear(format_date(day))
        self._layout_cache.pop(day, None)
        return changed

    # ---------- 归档 ----------

    def archive_plan(self, plan_id: str) -> str:
        plan = self.plan_by_id(plan_id)
        if plan is None:
            raise WorkspaceError(f"计划 {plan_id} 不存在")
        os.makedirs(self.archive_dir, exist_ok=True)
        name = os.path.basename(plan.source_path)
        target = os.path.join(self.archive_dir, name)
        if os.path.exists(target):
            stem, ext = os.path.splitext(name)
            target = os.path.join(self.archive_dir, f"{stem}-{datetime.now():%Y%m%d%H%M%S}{ext}")
        shutil.move(plan.source_path, target)
        self.reload()
        return target

    def archived(self) -> list[dict[str, Any]]:
        if not os.path.isdir(self.archive_dir):
            return []
        items = []
        for name in sorted(os.listdir(self.archive_dir)):
            path = os.path.join(self.archive_dir, name)
            if not name.lower().endswith(".md") or not os.path.isfile(path):
                continue
            item: dict[str, Any] = {"file": name, "path": path}
            try:
                plan = load_plan_file(path)
                item.update({"id": plan.id, "name": plan.name, "category": plan.category,
                             "start": format_date(plan.start), "end": format_date(plan.end)})
            except (PlanError, OSError, UnicodeDecodeError) as exc:
                item.update({"id": None, "name": name, "error": str(exc).splitlines()[0]})
            items.append(item)
        return items

    def _archived_path(self, filename: str) -> str:
        if not filename or os.path.basename(filename) != filename:
            raise WorkspaceError("文件名不合法")
        path = os.path.join(self.archive_dir, filename)
        if not os.path.isfile(path):
            raise WorkspaceError(f"归档里没有 {filename}")
        return path

    def restore_plan(self, filename: str) -> str:
        path = self._archived_path(filename)
        try:
            plan_id = load_plan_file(path).id
        except PlanError:
            plan_id = None
        if plan_id and self.plan_by_id(plan_id):
            raise WorkspaceError(f"已经有 id 为 {plan_id} 的计划，不能恢复")
        target = os.path.join(self.plans_dir, filename)
        if os.path.exists(target):
            raise WorkspaceError(f"计划文件夹里已经有 {filename}")
        shutil.move(path, target)
        self.reload()
        return target

    def delete_archived(self, filename: str) -> int:
        """彻底删除归档里的计划文件和它的完成记录，返回删除的记录条数。"""
        path = self._archived_path(filename)
        try:
            plan_id = load_plan_file(path).id
        except PlanError:
            plan_id = None
        os.remove(path)
        removed = 0
        if plan_id and not self.plan_by_id(plan_id):
            removed = self.progress.remove_plan(plan_id)
        return removed

    # ---------- 统计与检查 ----------

    def feasibility(self, start: date, end: date) -> Feasibility:
        return feasibility(self.sessions_on, self.profile, start, end, self.manual_order)

    def plan_warnings(self) -> list[str]:
        warnings = []
        tags = self.profile.tags()
        for plan in self.plans:
            expansion = self.expansions[plan.id]
            for name, usage in expansion.usage.items():
                if usage.skipped:
                    warnings.append(f"[{plan.id}] 序列 {name} 在 {format_date(usage.exhausted_on)} 用完，之后有 {usage.skipped} 次任务因为没有内容被跳过")
                if usage.used < usage.total:
                    warnings.append(f"[{plan.id}] 序列 {name} 到结束日只排到 {usage.used}/{usage.total} 项，剩下 {usage.total - usage.used} 项没有安排")
            slots = {session.slot for session in expansion.all_sessions() if session.slot and not session.is_fixed}
            for slot in sorted(slots - tags):
                warnings.append(f"[{plan.id}] 任务使用的 slot \"{slot}\" 在空闲时间里没有对应的 tag，这些任务都无法排入")
            no_slot = sum(1 for phase in plan.phases for tasks in phase.week.values() for task in tasks if not task.slot and task.time is None)
            no_slot += sum(1 for event in plan.events if not event.task.slot and event.task.time is None)
            if no_slot:
                warnings.append(f"[{plan.id}] 有 {no_slot} 个任务模板既没有 slot 也没有 time，会被放进任意时间段")
            warnings.extend(f"[{plan.id}] {issue}" for issue in phase_table_issues(plan, expansion))
        return warnings

    def plan_status(self, plan: Plan, today: date) -> PlanStatus:
        expansion = self.expansions[plan.id]
        sessions = expansion.all_sessions()
        done = [session for session in sessions if self.progress.is_done(session.uid)]
        overdue = [session for session in sessions if session.day < today and not self.progress.is_done(session.uid)]
        total_minutes = sum(session.minutes for session in sessions)
        overdue_minutes = sum(session.minutes for session in overdue)
        average = total_minutes / len(expansion.by_date) if expansion.by_date else 0
        extra_days = math.ceil(overdue_minutes / average) if overdue_minutes and average else 0
        if today < plan.start:
            state = "未开始"
        elif today > plan.end:
            state = "已结束"
        else:
            state = "进行中"
        records = self.progress.for_plan(plan.id)
        uids = {session.uid for session in sessions}
        sequences = []
        for name, sequence in plan.sequences.items():
            done_labels = {record["uses"]["item"] for _, record in records if isinstance(record.get("uses"), dict) and record["uses"].get("seq") == name}
            usage = expansion.usage[name]
            sequences.append(SequenceStatus(
                name=name, total=len(sequence.items),
                done_items=[item for item in sequence.items if item in done_labels],
                remaining_items=[item for item in sequence.items if item not in done_labels],
                scheduled=min(usage.used, usage.total), skipped=usage.skipped, exhausted_on=usage.exhausted_on,
            ))
        return PlanStatus(
            plan=plan, state=state, current_phase=plan.phase_for(today),
            total_sessions=len(sessions), done_sessions=len(done),
            total_minutes=total_minutes, done_minutes=sum(session.minutes for session in done),
            overdue=overdue, overdue_minutes=overdue_minutes, extra_days=extra_days,
            upcoming_milestones=[item for item in self.plan_milestones(plan, today) if not item.done and item.day >= today][:3],
            sequences=sequences, history_records=sum(1 for uid, _ in records if uid not in uids),
        )
