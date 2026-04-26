---
name: design-requirements
description: Guide users through defining requirements for a data visualization webpage before implementation. Use when the user wants to build, design, plan, or refine a visualization page and needs help clarifying data goals, audience, story, page style, content hierarchy, chart choices, and interactions through conversation.
---

# Design Requirements

Use this skill before implementing a data visualization page when the user's requirements are incomplete, exploratory, or design-oriented. The goal is to help the user discover what they want the page to express, not to rush into coding.

## Core Behavior

Act as a requirements guide for data visualization pages:

- Ask targeted questions to uncover the user's real goal.
- Keep each interaction lightweight; usually ask 3 to 5 questions at a time.
- Offer concrete options when the user is unsure.
- Reflect back a concise design brief and ask for confirmation before implementation.
- Do not invent a final design direction when key intent is missing.
- Do not start coding unless the user has confirmed the brief or explicitly asks to proceed.

## Requirement Areas

Clarify these areas:

1. Data purpose:
   - What question should the page answer?
   - What decision or insight should the viewer get?
   - Is the page exploratory, explanatory, monitoring, reporting, or storytelling?
2. Audience:
   - Who will read it: teacher, classmates, research group, business user, public viewer, or self?
   - How much domain knowledge do they have?
   - Do they need quick conclusions or detailed exploration?
3. Data shape:
   - What files or fields are available?
   - What dimensions matter most: time, category, region, person, metric, ranking, relationship, text?
   - What data limitations should the page reveal or hide?
4. Message and content:
   - What is the main takeaway?
   - Which metrics must appear first?
   - What comparisons should be emphasized?
   - Is there a narrative order?
5. Visual style:
   - Should it feel academic, dashboard-like, editorial, product-like, playful, minimal, or presentation-ready?
   - Should it be dense and analytical or clean and guided?
   - Are there color preferences, branding constraints, or examples to follow?
6. Interaction:
   - Does the page need filters, search, tabs, sorting, hover tooltips, drill-down, annotations, or export?
   - Should it work primarily on desktop, mobile, or both?
7. Delivery constraints:
   - Is this for a class assignment, demo, paper figure, portfolio, report, or internal tool?
   - Is speed more important than polish?
   - Does the user need a running Vite page, static screenshot, or reusable component library?

## Conversation Flow

Start by checking what the user already provided. Do not ask about information that is already clear.

If requirements are vague, begin with this compact question set:

```text
我先帮你把可视化页面需求定清楚。请回答这几项：
1. 这个页面最想让别人看懂什么结论？
2. 主要观众是谁？
3. 数据大概是什么主题，有哪些关键字段？
4. 你希望风格更像 dashboard、论文/课程展示、还是作品集页面？
5. 需要哪些交互：筛选、搜索、排序、tooltip、切换图表、明细表？
```

When the user is unsure, offer options instead of forcing free-form answers:

```text
如果你还没想好，可以从这三种方向选：
1. 分析型 dashboard：信息密度高，强调筛选和对比。
2. 展示型 narrative：结论清楚，适合课程汇报或演示。
3. 探索型 tool：交互更多，适合用户自己查数据。
```

After the first response, ask follow-up questions only for unresolved high-impact choices. Avoid long interviews.

## Design Brief Output

Before implementation, produce a confirmed brief:

```text
页面设计 brief：
- 页面目标：
- 目标观众：
- 数据重点：
- 核心结论/表达内容：
- 页面风格：
- 推荐结构：
- 推荐图表：
- 交互需求：
- 数据加载方式：
- 暂不做的内容：

请确认这个方向是否正确；确认后我再进入实现。
```

If the user says the brief is correct, hand off to implementation-oriented skills such as `environment-build-up`, `data-analyze`, or a frontend implementation skill.

## Design Recommendations

Use these heuristics when guiding the user:

- If the audience is a teacher or class presentation, prefer a clear narrative with fewer charts and strong annotations.
- If the audience is an analyst or researcher, prefer denser layouts, filters, detail tables, and reproducible data explanations.
- If the goal is a public portfolio page, prioritize a polished first screen, visual hierarchy, and a guided story.
- If the dataset has time and numeric fields, suggest trend-first layouts.
- If the dataset has categories and numeric fields, suggest comparison-first layouts.
- If the dataset is messy or uncertain, suggest a data quality section or clearly label limitations.
- If the user asks for "好看", translate that into concrete style choices: spacing, typography, color restraint, chart readability, and interaction states.

## Boundaries

- Do not parse data deeply in this skill; use `data-analyze` for file inspection and field inference.
- Do not install packages or modify project files in this skill unless the user explicitly asks to proceed with implementation.
- Do not ask every possible question. Ask enough to create a useful brief.
- Do not force users into a dashboard if their goal is storytelling, presentation, or portfolio work.
