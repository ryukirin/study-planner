from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from .timeutil import parse_time

DATE_FMT = "%Y-%m-%d"
BLOCK_NAME = "study-plan"
WEEK_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
TEMPLATE_KEYS = ("daily", "weekdays", "weekend") + WEEK_KEYS
WEEKDAY_CN = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
RESERVED_FIELDS = ("phase", "week", "n")
DEFAULT_COLORS = ("#d16a3a", "#3a7bd1", "#2f8f5b", "#8e5bd1", "#c9a227", "#d13a6f")
MAX_SEQUENCE_ITEMS = 5000
MAX_TASK_MINUTES = 600

MAX_REMIND_MINUTES = 1440

TOP_KEYS = {"schema", "id", "name", "goal", "category", "color", "priority", "start_date", "deadline", "resources", "sequences", "phases", "events", "milestones"}
PHASE_KEYS = {"name", "goal", "focus", "weeks", "week"}
TASK_COMMON_KEYS = {"title", "minutes", "slot", "detail", "time", "location", "links", "remind"}
TASK_KEYS = TASK_COMMON_KEYS | {"uses"}
EVENT_KEYS = TASK_COMMON_KEYS | {"date", "offset_days"}
MILESTONE_KEYS = {"text", "note", "date", "offset_days"}
SEQUENCE_KEYS = {"items", "range", "label", "on_exhausted", "title"}
RANGE_KEYS = {"from", "to", "step"}

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
SEQ_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_TOKEN_RE = re.compile(r"\{\{|\}\}|\{([A-Za-z_][A-Za-z0-9_]*)\}|[{}]")
_RANGE_LABEL_RE = re.compile(r"\{\{|\}\}|\{(from|to|i)(?::(0?)(\d*)d)?\}|[{}]")


class PlanError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("\n".join(errors))


@dataclass
class Sequence:
    name: str
    items: list[str]
    on_exhausted: str = "skip"
    title: str = ""


@dataclass
class TaskTemplate:
    title: str
    minutes: int
    slot: str | None = None
    detail: str = ""
    uses: str | None = None
    time: int | None = None
    location: str = ""
    links: list[dict[str, str]] = field(default_factory=list)
    remind: int | bool | None = None


@dataclass
class Phase:
    name: str
    goal: str
    focus: str
    start: date
    end: date
    week: dict[str, list[TaskTemplate]]


@dataclass
class Event:
    day: date
    task: TaskTemplate


@dataclass
class Milestone:
    day: date
    text: str
    note: str = ""


@dataclass
class Plan:
    id: str
    name: str
    goal: str
    color: str | None
    priority: int
    start: date
    end: date
    deadline: date | None
    resources: list[dict[str, str]]
    sequences: dict[str, Sequence]
    phases: list[Phase]
    events: list[Event]
    milestones: list[Milestone]
    notes: str = ""
    source_path: str = ""
    category: str = ""

    def phase_index_for(self, day: date) -> int | None:
        for index, phase in enumerate(self.phases):
            if phase.start <= day <= phase.end:
                return index
        return None

    def phase_for(self, day: date) -> Phase | None:
        index = self.phase_index_for(day)
        return None if index is None else self.phases[index]


@dataclass
class Session:
    uid: str
    plan_id: str
    plan_name: str
    color: str
    priority: int
    day: date
    order: int
    title: str
    detail: str
    minutes: int
    slot: str | None
    phase: str
    kind: str = "task"
    uses: dict[str, str] | None = None
    fixed_start: int | None = None
    location: str = ""
    links: list[dict[str, str]] = field(default_factory=list)
    remind: int | bool | None = None

    @property
    def date_str(self) -> str:
        return self.day.strftime(DATE_FMT)

    @property
    def is_fixed(self) -> bool:
        return self.fixed_start is not None


@dataclass
class SequenceUsage:
    total: int
    used: int = 0
    skipped: int = 0
    exhausted_on: date | None = None


@dataclass
class Expansion:
    plan: Plan
    by_date: dict[date, list[Session]]
    usage: dict[str, SequenceUsage]
    milestones: dict[date, list[Milestone]] = field(default_factory=dict)

    def all_sessions(self) -> list[Session]:
        return [session for day in sorted(self.by_date) for session in self.by_date[day]]


def parse_date(value: str) -> date:
    return datetime.strptime(value, DATE_FMT).date()


def format_date(value: date) -> str:
    return value.strftime(DATE_FMT)


def weekday_cn(value: date) -> str:
    return WEEKDAY_CN[value.weekday()]


# ---------- 文案占位符 ----------

def template_problems(text: str, allowed: set[str], sequence_names: set[str], uses: str | None) -> list[str]:
    problems: list[str] = []
    for match in _TOKEN_RE.finditer(text):
        token = match.group(0)
        if token in ("{{", "}}"):
            continue
        name = match.group(1)
        if name is None:
            problems.append("出现单独的花括号，字面花括号请写成 {{ 或 }}")
            continue
        if name in allowed:
            continue
        if name in sequence_names:
            problems.append(f"使用 {{{name}}} 需要同时写 \"uses\": \"{name}\"" + (f"（当前 uses 是 {uses}）" if uses else ""))
        else:
            problems.append(f"未知占位符 {{{name}}}，可用的有 {', '.join('{' + item + '}' for item in sorted(allowed))}")
    return problems


def render_text(text: str, values: dict[str, Any]) -> str:
    def replace(match: re.Match) -> str:
        token = match.group(0)
        if token == "{{":
            return "{"
        if token == "}}":
            return "}"
        name = match.group(1)
        if name is None or name not in values:
            return token
        return str(values[name])

    return _TOKEN_RE.sub(replace, text)


def _range_label_problems(label: str) -> list[str]:
    problems = []
    for match in _RANGE_LABEL_RE.finditer(label):
        token = match.group(0)
        if token in ("{{", "}}") or match.group(1):
            continue
        problems.append("label 里只能用 {from}、{to}、{i}，可写成 {from:03d} 这样补零，字面花括号写成 {{ 或 }}")
        break
    return problems


def _render_range_label(label: str, values: dict[str, int]) -> str:
    def replace(match: re.Match) -> str:
        token = match.group(0)
        if token == "{{":
            return "{"
        if token == "}}":
            return "}"
        name = match.group(1)
        if not name:
            return token
        zero, width = match.group(2) or "", match.group(3) or ""
        return format(values[name], f"{zero}{width}d")

    return _RANGE_LABEL_RE.sub(replace, label)


# ---------- 读取 Markdown ----------

def extract_block(text: str) -> tuple[dict, str]:
    """返回 (study-plan 代码块的 JSON, 去掉代码块后的 Markdown 正文)。"""
    lines = text.splitlines()
    opening = None
    closing = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if opening is None:
            if stripped.lower() == f"```{BLOCK_NAME}":
                opening = index
        elif stripped == "```":
            closing = index
            break
    if opening is None:
        raise PlanError([f"没有找到 ```{BLOCK_NAME}``` 代码块"])
    if closing is None:
        raise PlanError([f"```{BLOCK_NAME}``` 代码块缺少结尾的 ```"])
    for line in lines[closing + 1:]:
        if line.strip().lower() == f"```{BLOCK_NAME}":
            raise PlanError([f"一个文件只能有一个 ```{BLOCK_NAME}``` 代码块"])
    body = "\n".join(lines[opening + 1:closing])
    try:
        config = json.loads(body)
    except json.JSONDecodeError as exc:
        raise PlanError([f"JSON 格式错误（文件第 {opening + 1 + exc.lineno} 行第 {exc.colno} 列）：{exc.msg}"]) from exc
    notes = "\n".join(lines[:opening] + lines[closing + 1:]).strip()
    return config, notes


def load_plan_file(path: str) -> Plan:
    with open(path, "r", encoding="utf-8-sig") as handle:
        text = handle.read()
    config, notes = extract_block(text)
    return parse_plan(config, notes=notes, source_path=path)


# ---------- 校验 ----------

def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _unknown_keys(raw: dict, allowed: set[str], path: str, errors: list[str]) -> None:
    for key in raw:
        if key not in allowed:
            errors.append(f"{path}：未知字段 {key}，可用字段为 {', '.join(sorted(allowed))}")


def _parse_date_field(value: Any, path: str, errors: list[str], required: bool) -> date | None:
    if value is None:
        if required:
            errors.append(f"{path}：缺少日期，格式为 YYYY-MM-DD")
        return None
    if not isinstance(value, str):
        errors.append(f"{path}：日期必须是 YYYY-MM-DD 字符串")
        return None
    try:
        return parse_date(value)
    except ValueError:
        errors.append(f"{path}：日期 {value!r} 格式不对，应为 YYYY-MM-DD")
        return None


def _str_field(raw: dict, key: str, path: str, errors: list[str], required: bool = False, default: str = "") -> str:
    value = raw.get(key)
    if value is None:
        if required:
            errors.append(f"{path}.{key}：必填")
        return default
    if not isinstance(value, str) or (required and not value.strip()):
        errors.append(f"{path}.{key}：必须是非空字符串" if required else f"{path}.{key}：必须是字符串")
        return default
    return value


def _parse_sequences(raw: Any, errors: list[str]) -> dict[str, Sequence]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        errors.append("sequences：必须是对象，键为序列名")
        return {}
    sequences: dict[str, Sequence] = {}
    for name, spec in raw.items():
        path = f"sequences.{name}"
        if not SEQ_NAME_RE.match(name) or name in RESERVED_FIELDS:
            errors.append(f"{path}：序列名只能用字母、数字、下划线，不能以数字开头，也不能是 {', '.join(RESERVED_FIELDS)}")
            continue
        if not isinstance(spec, dict):
            errors.append(f"{path}：必须是对象")
            continue
        _unknown_keys(spec, SEQUENCE_KEYS, path, errors)
        title = spec.get("title", "")
        if not isinstance(title, str):
            errors.append(f"{path}.title：必须是字符串")
            title = ""
        on_exhausted = spec.get("on_exhausted", "skip")
        if on_exhausted not in ("skip", "repeat"):
            errors.append(f"{path}.on_exhausted：只能是 skip 或 repeat")
            on_exhausted = "skip"
        items: list[str] = []
        if "items" in spec and "range" in spec:
            errors.append(f"{path}：items 和 range 只能二选一")
            continue
        if "items" in spec:
            raw_items = spec["items"]
            if "label" in spec:
                errors.append(f"{path}.label：只有 range 序列需要 label")
            if not isinstance(raw_items, list) or not raw_items or not all(isinstance(item, str) and item.strip() for item in raw_items):
                errors.append(f"{path}.items：必须是非空字符串组成的非空数组")
                continue
            items = list(raw_items)
        elif "range" in spec:
            rng = spec["range"]
            label = spec.get("label")
            if not isinstance(rng, dict):
                errors.append(f"{path}.range：必须是对象，包含 from、to、step")
                continue
            _unknown_keys(rng, RANGE_KEYS, f"{path}.range", errors)
            start, end, step = rng.get("from"), rng.get("to"), rng.get("step", 1)
            if not (_is_int(start) and _is_int(end) and _is_int(step)) or step < 1 or end < start:
                errors.append(f"{path}.range：from、to、step 必须是整数，step ≥ 1 且 to ≥ from")
                continue
            if not isinstance(label, str) or not label.strip():
                errors.append(f"{path}.label：range 序列必须写 label，例如 \"金フレ {{from:03d}}-{{to:03d}}\"")
                continue
            problems = _range_label_problems(label)
            if problems:
                errors.extend(f"{path}.label：{problem}" for problem in problems)
                continue
            count = (end - start) // step + 1
            if count > MAX_SEQUENCE_ITEMS:
                errors.append(f"{path}.range：最多 {MAX_SEQUENCE_ITEMS} 项，当前 {count} 项")
                continue
            for index, value in enumerate(range(start, end + 1, step), start=1):
                items.append(_render_range_label(label, {"from": value, "to": min(value + step - 1, end), "i": index}))
        else:
            errors.append(f"{path}：需要 items 或 range")
            continue
        sequences[name] = Sequence(name=name, items=items, on_exhausted=on_exhausted, title=title)
    return sequences


def _parse_task(raw: Any, path: str, errors: list[str], sequences: dict[str, Sequence], allowed_keys: set[str], allow_uses: bool) -> TaskTemplate | None:
    if not isinstance(raw, dict):
        errors.append(f"{path}：必须是对象")
        return None
    before = len(errors)
    _unknown_keys(raw, allowed_keys, path, errors)
    title = _str_field(raw, "title", path, errors, required=True)
    detail = _str_field(raw, "detail", path, errors)
    minutes = raw.get("minutes")
    if not _is_int(minutes) or not 1 <= minutes <= MAX_TASK_MINUTES:
        errors.append(f"{path}.minutes：必须是 1 到 {MAX_TASK_MINUTES} 的整数")
    slot = raw.get("slot")
    if slot is not None and (not isinstance(slot, str) or not slot.strip()):
        errors.append(f"{path}.slot：必须是非空字符串，对应空闲时间段的 tag")
    uses = raw.get("uses") if allow_uses else None
    if uses is not None:
        if not isinstance(uses, str) or uses not in sequences:
            errors.append(f"{path}.uses：序列 {uses!r} 不存在")
            uses = None
    allowed = set(RESERVED_FIELDS) | ({uses} if uses else set())
    for key, text in (("title", title), ("detail", detail)):
        for problem in template_problems(text, allowed, set(sequences), uses):
            errors.append(f"{path}.{key}：{problem}")
    extra = parse_task_extras(raw, path, errors)
    if len(errors) > before:
        return None
    return TaskTemplate(title=title, minutes=minutes, slot=slot, detail=detail, uses=uses, **extra)


def parse_task_extras(raw: dict, path: str, errors: list[str]) -> dict[str, Any]:
    """time、location、links、remind 的校验，计划任务和临时任务共用。"""
    extra: dict[str, Any] = {"time": None, "location": "", "links": [], "remind": None}
    if raw.get("time") is not None:
        try:
            value = parse_time(raw["time"])
            if value >= 24 * 60:
                raise ValueError("开始时间不能是 24:00")
            extra["time"] = value
        except ValueError as exc:
            errors.append(f"{path}.time：{exc}")
    location = raw.get("location", "")
    if not isinstance(location, str):
        errors.append(f"{path}.location：必须是字符串")
    else:
        extra["location"] = location.strip()
    links = raw.get("links", [])
    if not isinstance(links, list):
        errors.append(f"{path}.links：必须是数组")
        links = []
    for index, link in enumerate(links):
        if (not isinstance(link, dict) or not isinstance(link.get("url"), str)
                or not link["url"].startswith(("http://", "https://")) or not isinstance(link.get("title", ""), str)):
            errors.append(f"{path}.links[{index}]：必须是 {{\"title\": 字符串, \"url\": \"http(s)://...\"}}")
            continue
        extra["links"].append({"title": link.get("title") or link["url"], "url": link["url"]})
    remind = raw.get("remind")
    if remind is not None:
        if remind is False or (_is_int(remind) and 0 <= remind <= MAX_REMIND_MINUTES):
            extra["remind"] = remind
        else:
            errors.append(f"{path}.remind：提前提醒的分钟数（0 到 {MAX_REMIND_MINUTES}），或 false 表示不提醒")
    return extra


def _parse_week(raw: Any, path: str, errors: list[str], sequences: dict[str, Sequence]) -> dict[str, list[TaskTemplate]]:
    week: dict[str, list[TaskTemplate]] = {key: [] for key in TEMPLATE_KEYS}
    if raw is None:
        return week
    if not isinstance(raw, dict):
        errors.append(f"{path}：必须是对象，键为 daily、weekdays、weekend、mon 到 sun")
        return week
    for key, tasks in raw.items():
        if key not in TEMPLATE_KEYS:
            errors.append(f"{path}：未知键 {key}，只能用 {', '.join(TEMPLATE_KEYS)}")
            continue
        if not isinstance(tasks, list):
            errors.append(f"{path}.{key}：必须是任务数组")
            continue
        for index, task_raw in enumerate(tasks):
            task = _parse_task(task_raw, f"{path}.{key}[{index}]", errors, sequences, TASK_KEYS, allow_uses=True)
            if task:
                week[key].append(task)
    return week


def _resolve_day(raw: dict, path: str, errors: list[str], start: date | None, end: date | None) -> date | None:
    has_date = raw.get("date") is not None
    has_offset = raw.get("offset_days") is not None
    if has_date == has_offset:
        errors.append(f"{path}：date 和 offset_days 必须且只能写一个")
        return None
    if has_date:
        day = _parse_date_field(raw.get("date"), f"{path}.date", errors, required=True)
    else:
        offset = raw.get("offset_days")
        if not _is_int(offset) or offset < 0:
            errors.append(f"{path}.offset_days：必须是 ≥ 0 的整数")
            return None
        day = start + timedelta(days=offset) if start else None
    if day and start and end and not start <= day <= end:
        errors.append(f"{path}：日期 {format_date(day)} 不在计划范围 {format_date(start)} ~ {format_date(end)} 内")
        return None
    if day and start and day < start:
        errors.append(f"{path}：日期 {format_date(day)} 早于 start_date {format_date(start)}")
        return None
    return day


def parse_plan(config: Any, notes: str = "", source_path: str = "") -> Plan:
    errors: list[str] = []
    if not isinstance(config, dict):
        raise PlanError([f"```{BLOCK_NAME}``` 代码块必须是 JSON 对象"])
    _unknown_keys(config, TOP_KEYS, "计划", errors)
    if config.get("schema") != 1:
        errors.append("schema：必须为 1")

    plan_id = config.get("id")
    if not isinstance(plan_id, str) or not ID_RE.match(plan_id):
        errors.append("id：必填，只能用字母、数字、-、_、.，且以字母或数字开头")
        plan_id = ""
    name = _str_field(config, "name", "计划", errors, required=True)
    goal = _str_field(config, "goal", "计划", errors)
    category = _str_field(config, "category", "计划", errors).strip()
    color = config.get("color")
    if color is not None and (not isinstance(color, str) or not COLOR_RE.match(color)):
        errors.append("color：必须是 #RRGGBB 格式")
        color = None
    priority = config.get("priority", 1)
    if not _is_int(priority) or priority < 1:
        errors.append("priority：必须是 ≥ 1 的整数，数字越小越优先")
        priority = 1

    start = _parse_date_field(config.get("start_date"), "start_date", errors, required=True)
    deadline = _parse_date_field(config.get("deadline"), "deadline", errors, required=False)
    if start and deadline and deadline < start:
        errors.append("deadline：早于 start_date")
        deadline = None

    resources: list[dict[str, str]] = []
    raw_resources = config.get("resources", [])
    if not isinstance(raw_resources, list):
        errors.append("resources：必须是数组")
    else:
        for index, item in enumerate(raw_resources):
            if not isinstance(item, dict) or not isinstance(item.get("item"), str) or not isinstance(item.get("kind", ""), str):
                errors.append(f"resources[{index}]：必须是 {{\"kind\": 字符串, \"item\": 字符串}}")
                continue
            resources.append({"kind": item.get("kind", ""), "item": item["item"]})

    sequences = _parse_sequences(config.get("sequences"), errors)

    errors_before_phases = len(errors)
    raw_phases = config.get("phases") or []
    phase_specs: list[tuple[str, str, str, int | None, dict]] = []
    if not isinstance(raw_phases, list):
        errors.append("phases：必须是数组")
        raw_phases = []
    raw_events_value = config.get("events")
    if not raw_phases and not (isinstance(raw_events_value, list) and raw_events_value):
        errors.append("phases 和 events 至少要写一个。长期计划用 phases，短期计划可以只写 events")
    for index, raw in enumerate(raw_phases):
        path = f"phases[{index}]"
        if not isinstance(raw, dict):
            errors.append(f"{path}：必须是对象")
            continue
        _unknown_keys(raw, PHASE_KEYS, path, errors)
        phase_name = _str_field(raw, "name", path, errors, required=True)
        weeks = raw.get("weeks")
        last = index == len(raw_phases) - 1
        if weeks is None:
            if not last:
                errors.append(f"{path}.weeks：只有最后一个阶段可以省略 weeks")
        elif not _is_int(weeks) or weeks < 1:
            errors.append(f"{path}.weeks：必须是 ≥ 1 的整数")
            weeks = None
        week = _parse_week(raw.get("week"), f"{path}.week", errors, sequences)
        phase_specs.append((phase_name, _str_field(raw, "goal", path, errors), _str_field(raw, "focus", path, errors), weeks, week))

    phases: list[Phase] = []
    end: date | None = None
    if start and phase_specs and len(errors) == errors_before_phases:
        errors_before_timeline = len(errors)
        cursor = start
        for index, (phase_name, phase_goal, phase_focus, weeks, week) in enumerate(phase_specs):
            path = f"phases[{index}]"
            last = index == len(phase_specs) - 1
            if deadline and cursor > deadline:
                errors.append(f"{path}：阶段从 {format_date(cursor)} 开始，已经晚于 deadline {format_date(deadline)}，请减少前面阶段的 weeks")
                break
            if weeks is None:
                if deadline is None:
                    errors.append(f"{path}.weeks：没有 deadline 时，最后一个阶段也要写 weeks")
                    break
                phase_end = deadline
            else:
                phase_end = cursor + timedelta(days=weeks * 7 - 1)
            if deadline and phase_end > deadline:
                errors.append(f"{path}：阶段到 {format_date(phase_end)} 结束，超出 deadline {format_date(deadline)}。请减少 weeks，或删掉最后一个阶段的 weeks 让它延伸到 deadline")
                break
            if last and deadline and phase_end < deadline:
                errors.append(f"{path}：最后一个阶段到 {format_date(phase_end)} 结束，早于 deadline {format_date(deadline)}。删掉它的 weeks 可以自动延伸到 deadline")
                break
            phases.append(Phase(name=phase_name, goal=phase_goal, focus=phase_focus, start=cursor, end=phase_end, week=week))
            cursor = phase_end + timedelta(days=1)
        if phases and len(errors) == errors_before_timeline:
            end = phases[-1].end
    elif not raw_phases:
        end = deadline

    events: list[Event] = []
    raw_events = config.get("events", [])
    if not isinstance(raw_events, list):
        errors.append("events：必须是数组")
        raw_events = []
    for index, raw in enumerate(raw_events):
        path = f"events[{index}]"
        task = _parse_task(raw, path, errors, sequences, EVENT_KEYS, allow_uses=False)
        if task and isinstance(raw, dict):
            day = _resolve_day(raw, path, errors, start, end)
            if day:
                events.append(Event(day=day, task=task))
    if not raw_phases and end is None and events:
        end = max(event.day for event in events)

    milestones: list[Milestone] = []
    raw_milestones = config.get("milestones", [])
    if not isinstance(raw_milestones, list):
        errors.append("milestones：必须是数组")
        raw_milestones = []
    for index, raw in enumerate(raw_milestones):
        path = f"milestones[{index}]"
        if not isinstance(raw, dict):
            errors.append(f"{path}：必须是对象")
            continue
        _unknown_keys(raw, MILESTONE_KEYS, path, errors)
        text = _str_field(raw, "text", path, errors, required=True)
        note = _str_field(raw, "note", path, errors)
        day = _resolve_day(raw, path, errors, start, end)
        if day and text:
            milestones.append(Milestone(day=day, text=text, note=note))

    if errors or start is None or end is None:
        raise PlanError(errors or ["计划范围无法计算"])
    milestones.sort(key=lambda item: item.day)
    events.sort(key=lambda item: item.day)
    return Plan(
        id=plan_id, name=name, goal=goal, color=color, priority=priority, start=start, end=end, deadline=deadline,
        resources=resources, sequences=sequences, phases=phases, events=events, milestones=milestones,
        notes=notes, source_path=source_path, category=category,
    )


# ---------- 展开 ----------

def expand_plan(plan: Plan, color: str | None = None) -> Expansion:
    """把计划展开成按日期的任务。星期结构跟随真实日期，序列按出现顺序依次取用。"""
    plan_color = plan.color or color or DEFAULT_COLORS[0]
    cursors = {name: 0 for name in plan.sequences}
    usage = {name: SequenceUsage(total=len(seq.items)) for name, seq in plan.sequences.items()}
    counters: dict[tuple[int, str, int], int] = {}
    events_by_day: dict[date, list[Event]] = {}
    for event in plan.events:
        events_by_day.setdefault(event.day, []).append(event)
    milestones: dict[date, list[Milestone]] = {}
    for milestone in plan.milestones:
        milestones.setdefault(milestone.day, []).append(milestone)

    by_date: dict[date, list[Session]] = {}
    day = plan.start
    while day <= plan.end:
        phase_index = plan.phase_index_for(day)
        phase = plan.phases[phase_index] if phase_index is not None else None
        phase_name = phase.name if phase else ""
        week_no = (day - plan.start).days // 7 + 1
        weekday_key = WEEK_KEYS[day.weekday()]
        group_key = "weekdays" if day.weekday() < 5 else "weekend"
        slots = [(key, index, task) for key in ("daily", group_key, weekday_key) for index, task in enumerate(phase.week[key])] if phase else []
        sessions: list[Session] = []

        def add(slot_id: str, task: TaskTemplate, values: dict[str, Any], kind: str, uses: dict[str, str] | None) -> None:
            sessions.append(Session(
                uid=f"{plan.id}|{format_date(day)}|{slot_id}", plan_id=plan.id, plan_name=plan.name, color=plan_color,
                priority=plan.priority, day=day, order=len(sessions), title=render_text(task.title, values),
                detail=render_text(task.detail, values), minutes=task.minutes, slot=task.slot, phase=phase_name,
                kind=kind, uses=uses, fixed_start=task.time, location=task.location, links=list(task.links), remind=task.remind,
            ))

        for template_key, template_index, task in slots:
            counter_key = (phase_index, template_key, template_index)
            counters[counter_key] = counters.get(counter_key, 0) + 1
            values: dict[str, Any] = {"phase": phase_name, "week": week_no, "n": counters[counter_key]}
            uses = None
            if task.uses:
                sequence = plan.sequences[task.uses]
                record = usage[task.uses]
                position = cursors[task.uses]
                if position >= len(sequence.items):
                    if record.exhausted_on is None:
                        record.exhausted_on = day
                    if sequence.on_exhausted == "skip":
                        record.skipped += 1
                        continue
                item = sequence.items[position % len(sequence.items)]
                cursors[task.uses] = position + 1
                record.used += 1
                values[task.uses] = item
                uses = {"seq": task.uses, "item": item}
            add(f"{template_key}{template_index}", task, values, "task", uses)

        for event_index, event in enumerate(events_by_day.get(day, [])):
            add(f"e{event_index}", event.task, {"phase": phase_name, "week": week_no, "n": 1}, "event", None)

        if sessions:
            by_date[day] = sessions
        day += timedelta(days=1)
    return Expansion(plan=plan, by_date=by_date, usage=usage, milestones=milestones)
