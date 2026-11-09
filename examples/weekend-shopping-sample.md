# 周末逛街示例计划

示例文件，用于演示短期计划的格式。店名和链接是虚构的，实际计划由 plan-builder skill 根据地区、预算和偏好搜索后生成，并在“推荐理由”中写明信息的查询日期。

## 安排

| 时间 | 内容 | 地点 |
| --- | --- | --- |
| 13:00-14:30 | 逛服装店 A | 表参道 |
| 14:40-16:00 | 逛服装店 B | 原宿 |
| 16:10-16:50 | 咖啡休息 | 原宿 |
| 18:00-19:30 | 晚饭 | 涩谷 |

## 推荐理由

- 服装店 A：示例。
- 晚饭：示例。

```study-plan
{
  "schema": 1,
  "id": "weekend-shopping-sample",
  "name": "周末逛街",
  "category": "生活",
  "goal": "买两件冬季外套，顺路吃晚饭",
  "color": "#2f8f5b",
  "priority": 1,
  "start_date": "2026-11-14",
  "events": [
    {"date": "2026-11-14", "time": "13:00", "title": "逛服装店 A（示例）", "minutes": 90, "location": "表参道",
     "detail": "看外套，预算 2 万日元以内", "links": [{"title": "店铺页面", "url": "https://example.com/shop-a"}]},
    {"date": "2026-11-14", "time": "14:40", "title": "逛服装店 B（示例）", "minutes": 80, "location": "原宿"},
    {"date": "2026-11-14", "time": "16:10", "title": "咖啡休息", "minutes": 40, "location": "原宿", "remind": false},
    {"date": "2026-11-14", "time": "18:00", "title": "晚饭（示例）", "minutes": 90, "location": "涩谷", "remind": 30,
     "detail": "18:00 预约", "links": [{"title": "预约页面", "url": "https://example.com/dinner"}]}
  ]
}
```
