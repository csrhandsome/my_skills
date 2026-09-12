---
name: pm-weekly-report
description: 把用户粘贴的本周工作表先归纳成「这周已做 + 下周待做」，再自动调用 embodied-weekly-brief 生成行业周报，并按当前工作做关联后合成一篇 Obsidian 笔记。用于工作周报、本周总结、Murmur 周报、写周报。不要爬招聘网站，不要读源工作文档，不要改 Base。
---

# 个人工作周报

用户每周把工作表粘进对话。必须按这个顺序做，不要先写行业、再补工作：

1. 先归纳**我的工作**
2. 再**自动调用** `embodied-weekly-brief` 生成行业周报（同一周）
3. 最后把行业信号和我正在做的工作结合起来，写成一篇 Obsidian 笔记

不读工作内容源文档，不编造表里没有的事实。

- 工作格式：[references/weekly-format.md](references/weekly-format.md)
- 工作写作：[references/writing-policy.md](references/writing-policy.md)
- 行业如何挂钩工作：[references/work-industry-bridge.md](references/work-industry-bridge.md)
- 企微（可选）：[references/wecom-ops.md](references/wecom-ops.md)

# 输入

用户会贴一张表，列是周一到周五 + 下周待做，行是：

- **接收工作**：本周接到或推进中的事项
- **完成工作**：本周已完成及结果

缺表就停，让用户粘贴。不要用 `wecom-cli` 去读工作内容源文档。

# 工作流

## 1. 先写我的工作

读 `config.yaml`，从表头解析周次（如 `周一（9.7）` → `2026-09-07 ~ 09-11`）。年份用对话日期。

拆出接收、完成、下周待做。完成项只进「这周已做」；未完成与下周待做去重后只进「下周待做」。按 [weekly-format.md](references/weekly-format.md) 写出这两段，并抽出本周工作焦点（项目/主题列表），供下一步使用。

先在对话里贴出「这周已做 / 下周待做」，再进入行业周报。不要跳过这一步。

## 2. 自动调用行业周报

**必须**先阅读并执行 `../embodied-weekly-brief/SKILL.md`，不要在本 skill 里重写检索逻辑。

调用时传入：

- 同一 `week_range`
- 上一步的工作焦点（如数据平台、数据集、自动化标注、Tidel AI、设备管理）

`embodied-weekly-brief` 仍按自己的流程出完整行业周报，且必须带九镜扫描（公司追踪/洞察、技术雷达、拆解信号、产业链、市场、场景、投融资、政策）。完整稿写到它自己的输出路径：`$OBSIDIAN_VAULT_PATH/具身学习/News/{周五}_具身智能周报.md`；没有 vault 就写到那个 skill 的 `outputs/`。

## 3. 结合我的工作

按 [work-industry-bridge.md](references/work-industry-bridge.md)，从行业周报里挑和本周焦点真正相关的信号，写「和我工作的关系」。对不上的行业新闻留在「行业动态」，不要硬凑。

## 4. 合成一篇笔记

结构见 [weekly-format.md](references/weekly-format.md)：`这周已做` → `下周待做` → `行业动态` → `和我工作的关系`。

「行业动态」用行业周报的浓缩（头条 + 与工作相关的融资/技术/产品），文末 wikilink 完整行业稿。不要把行业全文再复制进这篇。

先在对话里贴出合成稿，再写入 Obsidian。`$OBSIDIAN_VAULT_PATH` 未设置就问路径，或先写到本 skill 的 `outputs/`。

仅当用户明确要求同步企微时，再按 [wecom-ops.md](references/wecom-ops.md) 写入归档表。

# 写入 Obsidian

```bash
OUTPUT_DIR="$OBSIDIAN_VAULT_PATH/工作/周报"
mkdir -p "$OUTPUT_DIR"
OUTPUT_PATH="$OUTPUT_DIR/{周五日期}_周报.md"
```

文件名用当周周五，例如 `2026-09-11_周报.md`。同一周重跑覆盖该文件。

# 禁止

- 不读、不改工作内容源文档
- 不跳过 `embodied-weekly-brief` 自己去搜行业新闻（除非用户明确说不要行业）
- 不把凭证、Bot ID、userid 写进回复或仓库
- 表内文档链接要关联到对应条目，不要丢链接，也不要编链接
