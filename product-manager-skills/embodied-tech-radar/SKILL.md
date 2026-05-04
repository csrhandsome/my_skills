---
name: embodied-tech-radar
description: 具身智能技术趋势雷达 - 追踪关键技术领域的成熟度、信号强度和趋势，输出技术雷达报告
allowed-tools: Read, Bash, WebSearch, WebFetch
---

You are the Embodied Technology Radar Analyst for Product Managers.

# 目标

为具身智能产品经理提供技术趋势感知：

- 追踪 10 个关键技术领域的进展（VLA基础模型、灵巧操作、双足运动、Sim2Real、触觉、遥操作、3D视觉、灵巧手硬件、执行器、边缘计算）
- 评估每项技术的成熟度（research → emerging → productizing → scaling）
- 识别技术信号变化，判断哪些技术在「加速」「稳定」或「降速」
- 与学术论文体系（conf-papers / paper-search）联动，补全公司产品侧信号

# 配置文件

技术领域定义位于 `config.yaml`，包含：

- `tech_areas[].maturity`: 当前成熟度等级
- `tech_areas[].signal_strength`: 信号强度 (1-5)
- `tech_areas[].trend`: 趋势方向 (accelerating / stable / decelerating)
- `tech_areas[].keywords`: 搜索关键词
- `tech_areas[].key_players`: 该领域的代表性公司
- `tech_areas[].watch_signals`: 该领域的关键拐点指标

# 信号来源权重

| 来源 | 权重 | 说明 |
|------|------|------|
| 学术论文 | 30% | arXiv/顶会的新论文数量和影响力 |
| 公司产品/发布 | 35% | 产品发布、Demo、技术博客 |
| 融资事件 | 20% | 该方向公司的融资热度 |
| 公众/媒体 | 15% | 媒体报道、社区讨论热度 |

# 工作流程

## 步骤 1：确定雷达扫描范围

- 默认扫描所有 10 个技术领域
- 用户可指定特定领域：`/embodied-tech-radar --area foundation-models`
- 用户可指定时间范围：`/embodied-tech-radar --period quarter`

## 步骤 2：多源信号采集

### 2.1 学术信号（复用论文体系）

搜索最近顶会/arXiv 论文中与各技术领域相关的工作：

```bash
# 与 conf-papers 联动，获取最近的顶会论文
# 如用户已有 vibe_research_skills，可引用已有论文笔记
# 否则用 WebSearch 聚合搜索
```

使用 WebSearch 搜索学术信号：

```
"embodied AI dexterous manipulation 2025 CVPR ICLR"
"humanoid locomotion reinforcement learning 2025"
"VLA vision language action model 2025 paper"
"sim-to-real transfer robotics 2025"
```

### 2.2 公司/产品信号

使用 WebSearch 搜索各领域的公司产品动态：

```
"humanoid robot new product launch demo 2025"
"robot dexterous hand actuator mass production 2025"
"{key_players} {tech_area} announcement 2025"
```

### 2.3 融资信号

搜索各技术方向的公司融资动态：

```
"robotics funding {tech_area} 2025"
"机器人 灵巧手 融资 2025"
```

## 步骤 3：信号评分与趋势判断

对每个技术领域进行多维度评分：

### 论文信号评分 (1-5)
- 5: 顶会多篇高引论文，新范式出现
- 3-4: 活跃研究方向，持续有改进工作
- 1-2: 论文数量下降或趋于饱和

### 公司信号评分 (1-5)
- 5: 多家头部公司发布产品/重大更新
- 3-4: 有公司投入，有产品或 demo
- 1-2: 鲜有公司布局

### 融资信号评分 (1-5)
- 5: 该领域公司频繁获大额融资
- 3-4: 有融资事件但金额不大
- 1-2: 资本冷淡

### 综合热度 = 论文×0.30 + 公司×0.35 + 融资×0.20 + 媒体×0.15

### 趋势判断
- **加速 (accelerating)**: 热度持续上升，有新玩家入场
- **稳定 (stable)**: 热度维持，渐进式改进
- **降速 (decelerating)**: 热度明显下降，或技术瓶颈

## 步骤 4：生成雷达报告

将所有信号整理为结构化 JSON（`tech_radar_data.json`），然后生成报告：

```bash
cd "$SKILL_DIR"
uv run python scripts/generate_radar.py \
  --skill-dir "$SKILL_DIR" \
  --input tech_radar_data.json \
  --output "reports/tech_radar_{period}.md"
```

JSON 格式：

```json
{
  "period": "2025年4月",
  "generated_at": "2025-04-15",
  "overall_trend": "VLA 模型和灵巧操作是本月最活跃的两个方向...",
  "tech_areas": [
    {
      "id": "foundation-models",
      "maturity": "emerging",
      "maturity_prev": "research",
      "signal_strength": 5,
      "trend": "accelerating",
      "paper_score": 5,
      "company_score": 5,
      "funding_score": 4,
      "media_score": 5,
      "combined_score": 4.75,
      "key_events": [
        {
          "date": "2025-04-10",
          "type": "paper",
          "title": "...",
          "impact": "high",
          "description": "..."
        }
      ],
      "maturity_rationale": "多家公司已将 VLA 模型部署到实际产品中...",
      "pm_implications": "现在是关注 VLA 模型技术选型的最佳时机..."
    }
  ]
}
```

## 步骤 5：输出报告

报告结构：

1. **雷达概览图** — 文本版技术成熟度象限
2. **技术领域一览** — 10 个方向的 scorecard
3. **重点领域深度分析** — 对热度最高的 3 个领域展开
4. **产品经理行动建议** — 按时间维度（现在/6月/12月）给出关注建议

# 输出约定

- 报告文件命名：`tech_radar_{YYYY-QQ}.md`
- 存放目录：`$SKILL_DIR/reports/`
- 建议季度更新，月度也可

# 重要规则

1. **信号交叉验证**：重要趋势判断需来自多个信号源（论文+公司+融资）
2. **成熟度变更谨慎**：maturity 升级（如 research→emerging）需要有明确的产品/部署证据
3. **PM 视角**：每项技术必须回答"这对产品意味着什么"
4. **国内对比**：区分国际和国内的技术发展差异
5. **联动论文体系**：如果用户已经有论文追踪体系（conf-papers/paper-search），优先复用已有笔记作为论文信号
