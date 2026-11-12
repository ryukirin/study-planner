# 计划文件格式

计划文件是 Markdown。正文写给人看，机器读取的部分放在唯一一个 ```` ```study-plan ```` 代码块里（代码块名称固定，长期和短期计划都用它），内容是 JSON。示例在 study-planner 仓库的 `examples/`（https://github.com/ryukirin/study-planner/tree/main/examples）：

- `toeic-700-sample.md`、`java-basics-sample.md`：长期计划
- `weekend-shopping-sample.md`：只有定时安排的短期计划

## 顶层字段

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `schema` | 是 | 固定为 `1` |
| `id` | 是 | 字母、数字、`-`、`_`、`.`，例如 `toeic-700-2026`。文件名用 `<id>.md`。重排时保持不变。`_tasks` 为临时任务保留 |
| `name` | 是 | 界面上显示的短名称，例如 `TOEIC 700` |
| `goal` | 否 | 一句话目标 |
| `category` | 否 | 类别，例如 `学习`、`转职`、`生活`，界面显示为标签 |
| `color` | 否 | `#RRGGBB`，不写时自动分配 |
| `priority` | 否 | ≥ 1 的整数，默认 1。数字越小越优先，空闲时间不够时先排优先的计划 |
| `start_date` | 是 | `YYYY-MM-DD` |
| `deadline` | 否 | `YYYY-MM-DD`。写了 deadline 时，计划到 deadline 结束 |
| `resources` | 否 | `[{"kind": "教材", "item": "书名"}]` |
| `sequences` | 否 | 有顺序的内容，见下文 |
| `phases` | 见说明 | 阶段数组，长期计划用 |
| `events` | 见说明 | 某一天的单次任务（模考、面试、逛街的每一站） |
| `milestones` | 否 | 里程碑 |

`phases` 和 `events` 至少写一个。只有 `events` 的计划（短期计划）在 `deadline` 结束，没写 `deadline` 时在最后一个 event 的日期结束。

未知字段会报错，拼错字段名时 `check` 会指出。

## sequences

每次展开带 `uses` 的任务时，从对应序列按顺序取下一项。

```json
"sequences": {
  "ch": {"title": "教程章节", "items": ["环境搭建", "变量与类型", "条件与循环"]},
  "vocab": {"title": "金フレ词块", "range": {"from": 1, "to": 400, "step": 20}, "label": "金フレ {from:03d}-{to:03d}", "on_exhausted": "repeat"}
}
```

- 序列名：字母、数字、下划线，不能以数字开头，不能叫 `phase`、`week`、`n`。
- `title`：界面上显示的名称，必写。
- `items`：字符串数组。
- `range` + `label`：按 `from`、`to`、`step` 生成编号区间。`label` 里可用 `{from}`、`{to}`、`{i}`（第几项），`{from:03d}` 表示补零到 3 位。上例生成 `金フレ 001-020`、`金フレ 021-040`……
- `on_exhausted`：序列用完后的处理，`skip`（默认，不再生成该任务）或 `repeat`（从头循环）。

## phases

```json
{"name": "基础期", "weeks": 3, "goal": "阶段目标", "focus": "阶段重点", "week": { ... }}
```

- 阶段按顺序首尾相接，从 `start_date` 开始。
- 除最后一个阶段外都必须写 `weeks`。最后一个阶段不写 `weeks` 时自动延伸到 `deadline`。没有 `deadline` 时最后一个阶段也必须写 `weeks`。
- 各阶段总长超过 `deadline`，或最后一个阶段写了 `weeks` 却早于 `deadline` 结束，都会报错。

`week` 是每周模板，键可以是：

| 键 | 适用日期 |
| --- | --- |
| `daily` | 每天 |
| `weekdays` | 周一到周五 |
| `weekend` | 周六、周日 |
| `mon` … `sun` | 指定星期 |

同一天会依次合并 `daily`、`weekdays`/`weekend`、具体星期的任务。没写到的日子当天没有任务。

各星期的空闲时长不同时，不用 `weekdays`，按星期分开写，让每天的任务总长加上任务间隔放得进当天的空闲时间。例如周二、周四晚上只有 100 分钟：

```json
"mon": [{"title": "...", "minutes": 55, "slot": "focus"}, {"title": "...", "minutes": 75, "slot": "focus"}],
"tue": [{"title": "...", "minutes": 40, "slot": "focus"}, {"title": "...", "minutes": 55, "slot": "focus"}]
```

## 按日期调整

阶段从 `start_date` 起按整周排，周模板按星期生效，没有“跳过某一天”的写法。只影响某一周的调整（休馆日、考试日、自己放假、长假）这样写：

- 把那一周单独写成 `"weeks": 1` 的阶段，前后阶段的 `weeks` 相应减少，阶段的 `week` 换成调整后的星期。
- 不排任务的一周写 `"week": {}`。
- 调整后重新核对序列的使用次数和项数。

例：`start_date` 为周一，第 8 周（12/28–1/3）健身房休业，第 10 周的周六（1/16）休馆，改到周日：

```json
"phases": [
  {"name": "进阶", "weeks": 7, "week": {"tue": [...], "thu": [...], "sat": [...]}},
  {"name": "冬季休业", "weeks": 1, "goal": "健身房休业，不安排", "week": {}},
  {"name": "保持 1", "weeks": 1, "week": {"tue": [...], "thu": [...], "sat": [...]}},
  {"name": "保持（1/16 休馆）", "weeks": 1, "week": {"tue": [...], "thu": [...], "sun": [...]}},
  {"name": "保持 2", "week": {"tue": [...], "thu": [...], "sat": [...]}}
]
```

用户某天想全天休息时，在 `profile.json` 的 `exceptions` 里把那天写成 `"windows": []`，再按上面的方法把各计划那天的任务挪到同一周的其他日子。定时任务（写了 `time` 的）不受空闲时间影响，照常出现。

## 任务

星期模板里的任务和 events 共用下面的字段：

```json
{"title": "Java：{ch}", "uses": "ch", "minutes": 60, "slot": "focus", "detail": "读一章并把例子敲一遍"}
{"title": "健身房", "minutes": 60, "time": "07:00", "location": "公司附近健身房", "remind": 15}
```

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `title` | 是 | 任务标题，可用占位符 |
| `minutes` | 是 | 1 到 600 的整数 |
| `slot` | 建议 | 对应 profile 时间段的 `tag`，App 把任务放进这类时间段。不写 `slot` 也不写 `time` 时，可以放进任意时间段 |
| `time` | 否 | `HH:MM`，固定开始时间。写了 `time` 的是定时任务，不受空闲时间段限制，其他任务会避开它 |
| `location` | 否 | 地点，App 里点击可以打开地图搜索 |
| `links` | 否 | `[{"title": "官网", "url": "https://..."}]`，只允许 http 和 https |
| `remind` | 否 | 定时任务提前提醒的分钟数（0 到 1440），覆盖 App 的默认值。`false` 表示这个任务不提醒 |
| `detail` | 否 | 补充说明，可用占位符 |
| `uses` | 否 | 序列名，只能用在星期模板里。写了才能在文案里用 `{序列名}` |

占位符：

- `{序列名}`：本次取到的序列项，需要同时写 `uses`
- `{phase}`：阶段名
- `{week}`：计划的第几周
- `{n}`：这个任务模板在本阶段第几次出现
- 字面花括号写 `{{` 和 `}}`

## events 和 milestones

```json
"events": [{"offset_days": 26, "time": "09:00", "title": "全真模考 Test 1", "minutes": 120, "detail": "连续做完"}],
"milestones": [{"date": "2026-12-26", "text": "第二次模考 700 分以上", "note": "可选备注", "tasks": ["模考"]}]
```

- `date` 和 `offset_days`（相对 `start_date` 的天数）二选一，日期必须在计划范围内。
- `tasks` 可选，列出里程碑跟随的任务：任务模板标题里的词或序列名。用户在 App 里改期或提前完成任务后，里程碑的日期按这些任务的进度推算。不写时 App 用任务模板标题的开头（第一个花括号或冒号之前）和序列标题去匹配 `text`。`text` 里不含对应任务的名称时写上 `tasks`。
- events 不能使用序列。

## 校验

写完草稿运行：

```
planner_cli check <草稿1> [<草稿2> ...]
```

可以一次传多份草稿，按全部加入后的状态一起检查。草稿和已有计划 id 相同时按替换处理，两份草稿 id 相同会报错。`--from YYYY-MM-DD --days N` 可以预览任意日期，用来抽查休馆日、考试日、祝日的安排。

输出包括错误（带字段路径，例如 `phases[1].week.thu[0].minutes`）、警告（序列用不完或不够用、slot 在空闲时间里不存在、正文阶段表和阶段数据对不上）、可行性（每周所需和可用分钟数、未排入的任务、定时任务重叠）、未来 14 天的时间表预览（定时任务带“（定时）”标记）。返回码 0 表示没有错误。
