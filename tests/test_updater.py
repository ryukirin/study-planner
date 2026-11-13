import hashlib
import io
import json
import os
import ssl
import tempfile
import unittest
import zipfile
from unittest import mock

from planner_core import updater
from tests.helpers import TempHome


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def opener_for(payload: bytes):
    return lambda request, timeout=None, context=None: FakeResponse(payload)


def make_zip(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        for name, data in files.items():
            bundle.writestr(name, data)
    return buffer.getvalue()


def release(tag="v0.3.0", asset=True, size=10, digest=""):
    data = {"tag_name": tag, "body": "## 更新内容\n- 新功能", "html_url": "https://example.test/r", "published_at": "2026-11-20T10:00:00Z",
            "assets": []}
    if asset:
        data["assets"].append({"name": updater.ASSET_NAME, "browser_download_url": "https://example.test/a.zip", "size": size, "digest": digest})
    return data


class VersionTest(unittest.TestCase):
    def test_parse_and_compare(self):
        self.assertEqual(updater.parse_version("v0.2.0"), (0, 2, 0))
        self.assertGreater(updater.parse_version("0.10.0"), updater.parse_version("0.9.3"))
        with self.assertRaises(updater.UpdateError):
            updater.parse_version("v0.3-beta")

    def test_release_info(self):
        info = updater.release_info(release(), "0.2.0")
        self.assertEqual((info["latest"], info["newer"], info["published"]), ("0.3.0", True, "2026-11-20"))
        self.assertEqual(info["asset"]["url"], "https://example.test/a.zip")
        self.assertFalse(updater.release_info(release("v0.2.0"), "0.2.0")["newer"])
        self.assertFalse(updater.release_info(release("v0.1.9"), "0.2.0")["newer"])
        self.assertIsNone(updater.release_info(release(asset=False), "0.2.0")["asset"])

    def test_fetch_latest_sends_generic_user_agent(self):
        seen = {}

        def opener(request, timeout=None, context=None):
            seen["agent"] = request.get_header("User-agent")
            seen["url"] = request.full_url
            seen["context"] = context
            return FakeResponse(json.dumps(release()).encode("utf-8"))

        self.assertEqual(updater.fetch_latest(opener)["tag_name"], "v0.3.0")
        self.assertEqual((seen["agent"], seen["url"]), (updater.USER_AGENT, updater.LATEST_URL))
        self.assertIsInstance(seen["context"], ssl.SSLContext)

    def test_ssl_context_adds_certifi_roots(self):
        import certifi
        system = len(ssl.create_default_context().get_ca_certs())
        self.assertGreater(len(updater.ssl_context().get_ca_certs()), system)
        self.assertTrue(os.path.exists(certifi.where()))


class DownloadTest(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.dir = self._dir.name

    def tearDown(self):
        self._dir.cleanup()

    def asset(self, payload, digest=None):
        digest = "sha256:" + hashlib.sha256(payload).hexdigest() if digest is None else digest
        return {"url": "https://example.test/a.zip", "size": len(payload), "digest": digest}

    def test_download_extracts_only_the_exes(self):
        payload = make_zip({"StudyPlanner.exe": b"app", "sub/planner-cli.exe": b"cli", "../evil.exe": b"x", "readme.txt": b"r"})
        seen = []
        files = updater.download(self.asset(payload), self.dir, lambda received, total: seen.append((received, total)), opener_for(payload))
        self.assertEqual(sorted(os.listdir(files)), ["StudyPlanner.exe", "planner-cli.exe"])
        with open(os.path.join(files, "planner-cli.exe"), "rb") as handle:
            self.assertEqual(handle.read(), b"cli")
        self.assertEqual(seen[-1], (len(payload), len(payload)))
        self.assertFalse(os.path.exists(os.path.join(self.dir, "evil.exe")))

    def test_download_rejects_bad_digest_size_and_missing_exe(self):
        payload = make_zip({"StudyPlanner.exe": b"app"})
        with self.assertRaisesRegex(updater.UpdateError, "校验失败"):
            updater.download(self.asset(payload, "sha256:" + "0" * 64), self.dir, opener=opener_for(payload))
        with self.assertRaisesRegex(updater.UpdateError, "不完整"):
            updater.download({**self.asset(payload), "size": len(payload) + 1}, self.dir, opener=opener_for(payload))
        other = make_zip({"planner-cli.exe": b"cli"})
        with self.assertRaisesRegex(updater.UpdateError, "没有 StudyPlanner.exe"):
            updater.download(self.asset(other), self.dir, opener=opener_for(other))
        with self.assertRaisesRegex(updater.UpdateError, "损坏"):
            updater.download(self.asset(b"not a zip"), self.dir, opener=opener_for(b"not a zip"))


class InstallTest(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.files = os.path.join(self._dir.name, "files")
        self.target = os.path.join(self._dir.name, "app")
        os.makedirs(self.files)
        os.makedirs(self.target)

    def tearDown(self):
        self._dir.cleanup()

    def write(self, folder, name, data):
        with open(os.path.join(folder, name), "wb") as handle:
            handle.write(data)

    def read(self, name):
        with open(os.path.join(self.target, name), "rb") as handle:
            return handle.read()

    def test_install_keeps_old_copies_and_cleanup_removes_them(self):
        for name in updater.EXE_NAMES:
            self.write(self.target, name, b"old")
            self.write(self.files, name, b"new")
        exe = updater.install(self.files, self.target)
        self.assertEqual(exe, os.path.join(self.target, "StudyPlanner.exe"))
        self.assertEqual((self.read("StudyPlanner.exe"), self.read("StudyPlanner.exe.old")), (b"new", b"old"))
        self.assertEqual(self.read("planner-cli.exe"), b"new")
        updater.cleanup_old(self.target)
        self.assertEqual(sorted(os.listdir(self.target)), ["StudyPlanner.exe", "planner-cli.exe"])

    def test_install_rolls_back_on_failure(self):
        for name in updater.EXE_NAMES:
            self.write(self.target, name, b"old")
            self.write(self.files, name, b"new")
        real_copy = updater.shutil.copy2

        def copy(source, target):
            if target.endswith("planner-cli.exe"):
                raise OSError("disk full")
            return real_copy(source, target)

        with mock.patch.object(updater.shutil, "copy2", copy):
            with self.assertRaisesRegex(updater.UpdateError, "替换文件失败"):
                updater.install(self.files, self.target)
        self.assertEqual((self.read("StudyPlanner.exe"), self.read("planner-cli.exe")), (b"old", b"old"))
        self.assertFalse(any(name.endswith(".old") for name in os.listdir(self.target)))


class ApiTest(unittest.TestCase):
    def setUp(self):
        from planner_ui import PlannerApi

        self.home = TempHome()
        self.home.write_profile()
        self.api = PlannerApi(self.home.path)

    def tearDown(self):
        self.home.cleanup()

    def test_check_update_reports_and_refreshes_once(self):
        with mock.patch.object(updater, "fetch_latest", return_value=release("v9.0.0")):
            result = self.api.check_update()
        self.assertEqual((result["ok"], result["latest"], result["newer"], result["has_asset"]), (True, "9.0.0", True, True))
        self.assertNotIn("asset", result)
        self.assertTrue(self.api.poll()["refresh"])
        self.assertEqual(self.api.state()["app"]["update"]["latest"], "9.0.0")
        with mock.patch.object(updater, "fetch_latest", return_value=release("v9.0.0")):
            self.api.check_update()
        self.assertFalse(self.api.poll()["refresh"])

    def test_close_choice_is_remembered(self):
        calls = []
        self.api._hide = lambda: calls.append("hide")
        self.api._quit = lambda: calls.append("quit")
        self.assertEqual(self.api.state()["settings"]["app"]["close_action"], "ask")
        self.assertEqual(self.api.close_choice("tray"), {"ok": True})
        self.assertEqual(self.api.state()["settings"]["app"]["close_action"], "tray")
        self.assertFalse(self.api.close_choice("minimize")["ok"])
        from planner_ui import PlannerApi
        self.assertEqual(PlannerApi(self.home.path).state()["settings"]["app"]["close_action"], "tray")
        import time
        time.sleep(0.4)
        self.assertEqual(calls, ["hide"])

    def test_check_update_error_and_source_run_cannot_install(self):
        with mock.patch.object(updater, "fetch_latest", side_effect=updater.UpdateError("无法连接 GitHub：timeout")):
            self.assertEqual(self.api.check_update(), {"ok": False, "error": "无法连接 GitHub：timeout"})
        self.assertFalse(self.api.state()["app"]["can_update"])
        self.assertFalse(self.api.start_update()["ok"])
        self.assertFalse(self.api.install_update()["ok"])
        self.assertTrue(self.api.state()["settings"]["app"]["check_updates"])


if __name__ == "__main__":
    unittest.main()
