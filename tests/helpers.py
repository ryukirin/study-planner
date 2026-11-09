from __future__ import annotations

import copy
import json
import os
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES_DIR = os.path.join(PROJECT_ROOT, "examples")

# 2026-11-09 是周一
BASE_CONFIG = {
    "schema": 1,
    "id": "demo",
    "name": "演示计划",
    "start_date": "2026-11-09",
    "deadline": "2026-11-22",
    "sequences": {"ch": {"items": ["第1章", "第2章", "第3章"]}},
    "phases": [
        {
            "name": "A",
            "weeks": 1,
            "week": {
                "mon": [{"title": "学习 {ch}", "uses": "ch", "minutes": 60, "slot": "focus"}],
                "sat": [{"title": "周六长练习", "minutes": 120, "slot": "focus"}],
            },
        },
        {"name": "B", "week": {"daily": [{"title": "复习", "minutes": 15, "slot": "commute"}]}},
    ],
}

BASE_PROFILE = {
    "version": 1,
    "buffer_minutes": 5,
    "weekly": {
        key: [
            {"start": "07:30", "end": "08:00", "tag": "commute", "label": "通勤"},
            {"start": "20:00", "end": "22:00", "tag": "focus", "label": "晚上"},
        ]
        for key in ("mon", "tue", "wed", "thu", "fri")
    }
    | {"sat": [{"start": "14:00", "end": "17:00", "tag": "focus"}], "sun": []},
    "exceptions": [],
}


def config(**overrides) -> dict:
    data = copy.deepcopy(BASE_CONFIG)
    data.update(overrides)
    return data


def plan_markdown(data: dict, notes: str = "# 演示计划\n\n说明文字。") -> str:
    return f"{notes}\n\n```study-plan\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```\n"


class TempHome:
    """临时数据目录，写入 profile 和计划文件。"""

    def __init__(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.path = self._dir.name
        os.makedirs(os.path.join(self.path, "plans"), exist_ok=True)

    def write_profile(self, data: dict | None = None) -> None:
        with open(os.path.join(self.path, "profile.json"), "w", encoding="utf-8") as handle:
            json.dump(data or BASE_PROFILE, handle, ensure_ascii=False)

    def write_plan(self, filename: str, data: dict | str) -> str:
        path = os.path.join(self.path, "plans", filename)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(data if isinstance(data, str) else plan_markdown(data))
        return path

    def cleanup(self) -> None:
        self._dir.cleanup()
