# 11 月 Java 入门示例计划

示例文件，用于演示格式和测试。实际计划由 plan-builder skill 根据个人情况生成，并在“参考来源”中附上调研链接。

## 目标与现状

- 目标：11 月底前学完 Java 基础语法、面向对象和集合，能独立写一个命令行小程序。
- 现状：示例中假设有其他语言基础，没有系统学过 Java。

## 阶段安排

| 阶段 | 时间 | 重点 |
| --- | --- | --- |
| 语法基础 | 2 周 | 类型、流程控制、数组、方法、类与对象 |
| 面向对象与集合 | 8 天 | 继承、接口、异常、集合、IO，最后做一个小项目 |

## 参考来源

示例文件不附来源。

```study-plan
{
  "schema": 1,
  "id": "java-basics-sample",
  "name": "Java 入门",
  "goal": "11 月底前学完 Java 基础并完成一个命令行小程序",
  "color": "#3a7bd1",
  "priority": 1,
  "start_date": "2026-11-09",
  "deadline": "2026-11-30",
  "resources": [
    {"kind": "教程", "item": "任选一本 Java 入门教材或官方 Java Tutorials"},
    {"kind": "练习", "item": "在线判题网站的入门题"}
  ],
  "sequences": {
    "ch": {"title": "教程章节", "items": [
      "开发环境与第一个程序",
      "变量、基本类型与运算符",
      "条件与循环",
      "数组与字符串",
      "方法与参数传递",
      "类与对象",
      "封装、继承与多态",
      "抽象类与接口",
      "异常处理",
      "集合框架：List、Set、Map",
      "泛型与常用 API",
      "文件读写",
      "总复习：重写前面各章的练习"
    ]}
  },
  "phases": [
    {
      "name": "语法基础",
      "weeks": 2,
      "goal": "能写出带循环、数组和方法的小程序",
      "focus": "基础语法 / 类与对象",
      "week": {
        "mon": [{"title": "Java：{ch}", "uses": "ch", "minutes": 60, "slot": "focus", "detail": "读一章并把例子全部敲一遍"}],
        "tue": [{"title": "Java：{ch}", "uses": "ch", "minutes": 60, "slot": "focus", "detail": "读一章并把例子全部敲一遍"}],
        "wed": [{"title": "Java：{ch}", "uses": "ch", "minutes": 60, "slot": "focus", "detail": "读一章并把例子全部敲一遍"}],
        "thu": [{"title": "Java：{ch}", "uses": "ch", "minutes": 60, "slot": "focus", "detail": "读一章并把例子全部敲一遍"}],
        "fri": [{"title": "本周代码练习", "minutes": 45, "slot": "focus", "detail": "不看答案重写本周的例子"}],
        "sat": [{"title": "入门算法题 3 道", "minutes": 90, "slot": "focus"}]
      }
    },
    {
      "name": "面向对象与集合",
      "goal": "理解继承和接口，会用常用集合",
      "focus": "面向对象 / 集合 / 小项目",
      "week": {
        "mon": [{"title": "Java：{ch}", "uses": "ch", "minutes": 60, "slot": "focus"}],
        "tue": [{"title": "Java：{ch}", "uses": "ch", "minutes": 60, "slot": "focus"}],
        "wed": [{"title": "Java：{ch}", "uses": "ch", "minutes": 60, "slot": "focus"}],
        "thu": [{"title": "Java：{ch}", "uses": "ch", "minutes": 60, "slot": "focus"}],
        "fri": [{"title": "本周代码练习", "minutes": 45, "slot": "focus"}]
      }
    }
  ],
  "events": [
    {"date": "2026-11-28", "title": "综合小项目：命令行记账程序", "minutes": 150, "slot": "focus", "detail": "用到类、集合、异常和文件读写"}
  ],
  "milestones": [
    {"date": "2026-11-22", "text": "语法基础阶段结束"},
    {"date": "2026-11-30", "text": "学完全部章节"}
  ]
}
```
