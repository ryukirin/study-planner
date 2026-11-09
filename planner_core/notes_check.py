"""对照计划正文里手写的阶段表和计划数据，找出阶段名和日期的偏差。

阶段表指正文里第一列表头含“阶段”的 Markdown 表格。每行第一格是阶段名，
后面的格子里第一个形如 11/09–11/13 的日期范围按阶段内实际任务的起止日核对（只比月和日）。
实际任务指展开后落在阶段日期内的任务和 events。整个阶段都没有任务时，按阶段的起止日核对。
"""
from __future__ import annotations

import re
from datetime import date

from .plan_spec import Expansion, Plan, expand_plan

RANGE = re.compile(r"(\d{1,2})/(\d{1,2})\s*[–~\-]\s*(\d{1,2})/(\d{1,2})")
SEPARATOR = re.compile(r"^\s*\|[\s:\-|]+\|\s*$")


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def task_spans(plan: Plan, expansion: Expansion | None = None) -> list[tuple[date, date]]:
    """每个阶段第一个任务和最后一个任务的日期。阶段内没有任务时返回阶段的起止日。"""
    expansion = expansion or expand_plan(plan)
    spans = []
    for phase in plan.phases:
        days = [day for day in expansion.by_date if phase.start <= day <= phase.end]
        spans.append((min(days), max(days)) if days else (phase.start, phase.end))
    return spans


def format_span(span: tuple[date, date]) -> str:
    start, end = span
    return f"{start.month:02d}/{start.day:02d}–{end.month:02d}/{end.day:02d}"


def _key(span: tuple[date, date]) -> tuple[int, int, int, int]:
    start, end = span
    return start.month, start.day, end.month, end.day


def phase_table_issues(plan: Plan, expansion: Expansion | None = None) -> list[str]:
    lines = plan.notes.splitlines()
    issues: list[str] = []
    matched: set[int] = set()
    has_table = False
    spans = task_spans(plan, expansion)
    i = 0
    while i < len(lines):
        if not (lines[i].strip().startswith("|") and i + 1 < len(lines) and SEPARATOR.match(lines[i + 1])):
            i += 1
            continue
        header = _cells(lines[i])
        j = i + 2
        rows = []
        while j < len(lines) and lines[j].strip().startswith("|"):
            rows.append(_cells(lines[j]))
            j += 1
        i = j
        if not header or "阶段" not in header[0]:
            continue
        has_table = True
        for row in rows:
            name = row[0]
            candidates = [index for index, phase in enumerate(plan.phases) if phase.name == name]
            if not candidates:
                issues.append(f"正文阶段表里的「{name}」不是计划里的阶段名")
                continue
            found = RANGE.search(" | ".join(row[1:]))
            if not found:
                matched.add(candidates[0])
                continue
            written = tuple(int(group) for group in found.groups())
            hit = next((index for index in candidates if _key(spans[index]) == written), None)
            if hit is None:
                actual = "、".join(format_span(spans[index]) for index in candidates)
                issues.append(f"正文阶段表「{name}」写的是 {found.group(0)}，阶段内的任务在 {actual}")
                matched.add(candidates[0])
            else:
                matched.add(hit)
    if has_table:
        for index, phase in enumerate(plan.phases):
            if index not in matched:
                issues.append(f"正文阶段表缺少阶段「{phase.name}」（{format_span(spans[index])}）")
    return issues
