from __future__ import annotations

import json
import os
import sys

APP_DIR_NAME = "StudyPlanner"
ENV_HOME = "STUDY_PLANNER_HOME"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(relative_path: str) -> str:
    """打包后从 PyInstaller 解包目录取资源，源码运行时从项目根目录取。"""
    base_path = getattr(sys, "_MEIPASS", PROJECT_ROOT)
    return os.path.join(base_path, relative_path)


def default_home() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, APP_DIR_NAME)


def app_info_path() -> str:
    """App 启动时写入的记录文件，位置固定，不随 STUDY_PLANNER_HOME 变化。"""
    return os.path.join(default_home(), "app.json")


def read_app_info() -> dict:
    try:
        with open(app_info_path(), "r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def data_home(use_app_info: bool = False) -> str:
    """数据目录：环境变量 STUDY_PLANNER_HOME > App 记录的数据目录（仅命令行使用）> %APPDATA%\\StudyPlanner。"""
    override = os.environ.get(ENV_HOME)
    if override:
        return os.path.abspath(override)
    if use_app_info:
        recorded = read_app_info().get("home")
        if isinstance(recorded, str) and os.path.isdir(recorded):
            return recorded
    return default_home()


def cli_command() -> list[str]:
    """当前 App 对应的命令行工具。打包后为同目录的 planner-cli.exe，源码运行时为 python planner_cli.py。"""
    if getattr(sys, "frozen", False):
        exe = os.path.join(os.path.dirname(sys.executable), "planner-cli.exe")
        return [exe] if os.path.exists(exe) else []
    python = sys.executable
    console = os.path.join(os.path.dirname(python), "python.exe")
    if os.path.basename(python).lower() == "pythonw.exe" and os.path.exists(console):
        python = console
    return [python, os.path.join(PROJECT_ROOT, "planner_cli.py")]


def write_app_info(home: str, version: str) -> None:
    """记录 App 正在使用的数据目录和命令行工具，供命令行工具和 skill 读取。"""
    from datetime import datetime

    from .storage import write_json_atomic

    write_json_atomic(app_info_path(), {
        "version": version,
        "home": os.path.abspath(home),
        "cli": cli_command(),
        "app": sys.executable if getattr(sys, "frozen", False) else os.path.join(PROJECT_ROOT, "planner_app.py"),
        "updated": datetime.now().isoformat(timespec="seconds"),
    }, backup=False)


def plans_dir(home: str) -> str:
    return os.path.join(home, "plans")


def profile_path(home: str) -> str:
    return os.path.join(home, "profile.json")


def progress_path(home: str) -> str:
    return os.path.join(home, "progress.json")


def tasks_path(home: str) -> str:
    return os.path.join(home, "tasks.json")


def settings_path(home: str) -> str:
    return os.path.join(home, "settings.json")


def day_order_path(home: str) -> str:
    return os.path.join(home, "day_order.json")


def archive_dir(home: str) -> str:
    return os.path.join(plans_dir(home), "archive")


def ensure_home(home: str) -> None:
    os.makedirs(plans_dir(home), exist_ok=True)
