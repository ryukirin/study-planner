import unittest
from datetime import date

from planner_core.plan_spec import PlanError, expand_plan, extract_block, parse_plan, render_text
from tests.helpers import config, plan_markdown


def errors_of(data: dict) -> list[str]:
    with unittest.TestCase().assertRaises(PlanError) as ctx:
        parse_plan(data)
    return ctx.exception.errors


class ExtractBlockTest(unittest.TestCase):
    def test_returns_config_and_notes(self):
        data, notes = extract_block(plan_markdown(config(), notes="# 标题\n\n参考来源"))
        self.assertEqual(data["id"], "demo")
        self.assertIn("参考来源", notes)
        self.assertNotIn("study-plan", notes)

    def test_missing_block(self):
        with self.assertRaises(PlanError) as ctx:
            extract_block("# 没有代码块")
        self.assertIn("没有找到", ctx.exception.errors[0])

    def test_unterminated_block(self):
        with self.assertRaises(PlanError) as ctx:
            extract_block("```study-plan\n{}\n")
        self.assertIn("缺少结尾", ctx.exception.errors[0])

    def test_json_error_reports_file_line(self):
        with self.assertRaises(PlanError) as ctx:
            extract_block("标题\n\n```study-plan\n{\n  \"id\": \"x\",\n}\n```")
        self.assertIn("文件第 6 行", ctx.exception.errors[0])

    def test_two_blocks_rejected(self):
        text = "```study-plan\n{}\n```\n```study-plan\n{}\n```"
        with self.assertRaises(PlanError):
            extract_block(text)


class ValidationTest(unittest.TestCase):
    def test_base_config_is_valid(self):
        plan = parse_plan(config())
        self.assertEqual(plan.start, date(2026, 11, 9))
        self.assertEqual(plan.end, date(2026, 11, 22))
        self.assertEqual([phase.end for phase in plan.phases], [date(2026, 11, 15), date(2026, 11, 22)])

    def test_missing_weekday_means_rest_day(self):
        expansion = expand_plan(parse_plan(config()))
        self.assertNotIn(date(2026, 11, 10), expansion.by_date)  # 第一阶段周二没有模板

    def test_unknown_weekday_key(self):
        data = config()
        data["phases"][0]["week"]["thur"] = []
        self.assertTrue(any("thur" in error for error in errors_of(data)))

    def test_non_last_phase_requires_weeks(self):
        data = config()
        del data["phases"][0]["weeks"]
        self.assertTrue(any("phases[0].weeks" in error for error in errors_of(data)))

    def test_lone_braces_rejected(self):
        data = config()
        data["phases"][0]["week"]["sat"][0]["title"] = "用 {} 标记"
        self.assertTrue(any("花括号" in error for error in errors_of(data)))

    def test_escaped_braces_render_literally(self):
        data = config()
        data["phases"][0]["week"]["sat"][0]["title"] = "格式 {{n}} 第 {n} 次"
        expansion = expand_plan(parse_plan(data))
        self.assertEqual(expansion.by_date[date(2026, 11, 14)][0].title, "格式 {n} 第 1 次")

    def test_sequence_placeholder_requires_uses(self):
        data = config()
        data["phases"][0]["week"]["sat"][0]["title"] = "复习 {ch}"
        self.assertTrue(any("uses" in error for error in errors_of(data)))

    def test_unknown_placeholder(self):
        data = config()
        data["phases"][0]["week"]["sat"][0]["title"] = "{foo}"
        self.assertTrue(any("{foo}" in error for error in errors_of(data)))

    def test_phases_longer_than_deadline(self):
        data = config()
        data["phases"][0]["weeks"] = 3
        self.assertTrue(any("超出 deadline" in error for error in errors_of(data)))

    def test_last_phase_shorter_than_deadline(self):
        data = config()
        data["phases"][1]["weeks"] = 1
        data["deadline"] = "2026-11-29"
        self.assertTrue(any("早于 deadline" in error for error in errors_of(data)))

    def test_without_deadline_last_phase_needs_weeks(self):
        data = config()
        del data["deadline"]
        self.assertTrue(any("没有 deadline" in error for error in errors_of(data)))
        data["phases"][1]["weeks"] = 2
        self.assertEqual(parse_plan(data).end, date(2026, 11, 29))

    def test_typo_in_task_key_and_bad_minutes(self):
        data = config()
        data["phases"][0]["week"]["sat"][0] = {"title": "x", "minute": 30}
        errors = errors_of(data)
        self.assertTrue(any("未知字段 minute" in error for error in errors))
        self.assertTrue(any(".minutes" in error for error in errors))

    def test_collects_multiple_errors(self):
        data = config(schema=2, priority=0, color="red")
        self.assertGreaterEqual(len(errors_of(data)), 3)

    def test_event_out_of_range(self):
        data = config(events=[{"date": "2026-12-01", "title": "模考", "minutes": 120}])
        self.assertTrue(any("不在计划范围" in error for error in errors_of(data)))

    def test_range_label_placeholders(self):
        data = config(sequences={"ch": {"items": ["a"]}, "kf": {"range": {"from": 1, "to": 50, "step": 20}, "label": "金フレ {from:03d}-{to:03d}"}})
        plan = parse_plan(data)
        self.assertEqual(plan.sequences["kf"].items, ["金フレ 001-020", "金フレ 021-040", "金フレ 041-050"])

    def test_bad_range_label(self):
        data = config(sequences={"ch": {"items": ["a"]}, "kf": {"range": {"from": 1, "to": 5}, "label": "{start}"}})
        self.assertTrue(any("sequences.kf.label" in error for error in errors_of(data)))


class ExpansionTest(unittest.TestCase):
    def test_weekday_structure_follows_real_dates(self):
        expansion = expand_plan(parse_plan(config()))
        saturday_tasks = [s for s in expansion.all_sessions() if s.title == "周六长练习"]
        self.assertTrue(saturday_tasks)
        self.assertTrue(all(s.day.weekday() == 5 for s in saturday_tasks))

    def test_sequence_skip_when_exhausted(self):
        data = config(phases=[{"name": "A", "week": {"daily": [{"title": "{ch}", "uses": "ch", "minutes": 30}]}}])
        expansion = expand_plan(parse_plan(data))
        titles = [s.title for s in expansion.all_sessions()]
        self.assertEqual(titles, ["第1章", "第2章", "第3章"])
        usage = expansion.usage["ch"]
        self.assertEqual((usage.used, usage.skipped, usage.exhausted_on), (3, 11, date(2026, 11, 12)))

    def test_sequence_repeat(self):
        data = config(
            sequences={"ch": {"items": ["a", "b"], "on_exhausted": "repeat"}},
            phases=[{"name": "A", "week": {"daily": [{"title": "{ch}", "uses": "ch", "minutes": 30}]}}],
        )
        titles = [s.title for s in expand_plan(parse_plan(data)).all_sessions()]
        self.assertEqual(titles[:5], ["a", "b", "a", "b", "a"])
        self.assertEqual(len(titles), 14)

    def test_counter_week_and_phase_placeholders(self):
        data = config()
        data["phases"][1]["week"]["daily"][0]["title"] = "{phase} 第{week}周 第{n}次"
        sessions = expand_plan(parse_plan(data)).by_date
        self.assertEqual(sessions[date(2026, 11, 16)][0].title, "B 第2周 第1次")
        self.assertEqual(sessions[date(2026, 11, 17)][0].title, "B 第2周 第2次")

    def test_events_and_milestones(self):
        data = config(
            events=[{"offset_days": 5, "title": "小测", "minutes": 45, "slot": "focus"}],
            milestones=[{"date": "2026-11-22", "text": "完成"}],
        )
        expansion = expand_plan(parse_plan(data))
        saturday = expansion.by_date[date(2026, 11, 14)]
        self.assertEqual([s.title for s in saturday], ["周六长练习", "小测"])
        self.assertEqual(saturday[1].kind, "event")
        self.assertEqual(expansion.milestones[date(2026, 11, 22)][0].text, "完成")

    def test_milestone_tasks_field(self):
        plan = parse_plan(config(milestones=[{"date": "2026-11-22", "text": "完成", "tasks": ["学习", "ch"]}]))
        self.assertEqual(plan.milestones[0].tasks, ["学习", "ch"])
        self.assertEqual(parse_plan(config(milestones=[{"date": "2026-11-22", "text": "完成"}])).milestones[0].tasks, [])
        errors = errors_of(config(milestones=[{"date": "2026-11-22", "text": "完成", "tasks": "学习"}]))
        self.assertTrue(any("milestones[0].tasks" in error for error in errors))

    def test_uid_independent_of_text(self):
        first = config()
        second = config()
        second["phases"][0]["week"]["sat"][0]["title"] = "改过的标题"
        second["phases"][0]["week"]["sat"][0]["detail"] = "新增说明"
        uids_a = [s.uid for s in expand_plan(parse_plan(first)).all_sessions()]
        uids_b = [s.uid for s in expand_plan(parse_plan(second)).all_sessions()]
        self.assertEqual(uids_a, uids_b)

    def test_render_text_leaves_unknown(self):
        self.assertEqual(render_text("{a}-{b}", {"a": 1}), "1-{b}")


if __name__ == "__main__":
    unittest.main()
