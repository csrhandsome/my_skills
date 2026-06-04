---
name: start-my-day
description: 论文阅读工作流启动 - 生成今日论文推荐笔记 / Paper reading workflow starter - Generate daily paper recommendations
---

# Start My Day

生成今日论文推荐笔记：读取研究偏好，搜索和排重近期论文，输出轻量推荐列表，并把深度分析交给 `paper-analyze`。

## 职责边界

- **本 skill 负责**：偏好读取、论文搜索、已有笔记排重、推荐评分、daily 推荐笔记、关键词链接。
- **不负责深度分析**：不要在这里写完整方法解析、实验复盘、架构图解释或 MinerU 正文提取。
- **不负责提图**：图片提取交给 `extract-paper-images`；深度报告中的图片使用交给 `paper-analyze`。
- **交接方式**：推荐笔记中给每篇论文保留 `TODO: /paper-analyze [arXiv ID]`。

## 路径解析规则

```bash
START_MY_DAY_SKILL_DIR="[directory containing this SKILL.md]"
```

- 搜索：`$START_MY_DAY_SKILL_DIR/scripts/search_arxiv.py`
- 扫描：`$START_MY_DAY_SKILL_DIR/scripts/scan_existing_notes.py`
- Paperlist 更新：`$START_MY_DAY_SKILL_DIR/scripts/update_paperlist.py`
- 关键词链接：`$START_MY_DAY_SKILL_DIR/scripts/link_keywords.py`
- 禁止裸相对路径如 `python scripts/search_arxiv.py`
- 优先 `uv run python`，没有 `uv` 时退回 `python`
- 如果存在源码和安装两份副本，使用**本次实际加载**的副本；修改源码后需同步到安装副本

## 目录约定

start-my-day 的所有路径围绕 **用户提供的 preference 文件路径** 推导：

```
Vault/
  ├── Paper/                         ← 已精读论文（由 preference 向上级推导）
  └── vibe_research_XXX/
        ├── preference_XXX.md        ← 用户提供（必需）
        ├── YYYY-MM-DD_论文推荐.md    ← 历史推荐 + 本次输出
        └── Paperlist.md             ← 论文汇总表（脚本自动更新）
```

- **已精读论文**：`dirname(preference)/../Paper/`（由 `scan_existing_notes.py --preference` 自动推导）
- **已推荐论文**：`preference` 所在目录下的 `*_论文推荐.md` / `*_paper-recommendations.md`
- **输出位置**：所有产物均写入 preference 所在目录，不写 skill 目录或当前工作目录

## Preference 文件

启动时用户**必须**提供 preference 文件的绝对路径（`.md` 格式）。Skill 不内置任何预设。

Preference 文件是 Obsidian 笔记，frontmatter 中包含结构化配置，正文为人类可读的研究偏好说明。最小 frontmatter 示例：

```yaml
---
language: "zh"
research_domains:
  domain_key:
    name: "领域显示名"
    priority: 1.0
    keywords:
      - "keyword 1"
    arxiv_categories:
      - "cs.XX"
---
```

- `language`：`zh` / `en`
- `research_domains`：至少 1 个领域，每个必须有 `name`、`keywords`、`arxiv_categories`
- `arxiv_categories` 不能为空
- 文件不存在时，先询问用户研究方向再创建结构化 `.md` 文件，正文写自由文本说明，不写自由文本代替 frontmatter

## 执行流程

下面按**时间顺序**描述 start-my-day 的完整执行步骤。中间 JSON 文件放在 `/tmp/start_my_day_YYYYMMDD/`。

### 阶段 1：获取路径

1. 若用户未提供 preference 绝对路径 → 询问。文件不存在则先创建。
2. 从 preference 读 `language`，推导输出路径：
   - `DAILY_DIR = dirname(PREFERENCE_FILE)`
   - 中文：`{DAILY_DIR}/YYYY-MM-DD_论文推荐.md`
   - 英文：`{DAILY_DIR}/YYYY-MM-DD_paper-recommendations.md`
   - 同日已存在文件 → 追加或更新

### 阶段 2：脚本执行（搜论文）

执行顺序固定，不宜跳过任何一步：

```
scan_existing_notes.py --preference → existing_notes_index.json
                                      （扫描 ../Paper/ 和历史推荐，构建排重索引）

search_arxiv.py --config + --existing-index → arxiv_filtered.json + selected_papers.json
                                              （搜索 arXiv，排重，评分，Top-N）
```

### 阶段 3：生成推荐笔记

1. 读取 `arxiv_filtered.json`，用其中的 `top_papers` 写推荐内容（不要手工重新搜索）
2. 推荐笔记为轻量级别，结构见下方模板
3. 每篇论文标注 `TODO: /paper-analyze [arXiv ID]`
4. 写入步骤 1 推导的 daily note 路径

### 阶段 4：更新 Paperlist

执行 `update_paperlist.py`，从刚写好的 daily note 中提取论文：

```
update_paperlist.py --preference + --daily-note
  → 按 arXiv ID 排重：
    - 新论文 → 追加表格行
    - 已存在 → 追加推荐来源日期和评分
  → 更新 papers_count / read_count
  → 写入 {DAILY_DIR}/Paperlist.md
```

### 阶段 5（可选）：关键词链接

```
link_keywords.py --index + --input + --output → 加 [[内部链接]]，覆盖 daily note
```

### 阶段 6：交付

给用户摘要：生成路径、推荐数量、今日最高优先级论文、可运行的 `/paper-analyze` 列表。

## 推荐笔记结构

中文默认结构：

```markdown
# YYYY-MM-DD 论文推荐

## 今日概览
- 推荐总数：N
- 主要方向：[方向1, 方向2]
- 今日最值得读：[论文标题]

## 推荐论文

### [[Note_Filename|论文标题显示名]]
- **arXiv**：2401.00001
- **作者**：A, B, C
- **发布日期**：YYYY-MM-DD
- **领域/分类**：cs.AI, cs.LG
- **推荐评分**：X.X/10
- **推荐理由**：1-3 句，说明为什么值得读
- **摘要速览**：2-4 句，不做深度分析
- **匹配偏好**：[关键词/研究方向]
- **已有状态**：新论文 / 已有笔记 / 可能重复
- **下一步**：TODO: /paper-analyze 2401.00001
- **读后心得**：
  - [ ]待读
```

英文时使用对应英文标题，例如 `Today's Overview`、`Recommended Papers`、`Why Read It`、`Next Step`。

## 推荐内容要求

- 每篇论文只写轻量推荐，不展开完整方法、实验和局限。
- 推荐理由要具体：说明与用户偏好、近期趋势、潜在价值的关系。
- 对已有笔记或疑似重复论文，要明确标注，不要当成全新论文推荐。
- 前 3 篇可以稍微多写几句，但仍不替代 `paper-analyze`。
- 不要复制长摘要；摘要速览必须用自己的话概括。

## 排重规则

优先使用 `existing_notes_index.json`：

- arXiv ID 完全匹配：标记为已有。
- frontmatter `title` / 文件名 alias 高相似：标记为可能重复。
- 标题大小写、标点、空格差异不应造成重复推荐。
- 已有高质量笔记可以在推荐中列为“复习/更新候选”，但不要混入新论文榜单。

## 关键词链接

可选执行：

```bash
uv run python "$START_MY_DAY_SKILL_DIR/scripts/link_keywords.py" \
  --index "$RUN_DIR/existing_notes_index.json" \
  --input "$DAILY_NOTE" \
  --output "$RUN_DIR/linked_daily_note.md"

cp "$RUN_DIR/linked_daily_note.md" "$DAILY_NOTE"
```

要求：

- 只链接与论文主题相关的关键词。
- 避免链接普通词、过短词和标题自身。
- 不要破坏已有 wikilink、代码块、URL、frontmatter。

## 与其他 skills 的关系

- `paper-search`：共享搜索能力；`start-my-day/scripts/search_arxiv.py` 是对 `paper-search/scripts/search_arxiv.py` 的 wrapper。
- `paper-analyze`：深度分析单篇论文；用户选中某篇后再调用。
- `extract-paper-images`：只在深度分析或明确需要图片时调用；daily 推荐默认不提图。
- `conf-papers`：用于会议论文专项搜索，不替代 daily arXiv 推荐。

## 错误处理

- **缺少 vault**：要求用户设置 `$OBSIDIAN_VAULT_PATH` 或提供 vault 路径。
- **缺少 preference**：要求用户提供 preference 文件的绝对路径。如果文件不存在，询问研究方向并创建最小 YAML 配置。
- **依赖缺失**：优先提示或执行 `uv add arxiv pyyaml requests`。
- **搜索失败**：说明是 arXiv / Semantic Scholar / 网络 / 配置问题，并保留已有中间文件路径。
- **无推荐结果**：说明筛选条件可能过窄，建议放宽关键词、分类或关闭部分过滤。

## 交付前自检

- 已确认用户提供了 preference 文件的绝对路径并完成加载。
- 已扫描已有论文笔记并用于排重。
- 已执行搜索脚本并读取 JSON 输出。
- 推荐笔记已写入 preference 文件所在目录（`YYYY-MM-DD_论文推荐.md`）。
- 推荐笔记只做轻量推荐，没有混入 `paper-analyze` 的深度报告内容。
- `update_paperlist.py` 已执行，`Paperlist.md` 已更新（追加新论文、更新已有论文的推荐来源和得分）。
- 每篇推荐都有明确下一步：`/paper-analyze [arXiv ID]`。
