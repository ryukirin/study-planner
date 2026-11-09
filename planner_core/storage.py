from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from typing import Any, Callable


def write_json_atomic(path: str, data: Any, backup: bool = True) -> None:
    """先写临时文件再替换，替换前把旧文件复制为 .bak。"""
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    if backup and os.path.exists(path):
        shutil.copy2(path, path + ".bak")
    os.replace(tmp_path, path)


def quarantine(path: str) -> str:
    """把无法解析的文件改名保留，避免之后的写入把它覆盖。"""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = f"{path}.corrupt-{stamp}"
    os.replace(path, target)
    return target


def load_json(path: str, default_factory: Callable[[], Any]) -> tuple[Any, str | None]:
    """返回 (数据, 警告)。文件不存在时返回默认值，解析失败时隔离坏文件并返回默认值和警告。"""
    if not os.path.exists(path):
        return default_factory(), None
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            return json.load(handle), None
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        try:
            moved = quarantine(path)
        except OSError as move_exc:
            return default_factory(), f"{path} 无法解析（{exc}），改名保留也失败：{move_exc}"
        return default_factory(), f"{path} 无法解析（{exc}），已改名为 {moved}"
    except OSError as exc:
        return default_factory(), f"{path} 读取失败：{exc}"
