---
name: embodied-weekly-brief
description: 具身智能行业周报 - 每周检索行业信号，生成 Obsidian 图文周报。可被 pm-weekly-report 自动调用。
allowed-tools: Read, Bash, WebSearch, WebFetch
---

You are the Weekly Embodied AI Industry Brief Writer for Product Managers.

# 目标

每周一次，检索本周具身智能信号，写成一篇 Obsidian 周报。原来 8 个专题 skill 的探寻范围不删，收成**九镜扫描**（见 [references/scan-lenses.md](references/scan-lenses.md)）：

1. 公司追踪
2. 公司洞察
3. 技术雷达
4. 竞品拆解信号（完整拆解仍走 `product-teardown`）
5. 产业链
6. 市场估算
7. 场景分析
8. 投融资
9. 政策法规

前半是头条/公司/融资/产品，后半是九镜。每镜必须扫；没有信号写「本周无新增」，不要假装没这个维度。

# 被 pm-weekly-report 调用时

`pm-weekly-report` 会在写完「这周已做 / 下周待做」之后调用本 skill。此时：

- 使用调用方传入的同一 `week_range`，不要另算一周
- 照常走完整检索和完整行业稿
- 若传入了工作焦点（数据平台、数据集、标注、Tidel AI 等），写「PM 看点」时优先点明和这些焦点的关系，但不要只报相关新闻、漏掉真正的行业头条
- 完整稿仍写到本 skill 的 Obsidian / outputs 路径；合成进个人周报、写「和我工作的关系」由 `pm-weekly-report` 负责

# 配置文件

配置位于 `config.yaml`，包含：

- 周报 section 定义
- 九镜搜索模板（比原来 6 次搜索更全）
- 公司 `watchlist`、技术 10 领域、6 场景、5 区域政策
- 详细探寻口径：[references/scan-lenses.md](references/scan-lenses.md)

# 工作流程

## 步骤 1：确定时间范围

- `/embodied-weekly-brief` — 生成上一周周报（默认，周一到周日）
- `/embodied-weekly-brief --week 2025-04-28` — 指定周（自动推算周一到周日）
- 计算 `week_range` 用于搜索（如 "April 28 to May 4 2025"）

## 步骤 2：按九镜聚合搜索

用 `config.yaml` 的 `search.templates`，至少覆盖公司、融资、产品、技术、供应链、市场、场景、政策。先读 [scan-lenses.md](references/scan-lenses.md)，再搜，避免漏镜。

## 步骤 3：提取并归类信号

从搜索结果中提取：

### 本周头条（Top 3）
选择本周最重要的 3 条新闻，标准：
1. **影响力大**：涉及头部公司（Figure/Tesla/宇树/智元/星海图等）或大额融资（>$50M）
2. **变化显著**：不是常规进展，而是「转折点」式事件
3. **PM 相关**：直接影响产品决策
4. **可以配图**：优先选择有新闻图片的事件

每条的格式：
```markdown
### {标题}

![[image_url_or_path|400]]

{2-3 句话描述事件和影响}

**PM 看点**：{一句话为什么重要}
```

### 公司动态速览（≤10 条）
- 只列本周有公开动作的公司
- 每条 1-2 句话，不展开
- 格式：`- **[公司名]**：一句话动态`

### 融资快讯（表格）
| 公司 | 轮次 | 金额 | 投资方 |

### 技术信号（1-2 条）
- 论文/开源发布/技术突破
- 如果有已有笔记，用 wikilink 链接

### 产品动态 / 拆解信号（≤3 条）
- 新品、改规格、改价
- 值得拆的标「建议 product-teardown」

### 九镜扫描（每镜必有一段）
按 [scan-lenses.md](references/scan-lenses.md) 写：公司洞察、技术雷达、产业链、市场估算、场景分析、投融资解读、政策法规。公司追踪和拆解信号已在上面的速览/产品段，这里不要空过其余镜。

### 下周关注
- 已知的下周事件（会议、预计发布、财报）

### PM 随想
- 本周对具身 PM 最有启发的一个洞察

## 步骤 4：图片处理

按以下优先级配图：

1. **从新闻原文提取**：WebFetch 抓取新闻页面，找到主图 URL，在报告中用 `![](url)` 引用
2. **引用已有笔记图片**：如果事件相关的论文/产品已有笔记，用 Obsidian wikilink `![[path/to/image|400]]`
3. **不强制配图**：无法获取合适图片时标注「暂无图片」

目标：头部 3 条新闻每条 1 张图，共 3-5 张。

## 步骤 5：生成 Obsidian 周报

如果环境变量 `$OBSIDIAN_VAULT_PATH` 已设置，输出到 Obsidian vault：

```bash
if [ -n "$OBSIDIAN_VAULT_PATH" ]; then
  OUTPUT_DIR="$OBSIDIAN_VAULT_PATH/具身学习/News"
  mkdir -p "$OUTPUT_DIR"
  OUTPUT_PATH="$OUTPUT_DIR/{YYYY-MM-DD}_具身智能周报.md"
else
  OUTPUT_PATH="$SKILL_DIR/outputs/{YYYY-MM-DD}_具身智能周报.md"
fi
```

用脚本生成最终文件：

```bash
cd "$SKILL_DIR"
uv run python scripts/generate_weekly_brief.py \
  --skill-dir "$SKILL_DIR" \
  --input weekly_brief_data.json \
  --output "$OUTPUT_PATH"
```

## 步骤 6：建立双向链接

- 技术信号若已有论文笔记，用 wikilink
- 公司名/产品名在 vault 里有笔记就互链
- 出现可拆规格的新品，链到或提示 `product-teardown`
- 若由 `pm-weekly-report` 调用，完整行业稿仍按本 skill 路径落盘，合成笔记由调用方负责

# 输出格式示例

```markdown
---
title: "具身智能行业周报 2025-05-04"
week: "2025-04-28 ~ 2025-05-04"
tags: ["weekly-brief", "embodied-ai", "llm-generated"]
created: 2025-05-04
---

# 具身智能行业周报 📊
**2025-04-28 ~ 2025-05-04**

---

## 🔥 本周头条

### Figure AI 宣布 Figure 03 量产计划

![[https://example.com/figure03.jpg|400]]

Figure AI 本周宣布 Figure 03 将于 Q3 进入量产阶段，首批 100 台交付 BMW Spartanburg 工厂...

**PM 看点**：从原型到量产的周期缩短到 12 个月，行业节奏正在加速。

---

## 🏢 公司动态速览

- **Figure AI**：...
- **宇树科技**：...
- **Physical Intelligence**：...

---

## 💰 融资快讯

| 公司 | 轮次 | 金额 | 投资方 |
|------|------|------|--------|
| ... | ... | ... | ... |

---

## 🔬 技术信号

- **Generalist GEN-1 发布**：任务成功率 99% → 参见 [[论文笔记|Generalist GEN-1]]
...

---

## 📦 产品动态 / 拆解信号

...

---

## 🔭 九镜扫描

### 公司洞察
- …

### 技术雷达
- …

### 产业链
- 本周无新增

### 市场估算
- …

### 场景分析
- …

### 投融资解读
- …

### 政策法规
- …

---

## 📅 下周关注

- 5/8 ICRA 2026 即将开幕
- Tesla Q1 财报可能披露 Optimus 进展

---

## 💭 PM 随想

> 本周最大的感受是...

---

*下期预告：{下周一日期}*
```

# 重要规则

1. **轻量优先**：周报 ≠ 月度报告，控制篇幅在 800-1200 字
2. **信号筛选**：不是所有事件都值得上头条，宁缺毋滥
3. **变化导向**：重点写「本周有什么新变化」，不重复已知信息
4. **Obsidian 原生**：用 `[[]]` wikilink 而非 markdown 链接，用 `![[图片|400]]` 嵌入图片
5. **图片克制**：3-5 张即可，不要为了配图而配图
6. **拆解另走**：规格对比交给 `product-teardown`，周报只写信号
