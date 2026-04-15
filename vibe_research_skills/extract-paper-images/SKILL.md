---
name: extract-images-and-text
description: 为论文提取图片与文字资产，优先从 arXiv 源码包获取真正的论文图，并整理全文文本
allowed-tools: Read, Write, Bash
---
You are the Paper Asset Preparer for OrbitOS.

# 目标
从已下载的论文 PDF / arXiv 源码中提取所有可用图片与文字资产，保存到`vibe_research/20_Research/Papers/[领域]/[论文标题]/`目录下，并输出 `prepared_paper_assets.json` 供 `start-my-day` 和 `paper-analyze` 使用。

**关键改进**：
- 不再把下载 PDF 作为本 skill 的主职责；PDF 由 `paper-search` 统一下载并写入 `paper_assets_manifest.json`
- 优先从 arXiv 源码包提取真正的论文图片（架构图、实验结果图等）
- 同时抽取全文文本、章节文本与 figure context，供后续图文联合审阅

# 工作流程

## 步骤1：读取资产清单

1. 输入应为 `paper_assets_manifest.json`
2. 逐篇读取：
   - `paper_id`
   - `paper_dir`
   - `pdf_path`
   - `images_dir`
   - `text_dir`

## 步骤2：提取图片（源码优先）

使用 `scripts/extract_images_and_text.py`：
- 优先下载 arXiv 源码包并查找 `pics/`、`figures/`、`fig/`、`images/`、`img/`
- 若源码中有 figure PDF，则调用 MinerU 提取/检测图片
- 若图片不足，再从已下载 PDF 中使用 MinerU 兜底提图
- 为每张图片标注粗粒度角色：`method`、`results`、`qualitative`、`ablation`、`noise`、`unknown`

## 步骤3：提取文字

- 从已下载的 PDF 中抽取全文文本
- 生成：
  - `text/full_text.md`
  - `text/sections.json`
  - `text/figure_context.json`
- 若可用，优先使用 MinerU 的 markdown 输出；否则退回到 PDF 文本提取

## 步骤4：输出统一资产

脚本输出：
- `images/`
- `images/index.md`
- `text/full_text.md`
- `text/sections.json`
- `text/figure_context.json`
- `prepared_paper_assets.json`

# 调用方式

```bash
uv run python "scripts/extract_images_and_text.py" \
  --manifest "paper_assets_manifest.json" \
  --output "prepared_paper_assets.json"
```

# 重要规则

- **下载职责属于 paper-search**：这里默认 PDF 已存在于 `paper_assets_manifest.json` 指定路径
- **优先源码图片**：源码包中的图片优先于 PDF 提取
- **同时输出图与文**：不能只提图，不提文本
- **为后续模型审阅服务**：输出必须能支持 `start-my-day` 先看图片及其对应文字，再决定是否配图
- **PDF 解析统一走 MinerU / 文本提取回退链**：保留当前源码优先 + MinerU 的优势
