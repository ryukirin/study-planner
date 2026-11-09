import unittest

from planner_core.notes_check import phase_table_issues
from planner_core.plan_spec import parse_plan
from tests.helpers import config

# config() 的阶段：A 为 2026-11-09 起 1 周，B 延伸到 2026-11-22


def plan_with(notes: str):
    return parse_plan(config(), notes=notes)


class PhaseTableTest(unittest.TestCase):
    def test_matching_table_has_no_issues(self):
        notes = "| 阶段 | 时间 | 内容 |\n| --- | --- | --- |\n| A | 11/09–11/15 | 第一周 |\n| B | 11/16–11/22 | 第二周 |"
        self.assertEqual(phase_table_issues(plan_with(notes)), [])

    def test_wrong_date_unknown_name_and_missing_phase(self):
        notes = "| 阶段 | 时间 |\n| --- | --- |\n| A | 11/09–11/14 |\n| C | 11/16–11/22 |"
        issues = phase_table_issues(plan_with(notes))
        self.assertIn("正文阶段表「A」写的是 11/09–11/14，计划里是 11/9–11/15", issues)
        self.assertIn("正文阶段表里的「C」不是计划里的阶段名", issues)
        self.assertIn("正文阶段表缺少阶段「B」（11/16–11/22）", issues)

    def test_other_tables_and_plain_text_are_ignored(self):
        notes = "| 星期 | 时间 |\n| --- | --- |\n| 周二 | 18:45–19:25 |\n\n冬季休业 12/28–1/3。"
        self.assertEqual(phase_table_issues(plan_with(notes)), [])


if __name__ == "__main__":
    unittest.main()
