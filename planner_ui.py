"""桌面窗口：pywebview 加载 web/ 下的界面，PlannerApi 提供数据和操作，DesktopRuntime 负责托盘、提醒和单实例。"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import stat
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from datetime import date, datetime, timedelta
from typing import Any, Callable

from planner_core import paths
from planner_core.availability import ProfileError, parse_profile
from planner_core.paths import resource_path
from planner_core.plan_spec import parse_date
from planner_core.pomodoro import Pomodoro
from planner_core.reminders import due_reminders
from planner_core.settings import SettingsError
from planner_core.tasks import TaskError
from planner_core.view_model import build_state, find_session
from planner_core.workspace import Workspace, WorkspaceError

APP_TITLE = "计划本"
APP_VERSION = "0.2.0"
PROFILE_FIELDS = ("version", "buffer_minutes", "weekly", "exceptions", "holidays", "holiday")
SHORTCUT_NAME = "计划本.lnk"
SKILL_NAME = "plan-builder"
SKILL_MARKER = ".study-planner.json"  # 安装时写入，记录安装的版本


# ---------- plan-builder skill 安装 ----------

def skill_source_dir() -> str | None:
    """App 自带的 skill 文件。打包时只放入 SKILL.md 和 references/*.md。"""
    path = resource_path(os.path.join("skills", SKILL_NAME))
    return path if os.path.isfile(os.path.join(path, "SKILL.md")) else None


def skill_targets() -> list[tuple[str, str]]:
    """Claude Code 总是安装，Codex 只在 ~/.codex 存在时安装。"""
    home = os.path.expanduser("~")
    targets = [("Claude Code", os.path.join(home, ".claude", "skills", SKILL_NAME))]
    if os.path.isdir(os.path.join(home, ".codex")):
        targets.append(("Codex", os.path.join(home, ".codex", "skills", SKILL_NAME)))
    return targets


def is_link(path: str) -> bool:
    """符号链接或目录联接（junction）。"""
    try:
        info = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT


def installed_skill_version(target: str) -> str | None:
    try:
        with open(os.path.join(target, SKILL_MARKER), encoding="utf-8") as handle:
            return json.load(handle).get("version")
    except (OSError, ValueError, AttributeError):
        return None


def copy_skill(source: str, target: str) -> None:
    """复制 SKILL.md 和 references 下的 .md 文件。目标里的其他文件（例如 references/local/）保留不动。"""
    os.makedirs(os.path.join(target, "references"), exist_ok=True)
    shutil.copy2(os.path.join(source, "SKILL.md"), os.path.join(target, "SKILL.md"))
    ref_dir = os.path.join(source, "references")
    if os.path.isdir(ref_dir):
        for name in os.listdir(ref_dir):
            path = os.path.join(ref_dir, name)
            if os.path.isfile(path) and name.endswith(".md"):
                shutil.copy2(path, os.path.join(target, "references", name))
    with open(os.path.join(target, SKILL_MARKER), "w", encoding="utf-8") as handle:
        json.dump({"version": APP_VERSION, "installed": datetime.now().isoformat(timespec="seconds")}, handle)


# ---------- 开机自启 ----------

def startup_folder() -> str:
    return os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup")


def autostart_supported() -> bool:
    """只有打包后的 exe、且使用默认数据目录时才管理开机自启。"""
    return sys.platform == "win32" and getattr(sys, "frozen", False) and not os.environ.get(paths.ENV_HOME)


def autostart_enabled(folder: str | None = None) -> bool:
    return os.path.exists(os.path.join(folder or startup_folder(), SHORTCUT_NAME))


def set_autostart(enabled: bool, target: str | None = None, folder: str | None = None) -> None:
    shortcut = os.path.join(folder or startup_folder(), SHORTCUT_NAME)
    if not enabled:
        if os.path.exists(shortcut):
            os.remove(shortcut)
        return
    target = target or sys.executable
    script = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:SP_LINK); "
        "$s.TargetPath = $env:SP_TARGET; $s.Arguments = '--background'; "
        "$s.WorkingDirectory = (Split-Path $env:SP_TARGET); $s.IconLocation = $env:SP_TARGET; $s.Save()"
    )
    env = dict(os.environ, SP_LINK=shortcut, SP_TARGET=target)
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], env=env, check=True,
                   capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _to_minutes(text: str) -> int:
    hour, minute = text.split(":")
    return int(hour) * 60 + int(minute)


def menu_text(text: str, limit: int = 24) -> str:
    """托盘菜单项文字：过长时截断，& 在 Windows 菜单里是快捷键标记，需要写成 &&。"""
    text = text if len(text) <= limit else text[: limit - 1] + "…"
    return text.replace("&", "&&")


# ---------- 系统通知 ----------

def windows_toasts_enabled() -> bool | None:
    """读取 Windows“设置 → 系统 → 通知”的总开关。关闭时托盘图标发出的通知不会弹出。

    返回 None 表示不是 Windows 或读取失败。
    """
    if sys.platform != "win32":
        return None
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\PushNotifications") as key:
            value, _ = winreg.QueryValueEx(key, "ToastEnabled")
    except FileNotFoundError:
        return True  # 没有这个值时为默认的开启状态
    except OSError:
        return None
    return bool(value)


# ---------- 接口 ----------

class PlannerApi:
    """暴露给前端的接口。pywebview 和开发用 HTTP 服务器共用这一个类。"""

    def __init__(self, home: str | None = None, today: date | None = None) -> None:
        self._lock = threading.RLock()
        self._today_override = today
        self._ws = Workspace(home)
        self._fingerprint = self._ws.fingerprint()
        self._pomodoro = Pomodoro(lambda: self._ws.settings["pomodoro"])
        self._notifier: Callable[[str, str], None] | None = None
        self._last_check = datetime.now()
        self._fired: set[str] = set()
        self._generation = 0  # 每次因外部修改重新加载时加一
        self._seen_generation = 0
        self._ui_changes = 0  # 托盘菜单改了状态（完成任务、番茄钟等）时加一，前端轮询到后刷新
        self._seen_ui_changes = 0
        self._mute_until: datetime | None = None  # 暂停任务提醒到这个时间，番茄钟提醒不受影响

    # ----- 内部 -----

    def _today(self) -> date:
        return self._today_override or date.today()

    def _notify(self, title: str, message: str) -> None:
        if self._notifier:
            self._notifier(title, message)

    def _reload_if_changed(self) -> bool:
        current = self._ws.fingerprint()
        if current == self._fingerprint:
            return False
        self._ws.reload()
        self._fingerprint = self._ws.fingerprint()
        self._generation += 1
        return True

    def _after_write(self) -> None:
        self._fingerprint = self._ws.fingerprint()

    def background_tick(self, now: datetime | None = None) -> None:
        """推进番茄钟、发送到期提醒。桌面端由后台线程调用，开发服务器在每次请求时调用。"""
        with self._lock:
            reminders_cfg = self._ws.settings["reminders"]
            for event in self._pomodoro.tick():
                if event.kind == "focus_done":
                    self._ws.progress.add_focus(event.minutes, event.task)
                    if reminders_cfg["pomodoro"]:
                        rest = self._ws.settings["pomodoro"]["long_break" if event.next_mode == "long_break" else "short_break"]
                        title = f"专注 {event.minutes} 分钟完成"
                        self._notify(title, f"{(event.task or {}).get('title') or '专注'}，休息 {rest} 分钟")
                elif reminders_cfg["pomodoro"]:
                    self._notify("休息结束", "可以开始下一个番茄钟")
            now = now or datetime.now()
            self._reload_if_changed()
            if self._mute_until is not None and now >= self._mute_until:
                self._mute_until = None
            for reminder in due_reminders(self._ws, self._ws.settings, self._last_check, now):
                if reminder.key in self._fired:
                    continue
                self._fired.add(reminder.key)  # 暂停期间到期的提醒直接跳过，恢复后不补发
                if self._mute_until is None:
                    self._notify(reminder.title, reminder.message)
            self._last_check = now

    # ----- 读取 -----

    def state(self, selected: str | None = None) -> dict[str, Any]:
        with self._lock:
            if self._notifier is None:
                self.background_tick()
            try:
                day = parse_date(selected) if selected else self._today()
            except ValueError:
                day = self._today()
            state = build_state(self._ws, day, self._today())
            state["pomodoro"] = self._pomodoro.snapshot()
            state["app"] = {"autostart_supported": autostart_supported(), "autostart_enabled": autostart_enabled(),
                            "tray": self._notifier is not None, "notifications_enabled": windows_toasts_enabled(),
                            "version": APP_VERSION, "skill": self.skill_status()}
            return state

    def poll(self) -> dict[str, Any]:
        """计划文件夹、profile 或临时任务被外部修改时重新加载。顺带返回番茄钟状态。"""
        with self._lock:
            if self._notifier is None:
                self.background_tick()
            self._reload_if_changed()
            changed = self._generation != self._seen_generation
            self._seen_generation = self._generation
            refresh = self._ui_changes != self._seen_ui_changes
            self._seen_ui_changes = self._ui_changes
            return {"changed": changed, "refresh": refresh, "pomodoro": self._pomodoro.snapshot()}

    # ----- 托盘菜单 -----

    def mark_ui_changed(self) -> None:
        with self._lock:
            self._ui_changes += 1

    def tray_status(self, now: datetime | None = None) -> dict[str, Any]:
        """托盘菜单显示的内容：今天的完成情况、正在进行和下一个任务、番茄钟、提醒暂停状态。"""
        with self._lock:
            now = now or datetime.now()
            if self._mute_until is not None and now >= self._mute_until:
                self._mute_until = None
            today = self._today()
            day = build_state(self._ws, today, today)["day"]
            minute = now.hour * 60 + now.minute
            timed = sorted([t for g in day["groups"] for t in g["tasks"]] + list(day["fixed"]), key=lambda t: t["start"])
            pending = [t for t in timed if not t["done"] and _to_minutes(t["end"]) > minute]
            current = next((t for t in pending if _to_minutes(t["start"]) <= minute), None)
            upcoming = next((t for t in pending if _to_minutes(t["start"]) > minute), None)

            def brief(task: dict[str, Any] | None) -> dict[str, Any] | None:
                return task and {"uid": task["uid"], "title": task["title"], "start": task["start"], "end": task["end"]}

            snap = self._pomodoro.snapshot()
            pomodoro = {
                "mode": snap["mode"], "mode_name": snap["mode_name"], "paused": snap["paused"],
                "task_title": (snap["task"] or {}).get("title"),
                "ends_at": datetime.fromtimestamp(snap["ends_at_ms"] / 1000).strftime("%H:%M") if snap["ends_at_ms"] else None,
                "remaining_min": math.ceil(snap["remaining_s"] / 60) if snap["paused"] and snap["remaining_s"] is not None else None,
            }
            muted = None
            if self._mute_until is not None:
                end_of_day = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
                muted = "今天结束" if self._mute_until >= end_of_day else self._mute_until.strftime("%H:%M")
            return {
                "date": today.isoformat(), "done": day["done"], "total": day["total"],
                "left_minutes": day["minutes"] - day["done_minutes"],
                "current": brief(current), "next": brief(upcoming), "pomodoro": pomodoro, "muted_until": muted,
            }

    def mute_reminders(self, minutes: int | None = None, now: datetime | None = None) -> dict[str, Any]:
        """暂停任务提醒。minutes 为空时暂停到今天结束。"""
        now = now or datetime.now()
        with self._lock:
            if minutes:
                self._mute_until = now + timedelta(minutes=int(minutes))
            else:
                self._mute_until = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
            return {"ok": True}

    def unmute_reminders(self) -> dict[str, Any]:
        with self._lock:
            self._mute_until = None
            return {"ok": True}

    def reload(self) -> dict[str, Any]:
        with self._lock:
            self._ws.reload()
            self._after_write()
            return {"ok": True}

    # ----- 任务和空闲时间 -----

    def set_done(self, uid: str, done: bool) -> dict[str, Any]:
        with self._lock:
            session = find_session(self._ws, uid)
            if session is None:
                return {"ok": False, "error": "找不到这个任务，计划文件可能刚被修改，请刷新后再试。"}
            try:
                self._ws.set_done(session, bool(done))
            except OSError as exc:
                return {"ok": False, "error": f"保存完成记录失败：{exc}"}
            return {"ok": True}

    def save_profile(self, data: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            payload = {key: data[key] for key in PROFILE_FIELDS if isinstance(data, dict) and key in data}
            try:
                profile = parse_profile(payload)
            except ProfileError as exc:
                return {"ok": False, "errors": exc.errors}
            try:
                self._ws.save_profile(profile)
            except OSError as exc:
                return {"ok": False, "errors": [f"保存失败：{exc}"]}
            self._after_write()
            return {"ok": True}

    def add_task(self, data: dict[str, Any]) -> dict[str, Any]:
        return self._task_call(lambda: self._ws.add_task(data))

    def update_task(self, task_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return self._task_call(lambda: self._ws.update_task(task_id, data))

    def delete_task(self, task_id: str) -> dict[str, Any]:
        return self._task_call(lambda: self._ws.delete_task(task_id))

    def _task_call(self, action: Callable[[], Any]) -> dict[str, Any]:
        with self._lock:
            try:
                action()
            except TaskError as exc:
                return {"ok": False, "errors": exc.errors}
            except OSError as exc:
                return {"ok": False, "errors": [f"保存失败：{exc}"]}
            self._after_write()
            return {"ok": True}

    # ----- 归档 -----

    def archive_plan(self, plan_id: str) -> dict[str, Any]:
        return self._archive_call(lambda: self._ws.archive_plan(plan_id))

    def restore_plan(self, filename: str) -> dict[str, Any]:
        return self._archive_call(lambda: self._ws.restore_plan(filename))

    def delete_archived(self, filename: str) -> dict[str, Any]:
        return self._archive_call(lambda: self._ws.delete_archived(filename))

    def _archive_call(self, action: Callable[[], Any]) -> dict[str, Any]:
        with self._lock:
            try:
                action()
            except (WorkspaceError, OSError) as exc:
                return {"ok": False, "error": str(exc)}
            self._after_write()
            return {"ok": True}

    # ----- 设置 -----

    def save_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            try:
                settings = self._ws.save_settings(data)
            except SettingsError as exc:
                return {"ok": False, "errors": exc.errors}
            except OSError as exc:
                return {"ok": False, "errors": [f"保存失败：{exc}"]}
        if autostart_supported() and settings["app"]["autostart"] != autostart_enabled():
            try:
                set_autostart(settings["app"]["autostart"])
            except (OSError, subprocess.CalledProcessError) as exc:
                return {"ok": False, "errors": [f"设置已保存，但开机自启修改失败：{exc}"]}
        return {"ok": True}

    def test_notification(self) -> dict[str, Any]:
        if self._notifier is None:
            return {"ok": False, "error": "当前不是桌面窗口，无法发送系统通知"}
        self._notify("计划本测试通知", "能看到这条通知，说明提醒功能正常")
        if windows_toasts_enabled() is False:
            return {"ok": True, "warning": "已发送，但 Windows 的通知总开关是关闭的，通知不会弹出。在“设置 → 系统 → 通知”里打开“通知”后再试。"}
        return {"ok": True, "message": "已发送测试通知"}

    def open_notification_settings(self) -> dict[str, Any]:
        """打开 Windows 的通知设置页，由用户自己修改。"""
        return self._open("ms-settings:notifications")

    # ----- plan-builder skill -----

    def skill_status(self) -> dict[str, Any]:
        items = []
        for label, target in skill_targets():
            if is_link(target):
                state, detail = "linked", f"链接到 {os.path.realpath(target)}"
            elif os.path.isfile(os.path.join(target, "SKILL.md")):
                version = installed_skill_version(target)
                state = "installed" if version == APP_VERSION else "outdated"
                detail = f"已安装 {version}" if version else "已安装（版本未知）"
            else:
                state, detail = "missing", "未安装"
            items.append({"label": label, "target": target, "state": state, "detail": detail})
        return {"available": skill_source_dir() is not None, "version": APP_VERSION, "targets": items}

    def install_skill(self) -> dict[str, Any]:
        """把 App 自带的 plan-builder skill 复制到 Claude Code（和 Codex）的 skills 目录。链接不覆盖。"""
        source = skill_source_dir()
        if source is None:
            return {"ok": False, "error": "这个版本没有内置 skill 文件"}
        results = []
        for label, target in skill_targets():
            if is_link(target):
                results.append({"label": label, "state": "skipped",
                                "message": f"{label}：{target} 是链接（指向 {os.path.realpath(target)}），没有覆盖"})
                continue
            try:
                copy_skill(source, target)
            except OSError as exc:
                results.append({"label": label, "state": "error", "message": f"{label}：复制失败（{exc}）"})
                continue
            results.append({"label": label, "state": "installed", "message": f"{label}：已安装到 {target}"})
        return {"ok": not any(item["state"] == "error" for item in results), "results": results}

    # ----- 番茄钟 -----

    def pomodoro_start(self, uid: str | None = None) -> dict[str, Any]:
        with self._lock:
            task = None
            if uid:
                session = find_session(self._ws, uid)
                if session:
                    task = {"uid": session.uid, "title": session.title, "plan_id": session.plan_id, "plan_name": session.plan_name}
            self._pomodoro.start_focus(task)
            return self._pomodoro.snapshot()

    def pomodoro_pause(self) -> dict[str, Any]:
        self._pomodoro.pause()
        return self._pomodoro.snapshot()

    def pomodoro_resume(self) -> dict[str, Any]:
        self._pomodoro.resume()
        return self._pomodoro.snapshot()

    def pomodoro_stop(self) -> dict[str, Any]:
        self._pomodoro.stop()
        return self._pomodoro.snapshot()

    def pomodoro_skip(self) -> dict[str, Any]:
        self._pomodoro.skip_break()
        return self._pomodoro.snapshot()

    def pomodoro_tick(self) -> dict[str, Any]:
        """倒计时归零时前端调用，立即推进状态，不等后台线程。"""
        with self._lock:
            self.background_tick()
            return self._pomodoro.snapshot()

    # ----- 打开文件和链接 -----

    def open_plans_dir(self) -> dict[str, Any]:
        return self._open(self._ws.plans_dir)

    def open_data_dir(self) -> dict[str, Any]:
        return self._open(self._ws.home)

    def open_file(self, path: str) -> dict[str, Any]:
        with self._lock:
            allowed = {plan.source_path for plan in self._ws.plans} | {item.path for item in self._ws.plan_errors}
            allowed |= {item["path"] for item in self._ws.archived()} | {self._ws.profile_path}
        if path not in allowed:
            return {"ok": False, "error": "只能打开计划文件和空闲时间文件"}
        return self._open(path)

    def open_url(self, url: str) -> dict[str, Any]:
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            return {"ok": False, "error": "只能打开 http 或 https 链接"}
        webbrowser.open(url)
        return {"ok": True}

    @staticmethod
    def _open(path: str) -> dict[str, Any]:
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except OSError as exc:
            return {"ok": False, "error": f"无法打开 {path}：{exc}"}
        return {"ok": True}


# ---------- 桌面运行时 ----------

class SingleInstance:
    """命名互斥量保证只运行一个实例。第二个实例通过命名事件通知第一个实例显示窗口。"""

    def __init__(self, home: str) -> None:
        import ctypes

        self._kernel32 = ctypes.windll.kernel32
        suffix = hashlib.sha1(home.lower().encode("utf-8")).hexdigest()[:12]
        self._mutex = self._kernel32.CreateMutexW(None, False, f"Local\\Jihuaben.{suffix}.Mutex")
        self.is_first = self._kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS
        self._event_name = f"Local\\Jihuaben.{suffix}.Show"
        self._event = self._kernel32.CreateEventW(None, False, False, self._event_name) if self.is_first else None

    def signal_first(self) -> None:
        handle = self._kernel32.OpenEventW(0x0002, False, self._event_name)  # EVENT_MODIFY_STATE
        if handle:
            self._kernel32.SetEvent(handle)
            self._kernel32.CloseHandle(handle)

    def wait_for_show(self, callback: Callable[[], None]) -> None:
        def loop() -> None:
            while True:
                self._kernel32.WaitForSingleObject(self._event, 0xFFFFFFFF)
                callback()

        threading.Thread(target=loop, daemon=True).start()


SEPARATOR = "-"


def tray_menu_spec(status: dict[str, Any]) -> list[Any]:
    """按 tray_status 的结果生成托盘菜单。每项是 SEPARATOR 或
    {"text", "action": (名称, 参数...) 或 None, "enabled", "default", "submenu"}，由 DesktopRuntime 转成 pystray 菜单。"""

    def item(text: str, action: tuple | None = None, *, enabled: bool = True, default: bool = False,
             submenu: list | None = None) -> dict[str, Any]:
        return {"text": text, "action": action, "enabled": enabled, "default": default, "submenu": submenu}

    current, upcoming = status.get("current"), status.get("next")
    items: list[Any] = [item("打开计划本", ("show",), default=True), SEPARATOR]
    if status.get("total"):
        items.append(item(f"今天 {status['done']}/{status['total']} 项完成，还剩 {status['left_minutes']} 分钟", enabled=False))
    else:
        items.append(item("今天没有安排任务", enabled=False))
    if current:
        items.append(item(f"进行中：{current['start']}–{current['end']} {menu_text(current['title'])}", ("view", "day")))
        items.append(item(f"标记完成：{menu_text(current['title'])}", ("set_done", current["uid"])))
    if upcoming:
        items.append(item(f"下一项：{upcoming['start']} {menu_text(upcoming['title'])}", ("view", "day")))

    items.append(SEPARATOR)
    pomodoro = status.get("pomodoro") or {"mode": "idle"}
    if pomodoro["mode"] == "idle":
        target = current or upcoming
        if target:
            items.append(item(f"开始专注：{menu_text(target['title'])}", ("pomodoro_start", target["uid"])))
        items.append(item("开始专注（不关联任务）", ("pomodoro_start", None)))
    else:
        name = pomodoro["mode_name"]
        if pomodoro["paused"]:
            items.append(item(f"{name}已暂停，还剩 {pomodoro['remaining_min']} 分钟", enabled=False))
            items.append(item("继续", ("pomodoro_resume",)))
        else:
            items.append(item(f"{name}中，{pomodoro['ends_at']} 结束", enabled=False))
            items.append(item("暂停", ("pomodoro_pause",)))
        if pomodoro["mode"] == "focus":
            items.append(item("放弃本次专注", ("pomodoro_stop",)))
        else:
            items.append(item("跳过休息", ("pomodoro_skip",)))

    items.append(SEPARATOR)
    if status.get("muted_until"):
        until = status["muted_until"]
        items.append(item("任务提醒已暂停到今天结束" if until == "今天结束" else f"任务提醒已暂停，{until} 恢复", enabled=False))
        items.append(item("恢复任务提醒", ("unmute",)))
    else:
        items.append(item("暂停任务提醒", submenu=[
            item("30 分钟", ("mute", 30)), item("1 小时", ("mute", 60)), item("到今天结束", ("mute", None)),
        ]))
    items.append(item("跳转到", submenu=[
        item("今天的日程", ("view", "day")), item("计划", ("view", "plans")),
        item("空闲时间", ("view", "profile")), item("设置", ("view", "settings")),
    ]))
    items.append(item("打开计划文件夹", ("open_plans_dir",)))
    items += [SEPARATOR, item("退出", ("quit",))]
    return items


class DesktopRuntime:
    def __init__(self, api: PlannerApi) -> None:
        self.api = api
        self.window = None
        self.icon = None
        self.quitting = False
        self.hint_shown = False
        self.tray_status: dict[str, Any] = {}

    def notify(self, title: str, message: str) -> None:
        if self.icon is not None:
            try:
                self.icon.notify(message, title)
            except Exception:  # 通知失败不影响主程序
                pass
        if self.api._ws.settings["reminders"]["sound"]:
            try:
                import winsound

                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except (ImportError, RuntimeError):
                pass

    def start_tray(self) -> None:
        import pystray
        from PIL import Image

        image = Image.open(resource_path(os.path.join("assets", "tray_icon.png")))
        self.tray_status = self.api.tray_status()
        # 菜单按 tray_status 动态生成，状态变化时由 refresh_menu 调用 update_menu 重建
        self.icon = pystray.Icon("jihuaben", image, APP_TITLE, pystray.Menu(self._menu_items))
        self.icon.run_detached()

    def _menu_items(self) -> list[Any]:
        import pystray

        def convert(spec: Any) -> Any:
            if spec == SEPARATOR:
                return pystray.Menu.SEPARATOR
            if spec["submenu"]:
                return pystray.MenuItem(spec["text"], pystray.Menu(*[convert(x) for x in spec["submenu"]]))
            action = spec["action"]
            return pystray.MenuItem(spec["text"], (lambda: self.run_action(action)) if action else None,
                                    enabled=spec["enabled"], default=spec["default"])

        return [convert(spec) for spec in tray_menu_spec(self.tray_status)]

    def run_action(self, action: tuple) -> None:
        name, *args = action
        try:
            if name == "show":
                self.show()
            elif name == "view":
                self.open_view(args[0])
            elif name == "quit":
                self.quit()
                return
            elif name == "mute":
                self.api.mute_reminders(args[0])
            elif name == "unmute":
                self.api.unmute_reminders()
            elif name in ("set_done",):
                self.api.set_done(args[0], True)
            elif name in ("pomodoro_start", "pomodoro_pause", "pomodoro_resume", "pomodoro_stop", "pomodoro_skip",
                          "open_plans_dir"):
                getattr(self.api, name)(*args)
        except Exception:  # 菜单操作失败不影响主程序
            traceback.print_exc()
        self.api.mark_ui_changed()
        self.refresh_menu(force=True)

    def refresh_menu(self, force: bool = False) -> None:
        """状态有变化时重建托盘菜单。番茄钟显示结束时刻而不是剩余分钟，避免每分钟重建。"""
        if self.icon is None:
            return
        try:
            status = self.api.tray_status()
        except Exception:
            traceback.print_exc()
            return
        if force or status != self.tray_status:
            self.tray_status = status
            self.icon.update_menu()

    def show(self) -> None:
        if self.window is not None:
            self.window.show()
            self.window.restore()

    def open_view(self, view: str) -> None:
        self.show()
        if self.window is not None:
            self.window.evaluate_js(f"window.gotoView && window.gotoView({json.dumps(view)})")

    def quit(self) -> None:
        self.quitting = True
        if self.icon is not None:
            self.icon.stop()
        if self.window is not None:
            self.window.destroy()

    def on_closing(self) -> bool:
        if self.quitting or not self.api._ws.settings["app"]["close_to_tray"]:
            return True
        self.window.hide()
        if not self.hint_shown:
            self.hint_shown = True
            self.notify("计划本仍在运行", "已缩到右下角托盘，提醒会照常发送。在托盘菜单里选“退出”可以完全关闭。")
        return False

    def background_loop(self) -> None:
        while not self.quitting:
            try:
                self.api.background_tick()
                self.refresh_menu()
            except Exception:  # 后台线程出错时继续运行，下一轮再试
                traceback.print_exc()
            time.sleep(2)


def show_fatal(message: str) -> None:
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, APP_TITLE, 0x10)
    else:
        print(message, file=sys.stderr)


def main() -> None:
    try:
        import webview

        background = "--background" in sys.argv
        home = paths.data_home()
        instance = SingleInstance(home)
        if not instance.is_first:
            instance.signal_first()
            return
        api = PlannerApi()
        try:
            paths.write_app_info(api._ws.home, APP_VERSION)  # 让命令行工具和 skill 找到这个 App 的数据目录
        except OSError:
            traceback.print_exc()
        runtime = DesktopRuntime(api)
        api._notifier = runtime.notify
        if autostart_supported() and api._ws.settings["app"]["autostart"] and not autostart_enabled():
            try:
                set_autostart(True)
            except (OSError, subprocess.CalledProcessError):
                pass
        window = webview.create_window(
            APP_TITLE, url=resource_path(os.path.join("web", "index.html")), js_api=api,
            width=1280, height=840, min_size=(980, 640), background_color="#F6F7F9", hidden=background,
        )
        runtime.window = window
        window.events.closing += runtime.on_closing
        instance.wait_for_show(runtime.show)
        runtime.start_tray()
        threading.Thread(target=runtime.background_loop, daemon=True).start()
        # 关闭私密模式，界面的本地存储（计划卡片的折叠状态等）在重启后保留
        webview.start(
            icon=resource_path(os.path.join("assets", "app_icon.ico")),
            private_mode=False, storage_path=os.path.join(home, "webview"),
        )
        runtime.quitting = True
        if runtime.icon is not None:
            runtime.icon.stop()
    except Exception as exc:  # 窗口程序没有控制台，用系统对话框显示原因
        show_fatal(f"启动失败：{exc}\n\n{traceback.format_exc()[-1500:]}")
