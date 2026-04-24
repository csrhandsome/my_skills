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

所有脚本路径必须相对于当前加载的 `start-my-day/SKILL.md` 所在目录解析，不要按当前工作目录猜。

```bash
START_MY_DAY_SKILL_DIR="[directory containing this SKILL.md]"
```

- 搜索脚本：`$START_MY_DAY_SKILL_DIR/scripts/search_arxiv.py`
- 扫描脚本：`$START_MY_DAY_SKILL_DIR/scripts/scan_existing_notes.py`
- 链接脚本：`$START_MY_DAY_SKILL_DIR/scripts/link_keywords.py`
- 禁止裸用：`python scripts/search_arxiv.py`、`uv run python scripts/scan_existing_notes.py`
- 如果同时存在源码副本 `vibe_research_skills/start-my-day/` 和安装副本 `/Users/three/.cc-switch/skills/start-my-day/`，使用本次实际加载的 skill 副本；修改源码后需要同步到安装副本才会生效。

## 配置与语言

Vault 来自 `$OBSIDIAN_VAULT_PATH`。如果当前 shell 未设置，可尝试读取 `~/.zshrc` / `~/.bash_profile`。

配置文件：`$OBSIDIAN_VAULT_PATH/vibe_research/research_preference/preference.md`

- 如果配置不存在，先询问用户研究方向，创建最小可用 `preference.md`，然后继续。
- `language: "zh"` 输出中文，`language: "en"` 输出英文；默认中文。
- 搜索分类优先从 `research_domains.*.arxiv_categories` 聚合；配置缺失或格式不合法时，脚本应报错，不要静默回退到无关默认领域。

### preference.md 最小格式

如果 `preference.md` 不存在，先问用户想看哪些研究方向，然后按下面结构创建；不要只写自由文本。

```yaml
language: "zh"
research_domains:
  robotics:
    name: "机器人与具身智能"
    priority: 1.0
    keywords:
      - "robot learning"
      - "embodied AI"
      - "vision-language-action"
    arxiv_categories:
      - "cs.RO"
      - "cs.AI"
      - "cs.LG"
  multimodal:
    name: "多模态技术"
    priority: 0.8
    keywords:
      - "multimodal"
      - "vision language model"
    arxiv_categories:
      - "cs.CV"
      - "cs.CL"
      - "cs.AI"
```

字段要求：

- `language`：`zh` 或 `en`。
- `research_domains`：至少 1 个领域。
- 每个领域必须有 `name`、`keywords`、`arxiv_categories`。
- `priority` 可选但推荐填写，用于排序和筛选权重。
- `arxiv_categories` 不能空；否则搜索脚本会报错。

## 输出路径约束

最终推荐文章必须写入 Obsidian vault 的 daily 目录，不要写在 skill 目录、临时目录或当前工作目录：

- 中文：`$OBSIDIAN_VAULT_PATH/vibe_research/10_Daily/YYYY-MM-DD_论文推荐.md`
- 英文：`$OBSIDIAN_VAULT_PATH/vibe_research/10_Daily/YYYY-MM-DD_paper-recommendations.md`
- 中间文件可放 `/tmp/start_my_day_YYYYMMDD/`，但最终用户要看的推荐笔记只能以上面路径为准。
- 如果同日文件已存在，优先更新同一个 daily 推荐文件，不要生成多个散落副本。

## 快速执行

建议在临时工作目录执行，避免把中间 JSON 放进 skill 目录：

```bash
START_MY_DAY_SKILL_DIR="[directory containing this SKILL.md]"
VAULT_ROOT="$OBSIDIAN_VAULT_PATH"
PREFERENCE_FILE="$VAULT_ROOT/vibe_research/research_preference/preference.md"
RUN_DIR="/tmp/start_my_day_$(date +%Y%m%d)"
mkdir -p "$RUN_DIR"
DAILY_DIR="$VAULT_ROOT/vibe_research/10_Daily"
mkdir -p "$DAILY_DIR"
if [ "$LANGUAGE" = "en" ]; then
  DAILY_NOTE="$DAILY_DIR/$(date +%Y-%m-%d)_paper-recommendations.md"
else
  DAILY_NOTE="$DAILY_DIR/$(date +%Y-%m-%d)_论文推荐.md"
fi

uv run python "$START_MY_DAY_SKILL_DIR/scripts/scan_existing_notes.py" \
  --vault "$VAULT_ROOT" \
  --output "$RUN_DIR/existing_notes_index.json"

uv run python "$START_MY_DAY_SKILL_DIR/scripts/search_arxiv.py" \
  --config "$PREFERENCE_FILE" \
  --existing-index "$RUN_DIR/existing_notes_index.json" \
  --output "$RUN_DIR/arxiv_filtered.json" \
  --selected-output "$RUN_DIR/selected_papers.json" \
  --max-results 200 \
  --top-n 10 \
  --output-format start-my-day
```

没有 `uv` 时才退回当前 Python：

```bash
python "$START_MY_DAY_SKILL_DIR/scripts/search_arxiv.py" --config "$PREFERENCE_FILE" --output "$RUN_DIR/arxiv_filtered.json"
```

必要依赖优先装到 vault 的 uv 环境：`uv add arxiv pyyaml requests`。

## 工作流程

1. **解析日期**：使用当前日期作为推荐笔记日期，可通过搜索脚本 `--target-date YYYY-MM-DD` 复现历史日期。
2. **读取偏好**：加载关键词、研究领域、arXiv 分类、语言设置。
3. **扫描已有笔记**：执行 `scan_existing_notes.py`，构建标题、arXiv ID、alias、关键词索引，用于排重和自动链接。
4. **搜索论文**：执行 `search_arxiv.py`，搜索最近 30 天和过去一年热门/高相关论文；默认 top 10。
5. **读取结果**：使用 `arxiv_filtered.json` 中的 `top_papers` / 推荐结果，不要重新手工搜索一套结果。
6. **生成 daily 推荐笔记**：写入 `$OBSIDIAN_VAULT_PATH/vibe_research/10_Daily/YYYY-MM-DD_论文推荐.md` 或英文后缀 `YYYY-MM-DD_paper-recommendations.md`。
7. **关键词链接**：可选执行 `link_keywords.py`，用已有笔记索引给推荐笔记自动加 `[[内部链接]]`。
8. **交付摘要**：告诉用户生成路径、推荐数量、最高优先级论文和下一步可运行的 `/paper-analyze`。

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
- **缺少 preference**：询问研究方向并创建最小配置，不要直接退出。
- **依赖缺失**：优先提示或执行 `uv add arxiv pyyaml requests`。
- **搜索失败**：说明是 arXiv / Semantic Scholar / 网络 / 配置问题，并保留已有中间文件路径。
- **无推荐结果**：说明筛选条件可能过窄，建议放宽关键词、分类或关闭部分过滤。

## 交付前自检

- 已读取或创建 preference。
- 已扫描已有论文笔记并用于排重。
- 已执行搜索脚本并读取 JSON 输出。
- daily 推荐笔记已写入 `vibe_research/10_Daily/`。
- 推荐笔记只做轻量推荐，没有混入 `paper-analyze` 的深度报告内容。
- 每篇推荐都有明确下一步：`/paper-analyze [arXiv ID]`。
