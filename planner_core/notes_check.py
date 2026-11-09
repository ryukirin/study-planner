"""对照计划正文里手写的阶段表和计划数据，找出阶段名和日期的偏差。

阶段表指正文里第一列表头含“阶段”的 Markdown 表格。每行第一格是阶段名，
后面的格子里第一个形如 11/09–11/15 的日期范围按阶段的起止日期核对（只比月和日）。
"""
from __future__ import annotations

import re

from .plan_spec import Plan

RANGE = re.compile(r"(\d{1,2})/(\d{1,2})\s*[–~\-]\s*(\d{1,2})/(\d{1,2})")
SEPARATOR = re.compile(r"^\s*\|[\s:\-|]+\|\s*$")


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _span(phase) -> str:
    return f"{phase.start.month}/{phase.start.day}–{phase.end.month}/{phase.end.day}"


def phase_table_issues(plan: Plan) -> list[str]:
    lines = plan.notes.splitlines()
    issues: list[str] = []
    matched: set[int] = set()
    has_table = False
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
            hit = next((index for index in candidates
                        if (plan.phases[index].start.month, plan.phases[index].start.day,
                            plan.phases[index].end.month, plan.phases[index].end.day) == written), None)
            if hit is None:
                actual = "、".join(_span(plan.phases[index]) for index in candidates)
                issues.append(f"正文阶段表「{name}」写的是 {found.group(0)}，计划里是 {actual}")
                matched.add(candidates[0])
            else:
                matched.add(hit)
    if has_table:
        for index, phase in enumerate(plan.phases):
            if index not in matched:
                issues.append(f"正文阶段表缺少阶段「{phase.name}」（{_span(phase)}）")
    return issues
