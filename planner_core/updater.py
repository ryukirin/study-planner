"""检查和安装新版本。

新版本来自 GitHub Releases 上最新的正式版，安装包是其中的 StudyPlanner-windows.zip。
安装时把正在运行的 exe 改名为 *.exe.old（Windows 允许给运行中的 exe 改名，不允许删除），
再把新的 exe 复制到原来的位置，由新进程启动后删除 *.exe.old。
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import zipfile
from typing import Any, Callable
from urllib.error import URLError
from urllib.request import Request, urlopen

REPO = "ryukirin/study-planner"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
ASSET_NAME = "StudyPlanner-windows.zip"
APP_EXE = "StudyPlanner.exe"
EXE_NAMES = (APP_EXE, "planner-cli.exe")
USER_AGENT = "StudyPlanner-updater"
TIMEOUT = 20
CHUNK = 256 * 1024


class UpdateError(Exception):
    pass


def parse_version(text: str) -> tuple[int, ...]:
    """'v0.2.0' 或 '0.2.0' → (0, 2, 0)。"""
    raw = str(text).strip().lstrip("vV")
    try:
        parts = tuple(int(part) for part in raw.split("."))
    except ValueError:
        raise UpdateError(f"版本号 {text!r} 格式不对") from None
    if not parts:
        raise UpdateError(f"版本号 {text!r} 格式不对")
    return parts


def _request(url: str, accept: str) -> Request:
    return Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})


def fetch_latest(opener: Callable[..., Any] = urlopen) -> dict[str, Any]:
    """读取最新正式版的信息（GitHub API 的原始 JSON）。"""
    try:
        with opener(_request(LATEST_URL, "application/vnd.github+json"), timeout=TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        raise UpdateError(f"无法连接 GitHub：{getattr(exc, 'reason', exc)}") from exc
    except (OSError, ValueError) as exc:
        raise UpdateError(f"读取版本信息失败：{exc}") from exc


def release_info(data: dict[str, Any], current: str) -> dict[str, Any]:
    """整理成界面需要的信息。newer 表示比 current 新。"""
    tag = data.get("tag_name")
    if not isinstance(tag, str):
        raise UpdateError("版本信息里没有版本号")
    latest = tag.lstrip("vV")
    asset = next((item for item in data.get("assets") or [] if item.get("name") == ASSET_NAME), None)
    return {
        "current": current,
        "latest": latest,
        "newer": parse_version(latest) > parse_version(current),
        "notes": data.get("body") or "",
        "url": data.get("html_url") or RELEASES_PAGE,
        "published": (data.get("published_at") or "")[:10],
        "asset": {"url": asset.get("browser_download_url"), "size": asset.get("size") or 0,
                  "digest": asset.get("digest") or ""} if asset else None,
    }


def download(asset: dict[str, Any], dest_dir: str, progress: Callable[[int, int], None] | None = None,
             opener: Callable[..., Any] = urlopen) -> str:
    """下载安装包并解压出 exe，返回存放新 exe 的文件夹。

    核对文件大小，GitHub 提供 sha256 时也核对 sha256。压缩包里必须有 StudyPlanner.exe。"""
    if not asset or not asset.get("url"):
        raise UpdateError(f"这个版本没有 {ASSET_NAME}")
    os.makedirs(dest_dir, exist_ok=True)
    part = os.path.join(dest_dir, ASSET_NAME + ".part")
    total = int(asset.get("size") or 0)
    digest = hashlib.sha256()
    received = 0
    try:
        with opener(_request(asset["url"], "application/octet-stream"), timeout=TIMEOUT) as response, open(part, "wb") as handle:
            while True:
                chunk = response.read(CHUNK)
                if not chunk:
                    break
                handle.write(chunk)
                digest.update(chunk)
                received += len(chunk)
                if progress:
                    progress(received, total)
    except URLError as exc:
        raise UpdateError(f"下载失败：{getattr(exc, 'reason', exc)}") from exc
    except OSError as exc:
        raise UpdateError(f"下载失败：{exc}") from exc
    if total and received != total:
        raise UpdateError(f"下载不完整：收到 {received} 字节，应为 {total} 字节")
    expected = str(asset.get("digest") or "")
    if expected.startswith("sha256:") and expected[7:].lower() != digest.hexdigest():
        raise UpdateError("下载的文件校验失败，请重试")
    archive = os.path.join(dest_dir, ASSET_NAME)
    os.replace(part, archive)
    files = os.path.join(dest_dir, "files")
    shutil.rmtree(files, ignore_errors=True)
    os.makedirs(files)
    try:
        with zipfile.ZipFile(archive) as bundle:
            # 只取需要的 exe，按文件名放进 files，不使用压缩包里的路径
            members = {os.path.basename(name.replace("\\", "/")): name for name in bundle.namelist()}
            if APP_EXE not in members:
                raise UpdateError(f"安装包里没有 {APP_EXE}")
            for name in EXE_NAMES:
                if name in members:
                    with bundle.open(members[name]) as source, open(os.path.join(files, name), "wb") as target:
                        shutil.copyfileobj(source, target)
    except zipfile.BadZipFile as exc:
        raise UpdateError("安装包已损坏，请重试") from exc
    return files


def install(files_dir: str, target_dir: str) -> str:
    """用 files_dir 里的 exe 替换 target_dir 里的同名文件，返回新的 StudyPlanner.exe 的路径。

    原来的 exe 改名为 *.exe.old。中途失败时恢复已经替换的文件。"""
    if not os.path.isfile(os.path.join(files_dir, APP_EXE)):
        raise UpdateError(f"没有找到下载的 {APP_EXE}")
    done: list[str] = []
    try:
        for name in EXE_NAMES:
            source = os.path.join(files_dir, name)
            if not os.path.isfile(source):
                continue
            target = os.path.join(target_dir, name)
            old = target + ".old"
            if os.path.exists(old):
                os.remove(old)
            if os.path.exists(target):
                os.replace(target, old)
            done.append(name)
            shutil.copy2(source, target)
    except OSError as exc:
        for name in reversed(done):
            target = os.path.join(target_dir, name)
            old = target + ".old"
            if os.path.exists(old):
                try:
                    if os.path.exists(target):
                        os.remove(target)
                    os.replace(old, target)
                except OSError:
                    pass
        raise UpdateError(f"替换文件失败：{exc}") from exc
    return os.path.join(target_dir, APP_EXE)


def cleanup_old(target_dir: str) -> None:
    """删除上次更新留下的 *.exe.old。旧进程还没退出时删不掉，下次启动再删。"""
    for name in EXE_NAMES:
        try:
            os.remove(os.path.join(target_dir, name + ".old"))
        except OSError:
            pass
