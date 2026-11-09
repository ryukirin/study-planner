"""App 设置：提醒、番茄钟、后台运行。保存在 settings.json。"""
from __future__ import annotations

import copy
from typing import Any

from .storage import load_json, write_json_atomic
from .timeutil import parse_time

DEFAULT_SETTINGS: dict[str, dict[str, Any]] = {
    "reminders": {"timed": True, "timed_lead": 10, "task_start": True, "daily_summary": True,
                  "summary_time": "08:00", "pomodoro": True, "sound": True},
    "pomodoro": {"focus": 25, "short_break": 5, "long_break": 15, "long_every": 4, "full_page": True},
    "app": {"close_to_tray": True, "autostart": True},
}

# 字段类型和取值范围：bool，(int, 最小, 最大)，"time"
RULES: dict[str, dict[str, Any]] = {
    "reminders": {"timed": bool, "timed_lead": (int, 0, 1440), "task_start": bool, "daily_summary": bool,
                  "summary_time": "time", "pomodoro": bool, "sound": bool},
    "pomodoro": {"focus": (int, 1, 180), "short_break": (int, 1, 60), "long_break": (int, 1, 120), "long_every": (int, 1, 12),
                 "full_page": bool},
    "app": {"close_to_tray": bool, "autostart": bool},
}

LABELS = {
    "timed_lead": "定时任务提前提醒分钟数", "summary_time": "当日概览时间", "focus": "专注分钟数",
    "short_break": "短休息分钟数", "long_break": "长休息分钟数", "long_every": "几次专注后长休息",
}


class SettingsError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("\n".join(errors))


def validate_settings(data: Any) -> dict[str, dict[str, Any]]:
    """缺少的字段用默认值补齐，类型或范围不对时报错。"""
    if not isinstance(data, dict):
        raise SettingsError(["设置必须是对象"])
    result = copy.deepcopy(DEFAULT_SETTINGS)
    errors: list[str] = []
    for section, rules in RULES.items():
        values = data.get(section, {})
        if not isinstance(values, dict):
            errors.append(f"{section}：必须是对象")
            continue
        for key, rule in rules.items():
            if key not in values:
                continue
            value = values[key]
            label = LABELS.get(key, key)
            if rule is bool:
                if not isinstance(value, bool):
                    errors.append(f"{section}.{key}：必须是 true 或 false")
                    continue
            elif rule == "time":
                try:
                    if parse_time(value) >= 24 * 60:
                        raise ValueError("不能是 24:00")
                except ValueError as exc:
                    errors.append(f"{label}：{exc}")
                    continue
            else:
                _, low, high = rule
                if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
                    errors.append(f"{label}：必须是 {low} 到 {high} 的整数")
                    continue
            result[section][key] = value
    if errors:
        raise SettingsError(errors)
    return result


def load_settings(path: str) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """返回 (设置, 问题列表)。文件有问题时使用默认值。"""
    data, warning = load_json(path, lambda: {})
    problems = [warning] if warning else []
    try:
        return validate_settings(data), problems
    except SettingsError as exc:
        return copy.deepcopy(DEFAULT_SETTINGS), problems + [f"settings.json 有错误，已使用默认设置：{'，'.join(exc.errors)}"]


def save_settings(path: str, settings: dict[str, Any]) -> dict[str, dict[str, Any]]:
    validated = validate_settings(settings)
    write_json_atomic(path, validated)
    return validated
