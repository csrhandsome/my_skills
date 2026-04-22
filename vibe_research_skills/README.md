# 让你的 Obsidian 变成你的文献阅读器

> 这不是一个 Obsidian 插件。  
> 这是一套围绕 Obsidian Vault 组织的文献阅读工作流 skills，用来把“找论文、筛论文、读论文、拆图、写笔记、连旧笔记”变成一条连续流程。

很多人的 Obsidian 里已经有知识库，却没有真正的“阅读入口”。论文要么躺在浏览器标签页里，要么留在 PDF 阅读器里，要么变成一堆零散摘要，最后很难沉淀成可复用的研究资产。`vibe_research_skills` 的目标，就是把论文阅读过程直接写回你的 Vault，让 Obsidian 不只是记笔记的地方，而是你的文献阅读器、研究面板和长期记忆。

如果你想要的不是“再来一个论文收藏夹”，而是一套能持续把论文变成 Markdown 笔记、图片资产、双链关系和每日阅读入口的工作流，这个目录就是为这个场景准备的。

## 它解决的不是“存论文”，而是“读论文”

把 Obsidian 当文献阅读器，关键不在于能不能打开 PDF，而在于下面这些动作能不能连起来：

- 今天先读什么
- 最近有哪些新论文值得看
- 某个方向有哪些顶会文章不该漏掉
- 一篇论文的图、方法、实验、结论怎么快速拆出来
- 新论文和你过去写过的笔记之间怎么建立关系
- 读完之后，内容能不能直接变成你 Vault 里长期可搜索、可链接、可回顾的资产

`vibe_research_skills` 做的，就是把这些动作尽量自动化。

## 核心能力

- `start-my-day`
  每天生成一份论文推荐笔记，按你的研究兴趣从 arXiv 检索、筛选、评分、排重，给出当天的阅读入口。

- `paper-search`
  执行标准外部论文检索，并结合你 Vault 里已有论文笔记做确定性排重，输出结构化候选池。

- `paper-analyze`
  对单篇论文做深度分析，整理摘要、方法、实验、贡献、局限和研究价值，并生成可继续编辑的 Obsidian 笔记。

- `extract-paper-images`
  优先从 arXiv 源码包提取真正有用的论文图，而不是只从 PDF 里抠出 logo 或碎片图标。

- `conf-papers`
  面向顶会检索，支持 `computer` / `hci` 两套预设，覆盖 AI、CV、NLP 和 HCI 常见顶会。

- `auto-upgrade`
  把 `start-my-day` 当成可持续迭代的工作流来跑、复盘、修正和重跑，用于维护这套系统本身的稳定性。

## 为什么适合放进 Obsidian

- Markdown、图片和笔记都在本地，长期可控，不依赖某个网页产品继续存在。
- 双链、标签、图谱和搜索让“读过”这件事变成“能回忆、能关联、能复用”。
- 每日推荐、单篇精读和历史笔记天然可以放进同一个 Vault，不需要在多个工具之间来回切换。
- 论文不是一次性消费品。好的阅读系统应该把阅读结果持续沉淀，而不是只留下“我好像看过”。

一句话说，这套 skills 不是把 Obsidian 伪装成 PDF 阅读器，而是把它变成你的研究工作台。

## 推荐工作流

最自然的一条使用路径是：

1. 用 `start-my-day` 生成当天的论文推荐。
2. 从推荐里挑出真正要读的论文。
3. 用 `paper-analyze` 生成单篇深度笔记。
4. 需要图时，用 `extract-paper-images` 把关键图提到笔记旁边。
5. 想做方向性补充时，用 `conf-papers` 看某年某些顶会的代表性工作。
6. 新笔记写回 Vault 后，再和已有笔记自动或手动建立链接。

这样你的 Obsidian 就不是“读完之后记录一下”的地方，而是“从决定读什么开始”就已经参与进来的地方。

## 目录结构

```text
vibe_research_skills/
├── README.md
├── config.example.yaml
├── ccf_list.pdf
├── auto-upgrade/
├── conf-papers/
├── extract-paper-images/
├── paper-analyze/
├── paper-search/
└── start-my-day/
```

各目录职责如下：

- `start-my-day/`
  每日论文推荐入口。

- `paper-search/`
  标准外部检索与排重。

- `paper-analyze/`
  单篇论文深度分析。

- `extract-paper-images/`
  论文图片提取与整理。

- `conf-papers/`
  顶会论文搜索推荐。

- `auto-upgrade/`
  用于迭代升级 `start-my-day` 的自检闭环。

- `config.example.yaml`
  研究兴趣配置模板。

## 你的 Vault 最终会长成什么样

推荐的 Obsidian 目录结构如下：

```text
YourVault/
└── vibe_research/
    ├── 10_Daily/
    │   └── YYYY-MM-DD论文推荐.md
    ├── 20_Research/
    │   ├── Papers/
    │   │   └── 研究方向/
    │   │       └── 论文标题.md
    │   │           └── images/
    │   └── PaperGraph/
    └── research_preference/
        └── preference.md
```

这个结构的意义很直接：

- `10_Daily/` 是“今天先读什么”的入口。
- `20_Research/Papers/` 是稳定的论文笔记归档区。
- `images/` 存放论文的关键图、结果图和方法图。
- `research_preference/preference.md` 定义你的研究方向、关键词和 arXiv 分类。

## 快速开始

### 1. 设置 Obsidian Vault 路径

推荐使用环境变量：

```bash
export OBSIDIAN_VAULT_PATH="/path/to/your/Obsidian Vault"
```

### 2. 初始化运行环境

这个仓库当前使用 `uv` / `pyproject.toml` 方案，建议优先用 `uv`：

```bash
cd "$OBSIDIAN_VAULT_PATH"
[ -f pyproject.toml ] || uv init --bare
uv add arxiv pyyaml requests
```

可选依赖：

- `semantic_scholar_api_key`
  不是必须，但能明显减少 Semantic Scholar 的限流问题。

- `mineru-open-api`
  只有当你需要完整提取图片、表格、公式等资源时才需要。

### 3. 写研究偏好配置

把 [config.example.yaml](./config.example.yaml) 改成你自己的版本，然后放到：

```text
$OBSIDIAN_VAULT_PATH/vibe_research/research_preference/preference.md
```

注意：虽然文件名叫 `preference.md`，内容实际按 YAML 结构书写。

最小示例：

```yaml
language: "zh"

research_domains:
  "Agents & Autonomous Systems":
    keywords:
      - "agent"
      - "multi-agent"
      - "tool use"
      - "planning"
    arxiv_categories:
      - "cs.AI"
      - "cs.CL"
      - "cs.MA"
    priority: 5
```

### 4. 在 Vault 中准备目录

```bash
mkdir -p "$OBSIDIAN_VAULT_PATH/vibe_research/10_Daily"
mkdir -p "$OBSIDIAN_VAULT_PATH/vibe_research/20_Research/Papers"
mkdir -p "$OBSIDIAN_VAULT_PATH/vibe_research/20_Research/PaperGraph"
mkdir -p "$OBSIDIAN_VAULT_PATH/vibe_research/research_preference"
```

### 5. 在支持 `SKILL.md` 的 agent 环境里调用

常见用法示例：

```text
start-my-day
paper-analyze 2402.12345
extract-paper-images 2402.12345
conf-papers computer 2025
conf-papers hci 2025 CHI,UIST
```

如果你更习惯自然语言，也可以直接表达意图，例如：

- “帮我开始今天的论文阅读”
- “分析这篇 arXiv 论文：2402.12345”
- “看看 2025 年 HCI 顶会里值得读的论文”

## 每个 skill 输出什么

### `start-my-day`

- 读取你的研究偏好
- 扫描已有笔记建立索引
- 搜索最近论文并做去重和评分
- 生成当天推荐笔记

典型输出：

- `vibe_research/10_Daily/YYYY-MM-DD论文推荐.md`

### `paper-search`

- 搜外部论文，不只搜本地
- 和已有笔记做确定性排重
- 输出结构化候选 JSON，方便下游继续处理

### `paper-analyze`

- 生成一篇论文的结构化精读笔记
- 总结问题、方法、实验、贡献和局限
- 把结果放进长期可编辑的笔记路径里

### `extract-paper-images`

- 优先从 arXiv 源码中提图
- 补充 PDF / MinerU 图像提取
- 把图放进论文笔记旁边的 `images/` 目录

### `conf-papers`

- 支持 `computer` / `hci` 预设
- 适合做年度回顾、方向补课和顶会扫读

## 一套更像“阅读系统”的使用心法

如果你已经在用 Zotero、浏览器书签或者各种论文网站收藏功能，这套东西最值得保留的不是“它也能搜论文”，而是它把阅读后的结果稳定写回到你的 Obsidian。

推荐把它理解成三层：

- 第 1 层：`start-my-day`
  决定今天读什么。

- 第 2 层：`paper-analyze` / `extract-paper-images`
  决定怎么读、读到什么程度。

- 第 3 层：Obsidian Vault
  决定这些阅读结果未来怎么被再次找到、关联和使用。

当这三层是连在一起的，你的 Obsidian 才真正像一个文献阅读器，而不是一个事后补记的仓库。

## 适合谁

- 想把论文阅读从“临时浏览”变成“长期积累”的研究者
- 已经在用 Obsidian，希望论文笔记也进入同一套知识系统的人
- 想让 agent 帮自己完成检索、筛选、初步分析和图像整理的人
- 需要按研究方向持续追踪 arXiv / 顶会论文的人

## 目前依赖

- Python `>=3.12`
- `arxiv`
- `pyyaml`
- `requests`

按场景可选：

- Semantic Scholar API Key
- MinerU Open API CLI

## 边界说明

- 这套东西不会替你判断“这篇论文值不值得做三个月”，但会显著减少你在检索、初筛、拆解和整理上的机械时间。
- 它不是 Obsidian 插件，没有在 Obsidian 内部加一个新面板；它的核心价值是把结果写回你的 Vault。
- 它也不是单纯的 PDF 管理器。重点不在于存 PDF，而在于生成和组织可复用的研究笔记。

## 一句话总结

如果说 PDF 阅读器解决的是“怎么看论文”，那 `vibe_research_skills` 试图解决的是另一件更麻烦的事：

**怎么让你读过的论文，真的留下来。**
