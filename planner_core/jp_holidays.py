"""日本的国民の祝日和休日，按《国民の祝日に関する法律》现行规定计算，不依赖第三方包。

覆盖 2020 年到 2099 年。春分日和秋分日用国立天文台常用的近似公式推算（1980–2099 年适用），
正式日期以国立天文台每年 2 月公布的暦要項为准。振替休日和国民の休日在内阁府的 CSV 里都记作“休日”，
这里分别命名为“振替休日”和“国民の休日”。
"""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

FIRST_YEAR = 2020
LAST_YEAR = 2099

SUBSTITUTE = "振替休日"
CITIZENS = "国民の休日"

# 东京奥运会特别措施法调整过的祝日
_SPECIAL = {
    2020: {"海の日": date(2020, 7, 23), "スポーツの日": date(2020, 7, 24), "山の日": date(2020, 8, 10)},
    2021: {"海の日": date(2021, 7, 22), "スポーツの日": date(2021, 7, 23), "山の日": date(2021, 8, 8)},
}


def _nth_monday(year: int, month: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(7 - first.weekday()) % 7 + 7 * (n - 1))


def _equinox_day(year: int, base: float) -> int:
    offset = year - 1980
    return int(base + 0.242194 * offset - offset // 4)


def vernal_equinox(year: int) -> date:
    return date(year, 3, _equinox_day(year, 20.8431))


def autumnal_equinox(year: int) -> date:
    return date(year, 9, _equinox_day(year, 23.2488))


def _national_holidays(year: int) -> dict[date, str]:
    """法律第 2 条列出的“国民の祝日”，不含振替休日和国民の休日。"""
    special = _SPECIAL.get(year, {})
    days = {
        date(year, 1, 1): "元日",
        _nth_monday(year, 1, 2): "成人の日",
        date(year, 2, 11): "建国記念の日",
        date(year, 2, 23): "天皇誕生日",
        vernal_equinox(year): "春分の日",
        date(year, 4, 29): "昭和の日",
        date(year, 5, 3): "憲法記念日",
        date(year, 5, 4): "みどりの日",
        date(year, 5, 5): "こどもの日",
        special.get("海の日", _nth_monday(year, 7, 3)): "海の日",
        special.get("山の日", date(year, 8, 11)): "山の日",
        _nth_monday(year, 9, 3): "敬老の日",
        autumnal_equinox(year): "秋分の日",
        special.get("スポーツの日", _nth_monday(year, 10, 2)): "スポーツの日",
        date(year, 11, 3): "文化の日",
        date(year, 11, 23): "勤労感謝の日",
    }
    return days


@lru_cache(maxsize=None)
def _holidays_cached(year: int) -> tuple[tuple[date, str], ...]:
    if not FIRST_YEAR <= year <= LAST_YEAR:
        return ()
    national = _national_holidays(year)
    result = dict(national)
    # 第 3 条第 3 项：前一天和后一天都是国民の祝日的日子（本身不是祝日）
    for day in national:
        middle = day + timedelta(days=1)
        if middle not in national and middle + timedelta(days=1) in national:
            result[middle] = CITIZENS
    # 第 3 条第 2 项：祝日在周日时，之后最近的非祝日放假
    for day in sorted(national):
        if day.weekday() == 6:
            substitute = day + timedelta(days=1)
            while substitute in national:
                substitute += timedelta(days=1)
            result.setdefault(substitute, SUBSTITUTE)
    return tuple(sorted(result.items()))


def holidays_in_year(year: int) -> dict[date, str]:
    """某年的祝日和休日，按日期排序。超出 2020–2099 年时返回空字典。"""
    return dict(_holidays_cached(year))


def holiday_name(day: date) -> str | None:
    return holidays_in_year(day.year).get(day)


def holidays_between(start: date, end: date) -> list[tuple[date, str]]:
    """start 到 end（含两端）之间的祝日和休日。"""
    result = []
    for year in range(start.year, end.year + 1):
        result.extend((day, name) for day, name in _holidays_cached(year) if start <= day <= end)
    return result
