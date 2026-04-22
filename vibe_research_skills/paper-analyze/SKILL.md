---
name: paper-analyze
description: 深度分析单篇论文，生成详细笔记和评估，图文并茂 / Deep analyze a single paper, generate detailed notes with images
allowed-tools: Read, Write, Bash
---

# Language Setting / 语言设置

This skill supports both Chinese and English reports. The language is determined by the `language` field in your config file:

- **Chinese (default)**: Set `language: "zh"` in config
- **English**: Set `language: "en"` in config

The config file should be located at: `$OBSIDIAN_VAULT_PATH/vibe_research/research_preference/preference.md`

## Language Detection

At the start of execution, read the config file to detect the language setting:

```bash
# Read language from config
LANGUAGE=$(grep -E "^\s*language:" "$OBSIDIAN_VAULT_PATH/vibe_research/research_preference/preference.md" | awk '{print $2}' | tr -d '"')

# Default to Chinese if not set
if [ -z "$LANGUAGE" ]; then
    LANGUAGE="zh"
fi
```

Then use this language setting throughout the workflow:
- When generating notes, pass `--language $LANGUAGE` to scripts
- Generate content in the appropriate language

---

You are the Paper Analyzer for OrbitOS.

# 目标
对特定论文进行深度分析，生成全面笔记，评估质量和价值，并更新知识库。

# 强制执行要求

在写任何正文分析之前，**必须先执行** `scripts/run_paper_analyze.py`。这是 `paper-analyze` 的唯一合法入口。

- 必须真实执行脚本，不允许只阅读 PDF、源码、已有图片后手工跳过执行
- 必须验证脚本产物存在：`analysis_run.json`、MinerU markdown、笔记文件、`images/index.md`
- 如果脚本失败、缺少产物，必须立即报错并说明缺口
- 不允许静默回退到“手工整理笔记”“直接读 main.tex”“只复用已有图片不执行 CLI / Python”

# 信息源原则

- 优先复用本地 PDF、已有笔记、`analysis_run.json`、MinerU markdown 和 `images/index.md`
- 允许联网补充 arXiv 元数据、外部链接和 related work；不要因为本地 PDF 存在就默认禁用 web research
- 只有在用户明确要求“只用本地资料”时，才切换到纯本地分析

# Daily 工作目录

`scripts/run_paper_analyze.py` 执行完成后，会额外创建一个 daily 工作目录，供最终分析报告落盘：

- 目录格式：`vibe_research/10_Daily/YYYY-MM-DD_论文标题/`
- `daily_report_path`：daily 目录下的最终分析报告工作副本
- `daily_images_dir`：与最终报告同目录的图片目录
- 如果输入是本地 PDF，脚本会把该 PDF 一并复制到这个 daily 目录
- `note_path` 仍然是 `20_Research/Papers/` 下的归档笔记；正式补写分析时，优先编辑 `daily_report_path`，需要归档一致时再同步回 `note_path`

# Research 原始资料归档

MinerU 提取的完整文本和所有图片必须在 `20_Research/Papers/` 目录下保留一份原始归档，确保论文原始内容不丢失：

- 归档目录：`vibe_research/20_Research/Papers/[domain]/[paper_title]/mineru/`
  - `mineru/[pdf_stem].md`：MinerU 提取的完整论文 Markdown 文本（包含内联图片引用 `![...](images/xxx.png)`）
  - `mineru/images/`：MinerU 从 PDF 提取的所有原始图片文件
- **必须保留**：完整文本和全部图片，不做筛选、不做裁剪
- **目的**：即使后续分析笔记只引用部分图片，原始 MinerU 产物也要完整保留，方便回溯和二次利用
- `scripts/run_paper_analyze.py` 执行过程中会自动将 MinerU 产物的 markdown 文件和 images 目录复制到归档目录

# 工作流程

## 实现脚本

### 步骤0：初始化环境

```bash
# 创建工作目录
mkdir -p /tmp/paper_analysis
cd /tmp/paper_analysis

# 设置变量（从环境变量 OBSIDIAN_VAULT_PATH 读取，或让用户指定）
PAPER_ID="[PAPER_ID]"
VAULT_ROOT="${OBSIDIAN_VAULT_PATH}"
PAPERS_DIR="${VAULT_ROOT}/vibe_research/20_Research/Papers"
```

### 步骤1：识别论文

### 1.1 解析论文标识符

接受输入格式：
- arXiv ID："2402.12345"
- 完整ID："arXiv:2402.12345"
- 论文标题："论文标题"
- 文件路径：直接路径到现有笔记

### 1.2 检查现有笔记

1. **搜索已有笔记**
   - 按arXiv ID在`vibe_research/20_Research/Papers/`目录中搜索
   - 按标题匹配
   - 如果找到，读取该笔记

2. **读取论文笔记**
   - 如果找到，返回完整内容

## 步骤2：统一获取论文内容与图片

### 2.1 获取论文元数据

1. **优先使用已有信息**
   - 如果用户已经给了 arXiv ID、标题或本地 PDF，直接基于现有输入继续
   - 如果库中已有对应笔记或 metadata，优先复用，不要重复拼装一套临时抓取流程
   - 本地 PDF 存在时，先用本地产物建立分析骨架，但允许继续联网补 arXiv 元数据、外部链接和 related work

2. **必要时补齐元数据**
   - 可以读取 arXiv 页面、已有笔记 frontmatter 或本地 PDF 附近的辅助文件来补齐标题、作者、日期
   - 不要在 `paper-analyze` 里维护一套“下载源码包 + 解压 + 手工读取 TeX 分章节”的旧流程

### 2.2 正文提取统一走 MinerU CLI

1. **确定输入 PDF**
   - 如果工作区或 vault 中已有本地 PDF，直接使用本地 PDF
   - 如果只有 arXiv ID，再先下载 PDF 到本地临时目录

2. **唯一入口**
   - 不要直接手工执行散落的命令
   - 先运行 `scripts/run_paper_analyze.py`，由它统一调度 CLI、图片提取、笔记生成和图谱更新

3. **正式分析默认命令**
   ```bash
   mineru-open-api extract "[PDF_PATH]" -o /tmp/paper_analysis/mineru_extract --language en --timeout 1800
   ```
   - `paper-analyze` 默认使用完整版 `mineru-open-api extract`
   - 这是正式深度分析的默认正文入口，不要改成手工读 TeX、手工拼章节或直接跳过 CLI
   - `extract` 需要 token，且通常耗时较长，任务运行期间不要手动 kill

4. **仅临时纯文本预览时**
   ```bash
   mineru-open-api flash-extract "[PDF_PATH]" -o /tmp/paper_analysis/mineru_flash
   ```
   - `flash-extract` 只适合临时快速预览
   - 不适合作为 `paper-analyze` 的主流程，因为它不提供完整资源

### 2.3 图片提取统一委托给 extract-paper-images

1. **固定入口**
   - 图片提取、源码包检查、figure PDF 处理统一调用 `extract-paper-images`
   - `paper-analyze` 不要自己维护“下载源码包 / 解压 figure / 手工复制图片”的旁路

2. **调用方式**
   ```bash
   /extract-paper-images "[PAPER_ID or PDF_PATH]"
   ```

3. **消费方式**
   - 读取 `extract-paper-images` 返回的图片路径和 `images/index.md`
   - 后续插图时只使用实际返回的文件名，不要猜测文件名

### 2.4 图片语义验证（必须）

1. **先判断图片作用**
   - 在插图前，先判断每张候选图“展示的是什么、在论文里起什么作用”
   - 角色至少标注为：方法/架构图、关键结果图、定性示例/消融图、噪声图（logo/附录装饰）

2. **再决定是否插入**
   - 只插入能支撑一句话总结或关键贡献的图片
   - 如果 `extract-paper-images` 返回很多图，优先方法/架构图和关键结果图

## 步骤3：执行深度分析

### 3.1 分析摘要

1. **提取关键概念**
   - 识别主要研究问题
   - 列出关键术语和概念
   - 注明技术领域

2. **总结研究目标**
   - 要解决的问题是什么？
   - 提出的解决方案方法是什么？
   - 主要贡献是什么？

3. **生成中文翻译**
   - 将英文摘要翻译成流畅的中文
   - 使用适当的技术术语

### 3.2 分析方法论

1. **识别核心方法**
   - 主要算法或方法
   - 技术创新点
   - 与现有方法的区别

2. **分析方法结构**
   - 方法组件及其关系
   - 数据流或处理流水线
   - 关键参数或配置

3. **评估方法新颖性**
   - 这个方法有什么独特之处？
   - 与现有方法相比如何？
   - 有什么关键创新？

### 3.3 分析实验

1. **提取实验设置**
   - 使用的数据集
   - 对比基线方法
   - 评估指标
   - 实验环境

2. **提取结果**
   - 关键性能数字
   - 与基线的对比
   - 消融研究（如果有）

3. **评估实验严谨性**
   - 实验是否全面？
   - 评估是否公平？
   - 基线是否合适？

### 3.4 生成洞察

1. **研究价值**
   - 理论贡献
   - 实际应用
   - 领域影响

2. **局限性**
   - 论文中提到的局限性
   - 潜在弱点
   - 有什么假设可能不成立？

3. **未来工作**
   - 作者建议的后续研究
   - 有什么自然的扩展？
   - 有什么改进空间？

4. **与相关工作对比**
   - 优先搜索本地库中已有的相关论文笔记和 `PaperGraph`
   - 如有必要，允许继续联网补充相关工作
   - 与相似论文相比如何？
   - 补充了什么空白？
   - 属于哪个研究路线

### 3.5 公式输出规范（Markdown LaTeX）

1. **统一格式**
   - 行内公式使用 `$...$`
   - 块级公式使用 `$$...$$` 并单独成行

2. **避免不可渲染写法**
   - 不要用三反引号代码块包裹需要渲染的公式
   - 不要使用纯文本伪公式替代 LaTeX

3. **推荐写法**
   - 行内示例：模型目标是最小化 `$L(\theta)$`
   - 块级示例：
     `$$\theta^* = \arg\min_\theta L(\theta)$$`

4. **复杂公式**
   - 多行或推导型公式统一使用块级 `$$...$$`
   - 保持符号与原论文一致，避免自行改写符号语义

### 3.6 接收图片结果并生成引用

1. **不要手工复制临时目录里的图片**
   - `extract-paper-images` 已经负责把图片写入目标 `images/` 目录
   - 也会同时生成 `images/index.md`

2. **在 `paper-analyze` 中只做消费**
   - 读取返回的图片路径
   - 结合 `images/index.md` 做图片筛选、排序和引用
   - 不要再写 `cp /tmp/...` 这类手工搬运步骤

## 步骤4：生成综合论文笔记

### 4.1 确定笔记路径和领域

```bash
# 根据论文内容确定领域（智能体/大模型/多模态技术/强化学习_LLM_Agent等）
# 推断规则：
# - 如果提到"agent/swarm/multi-agent/orchestration" → 智能体
# - 如果提到"vision/visual/image/video" → 多模态技术
# - 如果提到"reinforcement learning/RL" → 强化学习_LLM_Agent
# - 如果提到"language model/LLM/MoE" → 大模型
# - 否则 → 其他

PAPERS_DIR="${VAULT_ROOT}/vibe_research/20_Research/Papers"
DOMAIN="[推断的领域]"
PAPER_TITLE="[论文标题，空格替换为下划线]"
NOTE_PATH="${PAPERS_DIR}/${DOMAIN}/${PAPER_TITLE}.md"
IMAGES_DIR="${PAPERS_DIR}/${DOMAIN}/${PAPER_TITLE}/images"
INDEX_PATH="${IMAGES_DIR}/index.md"
MINERU_ARCHIVE_DIR="${PAPERS_DIR}/${DOMAIN}/${PAPER_TITLE}/mineru"
MINERU_TEXT_PATH="${MINERU_ARCHIVE_DIR}/[pdf_stem].md"
MINERU_IMAGES_DIR="${MINERU_ARCHIVE_DIR}/images"
```

### 4.2 使用Python生成笔记（正确处理Obsidian格式）

**Python 环境说明**：如果系统安装了 `uv`，优先在 `$OBSIDIAN_VAULT_PATH` 下初始化项目环境（若不存在则执行 `uv init`），并通过 `uv run python ...` 执行后续所有 Python 命令；新增依赖统一使用 `uv add 包名`，不要安装到全局 Python。

```bash
# 调用外部脚本生成笔记；若使用 uv 环境，请先在 "$OBSIDIAN_VAULT_PATH" 下执行 uv init（如需）
uv run python "scripts/generate_note.py" --paper-id "[PAPER_ID]" --title "[论文标题]" --authors "[作者]" --domain "[领域]" --language "$LANGUAGE"
```

### 4.3 使用obsidian-markdown skill生成最终笔记

当分析完成后，调用obsidian-markdown skill来确保格式正确，然后手动补充详细内容。

## 步骤5：更新知识图谱

### 5.1 读取现有图谱

```bash
GRAPH_PATH="${PAPERS_DIR}/../PaperGraph/graph_data.json"
cat "$GRAPH_PATH" 2>/dev/null || echo "{}"
```

### 5.2 生成图谱节点和边

```bash
# 调用外部脚本更新知识图谱；若使用 uv 环境，请用 uv run python 执行
uv run python "scripts/update_graph.py" --paper-id "[PAPER_ID]" --title "[论文标题]" --domain "[领域]" --score [评分] --language "$LANGUAGE"
```

## 步骤4：生成综合论文笔记

### 4.1 笔记结构

```markdown
---
date: "YYYY-MM-DD"
paper_id: "arXiv:XXXX.XXXXX"
title: "论文标题"
authors: "作者列表"
domain: "[领域名称]"
tags:
  - 论文笔记
  - [领域标签]
  - [方法标签-无空格]  # 标签名不能有空格，空格替换为-

# ⚠️ 标签名格式规则
# Obsidian的tag名称不能包含空格，如有空格需用短横线(-)连接
# 例如：
#   "Agent Swarm" → "Agent-Swarm"
#   "Visual Agentic" → "Visual-Agentic"
#   "MoonViT-3D" → "MoonViT-Three-D"
#
# Python脚本(scripts/generate_note.py)会自动处理标签名中的空格
# 将所有tag.replace(' ', '-')移除空格
  - [相关论文1]    ← 在tags中添加相关论文
  - [相关论文2]    ← 在tags中添加相关论文
quality_score: "[X.X]/10"
created: "YYYY-MM-DD"
updated: "YYYY-MM-DD"
status: analyzed
---

# [论文标题]

## 核心信息
- **论文ID**：arXiv:XXXX.XXXXX
- **作者**：[作者1, 作者2, 作者3]
- **机构**：[从作者推断或查看论文]
- **发布时间**：YYYY-MM-DD
- **会议/期刊**：[从categories推断]
- **链接**：[arXiv](链接) | [PDF](链接)
- **引用**：[如果可获取]

## 摘要翻译

### 英文摘要
[论文的英文摘要原文]

### 中文翻译
[将英文摘要翻译成流畅的中文，保持学术术语的准确性]

### 核心要点提炼
- **研究背景**：[该研究领域的现状和存在的问题]
- **研究动机**：[为什么要做这项研究]
- **核心方法**：[一句话概括主要方法]
- **主要结果**：[最重要的实验结果]
- **研究意义**：[该研究对领域的贡献]

## 研究背景与动机

### 领域现状
[详细描述该研究领域当前的发展状况]

### 现有方法的局限性
[深入分析现有方法存在的问题：]

### 研究动机
[解释为什么需要这项研究：]

## 研究问题

### 核心研究问题
[清晰、准确地描述论文要解决的核心问题]

## 方法概述

### 核心思想
[用通俗易懂的语言解释方法的核心思想，让非专业人士也能理解]

### 方法框架

#### 整体架构
[描述方法的整体架构，包括主要组件和它们之间的关系]

**架构图选择原则**：
1. **优先使用论文中的现成图** - 如果论文PDF中有架构图/流程图/方法图，直接插入
2. **仅在无图时创建Canvas** - 当论文没有合适的架构图时，才用JSON Canvas自行绘制

**方式1：插入论文中的图（优先）**
```
![[actual_returned_image_filename.ext|800]]

> 图1：[架构描述，包括图中各个部分的含义和它们之间的关系]
```
**注意**：图片文件名必须与 `extract-paper-images` 的实际返回结果匹配，常见为 `.jpg`、`.png` 或 `.webp`

**方式2：创建Canvas架构图（论文无图时使用）**
调用 `json-canvas` skill 创建 `.canvas` 文件，然后嵌入：
```
![[论文标题_Architecture.canvas|1200|400]]
```

Canvas 创建步骤：
1. 调用 `json-canvas` skill
2. 使用 `--create --file "路径/架构图.canvas"` 参数
3. 创建节点和连接，使用不同颜色区分层级
4. 保存后在markdown中嵌入引用

**文本图表示例**（当无法插入图片或创建Canvas时的最后备选）：
```
输入 → [模块1] → [模块2] → [模块3] → 输出
         ↓         ↓         ↓
       [子模块]  [子模块]  [子模块]
```

#### 各模块详细说明

**模块1：[模块名称]**
- **功能**：[该模块的主要功能]
- **输入**：[输入数据/信息]
- **输出**：[输出数据/信息]
- **处理流程**：
  1. [步骤1详细描述]
  2. [步骤2详细描述]
  3. [步骤3详细描述]
- **关键技术**：[使用的关键技术或算法]
- **数学公式**：[如果有重要的数学公式]
   行内示例：损失函数为 $L(\theta)$。
   块级示例：
   $$\theta^* = \arg\min_\theta L(\theta)$$

**模块2：[模块名称]**
- **功能**：[该模块的主要功能]
- **输入**：[输入数据/信息]
- **输出**：[输出数据/信息]
- **处理流程**：
  1. [步骤1详细描述]
  2. [步骤2详细描述]
  3. [步骤3详细描述]
- **关键技术**：[使用的关键技术或算法]

**模块3：[模块名称]**
[类似格式]

### 方法架构图
[选择最适合的方式展示架构]

**选择原则**：
1. **优先使用论文中的架构图** - 如果论文中有合适的方法架构图、流程图或系统图，直接插入
2. **仅在无图时创建Canvas** - 当论文没有相关架构图时，才用JSON Canvas自行绘制

**方式1：插入论文中的图（优先）**
```
![[actual_returned_image_filename.ext|800]]

> 图1：[架构描述，包括图中各个部分的含义和它们之间的关系]
```
**注意**：图片文件名必须与 `extract-paper-images` 的实际返回结果匹配，常见为 `.jpg`、`.png` 或 `.webp`

**方式2：创建Canvas架构图（论文无图时使用）**
```
![[论文标题_Architecture.canvas|1200|400]]
```
调用`json-canvas` skill创建，支持：
- 彩色节点（颜色1-6或自定义hex）
- 带标签的箭头连接
- 节点分组和层级结构
- Markdown文本渲染

**注意**：Canvas只作为补充手段，不要替换论文中原有的架构图。论文中的图通常更准确、更权威。

## 实验结果

### 实验目标
[本实验要验证什么]

### 数据集

#### 数据集统计

| 数据集 | 样本数 | 特征维度 | 类别数 | 数据类型 |
|--------|--------|----------|--------|----------|
| 数据集1 | X万 | Y维 | Z类 | [类型] |
| 数据集2 | X万 | Y维 | Z类 | [类型] |

### 实验设置

#### 基线方法
[列出所有对比的基线方法，并简要说明]


#### 评估指标
[列出所有评估指标，并解释每个指标的含义]


#### 实验环境

#### 超参数设置


### 主要结果

#### 主实验结果

| 方法 | 数据集1-指标1 | 数据集1-指标2 | 数据集2-指标1 | 数据集2-指标2 | 平均排名 |
|------|---------------|---------------|---------------|---------------|----------|
| 基线1 | X.X±Y.Y | X.X±Y.Y | X.X±Y.Y | X.X±Y.Y | N |
| 基线2 | X.X±Y.Y | X.X±Y.Y | X.X±Y.Y | X.X±Y.Y | N |
| 基线3 | X.X±Y.Y | X.X±Y.Y | X.X±Y.Y | X.X±Y.Y | N |
| **本文方法** | **X.X±Y.Y** | **X.X±Y.Y** | **X.X±Y.Y** | **X.X±Y.Y** | **N** |

> 注：±后的数字表示标准差，**粗体**表示最优结果

#### 结果分析
[对主实验结果的详细分析]

### 消融实验

#### 实验设计
[消融实验的设计思路]

#### 消融结果和分析

### 实验结果图
[插入论文中的实验结果图]

![[actual_returned_image_filename.ext|800]]

> 图2：[图描述]
**注意**：图片文件名必须与 `extract-paper-images` 的实际返回结果匹配，常见为 `.jpg`、`.png` 或 `.webp`

## 深度分析

### 研究价值评估

#### 理论贡献
- **贡献1**：[详细描述理论贡献]
  - 创新点：[新理论/新方法/新视角]
  - 学术价值：[对学术界的价值]
  - 影响范围：[影响的研究领域]

- **贡献2**：[详细描述理论贡献]
  [类似格式]

#### 实际应用价值
- **应用场景1**：[应用场景描述]
  - 适用性：[该方法在该场景的适用性]
  - 优势：[相比现有方案的优势]
  - 潜在影响：[可能带来的影响]

- **应用场景2**：[应用场景描述]
  [类似格式]

#### 领域影响
- **短期影响**：[近期可能产生的影响]
- **中期影响**：[中期可能产生的影响]
- **长期影响**：[长期可能产生的影响]
- **潜在变革**：[可能带来的范式变革]

### 方法优势详解

#### 优势1：[优势名称]
- **描述**：[详细描述该优势]
- **技术基础**：[该优势的技术基础]
- **实验验证**：[实验如何验证该优势]
- **对比分析**：[与现有方法相比的优势程度]

#### 优势2：[优势名称]
[类似格式]

#### 优势3：[优势名称]
[类似格式]

### 局限性分析

#### 局限1：[局限名称]
- **描述**：[详细描述该局限性]
- **表现**：[在实际中的表现]
- **原因**：[产生该局限的根本原因]
- **影响**：[对实际应用的影响]
- **可能的解决方案**：[如何缓解或解决]

#### 局限2：[局限名称]
[类似格式]

#### 局限3：[局限名称]
[类似格式]

### 适用性与场景分析

#### 适用场景
- **场景1**：[场景描述]
  - 适用原因：[为什么适用]
  - 预期效果：[预期能达到的效果]
  - 注意事项：[使用时需要注意什么]

- **场景2**：[场景描述]
  [类似格式]

#### 不适用场景
- **场景1**：[场景描述]
  - 不适用原因：[为什么不适用]
  - 替代方案：[建议使用什么替代方案]

- **场景2**：[场景描述]
  [类似格式]

## 与相关论文对比

### 对比论文选择依据
[为什么选择这些论文进行对比]

### [[相关论文1]] - [论文标题]

#### 基本信息
- **作者**：[作者]
- **发表时间**：[时间]
- **会议/期刊**：[ venue]
- **核心方法**：[一句话概括]

#### 方法对比
| 对比维度 | 相关论文1 | 本文方法 |
|----------|-----------|----------|
| 核心思想 | [描述] | [描述] |
| 技术路线 | [描述] | [描述] |
| 关键组件 | [描述] | [描述] |
| 创新程度 | [描述] | [描述] |

#### 性能对比
| 数据集 | 指标 | 相关论文1 | 本文方法 | 提升幅度 |
|--------|------|-----------|----------|----------|
| 数据集1 | 指标1 | X.X | Y.Y | +Z.Z% |
| 数据集2 | 指标2 | X.X | Y.Y | +Z.Z% |

#### 关系分析
- **关系类型**：[改进/扩展/对比/跟随]
- **本文改进**：[相比该论文的改进点]
- **优势**：[本文方法的优势]
- **劣势**：[本文方法的劣势]
- **互补性**：[两种方法是否互补]

### [[相关论文2]] - [论文标题]
[类似格式]

### [[相关论文3]] - [论文标题]
[类似格式]

### 对比总结
[对所有对比论文的总结]

## 技术路线定位

### 所属技术路线
本文属于[技术路线名称]，该技术路线的核心特点是：
- 特点1：[描述]
- 特点2：[描述]
- 特点3：[描述]

### 技术路线发展历程
```
[里程碑1] → [里程碑2] → [里程碑3] → [本文工作] → [未来方向]
   ↑           ↑           ↑           ↑
 [论文A]     [论文B]     [论文C]    [本文]
```

### 本文在技术路线中的位置
- **承上**：[继承了哪些前期工作]
- **启下**：[为后续工作提供了什么基础]
- **关键节点**：[为什么是技术路线中的关键节点]

### 具体子方向
本文主要关注[具体子方向]，该子方向的研究重点是：
- 重点1：[描述]
- 重点2：[描述]

### 相关工作图谱
[用文本或图形表示与相关工作的关系]

## 未来工作建议

### 作者建议的未来工作
1. **建议1**：[作者的建议]
   - 可行性：[是否可行]
   - 价值：[潜在价值]
   - 难度：[实现难度]

2. **建议2**：[作者的建议]
   [类似格式]

### 基于分析的未来方向
1. **方向1**：[方向描述]
   - 动机：[为什么这个方向值得研究]
   - 可能的方法：[可能的研究方法]
   - 预期成果：[可能取得的成果]
   - 挑战：[面临的挑战]

2. **方向2**：[方向描述]
   [类似格式]

3. **方向3**：[方向描述]
   [类似格式]

### 改进建议
[对本文方法的具体改进建议]
1. **改进1**：[改进描述]
   - 当前问题：[存在的问题]
   - 改进方案：[如何改进]
   - 预期效果：[预期能达到的效果]

2. **改进2**：[改进描述]
   [类似格式]

## 我的综合评价

### 价值评分

#### 总体评分
**[X.X]/10** - [评分理由简述]

#### 分项评分

| 评分维度 | 分数 | 评分理由 |
|----------|------|----------|
| 创新性 | [X]/10 | [详细理由] |
| 技术质量 | [X]/10 | [详细理由] |
| 实验充分性 | [X]/10 | [详细理由] |
| 写作质量 | [X]/10 | [详细理由] |
| 实用性 | [X]/10 | [详细理由] |

### 重点关注

#### 值得关注的技术点

#### 需要深入理解的部分

## 我的笔记

%% 用户可以在这里添加个人阅读笔记 %%

## 相关论文

### 直接相关
- [[相关论文1]] - [关系描述：改进/扩展/对比等]
- [[相关论文2]] - [关系描述]

### 背景相关
- [[背景论文1]] - [关系描述]
- [[背景论文2]] - [关系描述]
   
### 后续工作
- [[后续论文1]] - [关系描述]
- [[后续论文2]] - [关系描述]

## 外部资源
[可列举一些相关的视频、博客、项目等的链接]

> [!tip] 关键启示
> [论文最重要的启示，用一句话总结核心思想]

> [!warning] 注意事项
> - [注意事项1]
> - [注意事项2]
> - [注意事项3]

> [!success] 推荐指数
> ⭐⭐⭐⭐⭐ [推荐指数和简要理由，如：强烈推荐阅读！这是XX领域的里程碑论文]
```

## 步骤5：更新知识图谱

### 5.1 添加或更新节点

1. **读取图谱数据**
   - 文件路径：`$OBSIDIAN_VAULT_PATH/vibe_research/20_Research/PaperGraph/graph_data.json`

2. **添加或更新该论文的节点**
   - 包含分析元数据：
     - quality_score
     - tags
     - domain
     - analyzed: true

3. **创建到相关论文的边**
   - 对每篇相关论文，创建边
   - 边类型：
     - `improves`：改进关系
     - `related`：一般关系
   - 权重：基于相似度（0.3-0.8）

4. **更新时间戳**
   - 设置`last_updated`为当前日期

5. **保存图谱**
   - 写入更新的graph_data.json

## 步骤6：展示分析摘要

### 6.1 输出格式

```markdown
## 论文分析完成！

**论文**：[[论文标题]] (arXiv:XXXX.XXXXX)

**分析状态**：✅ 已生成详细笔记
**Daily 报告**：[[vibe_research/10_Daily/YYYY-MM-DD_论文标题/论文标题.md]]
**归档笔记**：[[vibe_research/20_Research/Papers/领域/论文标题.md]]

---

**综合评分**：[X.X/10]

**分项评分**：
- 创新性：[X/10]
- 技术质量：[X/10]
- 实验充分性：[X/10]
- 写作质量：[X/10]
- 实用性：[X/10]

**突出亮点**：
- [亮点1]
- [亮点2]
- [亮点3]

**主要优势**：
- [优势1]
- [优势2]

**主要局限**：
- [局限1]
- [局限2]

**相关论文**（N篇）：
- [[相关论文1]] - [关系]
- [[相关论文2]] - [关系]
- [[相关论文3]] - [关系]

**技术路线**：
本文属于[技术路线]，主要关注[子方向]。

---

**快速操作**：
- 点击笔记链接查看详细分析
- 使用`/paper-search`搜索更多相关论文
- 打开Graph View查看论文关系
- 根据分析决定深入研究或跳过

**建议**：
- [基于分析的具体建议1]
- [基于分析的具体建议2]
```

## 重要规则

- **保留用户现有笔记** - 不要覆盖手动笔记
- **使用全面分析** - 涵盖方法论、实验、价值评估
- **根据 `$LANGUAGE` 设置选择语言** - `"en"` 用英文写笔记，`"zh"` 用中文写笔记（section headers、content 都要匹配）
- **引用相关工作** - 建立连接到现有知识库
- **客观评分** - 使用一致的评分标准
- **更新知识图谱** - 维护论文间关系
- **图文并茂** - 论文中的核心图都要用上（核心架构图、方法图、实验结果图等），但插图前必须先完成图片语义验证（图的作用与价值）
- **MinerU 默认模式** - `paper-analyze` 默认走完整版 `extract`，因为需要图片和完整内容；`flash-extract` 只适合其他 skill 的临时纯文本预览
- **MinerU 原始资料归档** - MinerU 提取的完整 Markdown 文本和所有图片必须在 `20_Research/Papers/[domain]/[title]/mineru/` 保留一份完整归档，不做筛选和裁剪
- **优雅处理错误** - 如果一个源失败则继续
- **管理token使用** - 全面但不超出token限制

### Obsidian 格式规则（必须遵守！）

1. **图片嵌入**：**必须使用** `![[filename.png|800]]`，**禁止使用** `![alt](path%20encoded)`
   - Obsidian 不支持 URL 编码路径（`%20`, `%26` 等不工作）
   - Obsidian 会自动在 vault 中搜索文件名，无需写完整路径
   - 图片文件名必须直接取自 `extract-paper-images` 的实际返回结果，不要自己猜文件名
2. **Wikilink 必须用 display alias**：`[[File_Name|Display Title]]`，禁止 bare `[[File_Name]]`
   - 下划线文件名直接显示会很丑
3. **不要用 `---` 作为"无数据"占位符**：使用 `--` 代替（`---` 会被 Obsidian 解析为分隔线）
4. **机构/Affiliation 提取**：从 arXiv 源码包的 `.tex` 文件提取 `\author`/`\affiliation` 字段；若不可用，标 `--`

### 双语 Section Headers 对照表

根据 `$LANGUAGE` 设置选择对应语言的 section header：

| Chinese (`zh`) | English (`en`) |
|---|---|
| 核心信息 | Core Information |
| 摘要翻译 | Abstract & Translation |
| 研究背景与动机 | Research Background & Motivation |
| 研究问题 | Research Problem |
| 方法概述 | Method Overview |
| 实验结果 | Experimental Results |
| 深度分析 | In-Depth Analysis |
| 与相关论文对比 | Comparison with Related Work |
| 技术路线定位 | Technical Roadmap |
| 未来工作建议 | Future Work |
| 我的综合评价 | Assessment |
| 我的笔记 | My Notes |
| 相关论文 | Related Papers |
| 外部资源 | External Resources |

## 分析标准

### 评分细则（0-10分制）

**创新性**：
- 9-10分：新颖突破、新范式
- 7-8分：显著改进或组合
- 5-6分：次要贡献、已知或已确立
- 3-4分：增量改进
- 1-2分：已知或已确立

**技术质量**：
- 9-10分：严谨的方法论、合理的方法
- 7-8分：良好的方法、次要问题
- 5-6分：可接受的方法、有问题的方法
- 3-4分：有问题的方法、差的方法
- 1-2分：差的方法

**实验充分性**：
- 9-10分：全面的实验、强基线
- 7-8分：良好的实验、充分的基线
- 5-6分：可接受的实验、部分基线
- 3-4分：有限的实验、差基线
- 1-2分：差的实验或没有基线

**写作质量**：
- 9-10分：清晰、组织良好
- 7-8分：总体清晰、次要问题
- 5-6分：可理解、部分不清晰
- 3-4分：难以理解、混乱
- 1-2分：差写作

**实用性**：
- 9-10分：高实用影响、可直接应用
- 7-8分：良好实用潜力
- 5-6分：中等实用价值
- 3-4分：有限实用性、理论性仅
- 1-2分：低实用性、理论性仅

### 关系类型定义

- `improves`：对相关工作的明显改进
- `extends`：扩展或建立在相关工作之上
- `compares`：直接对比，可能更好/更差在什么方面
- `follows`：同一研究路线的后续工作
- `cites`：引用（如果有引用数据可用）
- `related`：一般概念关系
```

## 错误处理

- **论文未找到**：检查ID格式，建议搜索
- **arXiv掉线**：使用缓存或稍后重试，在输出中注明局限性
- **PDF解析失败**：停止当前流程，报告 `run_paper_analyze.py` 的失败步骤；不要静默回退到只看摘要
- **相关论文未找到**：说明缺乏上下文
- **图谱更新失败**：继续但不更新图谱

## 使用说明

当用户调用 `/paper-analyze [论文ID]` 时：

### 快速执行（推荐）

先执行强制入口脚本；没有这一步，就不允许继续写分析正文：

```bash
uv run python "scripts/run_paper_analyze.py" \
  --paper-id "$PAPER_ID" \
  --pdf-path "$PDF_PATH" \
  --title "$TITLE" \
  --authors "$AUTHORS" \
  --domain "$DOMAIN"
```

如果环境里没有 `uv`，再退回：

```bash
python "scripts/run_paper_analyze.py" \
  --paper-id "$PAPER_ID" \
  --pdf-path "$PDF_PATH" \
  --title "$TITLE" \
  --authors "$AUTHORS" \
  --domain "$DOMAIN"
```

脚本成功后，必须检查它打印出的这些路径是否真实存在：
- `analysis_run.json`
- `markdown_path`
- `note_path`
- `index_path`
- `daily_dir`
- `daily_report_path`
- `daily_images_dir`
- `daily_pdf_path`（如果输入是本地 PDF）
- `mineru_archive_dir`（MinerU 原始资料归档目录）
- `mineru_text_path`（归档的完整 MinerU Markdown 文本）
- `mineru_images_dir`（归档的 MinerU 原始图片目录）

只有在这些产物都存在之后，才允许继续补写分析正文。默认把最终分析写进 `daily_report_path`。

### 手动分步执行（用于调试）

只有在 `scripts/run_paper_analyze.py` 已经执行过、但你需要排查某一步失败原因时，才允许做手动调试。
手动调试不能替代强制入口脚本，也不能作为默认执行路径。

### 注意事项

1. **frontmatter格式（重要）**：所有字符串值必须用双引号包围
   ```yaml
   ---
   date: "YYYY-MM-DD"
   paper_id: "arXiv:XXXX.XXXXX"
   title: "论文标题"
   authors: "作者列表"
   domain: "[领域名称]"
   quality_score: "[X.X]/10"
   created: "YYYY-MM-DD"
   updated: "YYYY-MM-DD"
   status: analyzed
   ---
   ```
   **Obsidian对YAML格式要求严格，缺少引号会导致frontmatter无法正常显示！**

2. **图片嵌入**：**必须使用 Obsidian wikilink 语法** `![[filename.png|800]]`
   - **禁止使用** `![alt](path%20encoded)` — URL 编码在 Obsidian 中不工作
   - Obsidian 会自动搜索 vault 中的文件名，无需写完整路径
   - 图片文件名必须直接取自 `extract-paper-images` 的实际返回结果，常见为 `.jpg`、`.png` 或 `.webp`
3. **wikilinks**：必须使用 display alias `[[File_Name|Display Title]]`，禁止 bare `[[File_Name]]`
4. **领域推断**：根据论文内容自动推断
5. **相关论文**：在笔记中引用 `[[path/to/note|Paper Title]]`
