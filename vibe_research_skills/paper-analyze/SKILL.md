---
name: paper-analyze
description: 深度分析单篇论文，生成详细笔记和评估，图文并茂 / Deep analyze a single paper, generate detailed notes with images
allowed-tools: Read, Write, Bash
---

# Paper Analyzer

对单篇论文做深度分析，生成 Obsidian 论文笔记、daily 工作报告，并更新知识图谱。

## 硬性规则

1. **唯一入口**：写任何正文分析前，必须先真实执行 `scripts/run_paper_analyze.py`，不得手工跳过。
2. **路径解析**：所有脚本路径都按下面“路径解析规则”执行，不得按当前工作目录猜。
3. **失败处理**：入口脚本失败或关键产物缺失时，立即报错说明缺口；不得静默改成“只读 PDF / 只写摘要 / 手工整理”。
4. **信息源**：优先复用本地 PDF、已有笔记、`analysis_run.json`、MinerU markdown、`images/index.md`；允许联网补 arXiv 元数据、代码链接、related work，除非用户明确要求只用本地资料。
5. **图片要求**：最终分析必须结合 `images/index.md` 做图片筛选；若论文有方法/系统/架构图，至少保留 1 张对应图并解释信息流。

## 路径解析规则

本 skill 的脚本必须从**当前加载的 `paper-analyze/SKILL.md` 所在目录**解析，而不是从用户当前工作目录、vault 根目录或仓库根目录解析。

- 先定位当前加载的 skill 目录：`PAPER_ANALYZE_SKILL_DIR="[directory containing this SKILL.md]"`
- 执行入口：`uv run python "$PAPER_ANALYZE_SKILL_DIR/scripts/run_paper_analyze.py"`
- 执行辅助脚本：`python "$PAPER_ANALYZE_SKILL_DIR/scripts/generate_note.py"`
- 禁止裸相对路径：`python "scripts/run_paper_analyze.py"`、`uv run python "scripts/generate_note.py"`
- 如果同时存在源码副本 `vibe_research_skills/paper-analyze/` 和安装副本 `/Users/three/.cc-switch/skills/paper-analyze/`，使用**本次实际加载的 skill 副本**；不要自动切到另一个副本。
- 只有当用户明确说“修改源码 skill”时，才编辑 `vibe_research_skills/paper-analyze/`；要让运行生效时，还要同步到安装副本。

## 语言设置

从 `$OBSIDIAN_VAULT_PATH/vibe_research/research_preference/preference.md` 读取：

```bash
LANGUAGE=$(grep -E "^\s*language:" "$OBSIDIAN_VAULT_PATH/vibe_research/research_preference/preference.md" | awk '{print $2}' | tr -d '"')
[ -z "$LANGUAGE" ] && LANGUAGE="zh"
```

后续脚本传入 `--language "$LANGUAGE"`；默认中文。

## 目录约定

### Daily 工作目录

入口脚本会创建：`vibe_research/10_Daily/YYYY-MM-DD_论文标题`

- `daily_report_path`：最终分析报告工作副本，默认继续编辑这里。
- `daily_pdf_path`：仅当输入是本地 PDF 时复制 PDF。
- **daily 目录只保留 PDF 和报告，不存图片。**
- 报告图片用 Obsidian wikilink 引用 Research 目录图片，如：`![[filename.png|800]]`。

### Research 归档目录

长期资料保存在：`vibe_research/20_Research/Papers/[domain]/[paper_title]/`

- `note_path`：归档论文笔记。
- `images/`：由 `extract-paper-images` 生成的筛选/可引用图片和 `index.md`。
- `mineru/`：MinerU 完整原始归档。
  - `mineru/[pdf_stem].md`
  - `mineru/images/`

## 快速执行

当用户调用 `/paper-analyze [论文ID或PDF]`，先执行强制入口脚本：

```bash
PAPER_ANALYZE_SKILL_DIR="[directory containing this SKILL.md]"
uv run python "$PAPER_ANALYZE_SKILL_DIR/scripts/run_paper_analyze.py" \
  --paper-id "$PAPER_ID" \
  --pdf-path "$PDF_PATH" \
  --title "$TITLE" \
  --authors "$AUTHORS" \
  --domain "$DOMAIN" \
  --language "$LANGUAGE"
```

没有 `uv` 时才退回：

```bash
PAPER_ANALYZE_SKILL_DIR="[directory containing this SKILL.md]"
python "$PAPER_ANALYZE_SKILL_DIR/scripts/run_paper_analyze.py" \
  --paper-id "$PAPER_ID" \
  --pdf-path "$PDF_PATH" \
  --title "$TITLE" \
  --authors "$AUTHORS" \
  --domain "$DOMAIN" \
  --language "$LANGUAGE"
```

脚本成功后必须验证这些路径真实存在：

- `analysis_run.json`
- `markdown_path`
- `note_path`
- `index_path`
- `daily_dir`
- `daily_report_path`
- `daily_pdf_path`（仅本地 PDF 输入时）
- `mineru_archive_dir`
- `mineru_text_path`
- `mineru_images_dir`

## 入口脚本职责

`run_paper_analyze.py` 负责统一调度：

1. 解析 arXiv ID / 本地 PDF / 标题等输入。
2. 必要时下载 arXiv PDF。
3. 执行 `mineru-open-api extract` 获取完整 markdown。
4. 调用 `generate_note.py` 生成基础 Obsidian 笔记。
5. 调用 `extract-paper-images` 写入 Research 的 `images/` 和 `images/index.md`。
6. 调用 `update_graph.py` 更新知识图谱。
7. 创建 daily 工作目录并写入 `analysis_run.json`。
8. 归档 MinerU markdown 和原始图片到 Research 的 `mineru/`。

只有在入口脚本已经运行过、且需要排查失败原因时，才允许手动分步调试。

## 分析流程

入口脚本完成后，基于 `daily_report_path` 补写最终分析：

1. **识别论文**：确认标题、作者、arXiv ID、领域、发布时间、链接、代码/项目主页。
2. **摘要与问题**：翻译摘要，说明研究问题、背景动机、现有方法局限。
3. **方法解析**：讲清输入、输出、核心组件、端到端数据流；若有 training / inference、planner / executor、backbone / head 等阶段，分别解释。
4. **图片语义验证**：读取 `images/index.md`，判断候选图角色：方法/架构图、关键结果图、定性示例、消融图、噪声图；只插入能支撑关键结论的图片。
5. **实验分析**：总结数据集、基线、指标、主结果、消融、定性结果，并解释结果说明了什么。
6. **深度评价**：分析贡献、优势、局限、适用场景、失败条件和可复用点。
7. **相关工作**：对比 2-5 篇最相关论文，说明改进、继承、差异和路线定位。
8. **综合评分**：给出 0-10 总分与分项评分：创新性、技术质量、实验充分性、写作质量、实用性。

## 推荐笔记结构

中文默认使用以下结构；英文输出时翻译 section header：

```markdown
# [论文标题]

## 核心信息

## 摘要翻译

## 研究背景与动机

## 研究问题

## 方法概述

### 方法架构总览

### 架构图

### 模块拆解

### 训练与推理流程

## 实验结果

## 深度分析

## 与相关论文对比

## 技术路线定位

## 未来工作建议

## 我的综合评价

## 我的笔记

## 相关论文

## 外部资源
```

## Obsidian 与 Markdown 规范

- 图片引用用 wikilink：`![[actual_returned_image_filename.ext|800]]`。
- 图片文件名必须来自 `images/index.md` 或脚本实际输出，不要猜。
- 内部论文链接用 `[[论文标题]]`。
- 标签不能包含空格；空格用 `-` 替代。
- 行内公式用 `$...$`，块级公式用 `$$...$$` 且单独成行。
- 不要把长段原文整段复制进笔记；用自己的话总结。

## 图片写作要求

每张插入图片都要配一段解释：

- 这张图展示什么。
- 图中关键模块/坐标轴/流程是什么。
- 它支撑论文哪一个贡献或结论。
- 如果是架构图，必须说明输入、输出、箭头和中间表示如何流动。

如果没有可用原生架构图，可以用文本图或 Canvas 替代，并说明原因。

## 评分参考

- 9-10：突破性、新范式、实验强、影响大。
- 7-8：明确创新或有效组合，实验较充分。
- 5-6：增量贡献，实验或方法存在明显不足。
- 3-4：贡献弱、实验有限、论证不足。
- 1-2：主要是已知方法复述，质量差或无法验证。

评分需给出简短理由，避免只给数字。

## 错误处理

- **PDF / arXiv 获取失败**：说明具体错误和下一步需要的输入。
- **MinerU 失败**：停止流程，报告失败步骤；不要跳过正文提取。
- **图片索引缺失**：停止流程，说明 `images/index.md` 缺失。
- **图谱更新失败**：可继续完成报告，但必须注明图谱未更新。
- **路径不确定**：先定位当前加载的 `SKILL.md` 所在目录，不要猜当前工作目录。

## 交付前自检

最终回复用户前确认：

- 已执行入口脚本并验证关键产物。
- 正文写入 `daily_report_path`。
- 图片只保存在 Research 目录；daily 未复制 `images/`。
- 至少解释 1 张方法/架构相关图片（如果论文存在）。
- 方法、实验、局限、相关工作、评分均已补全。
- 如同步回 `note_path`，确保内容一致且链接可用。
