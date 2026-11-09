import contextlib
import io
import json
import os
import shutil
import unittest

import planner_cli
from tests.helpers import EXAMPLES_DIR, TempHome, config, plan_markdown


def run_cli(*argv: str) -> tuple[int, str]:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = planner_cli.main(list(argv))
    return code, buffer.getvalue()


class ExamplesTest(unittest.TestCase):
    """两个示例计划并行：都能通过校验，且全部任务能排入示例空闲时间。"""

    def setUp(self):
        self.home = TempHome()
        shutil.copy(os.path.join(EXAMPLES_DIR, "profile-sample.json"), os.path.join(self.home.path, "profile.json"))
        for name in ("toeic-700-sample.md", "java-basics-sample.md"):
            shutil.copy(os.path.join(EXAMPLES_DIR, name), os.path.join(self.home.path, "plans", name))

    def tearDown(self):
        self.home.cleanup()

    def test_check_examples(self):
        code, out = run_cli("--home", self.home.path, "--today", "2026-11-08", "check", "--days", "7")
        self.assertEqual(code, 0, out)
        self.assertIn("所有任务都能排入空闲时间", out)
        self.assertNotIn("警告", out)
        self.assertIn("20:30-21:30  [Java 入门] Java：开发环境与第一个程序", out)
        self.assertIn("21:35-22:15  [TOEIC 700] Part 5/6 练习 第 1 回", out)

    def test_status_json(self):
        code, out = run_cli("--home", self.home.path, "--today", "2026-11-12", "status", "--json")
        self.assertEqual(code, 0)
        data = json.loads(out)
        java = next(plan for plan in data["plans"] if plan["id"] == "java-basics-sample")
        self.assertEqual(java["state"], "进行中")
        self.assertEqual(java["current_phase"], "语法基础")
        self.assertEqual([item["date"] for item in java["overdue"]], ["2026-11-09", "2026-11-10", "2026-11-11"])
        self.assertEqual(java["sequences"][0]["remaining_items"][0], "开发环境与第一个程序")

    def test_draft_with_errors_returns_1(self):
        bad = config()
        bad["phases"][0]["weeks"] = 5
        draft = os.path.join(self.home.path, "draft.md")
        with open(draft, "w", encoding="utf-8") as handle:
            handle.write(plan_markdown(bad))
        code, out = run_cli("--home", self.home.path, "check", draft)
        self.assertEqual(code, 1)
        self.assertIn("超出 deadline", out)

    def test_draft_overflow_reported(self):
        heavy = config(id="heavy", priority=3)
        heavy["phases"][0]["week"]["mon"][0]["minutes"] = 120
        draft = os.path.join(self.home.path, "draft.md")
        with open(draft, "w", encoding="utf-8") as handle:
            handle.write(plan_markdown(heavy))
        code, out = run_cli("--home", self.home.path, "--today", "2026-11-08", "check", draft, "--days", "1")
        self.assertEqual(code, 0)
        self.assertIn("未排入：", out)
        self.assertIn("2026-11-09 周一  [演示计划] 学习 第1章  120 分钟", out)

    def test_several_drafts_checked_together(self):
        first = os.path.join(self.home.path, "a.md")
        second = os.path.join(self.home.path, "b.md")
        with open(first, "w", encoding="utf-8") as handle:
            handle.write(plan_markdown(config(id="draft-a", name="草稿 A")))
        with open(second, "w", encoding="utf-8") as handle:
            handle.write(plan_markdown(config(id="draft-b", name="草稿 B", priority=2)))
        code, out = run_cli("--home", self.home.path, "--today", "2026-11-08", "check", first, second, "--days", "1")
        self.assertEqual(code, 0, out)
        self.assertIn("id draft-a，作为新计划", out)
        self.assertIn("id draft-b，作为新计划", out)
        self.assertIn("[草稿 A] 学习 第1章", out)
        self.assertIn("[草稿 B] 学习 第1章", out)

        code, out = run_cli("--home", self.home.path, "check", first, first)
        self.assertEqual(code, 1)
        self.assertIn("和前面的草稿重复", out)

    def test_short_plan_preview_and_tasks(self):
        shutil.copy(os.path.join(EXAMPLES_DIR, "weekend-shopping-sample.md"), os.path.join(self.home.path, "plans"))
        code, out = run_cli("--home", self.home.path, "--today", "2026-11-13", "add-task", "--title", "给房东打电话",
                            "--date", "2026-11-14", "--time", "12:00", "--minutes", "10", "--remind", "off")
        self.assertEqual(code, 0, out)
        self.assertIn("已添加临时任务：2026-11-14 12:00  给房东打电话", out)
        code, out = run_cli("--home", self.home.path, "--today", "2026-11-13", "check", "--from", "2026-11-14", "--days", "1")
        self.assertEqual(code, 0, out)
        self.assertIn("12:00-12:10  [临时任务] 给房东打电话  10 分钟（定时）", out)
        self.assertIn("13:00-14:30  [周末逛街] 逛服装店 A（示例）  90 分钟（定时）  @表参道", out)
        self.assertNotIn("定时任务重叠", out)
        code, out = run_cli("--home", self.home.path, "--today", "2026-11-13", "tasks")
        task_id = out.strip().split("id=")[-1]
        code, out = run_cli("--home", self.home.path, "delete-task", "--id", task_id)
        self.assertEqual(code, 0, out)
        code, out = run_cli("--home", self.home.path, "add-task", "--title", "x", "--date", "2026-02-30")
        self.assertEqual(code, 1)

    def test_paths(self):
        code, out = run_cli("--home", self.home.path, "paths")
        self.assertEqual(code, 0)
        self.assertIn(os.path.join(self.home.path, "plans"), out)


if __name__ == "__main__":
    unittest.main()
