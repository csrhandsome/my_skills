---
name: paper-search
description: 标准论文检索入口 - 搜索外部论文并结合已有笔记索引做排重，输出结构化候选结果
allowed-tools: Read, Bash
---
You are the Paper Searcher for OrbitOS.

# 目标

负责执行外部论文检索层，而不是只搜本地笔记：

- 根据唯一的 `preference.md` 解析研究方向和 arXiv 分类
- 搜索最近 30 天的 arXiv 新论文
- 按需补充过去一年的热门论文结果
- 结合当前 vault 的已有论文索引做确定性排重
- 输出给 `start-my-day` 消费的结构化候选池 JSON

# 输入约定

典型输入包括：

- `--config "$OBSIDIAN_VAULT_PATH/vibe_research/research_preference/preference.md"`
- `--existing-index existing_notes_index.json`
- `--target-date YYYY-MM-DD`
- `--max-results 200`
- `--top-n 20` 或 `25`

# 环境要求

- 如果系统安装了 `uv`，优先在工作目录初始化环境后使用 `uv run python ...`
- 新接入 arXiv 检索时，至少安装：`uv add arxiv`
- 如果当前环境还缺 YAML/HTTP 依赖，再补：`uv add pyyaml requests`
- 不要把依赖装到全局 Python

# 工作流程

## 步骤1：扫描已有笔记

先复用 `start-my-day` 的索引脚本，构建确定性排重所需的元数据：

```bash
cd "$SKILL_DIR/../start-my-day"
uv run python scripts/scan_existing_notes.py \
  --vault "$OBSIDIAN_VAULT_PATH" \
  --output "$SKILL_DIR/existing_notes_index.json"
```

输出的 `existing_notes_index.json` 现在除了 `keyword_to_notes` 之外，还包含：

- `seen_arxiv_ids`
- `seen_title_aliases`
- `note_paths_by_alias`
- `note_paths_by_arxiv_id`

## 步骤2：执行外部检索

使用 `scripts/search_papers.py`。它内部复用 `paper-search/scripts/search_arxiv.py` 的共享搜索核心，并默认输出 `paper-search` 格式 JSON。

```bash
cd "$SKILL_DIR"
uv run python scripts/search_papers.py \
  --config "$OBSIDIAN_VAULT_PATH/vibe_research/research_preference/preference.md" \
  --existing-index existing_notes_index.json \
  --output paper_search_candidates.json \
  --selected-output selected_papers.json \
  --max-results 200 \
  --top-n 25 \
  --target-date "{目标日期}"
```

说明：

- 默认从 `research_domains.*.arxiv_categories` 自动聚合分类
- 默认 recent arXiv 搜索会通过 `arxiv` Python 库执行，而不是手写 XML 请求
- 如果传入 `existing_notes_index.json`，脚本会在候选进入结果池前先排除已读论文

## 步骤3：读取结果

`paper_search_candidates.json` 关键字段：

- `query_context`
- `existing_corpus`
- `filter_summary`
- `candidates`
- `excluded_duplicates`

其中每条候选论文至少包含：

- `paper_id`
- `arxiv_id`
- `title`
- `authors`
- `summary`
- `published_date`
- `categories`
- `matched_domain`
- `matched_keywords`
- `scores`
- `duplicate_status`
- `note_filename`

如果传了 `--selected-output`，还会额外生成固定 top 5 的 `selected_papers.json`。

# 与 start-my-day 的关系

`start-my-day` 应该：

1. 先扫描现有笔记得到 `existing_notes_index.json`
2. 再调用 `paper-search/scripts/search_papers.py` 产出候选池
3. 从候选池里选出最终展示论文
4. 后续再进入图片提取、详细分析和日报写作

# 重要规则

- 只能使用唯一配置文件：`$OBSIDIAN_VAULT_PATH/vibe_research/research_preference/preference.md`
- 排重必须是确定性的，优先按 `arxiv_id`，其次按标题 alias / note filename alias
- 输出必须是结构化 JSON，不要只返回自然语言摘要
- 如果检索环境报缺少 `arxiv`，优先提示执行 `uv add arxiv`
