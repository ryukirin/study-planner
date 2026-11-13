import unittest
from datetime import date

from planner_core.availability import ProfileError, Window, parse_profile, parse_time
from planner_core.plan_spec import Session
from planner_core.scheduler import feasibility, layout_day, replan_day
from tests.helpers import BASE_PROFILE

DAY = date(2026, 11, 9)


def session(title: str, minutes: int, slot: str | None = None, priority: int = 1, plan_id: str = "p", order: int = 0) -> Session:
    return Session(uid=f"{plan_id}|{title}", plan_id=plan_id, plan_name=plan_id, color="#000000", priority=priority, day=DAY,
                   order=order, title=title, detail="", minutes=minutes, slot=slot, phase="A")


def window(start: str, end: str, tag: str = "focus") -> Window:
    return Window(parse_time(start), parse_time(end), tag)


class LayoutTest(unittest.TestCase):
    def test_tag_matching(self):
        windows = [window("07:30", "08:00", "commute"), window("20:00", "22:00", "focus")]
        layout = layout_day(DAY, [session("精读", 60, "focus"), session("听力", 20, "commute", order=1)], windows, 5)
        placed = {item.session.title: (item.start, item.window.tag) for item in layout.placed}
        self.assertEqual(placed["听力"], (parse_time("07:30"), "commute"))
        self.assertEqual(placed["精读"], (parse_time("20:00"), "focus"))
        self.assertEqual([item.session.title for item in layout.placed], ["听力", "精读"])

    def test_priority_and_buffer(self):
        windows = [window("20:00", "22:00")]
        sessions = [session("Java", 60, "focus", priority=2, plan_id="java"), session("TOEIC", 30, "focus", priority=1, plan_id="toeic")]
        layout = layout_day(DAY, sessions, windows, 5)
        self.assertEqual([(item.session.title, item.start, item.end) for item in layout.placed],
                         [("TOEIC", parse_time("20:00"), parse_time("20:30")), ("Java", parse_time("20:35"), parse_time("21:35"))])

    def test_overflow(self):
        windows = [window("20:00", "21:00")]
        layout = layout_day(DAY, [session("a", 40, order=0), session("b", 40, order=1)], windows, 0)
        self.assertEqual([item.session.title for item in layout.placed], ["a"])
        self.assertEqual([item.title for item in layout.overflow], ["b"])

    def test_unknown_slot_overflows(self):
        layout = layout_day(DAY, [session("a", 10, "gym")], [window("20:00", "21:00")], 0)
        self.assertEqual(len(layout.overflow), 1)

    def test_no_slot_goes_anywhere(self):
        windows = [window("07:30", "08:00", "commute"), window("20:00", "22:00", "focus")]
        layout = layout_day(DAY, [session("a", 20), session("b", 40, order=1)], windows, 0)
        self.assertEqual([(item.session.title, item.window.tag) for item in layout.placed], [("a", "commute"), ("b", "focus")])

    def test_manual_order_within_window(self):
        windows = [window("20:00", "22:00")]
        sessions = [session("a", 30, "focus", order=0), session("b", 40, "focus", order=1), session("c", 20, "focus", order=2)]
        layout = layout_day(DAY, sessions, windows, 5, {parse_time("20:00"): ["p|c", "p|a"]})
        self.assertEqual([(item.session.title, item.start) for item in layout.placed],
                         [("c", parse_time("20:00")), ("a", parse_time("20:25")), ("b", parse_time("21:00"))])

    def test_manual_order_picks_window_and_ignores_tag(self):
        windows = [window("07:30", "08:00", "commute"), window("20:00", "22:00", "focus")]
        sessions = [session("精读", 30, "focus"), session("听力", 20, "commute", order=1)]
        layout = layout_day(DAY, sessions, windows, 5, {parse_time("07:30"): ["p|精读"], parse_time("20:00"): ["p|听力"]})
        self.assertEqual({item.session.title: item.window.tag for item in layout.placed}, {"精读": "commute", "听力": "focus"})

    def test_manual_order_skips_fixed_and_falls_back(self):
        windows = [window("07:30", "08:00", "commute"), window("20:00", "21:00", "focus")]
        fixed = session("定时", 30, order=2)
        fixed.fixed_start = parse_time("20:00")
        sessions = [session("长", 50, "focus"), session("短", 20, "focus", order=1), fixed]
        manual = {parse_time("07:30"): ["p|长", "p|不存在"], parse_time("20:00"): ["p|短"], parse_time("12:00"): ["p|短"]}
        layout = layout_day(DAY, sessions, windows, 5, manual)
        placed = {item.session.title: item.start for item in layout.placed}
        # 短 排在定时任务之后。长 在通勤时间段放不下，按自动规则处理，晚上也放不下，进入未排入
        self.assertEqual(placed, {"定时": parse_time("20:00"), "短": parse_time("20:35")})
        self.assertEqual([item.title for item in layout.overflow], ["长"])


class ReplanTest(unittest.TestCase):
    """20:00–22:00，间隔 5 分钟：a 20:00–20:30，b 20:35–21:15，c 21:20–21:40。"""

    def setUp(self):
        self.sessions = [session("a", 30, "focus", order=0), session("b", 40, "focus", order=1), session("c", 20, "focus", order=2)]
        self.windows = [window("19:00", "19:30", "commute"), window("20:00", "22:00")]

    def times(self, layout):
        return [(item.session.title, item.start, item.end) for item in layout.placed]

    def test_finish_early_pulls_the_rest_forward(self):
        base = layout_day(DAY, self.sessions, self.windows, 5)
        # 20:10 提前做完 b：b 记为 19:30–20:10，c 接着从 20:10 排。a 还没做，也从 20:10 起重排在 c 前面
        layout = replan_day(base, parse_time("20:10"), 5, {"p|b": parse_time("20:10")})
        self.assertEqual(self.times(layout), [
            ("b", parse_time("19:30"), parse_time("20:10")), ("a", parse_time("20:10"), parse_time("20:40")),
            ("c", parse_time("20:45"), parse_time("21:05"))])
        self.assertEqual({item.session.title: item.window.tag for item in layout.placed}, {"a": "focus", "b": "focus", "c": "focus"})

    def test_everything_undone_is_replanned_from_at(self):
        base = layout_day(DAY, self.sessions, self.windows, 5)
        # 21:00 重排：三个任务都没做，从 21:00 起按原来的顺序放。b 40 分钟放不下，c 放得下
        layout = replan_day(base, parse_time("21:00"), 5, {})
        self.assertEqual(self.times(layout), [("a", parse_time("21:00"), parse_time("21:30")), ("c", parse_time("21:35"), parse_time("21:55"))])
        self.assertEqual([item.title for item in layout.overflow], ["b"])

    def test_done_tasks_use_actual_time_only_when_needed(self):
        base = layout_day(DAY, self.sessions, self.windows, 5)
        # a 排在 21:00 之前，也在之前完成：保持原位
        layout = replan_day(base, parse_time("21:00"), 5, {"p|a": parse_time("20:25")})
        self.assertEqual(self.times(layout)[:2], [("a", parse_time("20:00"), parse_time("20:30")), ("b", parse_time("21:00"), parse_time("21:40"))])
        # 20:10 重排后，a 在 20:40 才勾完成：a 记为 20:10–20:40，后面的任务排在它之后
        layout = replan_day(base, parse_time("20:10"), 5, {"p|a": parse_time("20:40")})
        self.assertEqual(self.times(layout), [
            ("a", parse_time("20:10"), parse_time("20:40")), ("b", parse_time("20:45"), parse_time("21:25")),
            ("c", parse_time("21:30"), parse_time("21:50"))])
        # 不在当天完成的任务，排在重排时刻之后的按重排时刻算
        layout = replan_day(base, parse_time("20:10"), 5, {"p|b": None})
        self.assertEqual(self.times(layout)[0], ("b", parse_time("19:30"), parse_time("20:10")))

    def test_overflow_is_retried_and_fixed_is_avoided(self):
        fixed = session("定时", 20, order=3)
        fixed.fixed_start = parse_time("20:40")
        extra = session("d", 50, "focus", order=4)
        base = layout_day(DAY, self.sessions + [fixed, extra], self.windows, 5)
        self.assertEqual([item.title for item in base.overflow], ["c", "d"])
        # a、b 都在 20:15 前做完：c 排到定时任务之前，d 排到定时任务之后
        done = {"p|a": parse_time("20:05"), "p|b": parse_time("20:15")}
        layout = replan_day(base, parse_time("20:15"), 5, done)
        placed = {item.session.title: (item.start, item.end) for item in layout.placed}
        self.assertEqual(placed["c"], (parse_time("20:15"), parse_time("20:35")))
        self.assertEqual(placed["定时"], (parse_time("20:40"), parse_time("21:00")))
        self.assertEqual(placed["d"], (parse_time("21:05"), parse_time("21:55")))
        self.assertEqual(layout.overflow, [])

    def test_manual_order_uses_time_freed_by_done_tasks(self):
        extra = session("播客", 40, "commute", order=3)
        manual = {parse_time("20:00"): ["p|a", "p|b", "p|c", "p|播客"]}
        base = layout_day(DAY, self.sessions + [extra], self.windows, 5, manual)
        # 不重排时晚上排满了，播客放不下。commute 时间段也放不下 40 分钟
        self.assertEqual([item.title for item in base.overflow], ["播客"])
        # a 在 20:10 提前做完，后面的任务前移，手动排进晚上的播客放得下
        layout = replan_day(base, parse_time("20:10"), 5, {"p|a": parse_time("20:10")}, manual)
        self.assertEqual(self.times(layout), [
            ("a", parse_time("20:00"), parse_time("20:10")), ("b", parse_time("20:10"), parse_time("20:50")),
            ("c", parse_time("20:55"), parse_time("21:15")), ("播客", parse_time("21:20"), parse_time("22:00"))])
        self.assertEqual(layout.overflow, [])

    def test_fixed_task_done_early_frees_its_time(self):
        fixed = session("定时", 30, order=3)
        fixed.fixed_start = parse_time("20:35")
        base = layout_day(DAY, self.sessions + [fixed], self.windows, 5)
        # a 20:00–20:30，定时 20:35–21:05，b 21:10–21:50，c 放不下
        self.assertEqual([item.title for item in base.overflow], ["c"])
        # 定时任务 20:10 就做完了：记为 19:40–20:10，原来的时间让给 a、b、c
        layout = replan_day(base, parse_time("20:10"), 5, {"p|定时": parse_time("20:10")})
        self.assertEqual(self.times(layout), [
            ("定时", parse_time("19:40"), parse_time("20:10")), ("a", parse_time("20:10"), parse_time("20:40")),
            ("b", parse_time("20:45"), parse_time("21:25")), ("c", parse_time("21:30"), parse_time("21:50"))])
        # 没做完的定时任务仍然占着原来的时间
        layout = replan_day(base, parse_time("20:10"), 5, {})
        self.assertIn(("定时", parse_time("20:35"), parse_time("21:05")), self.times(layout))

    def test_missed_task_moves_to_a_matching_window_or_overflow(self):
        sessions = [session("听力", 20, "commute"), session("精读", 30, "focus", order=1), session("随便", 5, order=2)]
        base = layout_day(DAY, sessions, self.windows, 5)
        self.assertEqual({item.session.title: item.start for item in base.placed},
                         {"听力": parse_time("19:00"), "精读": parse_time("20:00"), "随便": parse_time("19:25")})
        # 19:50 重排：通勤时间段已经过去。没有 slot 的任务进晚上，commute 的任务没有匹配的时间段
        layout = replan_day(base, parse_time("19:50"), 5, {})
        self.assertEqual(self.times(layout), [("随便", parse_time("20:00"), parse_time("20:05")), ("精读", parse_time("20:10"), parse_time("20:40"))])
        self.assertEqual([item.title for item in layout.overflow], ["听力"])


class ProfileTest(unittest.TestCase):
    def test_parse_and_round_trip(self):
        profile = parse_profile(BASE_PROFILE)
        self.assertEqual(len(profile.windows_for(DAY)), 2)
        self.assertEqual(parse_profile(profile.to_dict()).to_dict(), profile.to_dict())

    def test_exception_day_overrides_weekly(self):
        data = dict(BASE_PROFILE, exceptions=[{"date": "2026-11-09", "windows": [], "note": "加班"}])
        profile = parse_profile(data)
        self.assertEqual(profile.windows_for(DAY), [])
        self.assertEqual(profile.exception_notes[DAY], "加班")

    def test_overlap_and_order_errors(self):
        data = dict(BASE_PROFILE, weekly={"mon": [
            {"start": "20:00", "end": "21:00"}, {"start": "20:30", "end": "22:00"}, {"start": "09:00", "end": "08:00"},
        ]})
        with self.assertRaises(ProfileError) as ctx:
            parse_profile(data)
        text = "\n".join(ctx.exception.errors)
        self.assertIn("重叠", text)
        self.assertIn("开始时间必须早于结束时间", text)

    def test_bad_time_and_unknown_key(self):
        with self.assertRaises(ProfileError) as ctx:
            parse_profile({"weekly": {"monday": [], "tue": [{"start": "25:00", "end": "26:00"}]}})
        text = "\n".join(ctx.exception.errors)
        self.assertIn("monday", text)
        self.assertIn("25:00", text)


class FeasibilityTest(unittest.TestCase):
    def test_weekly_totals_and_overflow(self):
        profile = parse_profile(BASE_PROFILE)

        def sessions_on(day):
            return [session("长任务", 150, "focus")] if day == DAY else []

        report = feasibility(sessions_on, profile, DAY, date(2026, 11, 15))
        self.assertEqual(len(report.weeks), 1)
        self.assertEqual(report.weeks[0].required, 150)
        self.assertEqual(report.weeks[0].available, 5 * 150 + 180)
        self.assertEqual(report.overflow_count, 1)


if __name__ == "__main__":
    unittest.main()
