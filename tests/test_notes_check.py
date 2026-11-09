import unittest

from planner_core.notes_check import phase_table_issues
from planner_core.plan_spec import parse_plan
from tests.helpers import config

# config() 的阶段：A 为 2026-11-09 起 1 周，任务在周一 11/09 和周六 11/14
# B 延伸到 2026-11-22，每天都有任务


def plan_with(notes: str, **overrides):
    return parse_plan(config(**overrides), notes=notes)


class PhaseTableTest(unittest.TestCase):
    def test_table_matching_task_span_has_no_issues(self):
        notes = "| 阶段 | 时间 | 内容 |\n| --- | --- | --- |\n| A | 11/09–11/14 | 第一周 |\n| B | 11/16–11/22 | 第二周 |"
        self.assertEqual(phase_table_issues(plan_with(notes)), [])

    def test_whole_week_span_is_reported_when_tasks_end_earlier(self):
        notes = "| 阶段 | 时间 |\n| --- | --- |\n| A | 11/09–11/15 |\n| B | 11/16–11/22 |"
        self.assertEqual(phase_table_issues(plan_with(notes)),
                         ["正文阶段表「A」写的是 11/09–11/15，阶段内的任务在 11/09–11/14"])

    def test_events_count_as_tasks(self):
        events = [{"offset_days": 6, "time": "10:00", "title": "模考", "minutes": 60}]
        notes = "| 阶段 | 时间 |\n| --- | --- |\n| A | 11/09–11/15 |\n| B | 11/16–11/22 |"
        self.assertEqual(phase_table_issues(plan_with(notes, events=events)), [])

    def test_phase_without_tasks_uses_phase_dates(self):
        phases = [
            {"name": "A", "weeks": 1, "week": {"mon": [{"title": "学习 {ch}", "uses": "ch", "minutes": 60, "slot": "focus"}]}},
            {"name": "休息", "weeks": 1, "week": {}},
        ]
        notes = "| 阶段 | 时间 |\n| --- | --- |\n| A | 11/09–11/09 |\n| 休息 | 11/16–11/22 |"
        self.assertEqual(phase_table_issues(plan_with(notes, phases=phases)), [])

    def test_wrong_date_unknown_name_and_missing_phase(self):
        notes = "| 阶段 | 时间 |\n| --- | --- |\n| A | 11/10–11/14 |\n| C | 11/16–11/22 |"
        issues = phase_table_issues(plan_with(notes))
        self.assertIn("正文阶段表「A」写的是 11/10–11/14，阶段内的任务在 11/09–11/14", issues)
        self.assertIn("正文阶段表里的「C」不是计划里的阶段名", issues)
        self.assertIn("正文阶段表缺少阶段「B」（11/16–11/22）", issues)

    def test_other_tables_and_plain_text_are_ignored(self):
        notes = "| 星期 | 时间 |\n| --- | --- |\n| 周二 | 18:45–19:25 |\n\n冬季休业 12/28–1/3。"
        self.assertEqual(phase_table_issues(plan_with(notes)), [])


if __name__ == "__main__":
    unittest.main()
