from __future__ import annotations

import os
import sys

APP_DIR_NAME = "StudyPlanner"
ENV_HOME = "STUDY_PLANNER_HOME"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(relative_path: str) -> str:
    """打包后从 PyInstaller 解包目录取资源，源码运行时从项目根目录取。"""
    base_path = getattr(sys, "_MEIPASS", PROJECT_ROOT)
    return os.path.join(base_path, relative_path)


def data_home() -> str:
    override = os.environ.get(ENV_HOME)
    if override:
        return os.path.abspath(override)
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, APP_DIR_NAME)


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


def archive_dir(home: str) -> str:
    return os.path.join(plans_dir(home), "archive")


def ensure_home(home: str) -> None:
    os.makedirs(plans_dir(home), exist_ok=True)
