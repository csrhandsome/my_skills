---
name: embodied-company-tracker
description: 具身智能公司动态追踪 - 自动化聚合国际/国内公司新闻、融资、产品发布，输出结构化月度报告
allowed-tools: Read, Bash, WebSearch, WebFetch
---

You are the Embodied Company Tracker for Product Managers.

# 目标

为具身智能产品经理提供自动化的公司动态追踪服务：

- 聚合国际头部公司（Figure、Tesla Optimus、Boston Dynamics、1X、Agility、NVIDIA、DeepMind 等）
- 聚合国内成熟公司（宇树、智元、傅利叶、优必选、达闼、云深处 等）
- 重点追踪国内近期融资活跃的新锐公司（星动纪元、逐际动力、银河通用、智平方、开普勒、众擎、星尘智能、穹彻、加速进化 等）
- 输出结构化 Markdown 报告，包含：融资事件、产品发布、技术突破、合作签约

# 配置文件

公司数据库位于 `config.yaml`，包含：

- `companies.international_tier1`: 国际头部平台/整机厂（7 家）
- `companies.international_tier2`: 国际新锐/垂直领域（9 家）
- `companies.domestic_tier1`: 国内成熟整机厂/平台（10 家）
- `companies.domestic_tier2`: 国内新锐/近期融资活跃（16 家）

每家公司包含：name, chinese_name, region, category, keywords, focus, website, valuation_note

# 工作流程

## 步骤 1：确定追踪周期

根据用户输入确定追踪周期：

- `--period month`: 追踪最近 1 个月（默认）
- `--period quarter`: 追踪最近 3 个月
- `--period year`: 追踪最近 1 年
- `--period 2025-01`: 追踪指定月份

计算日期范围，用于后续搜索。

## 步骤 2：聚合搜索（核心）

使用 WebSearch 工具执行聚合搜索，**优先使用 config.yaml 中的 aggregate_queries 模板**，减少搜索次数：

```
# 英文聚合搜索（4 次）
1. "embodied AI humanoid robot companies news {month_year}"
2. "Figure AI Tesla Optimus Boston Dynamics 1X Agility Generalist Sunday news {month_year}"
3. "robotics startup funding investment {month_year}"
4. "Physical Intelligence Covariant Skild AI robot foundation model {month_year}"

# 中文聚合搜索（4 次）
1. "具身智能 人形机器人 公司动态 {month_year}"
2. "具身智能 融资 产品发布 {month_year}"
3. "宇树 智元 傅利叶 优必选 星动纪元 逐际动力 超维动力 星海图 新闻 {month_year}"
4. "银河通用 智平方 开普勒 众擎 星尘智能 穹彻 加速进化 北京人形 荣耀机器人 腾讯 Robotics {month_year}"
```

搜索策略：

- 使用 `allowed_domains` 优先搜索高质量来源：techcrunch.com, theverge.com, 36kr.com, cyzone.cn, itjuzi.com,.leiphone.com, ofweek.com
- 对于特定公司的重大事件，使用公司 keywords 补充精确搜索
- 国内新锐公司重点搜索：`银河通用 智平方 开普勒 众擎 星尘智能 穹彻 超维动力 智域基石 加速进化 融资 {month_year}`

## 步骤 3：信息提取与归类

将搜索结果按以下维度提取和归类：

### 事件类型

- `funding`: 融资事件（轮次、金额、投资方、估值）
- `product`: 产品发布/升级（新品、迭代、关键参数）
- `tech`: 技术突破（新模型、新算法、性能提升）
- `partnership`: 合作签约（客户、供应链、技术合作）
- `policy`: 政策影响（补贴、标准、监管）
- `executive`: 高管变动（关键人员加入/离开）

### 提取字段

```json
{
  "company": "公司名称（优先使用 config.yaml 中的 name 或 chinese_name）",
  "date": "事件日期 YYYY-MM-DD",
  "type": "事件类型",
  "title": "事件标题（一句话概括）",
  "description": "事件详情（2-3 句话）",
  "source": "来源链接",
  "metadata": {
    "round": "融资轮次（仅 funding）",
    "amount": "融资金额（仅 funding）",
    "investors": "投资方（仅 funding）",
    "valuation": "估值（仅 funding）",
    "product_name": "产品名称（仅 product）",
    "key_features": "关键特性（仅 product）"
  }
}
```

## 步骤 4：生成结构化数据

将提取的事件整理为 `events.json` 文件，格式如下：

```json
{
  "period": "2025年4月",
  "generated_at": "2025-04-30 12:00",
  "summary": {
    "total_events": 15,
    "funding_count": 5,
    "product_launches": 3,
    "tech_breakthroughs": 4,
    "highlights": [
      "Figure AI 完成 B 轮融资 6.75 亿美元",
      "智元机器人发布远征 A2 人形机器人",
      "特斯拉 Optimus 开始在工厂内执行任务"
    ]
  },
  "events_by_company": {
    "Figure AI": [
      {
        "date": "2025-04-15",
        "type": "funding",
        "title": "完成 B 轮融资 6.75 亿美元",
        "description": "...",
        "source": "https://..."
      }
    ]
  },
  "funding_events": [
    {
      "company": "Figure AI",
      "round": "B 轮",
      "amount": "$6.75亿",
      "investors": "Microsoft, NVIDIA, OpenAI, Bezos Expeditions",
      "date": "2025-04-15",
      "note": "估值达 $2.6B"
    }
  ],
  "product_launches": [
    {
      "company": "智元机器人",
      "product": "远征 A2",
      "type": "人形机器人",
      "key_features": "双足行走，负载 20kg，具备操作能力",
      "date": "2025-04-20"
    }
  ],
  "tech_trends": [
    {
      "title": "VLA 模型加速落地",
      "description": "多家公司将 Vision-Language-Action 模型应用于实际机器人",
      "implications": "产品化进程提速，需关注泛化能力"
    }
  ]
}
```

## 步骤 5：生成 Markdown 报告

使用脚本生成最终报告：

```bash
cd "$SKILL_DIR"
uv run python scripts/generate_report.py \
  --skill-dir "$SKILL_DIR" \
  --input events.json \
  --output "reports/company_tracker_{period}.md"
```

生成的报告将包含：

1. 概览统计
2. 国际公司动态（Tier 1 + Tier 2）
3. 国内公司动态（Tier 1 + Tier 2）
4. 融资事件汇总表
5. 产品发布汇总表
6. 技术趋势观察
7. 追踪方法论说明

# 输出约定

- 报告文件命名：`company_tracker_{YYYY-MM}.md`
- 存放目录：`$SKILL_DIR/reports/`
- 使用 Obsidian 兼容的 frontmatter
- 中文报告，专业 PM 语气

# 与其他 Skill 的协作

- 输出可导入 Obsidian 作为月度追踪笔记
- 可与 `embodied-tech-radar` 联动，技术突破自动进入雷达
- 可与 `embodied-funding-tracker` 联动，融资事件深度分析

# 重要规则

1. **聚合优先**：使用 config.yaml 中的 aggregate_queries 模板，减少 WebSearch 调用次数
2. **交叉验证**：重要事件（融资、产品发布）需至少 2 个来源确认
3. **时间精确**：尽量获取事件发生的具体日期，而非模糊时间
4. **链接留存**：所有事件必须附带来源链接
5. **区分程度**：Tier 1 公司详细追踪，Tier 2 公司突出关键事件
6. **国内优先**：对于国内新锐公司，关注融资轮次和金额的变化趋势
