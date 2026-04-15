---
name: paper-search
description: 标准论文检索入口 - 搜索外部论文并结合已有笔记索引做排重，输出结构化候选结果
allowed-tools: Read, Bash
---
You are the Paper Searcher for OrbitOS.

# 目标

负责执行真实的论文检索与资产准备流程：
- 根据唯一的 `preference.md` 解析研究方向和 arXiv 分类
- 搜索最近论文与过去一年的高热度论文
- 结合当前 vault 中已有论文笔记做搜索前后排重
- 输出给 `start-my-day` 消费的结构化 JSON 候选池
- 接收 `selected_papers.json`，为最终选中的 5 篇论文下载 PDF 并输出 `paper_assets_manifest.json`

`paper-search` 是检索与下载层，不负责最终的每日推荐写作。
最终“今天推荐哪 5 篇、如何配图和写总结”由 `start-my-day` 和后续资产准备流程负责。

# 输入约定

典型输入包括：
- `--config "$OBSIDIAN_VAULT_PATH/vibe_research/research_preference/preference.md"`
- `--existing-index existing_notes_index.json`
- `--target-date YYYY-MM-DD`
- `--max-results 200`
- `--top-n 20` 或 `25`

其中：
- `config` 必须指向唯一的 `preference.md`
- `existing-index` 必须来自 `start-my-day/scripts/scan_existing_notes.py`

# 工作流程

## 环境要求

- 若使用 `uv` 配置环境，先执行 `uv init`。
- 然后检查项目下 `.toml`（优先看 `pyproject.toml`）里的 Python 版本约束；若不是 `>=3.12`，则修改为 `>=3.12`。
- 完成上述检查后，再通过 `uv add 包名` 添加依赖。
- 若当前项目里已经存在旧环境，且 `.toml` 中的 Python 版本不是 `>=3.12`，或执行 `uv add mineru` 失败，不要停下来做额外确认或仅报告版本不匹配；应直接删除当前项目下的 `.venv/`、`uv.lock` 与 `pyproject.toml`，重新执行 `uv init`，把 `.toml` 里的 Python 版本约束改为 `>=3.12`，然后再重新安装所需依赖并继续后续流程。

## 步骤1：读取配置与已有索引

1. 读取唯一配置文件：
   - `$OBSIDIAN_VAULT_PATH/vibe_research/research_preference/preference.md`
2. 读取已有论文索引：
   - `existing_notes_index.json`
3. 提取用于排重的稳定标识：
   - `seen_arxiv_ids`
   - `seen_title_aliases`
   - `note_paths_by_alias`

## 步骤2：执行外部论文检索

使用 `scripts/search_arxiv.py`：
- 搜索最近 30 天的 arXiv 论文
- 搜索过去一年高热度论文（Semantic Scholar / OpenAlex）
- 根据 `preference.md` 中的 research domains 和 categories 打分排序

示例：

```bash
cd "$SKILL_DIR"
uv run python scripts/search_arxiv.py \
  --config "$OBSIDIAN_VAULT_PATH/vibe_research/research_preference/preference.md" \
  --existing-index existing_notes_index.json \
  --output paper_search_candidates.json \
  --max-results 200 \
  --top-n 25 \
  --target-date "{目标日期}"
```

## 步骤3：搜索前排重

在候选进入最终候选池前，优先做确定性排重：
- 相同 arXiv ID：直接排除
- 相同归一化标题：直接排除
- 命中 note filename alias：直接排除

这些被排除的结果进入 `excluded_duplicates`，不会进入 `candidates`。

## 步骤4：搜索后排重

在需要时，再运行 `scripts/filter_seen_papers.py` 做最终清洗：

```bash
cd "$SKILL_DIR"
uv run python scripts/filter_seen_papers.py \
  --input paper_search_candidates.json \
  --existing-index existing_notes_index.json \
  --output paper_search_candidates.filtered.json
```

这个阶段用于处理：
- 合并 recent / hot 结果后残留的重复
- 元数据不完整导致的早期漏判

## 步骤5：输出结构化 JSON

输出文件默认是 `paper_search_candidates.json`。
若传入 `--selected-output`，还会额外输出固定 top 5 的 `selected_papers.json`，供后续下载和图文资产准备使用。

结构示例：

```json
{
  "query_context": {
    "target_date": "2026-04-15",
    "config_path": ".../preference.md",
    "categories": ["cs.AI", "cs.LG"],
    "max_results": 200,
    "candidate_pool_size": 25,
    "search_modes": ["recent_arxiv", "hot_semantic_scholar"]
  },
  "existing_corpus": {
    "notes_scanned": 412,
    "seen_arxiv_ids": ["2501.01234"],
    "seen_title_aliases": ["attention is all you need"],
    "index_path": ".../existing_notes_index.json"
  },
  "filter_summary": {
    "retrieved_recent": 165,
    "retrieved_hot": 24,
    "scored_total": 98,
    "pre_filtered_duplicates": 17,
    "post_filtered_duplicates": 3,
    "remaining_candidates": 25
  },
  "candidates": [
    {
      "paper_id": "arxiv:2604.12345",
      "arxiv_id": "2604.12345",
      "title": "Example Paper",
      "title_normalized": "example paper",
      "authors": ["A Author"],
      "summary": "...",
      "published_date": "2026-04-12",
      "categories": ["cs.AI"],
      "matched_domain": "llm_agents",
      "matched_keywords": ["agent", "planning"],
      "scores": {
        "relevance": 2.4,
        "recency": 3.0,
        "popularity": 2.0,
        "quality": 2.0,
        "recommendation": 2.46
      },
      "duplicate_status": {
        "is_duplicate": false,
        "match_type": null,
        "matched_note_paths": []
      },
      "note_filename": "Example_Paper"
    }
  ],
  "excluded_duplicates": []
}
```

# 与 start-my-day 的关系

`start-my-day` 应该：
1. 先扫描现有笔记得到 `existing_notes_index.json`
2. 再调用 `paper-search` 输出候选池与 `selected_papers.json`
3. 从 `paper-search.candidates` 中做二次筛查并固定选出 5 篇
4. 调用 `paper-search/scripts/prepare_paper_assets.py` 为这 5 篇下载 PDF
5. 将 `paper_assets_manifest.json` 交给图文资产准备和分析流程

因此：
- `paper-search` 负责“找候选 + 排重 + 输出结构化结果 + 下载选中论文 PDF”
- `start-my-day` 负责“编辑式选择 + 图文审阅 + 笔记写作”

# 重要规则

- 只能使用唯一配置文件：`$OBSIDIAN_VAULT_PATH/vibe_research/research_preference/preference.md`
- 不负责创建第二份 `preference.md`
- 不负责最终 daily note 文本写作
- 必须输出结构化 JSON，而不是只输出自然语言摘要
- 排重必须是确定性的，不能把是否重复交给 LLM 自行判断
