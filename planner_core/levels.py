"""专注等级：按完成的番茄钟累计分钟数计算等级、称号和看剧换算。

升到 Lv n 需要累计 30 × n × (n+1) 分钟。Lv1 要 1 小时，之后每升一级比上一级多 1 小时，没有上限。
称号按等级段给，用户可以改每一段的名字。看剧换算从当前兴趣范围的剧目里选总时长不超过累计时长的最长一部，
没有合适的剧时换算成把最短或最长的一部看了几遍。时长相差不到 10% 的剧算作一组，每次启动 App 时随机选组里的一部。
"""
from __future__ import annotations

import math
import random
from typing import Any

from .show_presets import PRESETS

LEVEL_UNIT = 30  # 分钟

# 称号的起始等级和默认名字。到达起始等级后一直用这个称号，直到下一段
DEFAULT_TITLES: dict[int, str] = {
    0: "番茄种子", 1: "发芽", 3: "幼苗", 5: "开花", 10: "青果",
    15: "红果", 20: "丰收", 30: "番茄园主", 40: "番茄庄园", 50: "番茄传说",
}
TITLE_LEVELS = tuple(sorted(DEFAULT_TITLES))
TITLE_MAX_LEN = 16

CUSTOM_INTEREST = "custom"  # 只用自定义的剧
INTERESTS: tuple[str, ...] = tuple(PRESETS) + (CUSTOM_INTEREST,)
INTEREST_NAMES: dict[str, str] = {key: preset["name"] for key, preset in PRESETS.items()} | {CUSTOM_INTEREST: "只用自定义的剧"}

SHOW_TITLE_MAX_LEN = 30
SHOW_EPISODES_MAX = 2000
SHOW_MINUTES_MAX = 300
CUSTOM_SHOWS_MAX = 50

SIMILAR_RATIO = 0.1  # 时长相差不到 10% 的剧算作差不多
SESSION_PICK = random.random()  # 每次启动 App 时换一次，同一次运行里显示的剧不变


def minutes_for(level: int) -> int:
    """升到这一级需要的累计分钟数。"""
    return LEVEL_UNIT * level * (level + 1)


def level_for(minutes: int) -> int:
    """累计分钟数对应的等级。n(n+1) ≤ minutes // 30，用整数平方根避免浮点误差。"""
    k = max(int(minutes), 0) // LEVEL_UNIT
    return (math.isqrt(4 * k + 1) - 1) // 2


def title_table(overrides: dict[str, str] | None) -> list[dict[str, Any]]:
    """每个等级段的称号。overrides 的键是起始等级的字符串，只保存用户改过的段。"""
    overrides = overrides or {}
    rows = []
    for level in TITLE_LEVELS:
        custom = overrides.get(str(level))
        rows.append({"level": level, "title": custom or DEFAULT_TITLES[level], "default": DEFAULT_TITLES[level],
                     "custom": bool(custom), "minutes": minutes_for(level)})
    return rows


def title_for(level: int, overrides: dict[str, str] | None) -> dict[str, Any]:
    return [row for row in title_table(overrides) if row["level"] <= level][-1]


def show_minutes(show: dict[str, Any]) -> int:
    if "total_minutes" in show:
        return int(show["total_minutes"])
    return int(show["episodes"]) * int(show["minutes_per_episode"])


def show_list(interest: str, custom: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """当前兴趣范围的预设剧目加上自定义的剧，按总时长从短到长排列。"""
    shows = [] if interest == CUSTOM_INTEREST else list(PRESETS.get(interest, {}).get("shows", []))
    shows += [dict(show, custom=True) for show in custom or []]
    items = [{"title": show["title"], "minutes": show_minutes(show), "custom": bool(show.get("custom"))} for show in shows]
    return sorted(items, key=lambda item: (item["minutes"], item["title"]))


def _times(value: float) -> str:
    """遍数保留一位小数，整数不带小数点：2.0 → 2，2.34 → 2.3。"""
    text = f"{value:.1f}"
    return text[:-2] if text.endswith(".0") else text


def match_show(total: int, shows: list[dict[str, Any]], pick: float = 0.0) -> dict[str, Any] | None:
    """换算成一句话。有总时长不超过累计时长、又不是列表里最长的剧时，说看完了其中最长的一部。
    还没到最短的一部，或者已经超过最长的一部时，说把那一部看了几遍。不到 0.1 遍时不显示。
    和选中的剧时长相差不到 10% 的剧都可以显示，pick（0 到 1）决定选哪一部。"""
    if not shows or total <= 0:
        return None
    shortest, longest = shows[0]["minutes"], shows[-1]["minutes"]
    if total < shortest:
        group = [show for show in shows if show["minutes"] <= shortest * (1 + SIMILAR_RATIO)]
    elif total >= longest:
        group = [show for show in shows if show["minutes"] >= longest * (1 - SIMILAR_RATIO)]
    else:
        anchor = max(show["minutes"] for show in shows if show["minutes"] <= total)
        group = [show for show in shows if anchor * (1 - SIMILAR_RATIO) <= show["minutes"] <= total]
    target = group[min(int(pick * len(group)), len(group) - 1)]
    times = None if target["minutes"] <= total < longest else round(total / target["minutes"], 1)
    if times is not None and times < 0.1:
        return None
    if times == 1.0:  # 约 1 遍时说看完，不说“看了 1 遍”
        times = None
    text = f"相当于看完《{target['title']}》" if times is None else f"相当于把《{target['title']}》看了 {_times(times)} 遍"
    return {"title": target["title"], "times": times, "text": text}


def summary(total: int, settings: dict[str, Any], pick: float | None = None) -> dict[str, Any]:
    """界面显示用的等级信息。settings 是 settings.json 里的 levels 段。pick 为空时用这次启动的随机数。"""
    level = level_for(total)
    overrides = settings.get("titles", {})
    start, end = minutes_for(level), minutes_for(level + 1)
    current = title_for(level, overrides)
    shows = show_list(settings.get("interest", ""), settings.get("custom_shows", []))
    return {
        "total_minutes": total, "level": level, "title": current["title"],
        "level_start": start, "next_level_minutes": end, "to_next": end - total,
        "progress": round((total - start) / (end - start), 4),
        "titles": title_table(overrides),
        "show": match_show(total, shows, SESSION_PICK if pick is None else pick) if settings.get("show_shows", True) else None,
        "shows": shows,
        "interests": [{"key": key, "name": INTEREST_NAMES[key]} for key in INTERESTS],
        "interest_note": PRESETS.get(settings.get("interest", ""), {}).get("note", ""),
    }


def format_minutes(minutes: int) -> str:
    """通知里用的时长文字：90 → 1 小时 30 分钟。"""
    hours, rest = divmod(max(int(minutes), 0), 60)
    if not hours:
        return f"{rest} 分钟"
    return f"{hours} 小时" + (f" {rest} 分钟" if rest else "")


def level_up_message(before: int, after: int, settings: dict[str, Any]) -> tuple[str, str] | None:
    """一次专注前后的累计分钟数。升级时返回通知的标题和正文，否则返回 None。"""
    old, new = level_for(before), level_for(after)
    if new <= old:
        return None
    overrides = settings.get("titles", {})
    title = title_for(new, overrides)
    text = f"累计专注 {format_minutes(after)}"
    if title["level"] > old:  # 跨进了新的称号段
        text = f"获得称号「{title['title']}」，" + text
    return f"升到 Lv{new}", text


def validate_titles(value: Any) -> tuple[dict[str, str], list[str]]:
    """校验自定义称号。空字符串表示恢复默认，不保存。"""
    if not isinstance(value, dict):
        return {}, ["自定义称号必须是对象"]
    result: dict[str, str] = {}
    errors: list[str] = []
    allowed = {str(level) for level in TITLE_LEVELS}
    for key, title in value.items():
        if key not in allowed:
            errors.append(f"称号：没有从 Lv{key} 开始的等级段")
            continue
        if not isinstance(title, str):
            errors.append(f"Lv{key} 的称号必须是文字")
            continue
        title = title.strip()
        if len(title) > TITLE_MAX_LEN:
            errors.append(f"Lv{key} 的称号不能超过 {TITLE_MAX_LEN} 个字")
        elif title and title != DEFAULT_TITLES[int(key)]:
            result[key] = title
    return result, errors


def _int_in(value: Any, low: int, high: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def validate_shows(value: Any) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(value, list):
        return [], ["自定义的剧必须是列表"]
    if len(value) > CUSTOM_SHOWS_MAX:
        return [], [f"自定义的剧最多 {CUSTOM_SHOWS_MAX} 部"]
    result: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, show in enumerate(value, 1):
        if not isinstance(show, dict):
            errors.append(f"第 {index} 部自定义的剧格式不对")
            continue
        title = show.get("title").strip() if isinstance(show.get("title"), str) else ""
        name = title or f"第 {index} 部"
        if not 1 <= len(title) <= SHOW_TITLE_MAX_LEN:
            errors.append(f"第 {index} 部自定义的剧：剧名必须是 1 到 {SHOW_TITLE_MAX_LEN} 个字")
        elif not _int_in(show.get("episodes"), 1, SHOW_EPISODES_MAX):
            errors.append(f"《{name}》：集数必须是 1 到 {SHOW_EPISODES_MAX} 的整数")
        elif not _int_in(show.get("minutes_per_episode"), 1, SHOW_MINUTES_MAX):
            errors.append(f"《{name}》：每集分钟数必须是 1 到 {SHOW_MINUTES_MAX} 的整数")
        else:
            result.append({"title": title, "episodes": show["episodes"], "minutes_per_episode": show["minutes_per_episode"]})
    return result, errors
