import json
import os
import unittest
from datetime import date

from planner_core.workspace import Workspace
from tests.helpers import TempHome, config


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.home = TempHome()
        self.home.write_profile()
        self.plan_path = self.home.write_plan("demo.md", config())

    def tearDown(self):
        self.home.cleanup()

    def test_loads_plans_and_layout(self):
        ws = Workspace(self.home.path)
        self.assertEqual([plan.id for plan in ws.plans], ["demo"])
        layout = ws.layout(date(2026, 11, 9))
        self.assertEqual([item.session.title for item in layout.placed], ["学习 第1章"])
        self.assertFalse(ws.profile_is_default)

    def test_check_persists_and_survives_text_edit(self):
        ws = Workspace(self.home.path)
        target = ws.sessions_on(date(2026, 11, 14))[0]
        ws.set_done(target, True)
        edited = config()
        edited["phases"][0]["week"]["sat"][0]["title"] = "周六长练习（改了文字）"
        self.home.write_plan("demo.md", edited)
        ws2 = Workspace(self.home.path)
        session = ws2.sessions_on(date(2026, 11, 14))[0]
        self.assertEqual(session.title, "周六长练习（改了文字）")
        self.assertTrue(ws2.is_done(session.uid))

    def test_atomic_write_keeps_backup(self):
        ws = Workspace(self.home.path)
        sessions = ws.sessions_on(date(2026, 11, 16))
        ws.set_done(sessions[0], True)
        ws.set_done(sessions[0], False)
        self.assertTrue(os.path.exists(ws.progress_path + ".bak"))
        self.assertFalse(os.path.exists(ws.progress_path + ".tmp"))

    def test_corrupt_progress_is_quarantined_not_overwritten(self):
        path = os.path.join(self.home.path, "progress.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{broken")
        ws = Workspace(self.home.path)
        self.assertTrue(any("无法解析" in warning for warning in ws.warnings))
        moved = [name for name in os.listdir(self.home.path) if name.startswith("progress.json.corrupt-")]
        self.assertEqual(len(moved), 1)
        with open(os.path.join(self.home.path, moved[0]), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "{broken")
        self.assertEqual(ws.progress.records, {})

    def test_bad_plan_file_does_not_block_others(self):
        self.home.write_plan("broken.md", "```study-plan\n{\"schema\": 1}\n```")
        ws = Workspace(self.home.path)
        self.assertEqual([plan.id for plan in ws.plans], ["demo"])
        self.assertEqual(len(ws.plan_errors), 1)
        self.assertTrue(ws.plan_errors[0].path.endswith("broken.md"))

    def test_duplicate_id_reported(self):
        self.home.write_plan("copy.md", config(name="复制"))
        ws = Workspace(self.home.path)
        self.assertEqual(len(ws.plans), 1)
        self.assertTrue(any("重复" in error for item in ws.plan_errors for error in item.errors))

    def test_missing_profile_uses_default(self):
        os.remove(os.path.join(self.home.path, "profile.json"))
        ws = Workspace(self.home.path)
        self.assertTrue(ws.profile_is_default)
        self.assertEqual(ws.profile_errors, [])

    def test_invalid_profile_reports_errors(self):
        self.home.write_profile({"weekly": {"mon": [{"start": "9", "end": "10"}]}})
        ws = Workspace(self.home.path)
        self.assertTrue(ws.profile_is_default)
        self.assertTrue(ws.profile_errors)

    def test_overdue_and_status(self):
        ws = Workspace(self.home.path)
        ws.set_done(ws.sessions_on(date(2026, 11, 9))[0], True)
        today = date(2026, 11, 17)
        overdue = ws.overdue(today)
        self.assertEqual([s.date_str for s in overdue], ["2026-11-14", "2026-11-16"])
        status = ws.plan_status(ws.plans[0], today)
        self.assertEqual(status.state, "进行中")
        self.assertEqual(status.current_phase.name, "B")
        self.assertEqual(status.done_sessions, 1)
        self.assertEqual(status.overdue_minutes, 135)
        seq = status.sequences[0]
        self.assertEqual(seq.done_items, ["第1章"])
        self.assertEqual(seq.remaining_items, ["第2章", "第3章"])

    def test_history_records_after_replan(self):
        ws = Workspace(self.home.path)
        ws.set_done(ws.sessions_on(date(2026, 11, 9))[0], True)
        replanned = config(start_date="2026-11-16", deadline="2026-11-29", sequences={"ch": {"items": ["第2章", "第3章"]}})
        self.home.write_plan("demo.md", replanned)
        ws2 = Workspace(self.home.path)
        status = ws2.plan_status(ws2.plans[0], date(2026, 11, 16))
        self.assertEqual(status.history_records, 1)
        self.assertEqual(ws2.sessions_on(date(2026, 11, 16))[0].title, "学习 第2章")

    def test_draft_replaces_same_id(self):
        ws = Workspace(self.home.path)
        from planner_core.plan_spec import parse_plan
        self.assertTrue(ws.use_draft(parse_plan(config(name="草稿"))))
        self.assertEqual([plan.name for plan in ws.plans], ["草稿"])

    def test_warnings_for_sequences_and_slots(self):
        data = config()
        data["phases"][1]["week"]["daily"][0]["slot"] = "gym"
        self.home.write_plan("demo.md", data)
        ws = Workspace(self.home.path)
        text = "\n".join(ws.plan_warnings())
        self.assertIn("gym", text)
        self.assertIn("只排到 1/3", text)

    def test_saved_profile_changes_layout(self):
        ws = Workspace(self.home.path)
        profile = ws.profile
        profile.weekly["mon"] = []
        ws.save_profile(profile)
        self.assertEqual(len(ws.layout(date(2026, 11, 9)).overflow), 1)
        with open(ws.profile_path, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["weekly"]["mon"], [])


if __name__ == "__main__":
    unittest.main()
