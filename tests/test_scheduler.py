import unittest
from datetime import date

from planner_core.availability import ProfileError, Window, parse_profile, parse_time
from planner_core.plan_spec import Session
from planner_core.scheduler import feasibility, layout_day
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
