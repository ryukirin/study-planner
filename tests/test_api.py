import json
import os
import unittest
from datetime import date, datetime

from planner_ui import PlannerApi
from tests.helpers import BASE_PROFILE, TempHome, config


class PlannerApiTest(unittest.TestCase):
    def setUp(self):
        self.home = TempHome()
        self.home.write_profile()
        self.home.write_plan("demo.md", config())
        self.api = PlannerApi(self.home.path, today=date(2026, 11, 17))

    def tearDown(self):
        self.home.cleanup()

    def test_state_is_json_serializable(self):
        state = self.api.state("2026-11-09")
        json.dumps(state, ensure_ascii=False)
        self.assertEqual(state["selected"], "2026-11-09")
        self.assertEqual(state["today"], "2026-11-17")
        group = state["day"]["groups"][1]
        self.assertEqual(group["window"]["label"], "晚上")
        self.assertEqual(group["tasks"][0]["title"], "学习 第1章")
        self.assertEqual(group["tasks"][0]["start"], "20:00")
        self.assertEqual(group["free"], 60)
        self.assertEqual(state["calendar"]["2026-11-09"], "overdue")
        self.assertEqual(state["plans"][0]["sequences"][0]["next"], ["第1章", "第2章", "第3章"])

    def test_range_days_for_week_and_month_views(self):
        result = self.api.range_days("2026-11-09", 7)
        self.assertTrue(result["ok"])
        json.dumps(result, ensure_ascii=False)
        days = result["days"]
        self.assertEqual([day["date"] for day in days], [f"2026-11-{n:02d}" for n in range(9, 16)])
        self.assertEqual([day["total"] for day in days], [1, 0, 0, 0, 0, 1, 0])
        task = days[0]["tasks"][0]
        self.assertEqual((task["title"], task["start"], task["window"]["label"], task["unplaced"]), ("学习 第1章", "20:00", "晚上", False))
        self.assertEqual(days[5]["weekday"], "周六")
        self.api.set_done(task["uid"], True)
        self.assertEqual(self.api.range_days("2026-11-09", 1)["days"][0]["done"], 1)
        self.assertEqual(len(self.api.range_days("2026-11-01", 500)["days"]), 42)
        self.assertFalse(self.api.range_days("11/9", 7)["ok"])

    def test_phase_dates_include_task_span(self):
        phase = self.api.state()["plans"][0]["phases"][0]
        self.assertEqual((phase["start"], phase["end"], phase["days"]), ("2026-11-09", "2026-11-15", 7))
        self.assertEqual((phase["task_start"], phase["task_end"]), ("2026-11-09", "2026-11-14"))

    def test_invalid_selected_falls_back_to_today(self):
        self.assertEqual(self.api.state("not-a-date")["selected"], "2026-11-17")

    def test_set_done_by_uid(self):
        uid = self.api.state("2026-11-09")["day"]["groups"][1]["tasks"][0]["uid"]
        self.assertEqual(self.api.set_done(uid, True), {"ok": True})
        state = self.api.state("2026-11-09")
        task = state["day"]["groups"][1]["tasks"][0]
        self.assertTrue(task["done"])
        self.assertTrue(task["done_at"])
        self.assertEqual(task["uses"], {"seq": "ch", "item": "第1章"})
        self.assertEqual(task["focus_minutes"], 0)
        self.assertEqual(state["calendar"]["2026-11-09"], "done")
        self.assertFalse(self.api.set_done("demo|2026-11-09|nope", True)["ok"])

    def test_save_profile_ignores_display_fields_and_validates(self):
        profile = self.api.state()["profile"]
        profile["weekly"]["mon"] = [{"start": "21:00", "end": "20:00", "tag": "focus", "label": ""}]
        result = self.api.save_profile(profile)
        self.assertFalse(result["ok"])
        self.assertTrue(any("开始时间必须早于结束时间" in error for error in result["errors"]))
        profile["weekly"]["mon"] = [{"start": "19:00", "end": "20:00", "tag": "focus", "label": "提前"}]
        self.assertEqual(self.api.save_profile(profile), {"ok": True})
        with open(os.path.join(self.home.path, "profile.json"), encoding="utf-8") as handle:
            saved = json.load(handle)
        self.assertNotIn("standard_tags", saved)
        self.assertEqual(self.api.state("2026-11-09")["day"]["groups"][0]["tasks"][0]["start"], "19:00")

    def test_poll_detects_external_change(self):
        self.assertFalse(self.api.poll()["changed"])
        self.home.write_plan("other.md", config(id="other", name="另一个计划"))
        self.assertTrue(self.api.poll()["changed"])
        self.assertEqual(len(self.api.state()["plans"]), 2)
        self.assertFalse(self.api.poll()["changed"])

    def test_open_file_only_allows_known_files(self):
        self.assertFalse(self.api.open_file("C:/Windows/notepad.exe")["ok"])
        self.assertFalse(self.api.open_url("file:///C:/")["ok"])

    def test_banner_for_default_profile(self):
        os.remove(os.path.join(self.home.path, "profile.json"))
        api = PlannerApi(self.home.path, today=date(2026, 11, 17))
        banner = api.state()["banner"]
        self.assertEqual(banner[0]["level"], "info")
        self.assertEqual(banner[0]["view"], "profile")


if __name__ == "__main__":
    unittest.main()


class DayOrderTest(unittest.TestCase):
    """日程页拖动任务。2026-11-09 周一：通勤 07:30–08:00，晚上 20:00–22:00，间隔 5 分钟。"""

    def setUp(self):
        self.home = TempHome()
        self.home.write_profile()
        week = {"mon": [
            {"title": "精读", "minutes": 50, "slot": "focus"},
            {"title": "听力", "minutes": 20, "slot": "focus"},
            {"title": "单词", "minutes": 15, "slot": "commute"},
        ]}
        self.plan = config(sequences={}, phases=[{"name": "A", "week": week}])
        self.home.write_plan("demo.md", self.plan)
        self.api = PlannerApi(self.home.path, today=date(2026, 11, 9))

    def tearDown(self):
        self.home.cleanup()

    def day(self):
        return self.api.state("2026-11-09")["day"]

    def titles(self, group):
        return [(task["title"], task["start"]) for task in self.day()["groups"][group]["tasks"]]

    def uid(self, title):
        return next(task["uid"] for group in self.day()["groups"] for task in group["tasks"] if task["title"] == title)

    def test_reorder_within_window_and_reset(self):
        self.assertEqual(self.titles(1), [("精读", "20:00"), ("听力", "20:55")])
        self.assertFalse(self.day()["manual_order"])
        self.assertEqual(self.api.move_session(self.uid("听力"), "20:00", 0), {"ok": True, "changed": True})
        self.assertEqual(self.titles(1), [("听力", "20:00"), ("精读", "20:25")])
        self.assertTrue(self.day()["manual_order"])
        self.assertFalse(self.api.state("2026-11-16")["day"]["manual_order"])
        # 重新启动后顺序保留，计划文件没有被改动
        api = PlannerApi(self.home.path, today=date(2026, 11, 9))
        self.assertEqual([task["title"] for task in api.state("2026-11-09")["day"]["groups"][1]["tasks"]], ["听力", "精读"])
        self.assertEqual(self.api.reset_day_order("2026-11-09"), {"ok": True})
        self.assertEqual(self.titles(1), [("精读", "20:00"), ("听力", "20:55")])
        self.assertFalse(self.day()["manual_order"])

    def test_same_position_is_not_saved(self):
        self.assertEqual(self.api.move_session(self.uid("精读"), "20:00", 0), {"ok": True, "changed": False})
        self.assertFalse(self.day()["manual_order"])
        self.assertFalse(os.path.exists(os.path.join(self.home.path, "day_order.json")))

    def test_move_to_other_window(self):
        # 换时间段不受 slot 限制：单词（commute）拖到晚上的末尾
        self.assertTrue(self.api.move_session(self.uid("单词"), "20:00", 9)["changed"])
        self.assertEqual(self.titles(0), [])
        self.assertEqual(self.titles(1), [("精读", "20:00"), ("听力", "20:55"), ("单词", "21:20")])

    def test_rejects_when_window_is_too_small(self):
        result = self.api.move_session(self.uid("精读"), "07:30", 0)
        self.assertFalse(result["ok"])
        self.assertIn("放不下这个任务", result["error"])
        # 听力 20 分钟本身放得进通勤时间段，但会把 单词 挤出去
        result = self.api.move_session(self.uid("听力"), "07:30", 0)
        self.assertFalse(result["ok"])
        self.assertIn("单词", result["error"])
        self.assertFalse(self.day()["manual_order"])
        self.assertFalse(self.api.move_session(self.uid("听力"), "09:00", 0)["ok"])
        self.assertFalse(self.api.move_session("demo|2026-11-09|nope", "20:00", 0)["ok"])

    def test_fixed_task_cannot_move(self):
        self.api.add_task({"title": "电话", "date": "2026-11-09", "time": "20:00", "minutes": 10})
        uid = self.day()["fixed"][0]["uid"]
        self.assertFalse(self.api.move_session(uid, "20:00", 1)["ok"])
        # 其他任务避开定时任务，仍然可以调整顺序
        self.assertTrue(self.api.move_session(self.uid("听力"), "20:00", 0)["changed"])
        self.assertEqual(self.titles(1), [("听力", "20:15"), ("精读", "20:40")])

    def test_stale_entries_fall_back_to_auto(self):
        self.api.move_session(self.uid("听力"), "20:00", 0)
        # 计划重排后任务 id 变了：原来的条目失效，新任务按自动规则排
        self.plan["phases"][0]["week"] = {"daily": [{"title": "写作", "minutes": 30, "slot": "focus"}]}
        self.home.write_plan("demo.md", self.plan)
        self.assertTrue(self.api.poll()["changed"])
        self.assertEqual(self.titles(1), [("写作", "20:00")])


class ReplanApiTest(unittest.TestCase):
    """详情里的“完成并重排”和“排到明天”。2026-11-09 周一晚上 20:00–22:00：精读 20:00–20:50，听力 20:55–21:15。"""

    def setUp(self):
        self.home = TempHome()
        self.home.write_profile()
        week = {"weekdays": [
            {"title": "精读", "minutes": 50, "slot": "focus"},
            {"title": "听力", "minutes": 20, "slot": "focus"},
        ]}
        self.home.write_plan("demo.md", config(sequences={}, phases=[{"name": "A", "week": week}]))
        self.today = date(2026, 11, 10)
        self.api = PlannerApi(self.home.path, today=self.today)

    def tearDown(self):
        self.home.cleanup()

    def at(self, text):
        return datetime(2026, 11, 10, *map(int, text.split(":")))

    def tasks(self, day):
        state = self.api.state(day)["day"]
        return [(task["title"], task["start"], task["end"]) for group in state["groups"] for task in group["tasks"]]

    def uid(self, day, title):
        state = self.api.state(day)
        pools = [task for group in state["day"]["groups"] for task in group["tasks"]] + state["day"]["fixed"] + state["day"]["overflow"] + state["overdue"]
        return next(task["uid"] for task in pools if task["title"] == title and task["date"] == day)

    def test_finish_and_replan_uses_current_time(self):
        self.assertEqual(self.tasks("2026-11-10"), [("精读", "20:00", "20:50"), ("听力", "20:55", "21:15")])
        result = self.api.finish_and_replan(self.uid("2026-11-10", "精读"), now=self.at("20:20"))
        self.assertEqual(result, {"ok": True, "replanned": True, "time": "20:20"})
        # 精读原定 20:00 开始，20:20 完成：记为 20:00–20:20，听力接着排
        self.assertEqual(self.tasks("2026-11-10"), [("精读", "20:00", "20:20"), ("听力", "20:20", "20:40")])
        day = self.api.state("2026-11-10")["day"]
        self.assertTrue(day["manual_order"])
        self.assertEqual(day["groups"][1]["tasks"][0]["done_at"], "2026-11-10T20:20:00")
        # 重新启动后保留，“恢复自动”回到原来的时间
        api = PlannerApi(self.home.path, today=self.today)
        self.assertEqual(api.state("2026-11-10")["day"]["groups"][1]["tasks"][1]["start"], "20:20")
        self.api.reset_day_order("2026-11-10")
        self.assertEqual(self.tasks("2026-11-10"), [("精读", "20:00", "20:50"), ("听力", "20:55", "21:15")])

    def test_passed_windows_and_overflow_reasons(self):
        week = {"weekdays": [
            {"title": "精读", "minutes": 50, "slot": "focus"},
            {"title": "听力", "minutes": 20, "slot": "commute"},
            {"title": "健身", "minutes": 40, "slot": "gym"},
        ]}
        self.home.write_plan("demo.md", config(sequences={}, phases=[{"name": "A", "week": week}]))
        self.api.poll()
        day = self.api.state("2026-11-10")["day"]
        self.assertEqual([group["passed"] for group in day["groups"]], [False, False])
        self.assertIsNone(day["replan_at"])
        self.assertEqual([(task["title"], task["reason"]) for task in day["overflow"]], [("健身", "这一天没有“gym”类型的空闲时间段")])
        # 20:20 重排：通勤时间段已经过去，听力放不下
        self.api.finish_and_replan(self.uid("2026-11-10", "精读"), now=self.at("20:20"))
        day = self.api.state("2026-11-10")["day"]
        self.assertEqual(day["replan_at"], "20:20")
        self.assertEqual([group["passed"] for group in day["groups"]], [True, False])
        reasons = {task["title"]: task["reason"] for task in day["overflow"]}
        self.assertEqual(reasons["听力"], "20:20 起重排时，通勤 07:30–08:00 剩下的时间不够 20 分钟")

    def test_finish_on_another_day_frees_that_day(self):
        uid = self.uid("2026-11-11", "精读")
        result = self.api.finish_and_replan(uid, now=self.at("20:20"))
        self.assertEqual((result["ok"], result["replanned"]), (True, False))
        day = self.api.state("2026-11-11")["day"]
        self.assertFalse(day["manual_order"])
        # 明天的精读今天做完了：不占明天的时间，听力前移，后天的精读提前到明天
        self.assertEqual(self.moved("2026-11-11"), [("听力", "20:00", None), ("精读", "20:25", 12)])
        self.assertEqual([(task["title"], task["early"], task["start"]) for task in day["early"]], [("精读", True, None)])
        self.assertEqual((day["total"], day["done"]), (3, 1))
        brief = self.api.range_days("2026-11-11", 1)["days"][0]
        self.assertEqual([(task["title"], task["early"]) for task in brief["tasks"]], [("精读", True), ("听力", False), ("精读", False)])
        self.assertEqual((brief["total"], brief["done"]), (3, 1))
        # 取消完成后回到原来的时间
        self.api.set_done(uid, False)
        self.assertEqual(self.moved("2026-11-11"), [("精读", "20:00", None), ("听力", "20:55", None)])

    def test_early_done_pulls_the_same_series_forward_and_undo_restores(self):
        uid = self.uid("2026-11-12", "精读")
        # 11-12 之后还有 11-13、16、17、18、19、20 六项精读，各前移一格
        self.assertEqual(self.api.set_done(uid, True), {"ok": True, "shifted": 6})
        self.assertEqual(self.moved("2026-11-12"), [("听力", "20:00", None), ("精读", "20:25", 13)])
        self.assertEqual(self.moved("2026-11-13"), [("听力", "20:00", None), ("精读", "20:25", 16)])
        self.assertEqual(self.moved("2026-11-19"), [("听力", "20:00", None), ("精读", "20:25", 20)])
        self.assertEqual(self.moved("2026-11-20"), [("听力", "20:00", None)])
        # 重新启动后保留，取消完成时移回
        api = PlannerApi(self.home.path, today=self.today)
        self.assertEqual(api.set_done(uid, False), {"ok": True, "shifted": 6})
        self.assertEqual(api.state()["moved_total"], 0)
        self.assertEqual(api.state("2026-11-20")["day"]["total"], 2)

    def test_undo_pull_skips_tasks_changed_afterwards(self):
        uid = self.uid("2026-11-12", "精读")
        self.api.set_done(uid, True)
        pulled = next(task["uid"] for group in self.api.state("2026-11-13")["day"]["groups"] for task in group["tasks"] if task["title"] == "精读")
        self.api.postpone_session(pulled, now=self.at("12:00"))  # 前移到 11-13 的那一项又被排到 11-14
        self.assertEqual(self.api.set_done(uid, False), {"ok": True, "shifted": 5})
        self.assertEqual(self.api.state()["moved_total"], 1)

    def test_checkbox_on_the_same_day_or_fixed_task_does_not_pull(self):
        # 当天勾完成不改当天的时间，需要时用“完成并重排”
        self.assertEqual(self.api.set_done(self.uid("2026-11-10", "精读"), True), {"ok": True})
        self.assertEqual(self.tasks("2026-11-10"), [("精读", "20:00", "20:50"), ("听力", "20:55", "21:15")])
        # 定时任务提前完成后不占时间，后面的不前移
        week = {"weekdays": [{"title": "晨读", "minutes": 10, "time": "07:30"}, {"title": "听力", "minutes": 20, "slot": "focus"}]}
        self.home.write_plan("demo.md", config(sequences={}, phases=[{"name": "A", "week": week}]))
        self.api.poll()
        self.assertEqual(self.api.set_done(self.uid("2026-11-12", "晨读"), True), {"ok": True})
        self.assertEqual(self.api.state()["moved_total"], 0)

    def test_milestone_follows_only_related_tasks(self):
        milestones = [
            {"date": "2026-11-13", "text": "精读第一轮完成"},
            {"date": "2026-11-13", "text": "第一周目标", "tasks": ["听力"]},
            {"date": "2026-11-20", "text": "第二周目标"},
        ]
        week = {"weekdays": [{"title": "精读：第 {n} 篇", "minutes": 50, "slot": "focus"},
                             {"title": "听力", "minutes": 20, "slot": "focus"}]}
        self.home.write_plan("demo.md", config(sequences={}, phases=[{"name": "A", "week": week}], milestones=milestones))
        self.api.poll()
        shown = lambda: [(item["text"], item["date"], item["moved_from"], item["done"], item["follows"])
                         for item in self.api.state()["plans"][0]["milestones"]]
        self.assertEqual(shown(), [
            ("精读第一轮完成", "2026-11-13", None, False, ["精读"]),
            ("第一周目标", "2026-11-13", None, False, ["听力"]),
            ("第二周目标", "2026-11-20", None, False, []),
        ])
        # 11-13 的听力推到 11-14：只有跟随听力的里程碑移动
        self.api.postpone_session(self.uid("2026-11-13", "听力"), now=self.at("12:00"))
        self.assertEqual(shown()[:2], [
            ("精读第一轮完成", "2026-11-13", None, False, ["精读"]),
            ("第一周目标", "2026-11-14", "2026-11-13", False, ["听力"]),
        ])
        self.assertEqual([item["text"] for item in self.api.state("2026-11-14")["day"]["milestones"]], ["第一周目标"])
        self.assertEqual(self.api.range_days("2026-11-14", 1)["days"][0]["milestones"][0]["moved_from"], "2026-11-13")
        # 精读全部做完（从后往前勾，不触发前移）：里程碑已达成，日期是完成的那天
        titles = {13 - offset: f"精读：第 {5 - offset} 篇" for offset in range(5)}
        for day in sorted(titles, reverse=True):
            self.api.set_done(self.uid(f"2026-11-{day:02d}", titles[day]), True)
        first = self.api.state()["plans"][0]["milestones"][0]
        self.assertEqual((first["text"], first["date"], first["moved_from"], first["done"], first["past"]),
                         ("精读第一轮完成", "2026-11-10", "2026-11-13", True, True))

    def test_overdue_related_task_keeps_milestone_from_the_past(self):
        milestones = [{"date": "2026-11-09", "text": "精读开始"}]
        self.home.write_plan("demo.md", config(sequences={}, phases=[{"name": "A", "week": {"weekdays": [
            {"title": "精读", "minutes": 50, "slot": "focus"}]}}], milestones=milestones))
        self.api.poll()
        # 11-09 的精读没做：里程碑最早在今天
        item = self.api.state()["plans"][0]["milestones"][0]
        self.assertEqual((item["date"], item["moved_from"], item["past"]), ("2026-11-10", "2026-11-09", False))

    def test_milestones_and_plan_page_follow_moved_tasks(self):
        milestones = [{"date": "2026-11-13", "text": "第一周完成"}, {"date": "2026-11-20", "text": "全部完成"}]
        phases = [{"name": "A", "weeks": 1, "week": {"weekdays": [{"title": "精读", "minutes": 50, "slot": "focus"}]}},
                  {"name": "B", "week": {"weekdays": [{"title": "听力", "minutes": 20, "slot": "focus"}]}}]
        self.home.write_plan("demo.md", config(sequences={}, phases=phases, milestones=milestones))
        self.api.poll()
        plan = lambda: self.api.state()["plans"][0]
        self.assertEqual([(item["date"], item["moved_from"]) for item in plan()["milestones"]], [("2026-11-13", None), ("2026-11-20", None)])
        self.assertEqual([(phase["task_start"], phase["task_end"]) for phase in plan()["phases"]],
                         [("2026-11-09", "2026-11-13"), ("2026-11-16", "2026-11-20")])
        # 11-09 的精读逾期。只往后排：每天放得下两项精读，11-09 的排进今天，其余不动，里程碑也不动
        self.api.replan_all(False, now=self.at("12:00"))
        self.assertEqual(plan()["milestones"][0]["date"], "2026-11-13")
        self.assertEqual(plan()["phases"][0]["task_start"], "2026-11-10")
        self.assertEqual((plan()["moved_count"], plan()["last_task"]), (1, "2026-11-20"))
        # 提前：阶段 A 的精读集中到 11-10 和 11-11，阶段 B 的听力集中到 11-16。里程碑跟着各自之前的最后一项任务
        self.api.replan_all(True, now=self.at("12:00"))
        self.assertEqual([(phase["task_start"], phase["task_end"]) for phase in plan()["phases"]],
                         [("2026-11-10", "2026-11-12"), ("2026-11-16", "2026-11-16")])
        self.assertEqual([(item["date"], item["moved_from"]) for item in plan()["milestones"]],
                         [("2026-11-12", "2026-11-13"), ("2026-11-16", "2026-11-20")])
        self.assertEqual([item["text"] for item in self.api.state("2026-11-12")["day"]["milestones"]], ["第一周完成"])
        self.assertEqual(self.api.state("2026-11-13")["day"]["milestones"], [])
        self.assertEqual(self.api.range_days("2026-11-16", 1)["days"][0]["milestones"][0]["moved_from"], "2026-11-20")
        # 全部做完后，里程碑按完成的那天算。从后往前勾，避免触发前移
        for day in ("2026-11-12", "2026-11-11", "2026-11-10"):
            for task in [task for group in self.api.state(day)["day"]["groups"] for task in group["tasks"]]:
                self.api.set_done(task["uid"], True)
        self.assertEqual(plan()["milestones"][0]["date"], "2026-11-10")
        self.api.restore_all_days()
        self.assertEqual(plan()["phases"][0]["task_start"], "2026-11-09")

    def test_postpone_to_tomorrow_and_restore(self):
        uid = self.uid("2026-11-10", "听力")
        result = self.api.postpone_session(uid, now=self.at("20:30"))
        # 改期的任务按原定日期排，在明天同一计划的任务之前
        self.assertEqual((result["ok"], result["date"], result["weekday"], result["start"]), (True, "2026-11-11", "周三", "20:00"))
        # 今天从 20:30 起重排：精读还没做，从 20:30 开始
        self.assertEqual(self.tasks("2026-11-10"), [("精读", "20:30", "21:20")])
        self.assertEqual(self.tasks("2026-11-11"), [("听力", "20:00", "20:20"), ("精读", "20:25", "21:15"), ("听力", "21:20", "21:40")])
        moved = self.api.state("2026-11-11")["day"]["groups"][1]["tasks"][0]
        self.assertEqual((moved["uid"], moved["date"], moved["moved_from"]), (uid, "2026-11-11", "2026-11-10"))
        # 完成记录按新日期统计，任务 id 不变
        self.assertEqual(self.api.set_done(uid, True), {"ok": True, "shifted": 7})
        self.assertEqual(self.api.state("2026-11-11")["day"]["done"], 1)
        self.assertEqual(self.api.set_done(uid, False), {"ok": True, "shifted": 7})
        # 重新启动后保留
        api = PlannerApi(self.home.path, today=self.today)
        self.assertEqual(len(api.state("2026-11-11")["day"]["groups"][1]["tasks"]), 3)
        result = self.api.restore_session_day(uid, now=self.at("20:40"))
        self.assertEqual((result["ok"], result["date"]), (True, "2026-11-10"))
        self.assertEqual(len(self.tasks("2026-11-11")), 2)
        self.assertEqual(self.tasks("2026-11-10"), [("精读", "20:40", "21:30"), ("听力", "21:35", "21:55")])
        self.assertIsNone(self.api.state("2026-11-10")["day"]["groups"][1]["tasks"][1]["moved_from"])
        self.assertFalse(self.api.restore_session_day(uid)["ok"])

    def test_postpone_overdue_moves_to_today(self):
        uid = self.uid("2026-11-09", "听力")
        self.assertEqual(self.api.state()["overdue_total"], 2)
        result = self.api.postpone_session(uid, now=self.at("19:00"))
        self.assertEqual((result["date"], result["start"], result["end"]), ("2026-11-10", "20:00", "20:20"))
        self.assertEqual(self.api.state()["overdue_total"], 1)
        self.assertEqual(self.api.state("2026-11-09")["day"]["total"], 1)

    def test_postpone_when_tomorrow_is_full(self):
        self.api.add_task({"title": "搬家", "date": "2026-11-11", "time": "20:00", "minutes": 120})
        result = self.api.postpone_session(self.uid("2026-11-10", "精读"), now=self.at("12:00"))
        self.assertEqual((result["ok"], result["start"]), (True, None))
        self.assertIn("精读", [task["title"] for task in self.api.state("2026-11-11")["day"]["overflow"]])

    def test_postpone_temporary_task_changes_its_date(self):
        self.api.add_task({"title": "电话", "date": "2026-11-10", "minutes": 10})
        uid = self.uid("2026-11-10", "电话")
        result = self.api.postpone_session(uid, now=self.at("12:00"))
        self.assertEqual((result["ok"], result["date"]), (True, "2026-11-11"))
        self.assertNotEqual(result["uid"], uid)
        with open(os.path.join(self.home.path, "tasks.json"), encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["tasks"][0]["date"], "2026-11-11")

    def test_drag_still_works_after_replan(self):
        self.api.finish_and_replan(self.uid("2026-11-10", "精读"), now=self.at("20:20"))
        self.api.add_task({"title": "电话", "date": "2026-11-10", "minutes": 10})
        self.assertEqual(self.tasks("2026-11-10")[1:], [("电话", "20:20", "20:30"), ("听力", "20:35", "20:55")])
        self.assertTrue(self.api.move_session(self.uid("2026-11-10", "听力"), "20:00", 0)["changed"])
        self.assertEqual(self.tasks("2026-11-10")[1:], [("听力", "20:20", "20:40"), ("电话", "20:45", "20:55")])

    def test_drag_overflow_task_into_time_freed_by_replan(self):
        week = {"weekdays": [
            {"title": "精读", "minutes": 50, "slot": "focus"},
            {"title": "听力", "minutes": 20, "slot": "focus"},
            {"title": "播客", "minutes": 60, "slot": "commute"},
        ]}
        self.home.write_plan("demo.md", config(sequences={}, phases=[{"name": "A", "week": week}]))
        self.api.poll()
        overflow = lambda: [task["title"] for task in self.api.state("2026-11-10")["day"]["overflow"]]
        self.assertEqual(overflow(), ["播客"])
        # 不重排时晚上只剩 21:20–22:00，60 分钟放不下
        self.assertFalse(self.api.move_session(self.uid("2026-11-10", "播客"), "20:00", 2)["ok"])
        self.api.finish_and_replan(self.uid("2026-11-10", "精读"), now=self.at("20:20"))
        self.assertEqual(overflow(), ["播客"])
        # 精读提前做完后晚上有空余，拖进去放得下
        self.assertTrue(self.api.move_session(self.uid("2026-11-10", "播客"), "20:00", 2)["changed"])
        self.assertEqual(self.tasks("2026-11-10"), [("精读", "20:00", "20:20"), ("听力", "20:20", "20:40"), ("播客", "20:45", "21:45")])
        self.assertEqual(overflow(), [])

    def moved(self, day):
        """这一天排进时间段的任务：(标题, 开始时间, 原定日期的日)。"""
        state = self.api.state(day)["day"]
        return [(task["title"], task["start"], task["moved_from"] and int(task["moved_from"][8:]))
                for group in state["groups"] for task in group["tasks"]]

    def test_replan_all_pushes_overdue_tasks_into_later_days(self):
        # 11-09 的两项逾期。只往后排：逾期的先排进今天，放不下的任务依次顺延
        result = self.api.replan_all(False, now=self.at("12:00"))
        self.assertEqual(result, {"ok": True, "time": "12:00", "moved": 4, "beyond": 0, "unplaced": 0})
        self.assertEqual(self.moved("2026-11-10"), [("精读", "20:00", 9), ("听力", "20:55", 9), ("听力", "21:20", None)])
        self.assertEqual(self.moved("2026-11-11"), [("精读", "20:00", 10), ("精读", "20:55", None)])
        self.assertEqual(self.moved("2026-11-12"), [("听力", "20:00", 11), ("精读", "20:25", None), ("听力", "21:20", None)])
        self.assertEqual(self.moved("2026-11-13"), [("精读", "20:00", None), ("听力", "20:55", None)])
        self.assertEqual(self.moved("2026-11-14"), [])
        state = self.api.state()
        self.assertEqual((state["overdue_total"], state["moved_total"]), (0, 4))
        # 再排一次结果不变
        self.assertEqual(self.api.replan_all(False, now=self.at("12:00"))["moved"], 0)
        self.assertEqual(self.moved("2026-11-11"), [("精读", "20:00", 10), ("精读", "20:55", None)])
        # 全部移回
        self.assertEqual(self.api.restore_all_days(), {"ok": True, "restored": 4})
        state = self.api.state()
        self.assertEqual((state["overdue_total"], state["moved_total"]), (2, 0))
        self.assertEqual(self.moved("2026-11-11"), [("精读", "20:00", None), ("听力", "20:55", None)])

    def test_replan_all_pulls_later_tasks_into_freed_time(self):
        for title in ("精读", "听力"):
            self.api.set_done(self.uid("2026-11-09", title), True)
        self.api.set_done(self.uid("2026-11-11", "精读"), True)  # 明天的精读提前做完
        result = self.api.replan_all(True, now=self.at("12:00"))
        self.assertEqual((result["ok"], result["beyond"], result["unplaced"]), (True, 0, 0))
        self.assertEqual(self.moved("2026-11-10"), [("精读", "20:00", None), ("听力", "20:55", None), ("听力", "21:20", 11)])
        self.assertEqual(self.moved("2026-11-11"), [("精读", "20:00", 12), ("听力", "20:55", 12), ("听力", "21:20", 13)])
        self.assertEqual([task["title"] for task in self.api.state("2026-11-11")["day"]["early"]], ["精读"])
        # 周六下午有空闲时间，后面的任务提前到这里
        self.assertEqual(self.moved("2026-11-14")[0], ("精读", "14:00", 18))
        # 没有任务丢失，也没有排到今天之前
        days = self.api.range_days("2026-11-09", 21)["days"]
        self.assertEqual(sum(day["total"] for day in days), 20)
        self.assertEqual([task["title"] for task in days[0]["tasks"] if not task["done"]], [])

    def test_replan_all_leaves_fixed_event_and_temp_tasks_and_respects_phase_start(self):
        phases = [
            {"name": "A", "weeks": 1, "week": {"weekdays": [{"title": "精读", "minutes": 50, "slot": "focus"},
                                                             {"title": "晨读", "minutes": 10, "time": "07:30"}]}},
            {"name": "B", "week": {"weekdays": [{"title": "听力", "minutes": 20, "slot": "focus"}]}},
        ]
        events = [{"date": "2026-11-12", "title": "面谈", "minutes": 30}]
        self.home.write_plan("demo.md", config(sequences={}, phases=phases, events=events))
        self.api.poll()
        self.api.add_task({"title": "电话", "date": "2026-11-13", "minutes": 10})
        self.assertTrue(self.api.replan_all(True, now=self.at("12:00"))["ok"])
        tasks = [task for day in self.api.range_days("2026-11-09", 21)["days"] for task in day["tasks"]]
        where = lambda title: sorted({task["date"] for task in tasks if task["title"] == title})
        self.assertEqual(where("面谈"), ["2026-11-12"])
        self.assertEqual(where("电话"), ["2026-11-13"])
        self.assertEqual(where("晨读"), ["2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13"])
        self.assertTrue(all(task["moved_from"] is None for task in tasks if task["title"] in ("面谈", "电话", "晨读")))
        # 逾期的精读排进今天，阶段 B 的听力不早于阶段开始的 11-16
        self.assertEqual(where("精读")[0], "2026-11-10")
        self.assertEqual(where("听力")[0], "2026-11-16")
        self.assertEqual(len([task for task in tasks if task["title"] == "听力"]), 5)

    def test_phase_table_check_uses_planned_dates(self):
        from planner_core.notes_check import task_spans
        ws = self.api._ws
        before = task_spans(ws.plans[0], ws.expansions["demo"])
        self.api.postpone_session(self.uid("2026-11-20", "精读"), now=self.at("12:00"))
        self.api.postpone_session(self.uid("2026-11-20", "听力"), now=self.at("12:00"))
        self.assertEqual(self.api.state("2026-11-21")["day"]["total"], 2)
        self.assertEqual(task_spans(ws.plans[0], ws.expansions["demo"]), before)


class ApiExtensionTest(unittest.TestCase):
    def setUp(self):
        self.home = TempHome()
        self.home.write_profile()
        self.home.write_plan("demo.md", config())
        self.api = PlannerApi(self.home.path, today=date(2026, 11, 9))

    def tearDown(self):
        self.home.cleanup()

    def test_tasks_settings_archive_via_api(self):
        bad = self.api.add_task({"title": "", "date": "2026-11-09"})
        self.assertFalse(bad["ok"])
        self.assertTrue(self.api.add_task({"title": "取快递", "date": "2026-11-09", "time": "19:00", "minutes": 15})["ok"])
        state = self.api.state("2026-11-09")
        self.assertEqual([t["title"] for t in state["day"]["fixed"]], ["取快递"])
        task_id = state["day"]["fixed"][0]["task_id"]
        self.assertTrue(self.api.update_task(task_id, {"title": "取快递", "date": "2026-11-09", "minutes": 15})["ok"])
        state = self.api.state("2026-11-09")
        self.assertEqual(state["day"]["fixed"], [])
        self.assertEqual(state["day"]["groups"][0]["tasks"][0]["title"], "取快递")  # 不定时的临时任务优先级最高，进第一个时间段
        self.assertTrue(self.api.delete_task(task_id)["ok"])
        self.assertFalse(self.api.save_settings({"pomodoro": {"focus": 0}})["ok"])
        self.assertTrue(self.api.save_settings({"pomodoro": {"focus": 50}})["ok"])
        self.assertEqual(self.api.state()["settings"]["pomodoro"]["focus"], 50)
        self.assertTrue(self.api.archive_plan("demo")["ok"])
        state = self.api.state()
        self.assertEqual(state["plans"], [])
        self.assertEqual(state["archived"][0]["file"], "demo.md")
        self.assertTrue(self.api.restore_plan("demo.md")["ok"])
        self.assertFalse(self.api.restore_plan("demo.md")["ok"])

    def test_pomodoro_bound_to_task(self):
        uid = self.api.state("2026-11-09")["day"]["groups"][1]["tasks"][0]["uid"]
        snap = self.api.pomodoro_start(uid)
        self.assertEqual((snap["mode"], snap["task"]["title"]), ("focus", "学习 第1章"))
        self.assertTrue(self.api.pomodoro_pause()["paused"])
        self.assertFalse(self.api.pomodoro_resume()["paused"])
        self.api._pomodoro.ends_at = 0  # 让专注立即到期
        snap = self.api.pomodoro_tick()
        self.assertEqual(snap["mode"], "short_break")
        self.assertEqual(self.api.state(date.today().isoformat())["day"]["focus_count"], 1)  # 专注按实际结束日期记录
        self.assertEqual(self.api.state("2026-11-09")["day"]["groups"][1]["tasks"][0]["focus_count"], 1)
        self.assertEqual(self.api.pomodoro_skip()["mode"], "idle")

    def test_notifications_go_through_notifier(self):
        sent = []
        self.api._notifier = lambda title, message: sent.append((title, message))
        self.assertTrue(self.api.test_notification()["ok"])
        self.api.add_task({"title": "开会", "date": "2026-11-09", "time": "10:00", "minutes": 30})
        from datetime import datetime
        self.api._last_check = datetime(2026, 11, 9, 9, 49)
        self.api.background_tick(datetime(2026, 11, 9, 9, 50))
        self.api.background_tick(datetime(2026, 11, 9, 9, 51))
        self.assertEqual([title for title, _ in sent], ["计划本测试通知", "10 分钟后：开会"])

    def test_test_notification_warns_when_windows_toasts_are_off(self):
        from unittest import mock

        self.api._notifier = lambda title, message: None
        with mock.patch("planner_ui.windows_toasts_enabled", return_value=False):
            res = self.api.test_notification()
            self.assertTrue(res["ok"])
            self.assertIn("通知总开关", res["warning"])
            self.assertIs(self.api.state()["app"]["notifications_enabled"], False)
        with mock.patch("planner_ui.windows_toasts_enabled", return_value=True):
            self.assertNotIn("warning", self.api.test_notification())


class TrayTest(unittest.TestCase):
    """托盘菜单：2026-11-09 周一只有一个任务“学习 第1章”，20:00-21:00。"""

    def setUp(self):
        self.home = TempHome()
        self.home.write_profile()
        self.home.write_plan("demo.md", config())
        self.api = PlannerApi(self.home.path, today=date(2026, 11, 9))

    def tearDown(self):
        self.home.cleanup()

    @staticmethod
    def texts(spec):
        from planner_ui import SEPARATOR

        return [x["text"] for x in spec if x != SEPARATOR]

    @staticmethod
    def find(spec, prefix):
        return next(x for x in spec if x != "-" and x["text"].startswith(prefix))

    def test_next_and_current_task(self):
        from datetime import datetime
        from planner_ui import tray_menu_spec

        before = self.api.tray_status(datetime(2026, 11, 9, 19, 0))
        self.assertIsNone(before["current"])
        self.assertEqual(before["next"]["title"], "学习 第1章")
        spec = tray_menu_spec(before)
        self.assertIn("今天 0/1 项完成，还剩 60 分钟", self.texts(spec))
        self.assertEqual(self.find(spec, "开始专注：")["action"], ("pomodoro_start", before["next"]["uid"]))

        during = self.api.tray_status(datetime(2026, 11, 9, 20, 30))
        self.assertEqual(during["current"]["start"], "20:00")
        self.assertIsNone(during["next"])
        self.assertEqual(self.find(tray_menu_spec(during), "标记完成：")["action"], ("set_done", during["current"]["uid"]))

        self.api.set_done(during["current"]["uid"], True)
        after = self.api.tray_status(datetime(2026, 11, 9, 20, 30))
        self.assertIsNone(after["current"])
        self.assertIn("今天 1/1 项完成，还剩 0 分钟", self.texts(tray_menu_spec(after)))

    def test_pomodoro_items_follow_state(self):
        from planner_ui import tray_menu_spec

        self.api.pomodoro_start(None)
        texts = self.texts(tray_menu_spec(self.api.tray_status()))
        self.assertTrue(any(t.startswith("专注中，") and t.endswith("结束") for t in texts))
        self.assertIn("暂停", texts)
        self.assertIn("放弃本次专注", texts)
        self.api.pomodoro_pause()
        texts = self.texts(tray_menu_spec(self.api.tray_status()))
        self.assertTrue(any(t.startswith("专注已暂停，还剩") for t in texts))
        self.assertIn("继续", texts)

    def test_mute_skips_task_reminders_without_replaying_them(self):
        from datetime import datetime
        from planner_ui import tray_menu_spec

        sent = []
        self.api._notifier = lambda title, message: sent.append(title)
        self.api.add_task({"title": "开会", "date": "2026-11-09", "time": "10:00", "minutes": 30})
        self.api.mute_reminders(60, now=datetime(2026, 11, 9, 9, 30))
        status = self.api.tray_status(datetime(2026, 11, 9, 9, 40))
        self.assertEqual(status["muted_until"], "10:30")
        self.assertIn("任务提醒已暂停，10:30 恢复", self.texts(tray_menu_spec(status)))
        self.api._last_check = datetime(2026, 11, 9, 9, 49)
        self.api.background_tick(datetime(2026, 11, 9, 9, 51))
        self.api.background_tick(datetime(2026, 11, 9, 10, 31))  # 恢复后不补发暂停期间的提醒
        self.assertEqual(sent, [])
        self.assertIsNone(self.api.tray_status(datetime(2026, 11, 9, 10, 31))["muted_until"])

        self.api.mute_reminders(None, now=datetime(2026, 11, 9, 11, 0))
        self.assertEqual(self.api.tray_status(datetime(2026, 11, 9, 11, 0))["muted_until"], "今天结束")

    def test_tray_actions_ask_the_page_to_refresh(self):
        self.api.poll()
        self.api.mark_ui_changed()
        self.assertTrue(self.api.poll()["refresh"])
        self.assertFalse(self.api.poll()["refresh"])

    def test_menu_text_escapes_ampersand_and_truncates(self):
        from planner_ui import menu_text

        self.assertEqual(menu_text("Q&A"), "Q&&A")
        self.assertEqual(len(menu_text("一" * 40)), 24)


@unittest.skipUnless(os.name == "nt", "Windows only")
class AutostartTest(unittest.TestCase):
    def test_create_and_remove_shortcut(self):
        import tempfile
        from planner_ui import autostart_enabled, set_autostart
        with tempfile.TemporaryDirectory() as folder:
            set_autostart(True, target=r"C:\Windows\notepad.exe", folder=folder)
            self.assertTrue(autostart_enabled(folder))
            set_autostart(False, folder=folder)
            self.assertFalse(autostart_enabled(folder))
