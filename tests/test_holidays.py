import contextlib
import copy
import io
import json
import os
import unittest
from datetime import date

import planner_cli
from planner_core import jp_holidays
from planner_core.availability import ProfileError, parse_profile
from planner_ui import PlannerApi
from tests.helpers import BASE_PROFILE, TempHome, config

# 内阁府「国民の祝日」CSV（https://www8.cao.go.jp/chosei/shukujitsu/syukujitsu.csv）中 2026、2027 年的行。
# CSV 把振替休日和国民の休日都记作“休日”。
CABINET_OFFICE = {
    2026: """
2026/1/1,元日
2026/1/12,成人の日
2026/2/11,建国記念の日
2026/2/23,天皇誕生日
2026/3/20,春分の日
2026/4/29,昭和の日
2026/5/3,憲法記念日
2026/5/4,みどりの日
2026/5/5,こどもの日
2026/5/6,休日
2026/7/20,海の日
2026/8/11,山の日
2026/9/21,敬老の日
2026/9/22,休日
2026/9/23,秋分の日
2026/10/12,スポーツの日
2026/11/3,文化の日
2026/11/23,勤労感謝の日
""",
    2027: """
2027/1/1,元日
2027/1/11,成人の日
2027/2/11,建国記念の日
2027/2/23,天皇誕生日
2027/3/21,春分の日
2027/3/22,休日
2027/4/29,昭和の日
2027/5/3,憲法記念日
2027/5/4,みどりの日
2027/5/5,こどもの日
2027/7/19,海の日
2027/8/11,山の日
2027/9/20,敬老の日
2027/9/23,秋分の日
2027/10/11,スポーツの日
2027/11/3,文化の日
2027/11/23,勤労感謝の日
""",
}

# 2028–2030 年尚未由内阁府公布。按现行祝日法推算，春分、秋分取国立天文台的推算值，写法同 CSV。
PROJECTED = {
    2028: """
2028/1/1,元日
2028/1/10,成人の日
2028/2/11,建国記念の日
2028/2/23,天皇誕生日
2028/3/20,春分の日
2028/4/29,昭和の日
2028/5/3,憲法記念日
2028/5/4,みどりの日
2028/5/5,こどもの日
2028/7/17,海の日
2028/8/11,山の日
2028/9/18,敬老の日
2028/9/22,秋分の日
2028/10/9,スポーツの日
2028/11/3,文化の日
2028/11/23,勤労感謝の日
""",
    2029: """
2029/1/1,元日
2029/1/8,成人の日
2029/2/11,建国記念の日
2029/2/12,休日
2029/2/23,天皇誕生日
2029/3/20,春分の日
2029/4/29,昭和の日
2029/4/30,休日
2029/5/3,憲法記念日
2029/5/4,みどりの日
2029/5/5,こどもの日
2029/7/16,海の日
2029/8/11,山の日
2029/9/17,敬老の日
2029/9/23,秋分の日
2029/9/24,休日
2029/10/8,スポーツの日
2029/11/3,文化の日
2029/11/23,勤労感謝の日
""",
    2030: """
2030/1/1,元日
2030/1/14,成人の日
2030/2/11,建国記念の日
2030/2/23,天皇誕生日
2030/3/20,春分の日
2030/4/29,昭和の日
2030/5/3,憲法記念日
2030/5/4,みどりの日
2030/5/5,こどもの日
2030/5/6,休日
2030/7/15,海の日
2030/8/11,山の日
2030/8/12,休日
2030/9/16,敬老の日
2030/9/23,秋分の日
2030/10/14,スポーツの日
2030/11/3,文化の日
2030/11/4,休日
2030/11/23,勤労感謝の日
""",
}


def parse_rows(text: str) -> list[tuple[date, str]]:
    rows = []
    for line in text.strip().splitlines():
        raw_date, name = line.split(",")
        year, month, day = map(int, raw_date.split("/"))
        rows.append((date(year, month, day), name))
    return rows


def as_csv_names(year: int) -> list[tuple[date, str]]:
    rest_days = (jp_holidays.SUBSTITUTE, jp_holidays.CITIZENS)
    return [(day, "休日" if name in rest_days else name) for day, name in jp_holidays.holidays_in_year(year).items()]


def run_cli(*argv: str) -> tuple[int, str]:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = planner_cli.main(list(argv))
    return code, buffer.getvalue()


def holiday_profile(**overrides) -> dict:
    data = copy.deepcopy(BASE_PROFILE)
    data["holidays"] = "jp"
    data.update(overrides)
    return data


class HolidayCalendarTest(unittest.TestCase):
    def test_matches_cabinet_office_csv(self):
        for year, text in CABINET_OFFICE.items():
            with self.subTest(year=year):
                self.assertEqual(as_csv_names(year), parse_rows(text))

    def test_projected_years(self):
        for year, text in PROJECTED.items():
            with self.subTest(year=year):
                self.assertEqual(as_csv_names(year), parse_rows(text))

    def test_rest_day_kinds(self):
        self.assertEqual(jp_holidays.holiday_name(date(2026, 5, 6)), "振替休日")
        self.assertEqual(jp_holidays.holiday_name(date(2026, 9, 22)), "国民の休日")
        self.assertEqual(jp_holidays.holiday_name(date(2027, 3, 22)), "振替休日")
        self.assertIsNone(jp_holidays.holiday_name(date(2027, 1, 12)))

    def test_equinoxes(self):
        expected = {2026: (20, 23), 2027: (21, 23), 2028: (20, 22), 2029: (20, 23), 2030: (20, 23)}
        for year, (spring, autumn) in expected.items():
            self.assertEqual(jp_holidays.vernal_equinox(year), date(year, 3, spring))
            self.assertEqual(jp_holidays.autumnal_equinox(year), date(year, 9, autumn))

    def test_olympic_years(self):
        names_2020 = jp_holidays.holidays_in_year(2020)
        self.assertEqual(names_2020[date(2020, 7, 24)], "スポーツの日")
        self.assertEqual(names_2020[date(2020, 8, 10)], "山の日")
        self.assertNotIn(date(2020, 10, 12), names_2020)
        self.assertEqual(jp_holidays.holiday_name(date(2021, 8, 9)), "振替休日")

    def test_out_of_range_years(self):
        self.assertEqual(jp_holidays.holidays_in_year(2019), {})
        self.assertEqual(jp_holidays.holidays_in_year(2100), {})

    def test_between_crosses_years(self):
        days = jp_holidays.holidays_between(date(2026, 11, 23), date(2027, 1, 11))
        self.assertEqual(days, [(date(2026, 11, 23), "勤労感謝の日"), (date(2027, 1, 1), "元日"), (date(2027, 1, 11), "成人の日")])


class HolidayProfileTest(unittest.TestCase):
    def test_off_by_default(self):
        profile = parse_profile(BASE_PROFILE)
        self.assertEqual(profile.holidays, "none")
        self.assertIsNone(profile.holiday_name(date(2027, 1, 11)))
        self.assertEqual(profile.windows_for(date(2027, 1, 11))[1].start, 20 * 60)

    def test_weekday_holiday_uses_saturday_windows(self):
        profile = parse_profile(holiday_profile())
        windows = profile.windows_for(date(2027, 1, 11))
        self.assertEqual([(w.start, w.end, w.tag) for w in windows], [(14 * 60, 17 * 60, "focus")])
        self.assertEqual(profile.holiday_name(date(2027, 1, 11)), "成人の日")
        self.assertTrue(profile.uses_holiday_windows(date(2027, 1, 11)))

    def test_custom_holiday_windows(self):
        profile = parse_profile(holiday_profile(holiday=[{"start": "10:00", "end": "12:00", "tag": "focus", "label": "上午"}]))
        self.assertEqual(profile.windows_for(date(2026, 11, 23))[0].label, "上午")
        self.assertEqual(parse_profile(holiday_profile(holiday=[])).windows_for(date(2026, 11, 23)), [])

    def test_exception_wins_over_holiday(self):
        data = holiday_profile(exceptions=[{"date": "2027-01-11", "windows": [], "note": "出差"}])
        profile = parse_profile(data)
        self.assertEqual(profile.windows_for(date(2027, 1, 11)), [])
        self.assertFalse(profile.uses_holiday_windows(date(2027, 1, 11)))
        self.assertEqual(profile.holiday_name(date(2027, 1, 11)), "成人の日")

    def test_weekend_holiday_keeps_weekday_template(self):
        data = holiday_profile(holiday=[{"start": "10:00", "end": "12:00", "tag": "focus"}])
        profile = parse_profile(data)
        sunday = date(2027, 3, 21)  # 春分の日，周日
        self.assertEqual(profile.holiday_name(sunday), "春分の日")
        self.assertEqual(profile.windows_for(sunday), [])
        self.assertFalse(profile.uses_holiday_windows(sunday))

    def test_validation(self):
        with self.assertRaises(ProfileError) as ctx:
            parse_profile(holiday_profile(holidays="cn"))
        self.assertTrue(any(error.startswith("holidays：") for error in ctx.exception.errors))
        with self.assertRaises(ProfileError) as ctx:
            parse_profile(holiday_profile(holiday=[{"start": "12:00", "end": "11:00", "tag": "focus"}]))
        self.assertTrue(any(error.startswith("holiday：") for error in ctx.exception.errors))

    def test_round_trip(self):
        custom = [{"start": "10:00", "end": "12:00", "tag": "focus", "label": "上午"}]
        data = parse_profile(holiday_profile(holiday=custom)).to_dict()
        self.assertEqual(data["holidays"], "jp")
        self.assertEqual(data["holiday"], custom)
        self.assertNotIn("holiday", parse_profile(holiday_profile()).to_dict())
        self.assertIsNone(parse_profile(holiday_profile(holiday=None)).holiday)


def monday_plan() -> dict:
    return config(start_date="2027-01-04", deadline="2027-01-17", sequences={},
                  phases=[{"name": "A", "week": {"mon": [{"title": "周一学习", "minutes": 60, "slot": "focus"}]}}])


class HolidayCliTest(unittest.TestCase):
    def setUp(self):
        self.home = TempHome()
        self.home.write_plan("demo.md", monday_plan())

    def tearDown(self):
        self.home.cleanup()

    def test_check_with_holidays(self):
        self.home.write_profile(holiday_profile())
        code, out = run_cli("--home", self.home.path, "--today", "2027-01-04", "check", "--from", "2027-01-11", "--days", "1")
        self.assertEqual(code, 0, out)
        self.assertIn("  祝日  日本祝日（开启）  14:00-17:00 整块学习[focus]（同周六，用于周一至周五的祝日）", out)
        self.assertIn("  近期祝日  2027-01-11 周一 成人の日  2027-02-11 周四 建国記念の日  2027-02-23 周二 天皇誕生日", out)
        self.assertIn("2027-01-11 周一  祝日 成人の日\n  按祝日时间段  14:00-17:00 整块学习[focus]\n", out)
        self.assertIn("14:00-15:00  [演示计划] 周一学习", out)

    def test_check_without_holidays(self):
        self.home.write_profile()
        code, out = run_cli("--home", self.home.path, "--today", "2027-01-04", "check", "--from", "2027-01-11", "--days", "1")
        self.assertEqual(code, 0, out)
        self.assertIn('  祝日  未开启（profile.json 写 "holidays": "jp" 后按日本祝日排程）', out)
        self.assertIn("2027-01-11 周一\n", out)
        self.assertIn("20:00-21:00  [演示计划] 周一学习", out)


class HolidayApiTest(unittest.TestCase):
    def setUp(self):
        self.home = TempHome()
        self.home.write_profile(holiday_profile())
        self.home.write_plan("demo.md", monday_plan())
        self.api = PlannerApi(self.home.path, today=date(2027, 1, 4))

    def tearDown(self):
        self.home.cleanup()

    def test_day_payload(self):
        day = self.api.state("2027-01-11")["day"]
        self.assertEqual(day["holiday"], "成人の日")
        self.assertTrue(day["holiday_windows"])
        self.assertEqual(day["groups"][0]["tasks"][0]["start"], "14:00")
        plain = self.api.state("2027-01-12")["day"]
        self.assertIsNone(plain["holiday"])
        self.assertFalse(plain["holiday_windows"])

    def test_profile_payload_and_save(self):
        profile = self.api.state()["profile"]
        self.assertEqual(profile["holidays"], "jp")
        self.assertIsNone(profile["holiday"])
        self.assertEqual(profile["upcoming_holidays"][0], {"date": "2027-01-11", "weekday": "周一", "name": "成人の日"})
        profile["holiday"] = [{"start": "09:00", "end": "11:00", "tag": "focus", "label": "上午"}]
        self.assertEqual(self.api.save_profile(profile), {"ok": True})
        self.assertEqual(self.api.state("2027-01-11")["day"]["groups"][0]["tasks"][0]["start"], "09:00")
        profile["holidays"] = "none"
        self.assertEqual(self.api.save_profile(profile), {"ok": True})
        with open(os.path.join(self.home.path, "profile.json"), encoding="utf-8") as handle:
            saved = json.load(handle)
        self.assertEqual(saved["holidays"], "none")
        self.assertNotIn("upcoming_holidays", saved)
        self.assertIsNone(self.api.state("2027-01-11")["day"]["holiday"])
