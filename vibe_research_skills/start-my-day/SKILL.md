---
name: start-my-day
description: 论文阅读工作流启动 - 生成今日论文推荐笔记 / Paper reading workflow starter - Generate daily paper recommendations
---

# Language Setting / 语言设置

This skill supports both Chinese and English reports. The language is determined by the `language` field in your config file:

- **Chinese (default)**: Set `language: "zh"` in config
- **English**: Set `language: "en"` in config

The config file should be located at: `$OBSIDIAN_VAULT_PATH/vibe_research/research_preference/preference.md`

## Language Detection

At the start of execution, first check whether the preference file exists. If it does not exist, ask the user what research directions they want, create a minimal `$OBSIDIAN_VAULT_PATH/vibe_research/research_preference/preference.md`, and then continue the workflow. After that, read the file to detect the language setting:

```bash
# Resolve OBSIDIAN_VAULT_PATH if not set in the current session
# Claude Code bash sessions do not source ~/.zshrc automatically
if [ -z "$OBSIDIAN_VAULT_PATH" ]; then
    [ -f "$HOME/.zshrc" ] && source "$HOME/.zshrc" 2>/dev/null || true
    [ -f "$HOME/.bash_profile" ] && source "$HOME/.bash_profile" 2>/dev/null || true
fi

PREFERENCE_FILE="$OBSIDIAN_VAULT_PATH/vibe_research/research_preference/preference.md"

# If preference file is missing, ask the user for research directions,
# create a minimal preference file, and continue
if [ ! -f "$PREFERENCE_FILE" ]; then
    echo "Missing preference file: $PREFERENCE_FILE"
    echo "Ask the user what kinds of papers they want to read (e.g. LLM agents, multimodal learning, robotics, HCI)."
    echo "Then create a minimal preference.md and continue the workflow instead of exiting."
fi

# Read language from config after ensuring the preference file exists
LANGUAGE=$(grep -E "^\s*language:" "$PREFERENCE_FILE" | awk '{print $2}' | tr -d '"')

# Default to Chinese if not set
if [ -z "$LANGUAGE" ]; then
    LANGUAGE="zh"
fi

# Set note filename suffix based on language
if [ "$LANGUAGE" = "en" ]; then
    NOTE_SUFFIX="paper-recommendations"
else
    NOTE_SUFFIX="论文推荐"
fi
```

Then use this language setting throughout the workflow:
- When generating notes, pass `--language $LANGUAGE` to scripts
- Use appropriate section headers in the generated notes

---

# 目标
帮助用户开启他们的研究日，搜索最近一个月和最近一年的极火、极热门、极优质论文，生成推荐笔记。

# 工作流程

## 强约束

- 必须严格按照本 `start-my-day` skill 中定义的完整流程执行，不能跳步骤、并行改写成其他自定义流程，或绕过其中依赖的子 skill / 脚本约定。
- `preference.md` 只能有一个唯一来源：`$OBSIDIAN_VAULT_PATH/vibe_research/research_preference/preference.md`。
- 允许根据与用户的对话，把用户新表达出来的潜在兴趣方向增补到这唯一一份 `preference.md` 中；但只能直接更新这一个文件，不能在其他目录创建、复制、派生或临时维护第二份 `preference.md`。
- 如果该文件缺失，就在上述唯一路径创建最小可用文件并继续流程。

## 工作流程概述

本 skill 使用 Python 脚本调用 arXiv API 搜索论文，解析 XML 结果并根据研究兴趣进行筛选和评分。

## 步骤1：收集上下文（静默）

1. **获取今日日期**
   - 确定当前日期（YYYY-MM-DD格式）

2. **读取研究配置**
   - 先检查 `$OBSIDIAN_VAULT_PATH/vibe_research/research_preference/preference.md` 是否存在
   - 如果不存在，先询问用户想看什么方向的文章（如 LLM agents、多模态、机器人、HCI 等）
   - 根据用户回答创建最小可用的 `preference.md`
   - 创建后继续搜索，不要中断整个流程
   - 然后读取该文件获取研究偏好与语言设置
   - 提取：关键词、类别和优先级

3. **扫描现有笔记构建索引**
   - 扫描 `vibe_research/20_Research/Papers/` 目录下的所有 `.md` 文件
   - 提取笔记标题（从文件名和frontmatter的title字段）
   - 构建关键词到笔记路径的映射表，用于后续自动链接
   - 优先使用 frontmatter 中的 title 字段，其次使用文件名

## 步骤2：调用 paper-search 获取候选论文

### 2.1 搜索范围

候选论文由 `paper-search` 统一负责检索：

1. **搜索范围**
   - 最近 30 天的 arXiv 新论文
   - 过去一年内的高热度论文（Semantic Scholar / OpenAlex）
   - 查询范围来自唯一的 `preference.md` 中定义的 research domains / arXiv categories

2. **筛选策略**
   - `paper-search` 先根据研究兴趣配置打分
   - 再结合当前 vault 中已有论文索引做搜索前排重与搜索后排重
   - 输出 20-25 篇左右的非重复候选池，供 `start-my-day` 二次策展

### 2.2 执行搜索和筛选

不要再直接调用本目录下的 `scripts/search_arxiv.py`。
必须先生成 `existing_notes_index.json`，再调用 `paper-search/scripts/search_arxiv.py`。

**Python 环境说明**：如果系统安装了 `uv`，优先在 `$OBSIDIAN_VAULT_PATH` 下初始化项目环境（若不存在则执行 `uv init`），并通过 `uv run python ...` 执行后续所有 Python 命令；新增依赖统一使用 `uv add 包名`，不要安装到全局 Python。使用 `uv` 配置环境时，Python 版本必须大于 3.12。若当前仓库里的 Python 版本小于 3.12，且执行 `uv add mineru` 失败，则删除当前项目下的 `.venv/` 与 `uv.lock` 后，使用符合要求的 Python 重新创建虚拟环境并重新安装所需依赖。

```bash
# 先扫描已有论文，得到现有索引
cd "$SKILL_DIR"
uv run python scripts/scan_existing_notes.py \
  --vault "$OBSIDIAN_VAULT_PATH" \
  --output existing_notes_index.json

# 再调用 paper-search 的真实检索脚本
uv run python ../paper-search/scripts/search_arxiv.py \
  --config "$OBSIDIAN_VAULT_PATH/vibe_research/research_preference/preference.md" \
  --existing-index existing_notes_index.json \
  --output paper_search_candidates.json \
  --max-results 200 \
  --top-n 25

# 对候选池执行链接补齐后处理
uv run python ../paper-search/scripts/enrich_paper_links.py \
  --config "$OBSIDIAN_VAULT_PATH/vibe_research/research_preference/preference.md" \
  --input paper_search_candidates.json \
  --output paper_search_candidates_enriched.json
```

**脚本功能**：
1. **搜索外部论文**
   - 搜索最近论文与高热度论文
2. **解析与打分**
   - 提取标题、作者、摘要、发布日期、分类等元数据
   - 计算综合推荐评分（相关性40%、新近性20%、热门度30%、质量10%）
3. **确定性排重**
   - 结合 `existing_notes_index.json` 排除已存在论文
4. **输出候选池**
   - 输出 `paper_search_candidates.json`
   - 保留结构化字段供 `start-my-day` 做二次筛查
5. **后处理补齐链接**
   - 调用 `paper-search/scripts/enrich_paper_links.py`
   - 生成 `paper_search_candidates_enriched.json`
   - 为 `candidates` 补充 repo / project / code / demo 等结构化链接字段

## 步骤3：读取候选结果并做二次筛查

### 3.1 读取 JSON 结果

从 `paper_search_candidates_enriched.json` 中读取 `paper-search` 返回并补齐链接后的候选池：

```bash
cat paper_search_candidates_enriched.json
```

**结果包含**：
- `query_context`
- `existing_corpus`
- `filter_summary`
- `candidates`
- `excluded_duplicates`
- `enrichment_summary`

其中 `candidates` 是已经过脚本级初筛、排重和链接补齐的候选论文池，不是最终每日推荐列表。

### 3.2 二次筛查规则

`start-my-day` 必须基于 `paper_search_candidates_enriched.json` 做一轮 LLM 二次策展：
- 从候选池中最终精选 3-5 篇
- 不能重新选回 `excluded_duplicates` 中的论文
- 不能机械照搬分数前几名
- 需要兼顾 topic diversity、今日值得读的价值、与已有笔记的非重复性
- 优先利用 `automation_links` 与 `link_enrichment` 中的 repo / project / demo 信息辅助判断论文是否适合继续深挖
- 最终写入 daily note 的，是这轮二次筛查后的结果

## 步骤4：生成今日推荐笔记

### 4.1 读取二次筛查结果

从 `paper-search` 返回并补齐链接的候选池中，经过 LLM 二次筛查，最终选出 3-5 篇论文写入推荐笔记：
- 每篇论文仍保留完整信息：ID、标题、作者、摘要、评分、匹配领域
- 若存在 `automation_links.repo`、`automation_links.project`、`automation_links.demo`，应优先在推荐理由与后续代码学习待办中加以利用
- 推荐顺序允许不完全等同于原始分数排序，但必须给出明确的编辑性选择理由

### 4.2 创建推荐笔记文件

1. **创建推荐笔记文件**
   - 文件名（根据语言设置）：
     - 中文（`language: "zh"`）：`vibe_research/10_Daily/YYYY-MM-DD论文推荐.md`
     - 英文（`language: "en"`）：`vibe_research/10_Daily/YYYY-MM-DD-paper-recommendations.md`
   - 使用变量：`vibe_research/10_Daily/YYYY-MM-DD${NOTE_SUFFIX}.md`（其中 `NOTE_SUFFIX` 在语言检测阶段已设置）
   - 必须包含属性：
     - `keywords`: 当天推荐论文的关键词（逗号分隔，从论文标题和摘要中提取）
     - `tags`: ["llm-generated", "daily-paper-recommend"]

2. **检查论文是否值得详细写**
   - **很值得读的论文**：推荐评分 >= 7.5 或特别推荐的论文
   - **一般推荐论文**：其他论文

3. **检查论文是否已有笔记**
   - 搜索 `vibe_research/20_Research/Papers/` 目录
   - 查找是否有该论文的详细笔记
   - 如果已有笔记：简略写，引用已有笔记
   - 如果无笔记：
     - 很值得读：在推荐笔记中写详细部分
     - 一般推荐：只写基本信息

### 4.2 推荐笔记结构

笔记文件结构如下：

```markdown
---
keywords: [关键词1, 关键词2, ...]
tags: ["llm-generated", "daily-paper-recommend"]
---

[具体论文推荐列表...]
```

#### 4.2.1 今日概览（放在论文列表之前）

在论文列表之前，添加一个概览部分，总结今日推荐论文的整体情况。

**根据 `$LANGUAGE` 设置选择语言：**

**English (`language: "en"`)**:
```markdown
## Today's Overview

Today's {paper_count} recommended papers focus on **{direction1}**, **{direction2}**, and **{direction3}**.

- **Overall Trends**: {summary of research trends}
- **Quality Distribution**: Scores range from {min}-{max}, {quality assessment}.
- **Research Hotspots**:
  - **{hotspot1}**: {description}
  - **{hotspot2}**: {description}
  - **{hotspot3}**: {description}
- **Reading Suggestions**: {reading order recommendations}
```

**Chinese (`language: "zh"`)**:
```markdown
## 今日概览

今日推荐的{论文数量}篇论文主要聚焦于**{主要研究方向1}**、**{主要研究方向2}**和**{主要研究方向3}**等前沿方向。

- **总体趋势**：{总结今日论文的整体研究趋势}
- **质量分布**：今日推荐的论文评分在 {最低分}-{最高分} 之间，{整体质量评价}。
- **研究热点**：
  - **{热点1}**：{简要描述}
  - **{热点2}**：{简要描述}
  - **{热点3}**：{简要描述}
- **阅读建议**：{给出阅读顺序建议}
```

**说明**：
- 基于最终入选的 3-5 篇论文的标题、摘要和评分进行总结
- 提取共同的研究主题和趋势
- 给出合理的阅读顺序建议

#### 4.2.2 所有论文统一格式

所有论文按评分从高到低排列，使用统一格式

**根据 `$LANGUAGE` 设置选择标签语言：**

**English (`language: "en"`)**:
```markdown
### [[Note_Filename|Paper Title as Displayed]]
- **Authors**: [author list]
- **Affiliation**: [institution names, extracted from paper source or arXiv page]
- **Links**: [arXiv](url) | [PDF](url)
- **Source**: arXiv
- **Note**: [[existing_note_path|short title]] or --

**One-line Summary**: [one sentence summarizing the core contribution]

**Core Contributions**:
- [contribution 1]
- [contribution 2]
- [contribution 3]

**Key Results**: [most important results from abstract]

**Implementation Study TODOs**:
- [ ] [code learning task 1]
  - [ ] [optional subtask]
- [ ] [code learning task 2]

**Your Takeaways**:
> Waiting for your notes. Looking forward to your takeaways after reading.

---
```

**Chinese (`language: "zh"`)**:
```markdown
### [[Note_Filename|论文标题显示名]]
- **作者**：[作者列表]
- **机构**：[机构名称，从论文源码或 arXiv 页面提取]
- **链接**：[arXiv](链接) | [PDF](链接)
- **来源**：[arXiv]
- **笔记**：[[已有笔记路径|简称]] 或 --

**一句话总结**：[一句话概括论文的核心贡献]

**核心贡献/观点**：
- [贡献点1]
- [贡献点2]
- [贡献点3]

**关键结果**：[从摘要中提取的最重要结果]

**代码学习待办**：
- [ ] [代码学习点1]
  - [ ] [可选子任务]
- [ ] [代码学习点2]

**读后心得 / 你的总结**：
> 等待记录心得，期待您的输出。读完后把最想复现的一点写在这里。

---
```

#### 4.2.2.1 每篇论文后的待办模块

每篇论文条目在正文末尾都必须追加一个“代码学习待办”模块，用 task list 格式输出，帮助用户把阅读动作转成可执行的代码学习路线。

**待办生成要求：**
- **每篇都要有**：无论是否已有详细笔记、是否进入前3篇，都必须保留该模块
- **聚焦代码学习**：待办应围绕模型结构、训练/推理流程、关键算法、实验实现、工程设计或复现步骤，不要只写泛泛的“读论文”“了解背景”
- **顶层最多 4 个大点**：建议 2-4 个顶层待办；信息不足时宁可少写，也不要凑数
- **允许小点展开**：每个顶层待办下面可以有 0-3 个子点，用来补充要看的模块、脚本、指标或验证动作
- **动作导向**：优先使用“定位 / 理解 / 复现 / 对比 / 实现 / 验证 / 拆解”等动词开头，确保能直接执行
- **基于论文内容生成**：待办要从标题、摘要、核心贡献、关键结果、图片和详细报告中提炼，避免凭空编造具体仓库结构或不存在的代码接口

**推荐方向示例：**
- 拆解模型中的核心模块与数据流
- 梳理训练、推理或检索增强流程
- 复现最关键的损失函数、采样策略或优化技巧
- 对照 baseline 分析新增模块到底改进了什么
- 找出最值得实现的 ablation / evaluation 逻辑

#### 4.2.2.2 每篇论文后的读后心得区域

每篇论文条目在“代码学习待办”之后，都必须保留一个专门给用户手写总结的区域，用来记录读后心得、启发、疑问或后续行动。

**心得区域要求：**
- **每篇都要有**：无论论文是否已有笔记、是否位于前3篇，这个区域都必须出现
- **明确归属给用户**：该区域是用户读完后的个人输出区，不应被系统总结替代
- **空白时显示占位文案**：如果用户还没填写，就放一条轻松、有邀请感的占位语
- **填写后可直接覆盖占位语**：用户后续可以直接删除或替换占位文案，写入自己的总结
- **重跑时保护用户内容**：如果该区域已经不是默认占位语，而是用户真实填写的内容，重新生成同一天笔记时不要覆盖
- **语气要有一点趣味**：占位语可以温和、灵动一点，避免机械式的“暂无内容”

**占位文案示例：**
- `等待记录心得，期待您的输出。读完后把最想复现的一点写在这里。`
- `这块先替读完后的你占个座，欢迎回来补上今天最有意思的收获。`
- `灵感留言区已预留，等你把一句总结或一个好问题放进来。`

**重要格式规则**：
- **Wikilink 必须使用 display alias**：`[[File_Name|Display Title]]`，不要使用 bare `[[File_Name]]`（下划线会直接显示，影响阅读）
- **图片必须使用 Obsidian wikilink 嵌入语法**：`![[filename.png|600]]`，**禁止**使用 `![alt](path%20encoded)` 格式（URL 编码在 Obsidian 中不工作）
- **机构信息**：从论文 TeX 源码的 `\author` 或 `\affiliation` 字段提取；若 arXiv API 未提供，从下载的源码包读取
- **不要使用 `---` 作为"无数据"占位符**：使用 `--` 代替（三个短横线会被 Obsidian 解析为分隔线）

#### 4.2.3 前三篇论文进行图片语义筛选和详细分析

对于前3篇论文（评分最高的3篇，作为候选图来源）：

**步骤0：检查论文是否已有笔记**
```bash
# 在 vibe_research/20_Research/Papers/ 目录中搜索已有笔记
# 搜索方式：
# 1. 按论文ID搜索（如 2602.23351）
# 2. 按论文标题搜索（模糊匹配）
# 3. 按论文标题关键词搜索
```

**步骤1：根据检查结果决定处理方式**

如果已有笔记：
- 不生成新的详细报告
- 使用已有笔记路径作为 wikilink
- 在推荐笔记的"详细报告"字段引用已有笔记
- 检查是否需要提取图片（如果没有 images 目录或 images 目录为空）
  - 如果需要图片：调用 `extract-paper-images`
  - 如果已有图片：使用现有图片

如果没有笔记：
- 调用 `extract-paper-images` 提取图片
- 调用 `paper-analyze` 生成详细报告
- 在推荐笔记中添加图片和详细报告链接

**步骤2：在推荐笔记中插入图片和链接**

**如果已有笔记**：
```markdown
### [[已有论文名称]]
- **作者**：[作者列表]
- **机构**：[机构名称]
- **链接**：[arXiv](链接) | [PDF](链接)
- **来源**：[arXiv]
- **详细报告**：[[已有笔记路径]]
- **笔记**：已有详细分析

**一句话总结**：[一句话概括论文的核心贡献]

![[existing_image_filename.png|600]]

**核心贡献/观点**：
...

**代码学习待办**：
- [ ] [从已有笔记中提炼的代码学习点]
  - [ ] [可选子任务]

**读后心得 / 你的总结**：
> 等待记录心得，期待您的输出。欢迎回来补一条最重要的理解。
```

**如果没有笔记**：
```markdown
### [[Note_Filename|Paper Title Display Name]]
- **作者**：[作者列表]
- **机构**：[机构名称]
- **链接**：[arXiv](链接) | [PDF](链接)
- **来源**：[arXiv]
- **详细报告**：[[vibe_research/20_Research/Papers/[domain]/[note_filename]|Short Title]] (自动生成)

**一句话总结**：[一句话概括论文的核心贡献]

![[paperID_fig1.png|600]]

**核心贡献/观点**：
...

**代码学习待办**：
- [ ] [围绕新论文生成的代码学习点]
  - [ ] [可选子任务]

**读后心得 / 你的总结**：
> 这里留给读完后的你。期待您的输出，写下最值得实现的一点吧。
```

**图片格式规则（重要！）**：
- **必须使用 Obsidian wikilink 嵌入语法**：`![[filename.png|600]]`
- **禁止使用 markdown 图片语法**：~~`![alt](path%20with%20encoding)`~~ — URL 编码（`%20`, `%26`）在 Obsidian 中不工作
- 图片文件名示例：`2603.24124_fig1.png`
- Obsidian 会自动在 vault 中搜索匹配的文件名，无需写完整路径

**详细报告说明**：
- 报告路径：`vibe_research/20_Research/Papers/[论文分类]/[note_filename].md`
- **重要**：使用 JSON 中的 `note_filename` 字段拼接 wikilink
- **必须使用 display alias**：`[[vibe_research/20_Research/Papers/[domain]/[note_filename]|Short Title]]`
  - 正确：`[[vibe_research/20_Research/Papers/大模型/Hypothesis-Conditioned_Query_Rewriting|Hypothesis-Conditioned Query Rewriting]]`
  - 错误：`[[vibe_research/20_Research/Papers/大模型/Hypothesis-Conditioned_Query_Rewriting_for_Decision-Useful_Retrieval]]`（下划线直接显示，不美观）
- 详细报告由 `paper-analyze` 自动生成

**机构/Affiliation 提取**：
- 从下载的 arXiv 源码包（`.tar.gz`）中的 `.tex` 文件提取 `\author` 和 `\affiliation` 字段
- 若源码不可用，从 arXiv 页面 HTML 提取
- 若仍无法获取，标记为 `--`（使用两个短横线，**不要用三个** `---`，因为 Obsidian 会将其解析为分隔线）

## 步骤5：自动链接关键词（可选）

在生成推荐笔记后，自动链接关键词到同一个推荐笔记文件：

```bash
# 步骤1：扫描现有笔记
cd "$SKILL_DIR"
uv run python scripts/scan_existing_notes.py \
  --vault "$OBSIDIAN_VAULT_PATH" \
  --output existing_notes_index.json

# 步骤2：生成推荐笔记（正常流程）
# ... 使用 search_arxiv.py 搜索论文 ...

# 步骤3：链接关键词（新增步骤）
uv run python scripts/link_keywords.py \
  --index existing_notes_index.json \
  --input "vibe_research/10_Daily/YYYY-MM-DD${NOTE_SUFFIX}.md" \
  --output "vibe_research/10_Daily/YYYY-MM-DD${NOTE_SUFFIX}.md"
```

**注意**：
- 关键词链接脚本会自动跳过 frontmatter、标题行、代码块
- 过滤通用词（and, for, model, learning 等）
- 保留已有 wikilink 不被修改

# 重要规则

- **搜索范围扩大**：搜索近一个月 + 近一年热门论文
- **综合推荐评分**：结合相关性、新近性、热门度、质量四个维度
- **文件名以日期**：保持 `vibe_research/10_Daily/YYYY-MM-DD${NOTE_SUFFIX}.md` 格式（中文：`论文推荐`，英文：`paper-recommendations`）
- **添加今日概览**：在推荐笔记开头添加"## 今日概览"部分，总结今日论文的主要研究方向、总体趋势、质量分布、研究热点和阅读建议
- **按评分排序**：所有论文按推荐评分从高到低排列
- **每篇论文都要有待办模块**：
  - 在每篇论文末尾追加“代码学习待办 / Implementation Study TODOs”
  - 顶层待办最多 4 个，且必须是代码学习或复现导向
  - 每个顶层待办可带少量子点，补充具体脚本、模块、指标或验证步骤
- **每篇论文都要有读后心得区域**：
  - 在“代码学习待办”后追加“读后心得 / 你的总结”区域
  - 空白时显示一句有邀请感的占位文案，如“等待记录心得，期待您的输出”
  - 如果用户已经手写填写内容，重新生成时不要覆盖这块
- **前3篇特殊处理**：
  - 论文名称用 wikilink 格式：`[[论文名字]]`
  - 从候选图片中按语义作用选择用于总结的图片（方法/架构图优先，其次关键结果图）
  - 自动调用 `paper-analyze` 生成详细报告
  - 在"详细报告"字段显示 wikilink 关联
- **总结图片规则**：从前3篇候选论文中选择 2-3 张图片插入（优先方法/架构图与关键结果图；可选1张定性/消融图）
- **其余论文展示**：其余论文只保留文本信息；如无通过语义验证的图片，不显示图片占位
- **保持快速**：让用户快速了解当日推荐
- **避免重复**：检查已推荐论文
- **自动关键词链接**：
  - 在生成推荐笔记后，自动扫描现有笔记
  - 将文本中的关键词（如 BLIP、CLIP 等）替换为 wikilink
  - 示例：`BLIP` → `[[BLIP]]`
  - 保留已有 wikilink 不被修改
  - 不替换代码块中的内容
  - 不替换已存在 wikilink 的内容（避免重复）

# 与其他 skills 的区别

## start-my-day (本skill)
- **目的**：从大范围搜索中筛选推荐论文，生成每日推荐笔记
- **搜索范围**：近一个月 + 近一年热门/优质论文
- **内容**：推荐列表
  - 开头包含"今日概览"：总结主要研究方向、总体趋势、质量分布、研究热点和阅读建议
  - 所有论文统一格式
  - 前3篇特殊处理：
    - 论文名称用 wikilink 格式：`[[论文名字]]`
    - 从候选图片中按语义作用选择用于总结的图片（方法/架构图优先，其次关键结果图）
    - 自动调用 `paper-analyze` 生成详细报告
    - 在"详细报告"字段显示 wikilink 关联
- **图片处理**：从前3篇候选论文中语义筛选并插入2-3张图（非机械使用第一张）
- **详细报告**：前3篇自动生成，其他论文不生成
- **适用**：用户每天手动触发
- **笔记引用**：如果论文已有笔记，简略写并引用；如果分析需要引用历史笔记，也直接引用

## paper-analyze (深度分析skill)
- **目的**：用户主动查看单篇论文，深度研究
- **适用场景**：用户自己还想要看，但AI没有整理到的论文
- **内容**：详细的论文深度分析笔记
  - 包含所有核心信息：研究问题、方法概述、方法架构、关键创新、实验结果、深度分析、相关论文对比等
  - **图文并茂**：论文中的所有图片都要用上（核心架构图、方法图、实验结果图等）
- **适用**：用户主动调用 `/paper-analyze [论文ID]` 或论文标题
- **重要要求**：无论是start-my-day整理的论文，还是用户主动查看的论文，都要图文并茂

# 使用说明

当用户输入 "start my day" 时，按以下步骤执行：

- 必须遵循本 skill 的既定流程执行，不得自行改写流程。
- 全流程只允许使用这一份配置文件：`$OBSIDIAN_VAULT_PATH/vibe_research/research_preference/preference.md`。
- 如果通过对话发现用户新增了可能感兴趣的研究方向，可以直接补充到这唯一一份 `preference.md`；但绝不能因此创建第二份配置文件。

**日期参数支持**：
- 无参数：生成当天的论文推荐笔记
- 有参数（YYYY-MM-DD）：生成指定日期的论文推荐笔记
  - 例如：`/start-my-day 2026-02-27`

## 自动执行流程

1. **获取目标日期**
   - 无参数：使用当前日期（YYYY-MM-DD格式）
   - 有参数：使用指定日期

2. **扫描现有笔记构建索引**
   ```bash
   # 扫描 vault 中现有的论文笔记
   cd "$SKILL_DIR"
   uv run python scripts/scan_existing_notes.py \
     --vault "$OBSIDIAN_VAULT_PATH" \
     --output existing_notes_index.json
   ```
   - 扫描 `vibe_research/20_Research/Papers/` 目录
   - 提取笔记标题和 tags
   - 构建关键词到笔记路径的映射表

3. **调用 paper-search 获取候选论文**
   ```bash
   # 先扫描已有论文，得到可用于排重的索引
   cd "$SKILL_DIR"
   uv run python scripts/scan_existing_notes.py \
     --vault "$OBSIDIAN_VAULT_PATH" \
     --output existing_notes_index.json

   # 再调用 paper-search 的真实检索脚本
   uv run python ../paper-search/scripts/search_arxiv.py \
     --config "$OBSIDIAN_VAULT_PATH/vibe_research/research_preference/preference.md" \
     --existing-index existing_notes_index.json \
     --output paper_search_candidates.json \
     --max-results 200 \
     --top-n 25 \
     --target-date "{目标日期}"  # 如果用户指定了日期，替换为实际日期
   ```

4. **读取候选结果并做二次筛查**
   - 从 `paper_search_candidates_enriched.json` 中读取候选池
   - 候选池已经经过脚本级打分、初步排重与链接补齐
   - 再由 `start-my-day` 做 LLM 二次策展，最终精选 3-5 篇
   - 每篇候选论文包含：ID、标题、作者、摘要、评分、匹配领域、`note_filename`，以及 `automation_links` / `link_enrichment`

5. **生成推荐笔记（包含关键词链接）**
   - 创建 `vibe_research/10_Daily/YYYY-MM-DD${NOTE_SUFFIX}.md`（使用目标日期，`NOTE_SUFFIX` 依语言设置）
   - **按评分排序**：所有论文按推荐评分从高到低排列
   - **每篇论文追加代码学习待办**：
     - 每篇论文都要在末尾追加“代码学习待办 / Implementation Study TODOs”模块
     - 顶层待办最多 4 个大点，建议 2-4 个
     - 每个大点下可追加若干子点，补充具体代码阅读、复现或验证动作
   - **每篇论文追加读后心得区域**：
     - 在“代码学习待办”后追加“读后心得 / 你的总结”区域
     - 若用户尚未填写，则放置一句轻松的占位文案，例如“等待记录心得，期待您的输出”
     - 若该区域已有用户手写内容，则重新生成时保留原内容
   - **前3篇特殊处理**：
     - 论文名称用 wikilink 格式：`[[论文名字]]`
     - 在"一句话总结"后插入经语义筛选的图片（方法/架构图优先，其次关键结果图）
     - 在"详细报告"字段显示 wikilink 关联
   - **总结图片规则**：从前3篇候选论文中选择 2-3 张图片插入（优先方法/架构图与关键结果图；可选1张定性/消融图）
   - **其余论文展示**：其余论文只保留文本信息；如无通过语义验证的图片，不显示图片占位
   - **关键词自动链接**（重要！）：
     - 在生成笔记后，扫描文本中的关键词
     - 使用 `existing_notes_index.json` 进行匹配
     - 将关键词替换为 wikilink，如 `BLIP` → `[[BLIP]]`
     - 保留已有 wikilink 不被修改
     - 不替换代码块中的内容

6. **对前三篇论文执行深度分析**
   ```bash
   # 对每篇前三论文执行以下操作

   # 步骤1：检查论文是否已有笔记
   # 在 vibe_research/20_Research/Papers/ 目录中搜索
   # - 按论文ID搜索（如 2602.23351）
   # - 按论文标题搜索（模糊匹配）
   # - 按论文标题关键词搜索（如 "Pragmatics", "Reporting Bias"）

   # 步骤2：根据检查结果决定处理方式
   if 已有笔记:
       # 不生成新的详细报告
       # 使用已有的笔记路径
       # 只提取图片（如果没有图片的话）
   else:
       # 提取候选图片（后续做语义筛选）
       /extract-paper-images [论文ID]

       # 生成详细分析报告
       /paper-analyze [论文ID]
   ```
   - **如果已有笔记**：
     - 不重复生成详细报告
     - 使用已有笔记路径作为 wikilink
     - 检查是否需要提取图片（如果没有 images 目录或 images 目录为空）
     - 在推荐笔记的"详细报告"字段引用已有笔记
   - **如果没有笔记**：
     - 提取候选图片并执行语义筛选后保存到 vault
     - 生成详细的论文分析报告
     - 在推荐笔记中添加图片和详细报告链接

## 临时文件清理

- 搜索过程产生的临时 XML 和 JSON 文件可以清理
- 推荐笔记已保存到 vault 后，临时文件不再需要

## 依赖项

- Python 3.x（用于运行搜索和筛选脚本）
- PyYAML（用于读取研究兴趣配置文件）
- 网络连接（访问 arXiv API）
- `vibe_research/20_Research/Papers/` 目录（用于扫描现有笔记和保存详细报告）
- `extract-paper-images` skill（用于提取论文图片）
- `paper-analyze` skill（用于生成详细报告）

## 脚本说明

### paper-search/scripts/search_arxiv.py

位于 `../paper-search/scripts/search_arxiv.py`，功能包括：

1. **搜索外部论文**：获取最近论文与高热度论文
2. **解析元数据**：提取论文信息（ID、标题、作者、摘要等）
3. **筛选和打分**：根据研究兴趣配置计算综合推荐分
4. **搜索前排重**：结合 `existing_notes_index.json` 排除已存在论文
5. **输出 JSON**：保存候选结果到 `paper_search_candidates.json`

### paper-search/scripts/enrich_paper_links.py

位于 `../paper-search/scripts/enrich_paper_links.py`，功能包括：

1. **读取候选池**：读取 `paper_search_candidates.json`
2. **补齐外链**：按 arXiv 页面、DOI 页面、Semantic Scholar 等来源补 repo / project / code / demo 链接
3. **输出增强 JSON**：保存结果到 `paper_search_candidates_enriched.json`
4. **保留兼容性**：不破坏原有 `candidates` 结构，仅追加 `link_enrichment` 与 `automation_links`

### scan_existing_notes.py

位于 `scripts/scan_existing_notes.py`，功能包括：

1. **扫描笔记目录**：扫描 `vibe_research/20_Research/Papers/` 下所有 `.md` 文件
2. **提取笔记信息**：
   - 文件路径
   - 文件名
   - frontmatter 中的 title 字段
   - tags 字段
3. **构建索引**：创建关键词到笔记路径的映射表
4. **输出 JSON**：保存索引到 `existing_notes_index.json`

**使用方法**：
```bash
cd "$SKILL_DIR"
uv run python scripts/scan_existing_notes.py \
  --vault "$OBSIDIAN_VAULT_PATH" \
  --output existing_notes_index.json
```

**输出格式**：
```json
{
  "notes": [
    {
      "path": "vibe_research/20_Research/Papers/多模态技术/BLIP_Bootstrapping-Language-Image-Pre-training.md",
      "filename": "BLIP_Bootstrapping-Language-Image-Pre-training.md",
      "title": "BLIP: Bootstrapping Language-Image Pre-training for Unified Vision-Language Understanding and Generation",
      "title_keywords": ["BLIP", "Bootstrapping", "Language-Image", "Pre-training", "Unified", "Vision-Language", "Understanding", "Generation"],
      "tags": ["Vision-Language-Pre-training", "Multimodal-Encoder-Decoder", "Bootstrapping", "Image-Captioning", "Image-Text-Retrieval", "VQA"]
    }
  ],
  "keyword_to_notes": {
    "blip": ["vibe_research/20_Research/Papers/多模态技术/BLIP_Bootstrapping-Language-Image-Pre-training.md"],
    "bootstrapping": ["vibe_research/20_Research/Papers/多模态技术/BLIP_Bootstrapping-Language-Image-Pre-training.md"],
    "vision-language": ["vibe_research/20_Research/Papers/多模态技术/BLIP_Bootstrapping-Language-Image-Pre-training.md"]
  }
}
```

### link_keywords.py

位于 `scripts/link_keywords.py`，功能包括：

1. **读取文本**：读取需要处理的文本内容
2. **读取笔记索引**：从 `existing_notes_index.json` 加载笔记映射
3. **替换关键词**：在文本中查找关键词，替换为wikilink
   - 不替换已存在的 wikilink（如 `[[BLIP]]`）
   - 不替换代码块中的内容
   - 匹配规则：
     - 优先匹配完整的标题关键词
     - 其次匹配 tags 中的关键词
     - 匹配时忽略大小写
     - 过滤通用词（and, for, model, learning 等）
     - 跳过 frontmatter 和标题行
4. **输出结果**：输出处理后的文本

**使用方法**：
```bash
# 首先切换到 skill 目录，然后执行脚本
cd "$SKILL_DIR"
uv run python scripts/link_keywords.py \
  --index existing_notes_index.json \
  --input "input.txt" \
  --output "output.txt"
```

**匹配示例**：
```
原始文本：
"这篇论文使用了BLIP和CLIP作为基线方法。"

处理后：
"这篇论文使用了[[BLIP]]和[[CLIP]]作为基线方法。"
```

**使用方法**：
```bash
# 步骤1：扫描现有笔记
cd "$SKILL_DIR"
uv run python scripts/scan_existing_notes.py \
  --vault "$OBSIDIAN_VAULT_PATH" \
  --output existing_notes_index.json

# 步骤2：生成推荐笔记（正常流程）
# ... 使用 search_arxiv.py 搜索论文 ...

# 步骤3：链接关键词（新增步骤）
uv run python scripts/link_keywords.py \
  --index existing_notes_index.json \
  --input "vibe_research/10_Daily/YYYY-MM-DD${NOTE_SUFFIX}.md" \
  --output "vibe_research/10_Daily/YYYY-MM-DD${NOTE_SUFFIX}.md"
```

**关键特性**：
- **智能匹配**：忽略大小写匹配中文环境
- **保护已有链接**：不替换已存在的wikilink
- **避免代码污染**：不替换代码块和行内代码中的内容
- **路径编码**：使用UTF-8编码确保中文路径正确
- **跳过敏感区域**：不处理 frontmatter、标题行、代码块

### 关键词链接实现（新增！）

**功能概述**：
在生成每日推荐笔记后，自动扫描现有笔记，将文本中的关键词（如BLIP、CLIP等）替换为wikilink（如[[BLIP]]）。

**实现流程**：
1. **扫描现有笔记**：扫描 `vibe_research/20_Research/Papers/` 目录
   - 提取笔记的frontmatter（title、tags）
   - 从标题中提取关键词（按分隔符和常见词缀）
   - 从tags中提取关键词（按连字符分割）
   - 构建关键词到笔记路径的映射表

2. **生成推荐笔记**：正常生成推荐笔记内容

3. **链接关键词**：处理生成的笔记
   - 找到文本中的关键词
   - 用wikilink替换找到的关键词
   - 保留已有wikilink
   - 不替换代码块和行内代码中的内容

**使用方法**：
```bash
# 步骤1：扫描现有笔记
cd "$SKILL_DIR"
uv run python scripts/scan_existing_notes.py \
  --vault "$OBSIDIAN_VAULT_PATH" \
  --output existing_notes_index.json

# 步骤2：生成推荐笔记（正常流程）
# ... 使用 search_arxiv.py 搜索论文 ...

# 步骤3：链接关键词（新增步骤）
uv run python scripts/link_keywords.py \
  --index existing_notes_index.json \
  --input "vibe_research/10_Daily/YYYY-MM-DD${NOTE_SUFFIX}.md" \
  --output "vibe_research/10_Daily/YYYY-MM-DD${NOTE_SUFFIX}.md"
```

**关键特性**：
- **智能匹配**：忽略大小写匹配中文环境
- **保护已有链接**：不替换已存在的wikilink
- **避免代码污染**：不替换代码块和行内代码中的内容
- **路径编码**：使用UTF-8编码确保中文路径正确
