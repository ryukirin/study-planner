import json
import os
import unittest
from datetime import date

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

    def test_invalid_selected_falls_back_to_today(self):
        self.assertEqual(self.api.state("not-a-date")["selected"], "2026-11-17")

    def test_set_done_by_uid(self):
        uid = self.api.state("2026-11-09")["day"]["groups"][1]["tasks"][0]["uid"]
        self.assertEqual(self.api.set_done(uid, True), {"ok": True})
        state = self.api.state("2026-11-09")
        self.assertTrue(state["day"]["groups"][1]["tasks"][0]["done"])
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
