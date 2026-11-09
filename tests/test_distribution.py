"""发布相关：App 记录文件 app.json、命令行工具读取数据目录的顺序、skill 安装。"""
import json
import os
import tempfile
import unittest
from datetime import date
from unittest import mock

import planner_ui
from planner_core import paths
from tests.helpers import TempHome
from tests.test_cli import run_cli


class AppInfoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.appdata = os.path.join(self.tmp.name, "Roaming")
        self.other = os.path.join(self.tmp.name, "other-home")
        os.makedirs(self.other)
        env = {key: value for key, value in os.environ.items() if key != paths.ENV_HOME}
        env["APPDATA"] = self.appdata
        self.env = mock.patch.dict(os.environ, env, clear=True)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_data_home_order(self):
        default = os.path.join(self.appdata, "StudyPlanner")
        self.assertEqual(paths.data_home(use_app_info=True), default)
        paths.write_app_info(self.other, "9.9.9")
        self.assertEqual(paths.data_home(use_app_info=True), self.other)
        self.assertEqual(paths.data_home(), default)  # App 自己不读记录文件
        with mock.patch.dict(os.environ, {paths.ENV_HOME: self.tmp.name}):
            self.assertEqual(paths.data_home(use_app_info=True), os.path.abspath(self.tmp.name))

    def test_app_info_content(self):
        paths.write_app_info(self.other, "9.9.9")
        info = paths.read_app_info()
        self.assertEqual(info["version"], "9.9.9")
        self.assertEqual(info["home"], os.path.abspath(self.other))
        self.assertTrue(info["cli"][-1].endswith("planner_cli.py"))

    def test_cli_follows_app_info(self):
        paths.write_app_info(self.other, "9.9.9")
        code, out = run_cli("paths")
        self.assertEqual(code, 0)
        self.assertIn(f"数据目录：{self.other}", out)
        self.assertIn("数据目录来源：App 记录", out)


class SkillInstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.profile = os.path.join(self.tmp.name, "user")
        os.makedirs(os.path.join(self.profile, ".codex"))
        self.env = mock.patch.dict(os.environ, {"USERPROFILE": self.profile, "HOME": self.profile})
        self.env.start()
        self.home = TempHome()
        self.home.write_profile()
        self.api = planner_ui.PlannerApi(self.home.path, today=date(2026, 11, 9))

    def tearDown(self):
        self.env.stop()
        self.home.cleanup()
        self.tmp.cleanup()

    def target(self, tool):
        return os.path.join(self.profile, tool, "skills", "plan-builder")

    def test_install_copies_files_and_keeps_local_folder(self):
        local = os.path.join(self.target(".claude"), "references", "local")
        os.makedirs(local)
        with open(os.path.join(local, "mine.md"), "w", encoding="utf-8") as handle:
            handle.write("个人说明")
        self.assertEqual([t["state"] for t in self.api.skill_status()["targets"]], ["missing", "missing"])

        res = self.api.install_skill()
        self.assertTrue(res["ok"], res)
        self.assertEqual([r["state"] for r in res["results"]], ["installed", "installed"])
        for tool in (".claude", ".codex"):
            target = self.target(tool)
            self.assertTrue(os.path.isfile(os.path.join(target, "SKILL.md")))
            self.assertTrue(os.path.isfile(os.path.join(target, "references", "plan-schema.md")))
            with open(os.path.join(target, planner_ui.SKILL_MARKER), encoding="utf-8") as handle:
                self.assertEqual(json.load(handle)["version"], planner_ui.APP_VERSION)
        self.assertEqual(os.listdir(local), ["mine.md"])  # 已有的个人文件保留，源码里的 local/ 不会复制过去
        self.assertFalse(os.path.exists(os.path.join(self.target(".codex"), "references", "local")))
        self.assertEqual({t["state"] for t in self.api.skill_status()["targets"]}, {"installed"})

    @unittest.skipUnless(os.name == "nt", "Windows only")
    def test_linked_target_is_not_overwritten(self):
        import _winapi

        real = os.path.join(self.tmp.name, "repo-skill")
        os.makedirs(real)
        os.makedirs(os.path.dirname(self.target(".claude")))
        _winapi.CreateJunction(real, self.target(".claude"))
        res = self.api.install_skill()
        self.assertEqual(res["results"][0]["state"], "skipped")
        self.assertEqual(os.listdir(real), [])
        self.assertEqual(self.api.skill_status()["targets"][0]["state"], "linked")


if __name__ == "__main__":
    unittest.main()
