"""计划本命令行工具，供计划生成 skill 调用，也可手动使用。

python planner_cli.py paths
python planner_cli.py check [草稿.md] [--days 14] [--from YYYY-MM-DD]
python planner_cli.py status [--json] [--today YYYY-MM-DD]
python planner_cli.py add-task --title 标题 --date YYYY-MM-DD [--time HH:MM] [--minutes 30] [--location 地点] [--detail 说明] [--remind 分钟|off]
python planner_cli.py tasks
python planner_cli.py delete-task --id 任务id
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta

from planner_core import paths
from planner_core.availability import format_time
from planner_core.jp_holidays import holidays_between
from planner_core.plan_spec import WEEK_KEYS, WEEKDAY_CN, PlanError, format_date, load_plan_file, parse_date, weekday_cn
from planner_core.tasks import TaskError
from planner_core.workspace import Workspace


def _date_arg(value: str) -> date:
    try:
        return parse_date(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"日期格式应为 YYYY-MM-DD：{value}") from exc


def print_holidays(ws: Workspace, today: date) -> None:
    profile = ws.profile
    if profile.holidays != "jp":
        print('  祝日  未开启（profile.json 写 "holidays": "jp" 后按日本祝日排程）')
        return
    windows = profile.holiday_windows()
    text = "  ".join(window.describe() for window in windows) if windows else "全天无空"
    source = "同周六，" if profile.holiday is None else ""
    print(f"  祝日  日本祝日（开启）  {text}（{source}用于周一至周五的祝日）")
    upcoming = holidays_between(today, today + timedelta(days=365))[:3]
    if upcoming:
        print("  近期祝日  " + "  ".join(f"{format_date(day)} {weekday_cn(day)} {name}" for day, name in upcoming))


def print_profile(ws: Workspace, today: date) -> None:
    if ws.profile_errors:
        print(f"空闲时间：{ws.profile_path} 有错误，暂时使用默认时间段")
        for error in ws.profile_errors:
            print(f"  - {error}")
    elif ws.profile_is_default:
        print(f"空闲时间：尚未设置（{ws.profile_path} 不存在），暂时使用默认时间段")
    else:
        print(f"空闲时间：{ws.profile_path}（任务间隔 {ws.profile.buffer_minutes} 分钟）")
    for index, key in enumerate(WEEK_KEYS):
        windows = ws.profile.weekly[key]
        text = "  ".join(window.describe() for window in windows) if windows else "无"
        print(f"  {WEEKDAY_CN[index]}  {text}")
    print_holidays(ws, today)
    for day, windows in sorted(ws.profile.exceptions.items()):
        text = "  ".join(window.describe() for window in windows) if windows else "全天无空"
        note = ws.profile.exception_notes.get(day, "")
        print(f"  例外 {format_date(day)}  {text}" + (f"（{note}）" if note else ""))


def print_plans(ws: Workspace) -> None:
    print("计划：" if ws.plans else "计划：无")
    for plan in ws.plans:
        deadline = f"，截止 {format_date(plan.deadline)}" if plan.deadline else ""
        print(f"  [{plan.id}] {plan.name}  {format_date(plan.start)} ~ {format_date(plan.end)}{deadline}  优先级 {plan.priority}")


def print_day(ws: Workspace, day: date, indent: str = "  ") -> None:
    layout = ws.layout(day)
    marks = ws.milestones_on(day)
    holiday = ws.profile.holiday_name(day)
    print(f"{format_date(day)} {weekday_cn(day)}" + (f"  祝日 {holiday}" if holiday else ""))
    if ws.profile.uses_holiday_windows(day):
        windows = ws.profile.windows_for(day)
        text = "  ".join(window.describe() for window in windows) if windows else "全天无空"
        print(f"{indent}按祝日时间段  {text}")
    if not layout.placed and not layout.overflow:
        print(f"{indent}（没有任务）")
    for item in layout.placed:
        extra = "（定时）" if item.window is None else ""
        place = f"  @{item.session.location}" if item.session.location else ""
        print(f"{indent}{format_time(item.start)}-{format_time(item.end)}  [{item.session.plan_name}] {item.session.title}  {item.session.minutes} 分钟{extra}{place}")
    for session in layout.overflow:
        print(f"{indent}未排入  [{session.plan_name}] {session.title}  {session.minutes} 分钟" + (f"（slot={session.slot}）" if session.slot else ""))
    for plan, milestone in marks:
        print(f"{indent}里程碑  [{plan.name}] {milestone.text}")


def cmd_paths(ws: Workspace, args) -> int:
    print(f"数据目录：{ws.home}")
    if not args.home and not os.environ.get(paths.ENV_HOME):
        info = paths.read_app_info()
        source = "App 记录" if info.get("home") and os.path.abspath(info["home"]) == ws.home else "默认位置"
        print(f"数据目录来源：{source}（App 记录文件 {paths.app_info_path()}{'' if info else '，不存在'}）")
    print(f"计划文件夹：{ws.plans_dir}")
    print(f"空闲时间：{ws.profile_path}")
    print(f"完成记录：{ws.progress_path}")
    print(f"临时任务：{ws.tasks_path}")
    print(f"设置：{ws.settings_path}")
    print(f"归档：{ws.archive_dir}")
    return 0


def cmd_check(ws: Workspace, args) -> int:
    has_error = False
    draft_plans = []
    for path in args.draft:
        try:
            draft_plan = load_plan_file(path)
        except PlanError as exc:
            print(f"草稿 {path} 有错误：")
            for error in exc.errors:
                print(f"  - {error}")
            return 1
        except OSError as exc:
            print(f"草稿 {path} 读取失败：{exc}")
            return 1
        if any(item.id == draft_plan.id for item in draft_plans):
            print(f"草稿 {path} 的 id {draft_plan.id} 和前面的草稿重复")
            return 1
        replaced = ws.use_draft(draft_plan)
        draft_plans.append(draft_plan)
        print(f"草稿：{path}（id {draft_plan.id}，{'替换同 id 的现有计划' if replaced else '作为新计划'}参与检查）")
    draft_start = min((plan.start for plan in draft_plans), default=None)

    print_profile(ws, args.today)
    if ws.profile_errors:
        has_error = True
    print_plans(ws)
    for warning in ws.warnings:
        print(f"注意：{warning}")
    if ws.plan_errors:
        has_error = True
        print("计划文件错误：")
        for item in ws.plan_errors:
            print(f"  {item.path}")
            for error in item.errors:
                print(f"    - {error}")
    warnings = ws.plan_warnings()
    if warnings:
        print("警告：")
        for warning in warnings:
            print(f"  - {warning}")

    span = ws.date_range()
    if span:
        start = max(span[0], args.today)
        if draft_start:
            start = max(args.today, draft_start)
        end = span[1]
        if start <= end:
            report = ws.feasibility(start, end)
            print(f"可行性（{format_date(start)} ~ {format_date(end)}）：")
            weeks = [week for week in report.weeks if week.required]
            if weeks:
                busiest = max(weeks, key=lambda week: week.ratio)
                average_required = sum(week.required for week in weeks) / len(weeks)
                average_available = sum(week.available for week in weeks) / len(weeks)
                print(f"  平均每周需要 {average_required:.0f} 分钟，可用 {average_available:.0f} 分钟")
                print(f"  最满的一周从 {format_date(busiest.week_start)} 开始：需要 {busiest.required} 分钟，可用 {busiest.available} 分钟")
            if report.overflow:
                print(f"  未排入：{len(report.overflow)} 天，共 {report.overflow_count} 项")
                shown = 0
                for day, sessions in report.overflow:
                    for session in sessions:
                        if shown < 20:
                            print(f"    {format_date(day)} {weekday_cn(day)}  [{session.plan_name}] {session.title}  {session.minutes} 分钟" + (f"（slot={session.slot}）" if session.slot else ""))
                        shown += 1
                if shown > 20:
                    print(f"    …… 其余 {shown - 20} 项省略")
            else:
                print("  所有任务都能排入空闲时间")
            for day, first, second in report.overlaps[:20]:
                print(f"  定时任务重叠：{format_date(day)} {weekday_cn(day)}  [{first.plan_name}] {first.title} 和 [{second.plan_name}] {second.title}")

    preview_start = args.start or (max(args.today, draft_start) if draft_start else args.today)
    if args.days > 0 and (ws.plans or ws.task_expansion):
        print(f"时间表预览（{format_date(preview_start)} 起 {args.days} 天）：")
        for offset in range(args.days):
            print_day(ws, preview_start + timedelta(days=offset))
    return 1 if has_error else 0


def status_data(ws: Workspace, today: date) -> dict:
    plans = []
    for plan in ws.plans:
        status = ws.plan_status(plan, today)
        plans.append({
            "id": plan.id,
            "name": plan.name,
            "file": plan.source_path,
            "state": status.state,
            "start_date": format_date(plan.start),
            "end_date": format_date(plan.end),
            "deadline": format_date(plan.deadline) if plan.deadline else None,
            "current_phase": status.current_phase.name if status.current_phase else None,
            "sessions": {"done": status.done_sessions, "total": status.total_sessions, "percent": round(status.percent, 1)},
            "minutes": {"done": status.done_minutes, "total": status.total_minutes},
            "overdue": [
                {"date": session.date_str, "title": session.title, "minutes": session.minutes, "uses": session.uses}
                for session in status.overdue
            ],
            "overdue_minutes": status.overdue_minutes,
            "extra_days_if_not_replanned": status.extra_days,
            "sequences": [
                {"name": seq.name, "total": seq.total, "done": len(seq.done_items), "remaining_items": seq.remaining_items,
                 "scheduled_in_plan": seq.scheduled, "skipped_in_plan": seq.skipped}
                for seq in status.sequences
            ],
            "history_records": status.history_records,
            "upcoming_milestones": [{"date": format_date(item.day), "text": item.text} for item in status.upcoming_milestones],
        })
    return {
        "today": format_date(today),
        "home": ws.home,
        "profile": {"path": ws.profile_path, "is_default": ws.profile_is_default, "errors": ws.profile_errors},
        "plans": plans,
        "plan_errors": [{"file": item.path, "errors": item.errors} for item in ws.plan_errors],
        "warnings": ws.warnings,
    }


def cmd_status(ws: Workspace, args) -> int:
    data = status_data(ws, args.today)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    print(f"今天：{data['today']}")
    print(f"空闲时间：{'尚未设置，使用默认时间段' if data['profile']['is_default'] else data['profile']['path']}")
    if not data["plans"]:
        print("没有计划")
    for plan in data["plans"]:
        phase = f"，阶段：{plan['current_phase']}" if plan["current_phase"] else ""
        print(f"[{plan['id']}] {plan['name']}（{plan['state']}{phase}）  {plan['start_date']} ~ {plan['end_date']}")
        print(f"  完成 {plan['sessions']['done']}/{plan['sessions']['total']} 项（{plan['sessions']['percent']}%），"
              f"{plan['minutes']['done']}/{plan['minutes']['total']} 分钟")
        if plan["overdue"]:
            print(f"  逾期 {len(plan['overdue'])} 项，共 {plan['overdue_minutes']} 分钟。不重排的话，补完约需多 {plan['extra_days_if_not_replanned']} 天")
            for item in plan["overdue"][:10]:
                print(f"    {item['date']}  {item['title']}  {item['minutes']} 分钟")
            if len(plan["overdue"]) > 10:
                print(f"    …… 其余 {len(plan['overdue']) - 10} 项省略，完整列表用 --json 查看")
        for seq in plan["sequences"]:
            remaining = seq["remaining_items"]
            preview = "、".join(remaining[:5]) + ("……" if len(remaining) > 5 else "")
            print(f"  序列 {seq['name']}：已完成 {seq['done']}/{seq['total']}" + (f"，接下来：{preview}" if remaining else ""))
        if plan["history_records"]:
            print(f"  另有 {plan['history_records']} 条计划范围外的完成记录（重排前留下）")
        for item in plan["upcoming_milestones"]:
            print(f"  里程碑 {item['date']}  {item['text']}")
    for item in data["plan_errors"]:
        print(f"计划文件错误：{item['file']}")
        for error in item["errors"]:
            print(f"  - {error}")
    for warning in data["warnings"]:
        print(f"注意：{warning}")
    return 0


def _remind_arg(value: str):
    if value.lower() in ("off", "false", "no"):
        return False
    try:
        return int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--remind 填分钟数，或 off 表示不提醒") from exc


def cmd_add_task(ws: Workspace, args) -> int:
    data = {"title": args.title, "date": args.date, "minutes": args.minutes, "detail": args.detail or "",
            "location": args.location or ""}
    if args.time:
        data["time"] = args.time
    if args.remind is not None:
        data["remind"] = args.remind
    try:
        task = ws.add_task(data)
    except TaskError as exc:
        print("添加失败：")
        for error in exc.errors:
            print(f"  - {error}")
        return 1
    when = f"{task['date']} {task['time']}" if task["time"] else f"{task['date']}（不定时，按空闲时间排）"
    print(f"已添加临时任务：{when}  {task['title']}  {task['minutes']} 分钟  id={task['id']}")
    return 0


def cmd_tasks(ws: Workspace, args) -> int:
    upcoming = [task for task in ws.tasks.tasks if task["date"] >= format_date(args.today)]
    if not upcoming:
        print("没有今天及以后的临时任务")
    for task in sorted(upcoming, key=lambda item: (item["date"], item["time"] or "99:99")):
        when = f"{task['date']} {task['time'] or '不定时'}"
        place = f"  @{task['location']}" if task["location"] else ""
        print(f"{when}  {task['title']}  {task['minutes']} 分钟{place}  id={task['id']}")
    return 0


def cmd_delete_task(ws: Workspace, args) -> int:
    if ws.delete_task(args.id):
        print(f"已删除临时任务 {args.id}")
        return 0
    print(f"没有找到临时任务 {args.id}")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="计划本命令行工具")
    parser.add_argument("--home", help="数据目录。不写时依次使用环境变量 STUDY_PLANNER_HOME、App 记录的数据目录（%%APPDATA%%\\StudyPlanner\\app.json）、%%APPDATA%%\\StudyPlanner")
    parser.add_argument("--today", type=_date_arg, default=date.today(), help="把某天当作今天，默认是系统日期")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("paths", help="打印数据目录和各文件路径")
    check = sub.add_parser("check", help="校验空闲时间和全部计划，给出可行性检查和时间表预览")
    check.add_argument("draft", nargs="*", help="草稿计划文件，可以写多个，按全部加入后的状态一起检查")
    check.add_argument("--days", type=int, default=14, help="预览天数，默认 14，0 表示不预览")
    check.add_argument("--from", dest="start", type=_date_arg, help="预览起始日期")
    status = sub.add_parser("status", help="各计划的完成情况、逾期任务和序列剩余项")
    status.add_argument("--json", action="store_true", help="输出 JSON")
    add = sub.add_parser("add-task", help="添加一次性临时任务")
    add.add_argument("--title", required=True)
    add.add_argument("--date", required=True, help="YYYY-MM-DD")
    add.add_argument("--time", help="HH:MM，不写时按空闲时间排")
    add.add_argument("--minutes", type=int, default=30)
    add.add_argument("--location")
    add.add_argument("--detail")
    add.add_argument("--remind", type=_remind_arg, help="提前提醒的分钟数，off 表示不提醒")
    sub.add_parser("tasks", help="列出今天及以后的临时任务")
    delete = sub.add_parser("delete-task", help="删除临时任务")
    delete.add_argument("--id", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    ws = Workspace(args.home or paths.data_home(use_app_info=True))
    handler = {"paths": cmd_paths, "check": cmd_check, "status": cmd_status, "add-task": cmd_add_task,
               "tasks": cmd_tasks, "delete-task": cmd_delete_task}[args.command]
    return handler(ws, args)


if __name__ == "__main__":
    sys.exit(main())
