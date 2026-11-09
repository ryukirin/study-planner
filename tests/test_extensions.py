import os
import unittest
from datetime import date, datetime, timedelta

from planner_core.plan_spec import PlanError, expand_plan, parse_plan
from planner_core.pomodoro import Pomodoro
from planner_core.reminders import due_reminders
from planner_core.settings import DEFAULT_SETTINGS, SettingsError, validate_settings
from planner_core.tasks import TaskError, validate_task
from planner_core.workspace import Workspace, WorkspaceError
from tests.helpers import TempHome, config

SAT = date(2026, 11, 14)


def outing(**overrides):
    data = {
        "schema": 1, "id": "weekend", "name": "周末逛街", "category": "生活", "start_date": "2026-11-14",
        "events": [
            {"date": "2026-11-14", "time": "14:00", "title": "逛店 A", "minutes": 90, "location": "表参道",
             "links": [{"title": "官网", "url": "https://example.com/a"}]},
            {"date": "2026-11-14", "time": "18:30", "title": "晚饭", "minutes": 60, "remind": 30},
        ],
    }
    data.update(overrides)
    return data


class SchemaExtensionTest(unittest.TestCase):
    def test_events_only_plan(self):
        plan = parse_plan(outing())
        self.assertEqual((plan.start, plan.end, plan.category), (SAT, SAT, "生活"))
        sessions = expand_plan(plan).by_date[SAT]
        self.assertEqual([s.fixed_start for s in sessions], [14 * 60, 18 * 60 + 30])
        self.assertEqual(sessions[0].location, "表参道")
        self.assertEqual(sessions[0].links[0]["url"], "https://example.com/a")
        self.assertEqual(sessions[1].remind, 30)
        self.assertEqual(sessions[0].phase, "")

    def test_events_only_with_deadline_range_check(self):
        with self.assertRaises(PlanError) as ctx:
            parse_plan(outing(deadline="2026-11-13"))
        self.assertTrue(any("deadline" in e or "不在计划范围" in e for e in ctx.exception.errors))

    def test_no_phases_and_no_events(self):
        with self.assertRaises(PlanError) as ctx:
            parse_plan(outing(events=[]))
        self.assertTrue(any("phases 和 events" in e for e in ctx.exception.errors))

    def test_bad_extra_fields(self):
        data = outing()
        data["events"][0].update({"time": "25:00", "links": [{"url": "file:///c:/"}], "remind": -5})
        errors = "\n".join(self._errors(data))
        self.assertIn("events[0].time", errors)
        self.assertIn("events[0].links[0]", errors)
        self.assertIn("events[0].remind", errors)

    def test_weekly_template_with_time(self):
        data = config()
        data["phases"][1]["week"]["daily"][0]["time"] = "07:00"
        sessions = expand_plan(parse_plan(data)).by_date[date(2026, 11, 16)]
        self.assertEqual(sessions[0].fixed_start, 7 * 60)

    @staticmethod
    def _errors(data):
        try:
            parse_plan(data)
        except PlanError as exc:
            return exc.errors
        return []


class FixedLayoutTest(unittest.TestCase):
    def setUp(self):
        self.home = TempHome()
        self.home.write_profile({"weekly": {"sat": [{"start": "14:00", "end": "17:00", "tag": "focus"}]}})

    def tearDown(self):
        self.home.cleanup()

    def test_flexible_task_skips_fixed_interval(self):
        study = config(id="study", start_date="2026-11-14", deadline="2026-11-14",
                       phases=[{"name": "A", "week": {"sat": [{"title": "精读", "minutes": 60, "slot": "focus"}]}}],
                       sequences={})
        self.home.write_plan("study.md", study)
        self.home.write_plan("weekend.md", outing())
        ws = Workspace(self.home.path)
        layout = ws.layout(SAT)
        placed = {item.session.title: (item.start, item.end, item.window is None) for item in layout.placed}
        self.assertEqual(placed["逛店 A"], (14 * 60, 15 * 60 + 30, True))
        self.assertEqual(placed["精读"], (15 * 60 + 35, 16 * 60 + 35, False))
        self.assertEqual(placed["晚饭"][0], 18 * 60 + 30)

    def test_fixed_overlap_reported(self):
        data = outing()
        data["events"][1]["time"] = "15:00"
        self.home.write_plan("weekend.md", data)
        ws = Workspace(self.home.path)
        report = ws.feasibility(SAT, SAT)
        self.assertEqual([(a.title, b.title) for _, a, b in report.overlaps], [("逛店 A", "晚饭")])


class TaskStoreTest(unittest.TestCase):
    def setUp(self):
        self.home = TempHome()
        self.home.write_profile()
        self.ws = Workspace(self.home.path)

    def tearDown(self):
        self.home.cleanup()

    def test_validate_task(self):
        with self.assertRaises(TaskError) as ctx:
            validate_task({"title": " ", "date": "2026-13-01", "minutes": 0})
        self.assertEqual(len(ctx.exception.errors), 3)
        task = validate_task({"title": " 打电话 ", "date": "2026-11-13", "time": "18:00", "minutes": 10})
        self.assertEqual((task["title"], task["time"], task["remind"]), ("打电话", "18:00", None))

    def test_add_update_delete_with_progress(self):
        task = self.ws.add_task({"title": "给房东打电话", "date": "2026-11-13", "time": "18:00", "minutes": 10})
        sessions = self.ws.sessions_on(date(2026, 11, 13))
        self.assertEqual([s.title for s in sessions], ["给房东打电话"])
        self.assertTrue(sessions[0].uid.startswith("_tasks|2026-11-13|"))
        self.ws.set_done(sessions[0], True)
        self.ws.update_task(task["id"], {"title": "给房东打电话", "date": "2026-11-14", "time": "10:00", "minutes": 10})
        moved = self.ws.sessions_on(date(2026, 11, 14))[0]
        self.assertTrue(self.ws.is_done(moved.uid))
        self.assertEqual(self.ws.sessions_on(date(2026, 11, 13)), [])
        reloaded = Workspace(self.home.path)
        self.assertEqual(len(reloaded.tasks.tasks), 1)
        self.assertTrue(reloaded.delete_task(task["id"]))
        self.assertEqual(reloaded.progress.records, {})
        self.assertEqual(reloaded.sessions_on(date(2026, 11, 14)), [])

    def test_task_counts_in_overdue(self):
        self.ws.add_task({"title": "交材料", "date": "2026-11-10", "minutes": 20})
        self.assertEqual([s.title for s in self.ws.overdue(date(2026, 11, 11))], ["交材料"])


class SettingsTest(unittest.TestCase):
    def test_defaults_and_partial(self):
        self.assertEqual(validate_settings({}), DEFAULT_SETTINGS)
        merged = validate_settings({"pomodoro": {"focus": 50}})
        self.assertEqual((merged["pomodoro"]["focus"], merged["pomodoro"]["short_break"]), (50, 5))

    def test_full_page_flag(self):
        self.assertTrue(validate_settings({})["pomodoro"]["full_page"])
        self.assertFalse(validate_settings({"pomodoro": {"full_page": False}})["pomodoro"]["full_page"])
        with self.assertRaises(SettingsError):
            validate_settings({"pomodoro": {"full_page": 1}})

    def test_invalid_values(self):
        with self.assertRaises(SettingsError) as ctx:
            validate_settings({"pomodoro": {"focus": 0}, "reminders": {"summary_time": "8点", "timed": "yes"}})
        self.assertEqual(len(ctx.exception.errors), 3)


class ReminderTest(unittest.TestCase):
    def setUp(self):
        self.home = TempHome()
        self.home.write_profile({"weekly": {"sat": [{"start": "16:00", "end": "17:00", "tag": "focus"}]}})
        study = config(id="study", start_date="2026-11-14", deadline="2026-11-14", sequences={},
                       phases=[{"name": "A", "week": {"sat": [{"title": "精读", "minutes": 30, "slot": "focus"}]}}])
        self.home.write_plan("study.md", study)
        self.home.write_plan("weekend.md", outing())
        self.ws = Workspace(self.home.path)
        self.settings = validate_settings({})

    def tearDown(self):
        self.home.cleanup()

    def due(self, since, now, settings=None):
        return due_reminders(self.ws, settings or self.settings, since, now)

    def test_timed_lead_and_start(self):
        found = self.due(datetime(2026, 11, 14, 13, 49), datetime(2026, 11, 14, 13, 50))
        self.assertEqual([(r.kind, r.title) for r in found], [("timed", "10 分钟后：逛店 A")])
        self.assertIn("表参道", found[0].message)
        found = self.due(datetime(2026, 11, 14, 13, 50), datetime(2026, 11, 14, 14, 0))
        self.assertEqual([(r.kind, r.title) for r in found], [("start", "现在开始：逛店 A")])

    def test_task_remind_override(self):
        found = self.due(datetime(2026, 11, 14, 17, 59), datetime(2026, 11, 14, 18, 0))
        self.assertEqual([r.title for r in found], ["30 分钟后：晚饭"])

    def test_flexible_task_start(self):
        found = self.due(datetime(2026, 11, 14, 15, 59), datetime(2026, 11, 14, 16, 0))
        self.assertEqual([r.title for r in found], ["现在开始：精读"])

    def test_daily_summary(self):
        found = self.due(datetime(2026, 11, 14, 7, 59), datetime(2026, 11, 14, 8, 0))
        self.assertEqual(found[0].kind, "summary")
        self.assertIn("3 项任务，共 180 分钟", found[0].message)

    def test_done_and_disabled_and_late(self):
        session = next(s for s in self.ws.sessions_on(SAT) if s.title == "逛店 A")
        self.ws.set_done(session, True)
        self.assertEqual(self.due(datetime(2026, 11, 14, 13, 49), datetime(2026, 11, 14, 13, 50)), [])
        self.assertEqual(self.due(datetime(2026, 11, 14, 13, 50), datetime(2026, 11, 14, 14, 0)), [])
        late = self.due(datetime(2026, 11, 14, 15, 0), datetime(2026, 11, 14, 16, 30))
        self.assertEqual(late, [])
        off = validate_settings({"reminders": {"task_start": False}})
        self.assertEqual(self.due(datetime(2026, 11, 14, 15, 59), datetime(2026, 11, 14, 16, 0), off), [])


class PomodoroTest(unittest.TestCase):
    def setUp(self):
        self.now = 1000.0
        self.settings = {"focus": 25, "short_break": 5, "long_break": 15, "long_every": 2}
        self.p = Pomodoro(lambda: self.settings, clock=lambda: self.now)

    def advance(self, minutes):
        self.now += minutes * 60

    def test_cycle_with_long_break(self):
        self.p.start_focus({"uid": "x", "title": "精读"})
        self.advance(25)
        events = self.p.tick()
        self.assertEqual([(e.kind, e.minutes, e.next_mode) for e in events], [("focus_done", 25, "short_break")])
        self.assertEqual(events[0].task["title"], "精读")
        self.advance(5)
        self.assertEqual([e.kind for e in self.p.tick()], ["break_done"])
        self.assertEqual(self.p.mode, "idle")
        self.p.start_focus()
        self.advance(25)
        self.assertEqual(self.p.tick()[0].next_mode, "long_break")
        self.assertEqual(self.p.snapshot()["remaining_s"], 15 * 60)

    def test_pause_resume_and_stop(self):
        self.p.start_focus()
        self.advance(10)
        self.p.pause()
        self.advance(30)
        self.assertEqual(self.p.tick(), [])
        self.assertEqual(self.p.snapshot()["remaining_s"], 15 * 60)
        self.p.resume()
        self.advance(15)
        self.assertEqual(self.p.tick()[0].kind, "focus_done")
        self.p.stop()
        self.assertEqual(self.p.snapshot()["mode"], "idle")


class ArchiveTest(unittest.TestCase):
    def setUp(self):
        self.home = TempHome()
        self.home.write_profile()
        self.home.write_plan("demo.md", config())
        self.ws = Workspace(self.home.path)
        self.ws.set_done(self.ws.sessions_on(date(2026, 11, 9))[0], True)

    def tearDown(self):
        self.home.cleanup()

    def test_archive_restore_delete(self):
        self.ws.archive_plan("demo")
        self.assertEqual(self.ws.plans, [])
        self.assertEqual([item["id"] for item in self.ws.archived()], ["demo"])
        self.assertEqual(len(self.ws.progress.records), 1)
        self.ws.restore_plan("demo.md")
        self.assertEqual([plan.id for plan in self.ws.plans], ["demo"])
        self.ws.archive_plan("demo")
        self.assertEqual(self.ws.delete_archived("demo.md"), 1)
        self.assertEqual(self.ws.archived(), [])
        self.assertEqual(self.ws.progress.records, {})

    def test_restore_conflict_and_bad_name(self):
        self.ws.archive_plan("demo")
        self.home.write_plan("demo.md", config(name="新版"))
        self.ws.reload()
        with self.assertRaises(WorkspaceError):
            self.ws.restore_plan("demo.md")
        with self.assertRaises(WorkspaceError):
            self.ws.delete_archived("../profile.json")


if __name__ == "__main__":
    unittest.main()
