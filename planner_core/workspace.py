from __future__ import annotations

import math
import os
import shutil
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterator

from . import paths
from .availability import Profile, load_profile, save_profile
from .plan_spec import DEFAULT_COLORS, Expansion, Milestone, Phase, Plan, PlanError, Session, expand_plan, format_date, load_plan_file
from .notes_check import phase_table_issues
from .progress import ProgressStore
from .scheduler import DayLayout, Feasibility, feasibility, layout_day
from .settings import load_settings, save_settings
from .tasks import TASKS_PLAN_ID, TaskStore


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
        self._layout_cache: dict[date, DayLayout] = {}

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
        """计划文件夹、profile 和临时任务的修改时间，用于检测外部改动。"""
        entries = []
        candidates = [self.profile_path, self.tasks_path] + [os.path.join(self.plans_dir, name) for name in sorted(os.listdir(self.plans_dir))]
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

    def milestones_on(self, day: date) -> list[tuple[Plan, Milestone]]:
        return [(plan, item) for plan in self.plans for item in self.expansions[plan.id].milestones.get(day, [])]

    def layout(self, day: date) -> DayLayout:
        if day not in self._layout_cache:
            self._layout_cache[day] = layout_day(day, self.sessions_on(day), self.profile.windows_for(day), self.profile.buffer_minutes)
        return self._layout_cache[day]

    def date_range(self) -> tuple[date, date] | None:
        expansions = list(self.iter_expansions())
        if not expansions:
            return None
        return min(item.plan.start for item in expansions), max(item.plan.end for item in expansions)

    def is_done(self, uid: str) -> bool:
        return self.progress.is_done(uid)

    def set_done(self, session: Session, done: bool) -> None:
        self.progress.set_done(session, done)

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
        return feasibility(self.sessions_on, self.profile, start, end)

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
            warnings.extend(f"[{plan.id}] {issue}" for issue in phase_table_issues(plan))
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
            upcoming_milestones=[item for item in plan.milestones if item.day >= today][:3],
            sequences=sequences, history_records=sum(1 for uid, _ in records if uid not in uids),
        )
