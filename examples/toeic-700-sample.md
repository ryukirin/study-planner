# TOEIC 700 示例计划

示例文件，用于演示格式和测试。实际计划由 plan-builder skill 根据个人情况生成，并在“参考来源”中附上调研链接。

## 目标与现状

- 目标：2026 年 12 月底前 TOEIC L&R 达到 700 分。
- 现状：示例中假设基础在 550 分左右，阅读时间不够，听力 Part 3/4 容易丢分。

## 阶段安排

| 阶段 | 时间 | 重点 |
| --- | --- | --- |
| 基础期 | 3 周 | 词汇第一轮，Part 5/6 语法题型，Part 3/4 精听 |
| 强化期 | 2 周 | 提高 Part 7 速度，第一次全真模考 |
| 冲刺期 | 2 周 | 错题回顾，第二次全真模考 |

## 参考来源

示例文件不附来源。

```study-plan
{
  "schema": 1,
  "id": "toeic-700-sample",
  "name": "TOEIC 700",
  "goal": "2026 年 12 月底前 TOEIC L&R 700 分",
  "color": "#d16a3a",
  "priority": 2,
  "start_date": "2026-11-09",
  "deadline": "2026-12-27",
  "resources": [
    {"kind": "词汇", "item": "金のフレーズ 増補改訂版"},
    {"kind": "真题", "item": "公式 TOEIC Listening & Reading 問題集"}
  ],
  "sequences": {
    "vocab": {"title": "金フレ词块", "range": {"from": 1, "to": 600, "step": 20}, "label": "金フレ {from:03d}-{to:03d}", "on_exhausted": "repeat"},
    "part5": {"title": "Part 5/6 练习", "range": {"from": 1, "to": 19}, "label": "Part 5/6 练习 第 {from} 回"},
    "listen": {"title": "Part 3/4 听力", "range": {"from": 1, "to": 14}, "label": "Part 3/4 第 {from} 组"}
  },
  "phases": [
    {
      "name": "基础期",
      "weeks": 3,
      "goal": "词汇过第一轮，熟悉 Part 5/6 常见题型",
      "focus": "金フレ / Part 5/6 / Part 3/4 精听",
      "week": {
        "weekdays": [
          {"title": "{vocab}", "uses": "vocab", "minutes": 30, "slot": "commute", "detail": "听音频跟读，标出不认识的词"},
          {"title": "回听前一天的听力材料", "minutes": 30, "slot": "commute"}
        ],
        "mon": [{"title": "{part5}", "uses": "part5", "minutes": 40, "slot": "focus", "detail": "限时完成，错题写下错因"}],
        "wed": [{"title": "{part5}", "uses": "part5", "minutes": 40, "slot": "focus", "detail": "限时完成，错题写下错因"}],
        "fri": [{"title": "{part5}", "uses": "part5", "minutes": 40, "slot": "focus", "detail": "限时完成，错题写下错因"}],
        "tue": [{"title": "{listen}", "uses": "listen", "minutes": 40, "slot": "focus", "detail": "精听一遍，跟读一遍"}],
        "thu": [{"title": "{listen}", "uses": "listen", "minutes": 40, "slot": "focus", "detail": "精听一遍，跟读一遍"}],
        "sat": [{"title": "Part 7 长文限时练习", "minutes": 90, "slot": "focus"}],
        "sun": [{"title": "本周错题回顾", "minutes": 30, "slot": "light"}]
      }
    },
    {
      "name": "强化期",
      "weeks": 2,
      "goal": "Part 7 在 55 分钟内做完",
      "focus": "Part 7 速度 / 全真模考",
      "week": {
        "weekdays": [
          {"title": "{vocab}", "uses": "vocab", "minutes": 30, "slot": "commute"},
          {"title": "回听前一天的听力材料", "minutes": 30, "slot": "commute"}
        ],
        "mon": [{"title": "{part5}", "uses": "part5", "minutes": 40, "slot": "focus"}],
        "wed": [{"title": "{part5}", "uses": "part5", "minutes": 40, "slot": "focus"}],
        "fri": [{"title": "{part5}", "uses": "part5", "minutes": 40, "slot": "focus"}],
        "tue": [{"title": "{listen}", "uses": "listen", "minutes": 40, "slot": "focus"}],
        "thu": [{"title": "{listen}", "uses": "listen", "minutes": 40, "slot": "focus"}],
        "sat": [{"title": "Part 7 长文限时练习", "minutes": 90, "slot": "focus"}],
        "sun": [{"title": "本周错题回顾", "minutes": 30, "slot": "light"}]
      }
    },
    {
      "name": "冲刺期",
      "goal": "稳定在 700 分以上",
      "focus": "错题回顾 / 第二次模考",
      "week": {
        "weekdays": [
          {"title": "{vocab}", "uses": "vocab", "minutes": 30, "slot": "commute"},
          {"title": "回听前一天的听力材料", "minutes": 30, "slot": "commute"}
        ],
        "mon": [{"title": "{part5}", "uses": "part5", "minutes": 40, "slot": "focus"}],
        "wed": [{"title": "{part5}", "uses": "part5", "minutes": 40, "slot": "focus"}],
        "tue": [{"title": "{listen}", "uses": "listen", "minutes": 40, "slot": "focus"}],
        "thu": [{"title": "{listen}", "uses": "listen", "minutes": 40, "slot": "focus"}],
        "fri": [{"title": "整理模考错题", "minutes": 40, "slot": "focus"}],
        "sat": [{"title": "Part 7 长文限时练习", "minutes": 90, "slot": "focus"}],
        "sun": [{"title": "本周错题回顾", "minutes": 30, "slot": "light"}]
      }
    }
  ],
  "events": [
    {"offset_days": 26, "title": "全真模考 Test 1", "minutes": 120, "slot": "focus", "detail": "连续 120 分钟做完，结束后统计各 Part 正确率"},
    {"offset_days": 47, "title": "全真模考 Test 2", "minutes": 120, "slot": "focus", "detail": "和 Test 1 的各 Part 正确率对比"}
  ],
  "milestones": [
    {"offset_days": 26, "text": "第一次模考，目标 620 分以上"},
    {"offset_days": 47, "text": "第二次模考，目标 700 分以上"}
  ]
}
```
