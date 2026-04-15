# evil-read-arxiv

> 邪修的论文阅读工作流 - 自动化论文搜索、推荐、分析和整理

## 语言 / Language

- [中文版](README.md)
- [English Version](README_en.md)

## 简介

这是一套 Claude Code 技能（Skills）集合，用于自动化研究论文的搜索、推荐、分析和整理工作流。通过调用 arXiv 和 Semantic Scholar API，每天为你推荐高质量论文，并自动生成详细笔记和关系图谱。

## 更新日志

| 日期 | 版本 | 更新内容 |
|------|------|----------|
| 2026-04-06 | v1.2 | `conf-papers` 新增 `computer` / `hci` 两套预设配置，支持 CHI/UIST/CSCW/IUI/UbiComp/DIS 等 HCI 顶会，并统一识别两种调用场景 |
| 2026-03-13 | v1.1 | 新增 `conf-papers` 技能：支持搜索 CVPR/ICCV/ECCV/ICLR/AAAI/NeurIPS/ICML 等顶级会议论文，基于 DBLP + Semantic Scholar 双数据源，独立配置文件，三维评分推荐 |
| 2026-03-01 | v1.0 | 初始版本：start-my-day 每日推荐、paper-analyze 论文分析、extract-paper-images 图片提取、paper-search 论文搜索 |

## 功能特点

### 1. start-my-day - 每日论文推荐
- 先扫描当前 vault 中已有论文，构建索引和排重依据
- 调用 `paper-search` 获取最近论文与高热度论文候选池
- 基于非重复候选做二次 LLM 策展，最终精选 3-5 篇
- 自动生成今日概览和推荐列表
- 前三篇论文自动生成详细分析和提取图片
- 自动链接关键词到已有笔记

### 2. paper-analyze - 论文深度分析
- 深度分析单篇论文
- 生成结构化笔记，包含：
  - 摘要翻译和要点提炼
  - 研究背景与动机
  - 方法概述和架构
  - 实验结果分析
  - 研究价值评估
  - 优势和局限性分析
  - 与相关论文对比
- 自动提取论文图片并插入笔记
- 更新知识图谱

### 3. extract-paper-images - 论文图片提取
- 优先从 arXiv 源码包提取高质量图片
- 支持从 PDF 提取图片作为备选
- 自动生成图片索引
- 保存到笔记目录的 images 子目录

### 4. paper-search - 标准论文检索入口
- 负责真实的外部论文搜索
- 根据 `preference.md` 解析研究方向和 arXiv 分类
- 搜索 recent arXiv + hot papers
- 结合已有笔记索引做搜索前后排重
- 输出结构化 JSON 候选池给 `start-my-day` 消费

### 5. conf-papers - 顶会论文搜索推荐
- 支持 `computer` / `hci` 两套预设
- `computer` 预设覆盖 CVPR/ICCV/ECCV/ICLR/AAAI/NeurIPS/ICML/MICCAI/ACL/EMNLP
- `hci` 预设覆盖 CHI/UIST/CSCW/IUI/UbiComp/DIS
- 基于 DBLP API 获取论文列表 + Semantic Scholar 补充引用和摘要
- 独立配置文件 `computer_conf_papers.yaml` / `hci_conf_papers.yaml`（关键词、排除词、默认年份/会议）
- 两阶段过滤：标题关键词轻量筛选 → S2 补充 → 三维评分（相关性 40% + 热门度 40% + 质量 20%）
- 前三篇论文自动生成详细分析（需有 arXiv ID）

## 安装

### 前置要求

1. **Claude Code CLI** - 需要安装并配置 Claude Code
2. **Python 3.8+** - 用于运行搜索和分析脚本
3. **依赖库**：
   ```bash
   # 如果系统安装了 uv，优先在 Obsidian Vault 下初始化项目并安装依赖
   cd "$OBSIDIAN_VAULT_PATH"
   if command -v uv >/dev/null 2>&1; then
     [ -f pyproject.toml ] || uv init
     uv add -r "/path/to/evil-read-arxiv/requirements.txt"
   else
     pip install -r requirements.txt
   fi
   ```

### 安装步骤

1. 将此仓库克隆或复制到你的 Claude Code skills 目录：
   ```bash
   # Windows PowerShell
   Copy-Item -Recurse evil-read-arxiv\start-my-day $env:USERPROFILE\.claude\skills\
   Copy-Item -Recurse evil-read-arxiv\paper-analyze $env:USERPROFILE\.claude\skills\
   Copy-Item -Recurse evil-read-arxiv\extract-paper-images $env:USERPROFILE\.claude\skills\
   Copy-Item -Recurse evil-read-arxiv\paper-search $env:USERPROFILE\.claude\skills\
   Copy-Item -Recurse evil-read-arxiv\conf-papers $env:USERPROFILE\.claude\skills\

   # macOS/Linux
   cp -r evil-read-arxiv/start-my-day ~/.claude/skills/
   cp -r evil-read-arxiv/paper-analyze ~/.claude/skills/
   cp -r evil-read-arxiv/extract-paper-images ~/.claude/skills/
   cp -r evil-read-arxiv/paper-search ~/.claude/skills/
   cp -r evil-read-arxiv/conf-papers ~/.claude/skills/
   ```

2. 配置环境变量和路径（见下文"配置"部分）

3. 重启 Claude Code CLI

## 配置

> **强烈建议**：先阅读 [QUICKSTART.md](QUICKSTART.md) 快速完成设置。

### 步骤1：设置环境变量（推荐）

所有脚本统一通过 `OBSIDIAN_VAULT_PATH` 环境变量读取 Obsidian Vault 路径，这是最简单的配置方式：

```bash
# Windows PowerShell（临时生效）
$env:OBSIDIAN_VAULT_PATH = "C:/Users/YourName/Documents/Obsidian Vault"

# Windows PowerShell（永久生效）
[System.Environment]::SetEnvironmentVariable("OBSIDIAN_VAULT_PATH", "C:/Users/YourName/Documents/Obsidian Vault", "User")

# macOS/Linux（添加到 ~/.bashrc 或 ~/.zshrc）
export OBSIDIAN_VAULT_PATH="/Users/yourname/Documents/Obsidian Vault"
```

设置环境变量后，**无需修改任何脚本中的路径**。

### Python 虚拟环境（推荐）

如果系统安装了 `uv`，建议始终在 Obsidian Vault 目录下初始化并使用 `uv` 项目环境，而不是安装到全局 Python：

```bash
cd "$OBSIDIAN_VAULT_PATH"
if command -v uv >/dev/null 2>&1; then
  [ -f pyproject.toml ] || uv init
  uv add -r "/path/to/evil-read-arxiv/requirements.txt"
fi
```

后续所有 `python scripts/...` 命令都应改为在这个环境中通过 `uv run python ...` 执行；如果需要新增依赖，统一使用 `uv add 包名`；如果系统没有 `uv`，再退回使用全局 `pip install -r requirements.txt`。

使用 `uv` 配置环境时，Python 版本必须大于 3.12。若当前仓库里的 Python 版本小于 3.12，且执行 `uv add mineru` 失败，则删除当前项目下的 `.venv/` 与 `uv.lock` 后，使用符合要求的 Python 重新创建虚拟环境并重新安装所需依赖。

### 步骤2：创建配置文件

复制 `config.example.yaml` 并修改：

```bash
cp config.example.yaml config.yaml
```

编辑 `config.yaml`，根据你的研究兴趣修改关键词：

```yaml
vault_path: "/path/to/your/obsidian/vault"

research_domains:
  "你的研究领域1":
    keywords:
      - "keyword1"
      - "keyword2"
    arxiv_categories:
      - "cs.AI"
      - "cs.LG"
```

然后将修改后的 `config.yaml` 复制到 Vault 中：
```bash
mkdir -p "$OBSIDIAN_VAULT_PATH/vibe_research/research_preference"
cp config.yaml "$OBSIDIAN_VAULT_PATH/vibe_research/research_preference/preference.md"
```

### 步骤3（可选）：通过 CLI 参数覆盖路径

如果不想设置环境变量，也可以在每次调用脚本时通过参数指定路径。

如果系统安装了 `uv`，这些命令也应通过 `uv run python ...` 在 `$OBSIDIAN_VAULT_PATH` 下已初始化的环境中执行；依赖新增统一使用 `uv add 包名`。使用 `uv` 配置环境时，Python 版本必须大于 3.12；若当前仓库里的 Python 版本小于 3.12，且执行 `uv add mineru` 失败，则删除当前项目下的 `.venv/` 与 `uv.lock` 后，使用符合要求的 Python 重新创建虚拟环境并重新安装所需依赖。

```bash
uv run python paper-search/scripts/search_arxiv.py --config "/your/path/vibe_research/research_preference/preference.md"
uv run python start-my-day/scripts/scan_existing_notes.py --vault "/your/obsidian/vault"
uv run python scripts/generate_note.py --vault "/your/obsidian/vault" --paper-id "2402.12345" --title "Paper Title" --authors "Author" --domain "大模型"
uv run python scripts/update_graph.py --vault "/your/obsidian/vault" --paper-id "2402.12345" --title "Paper Title" --domain "大模型"
```

### 路径格式说明

- **Windows**：可以使用正斜杠 `/` 或双反斜杠 `\\`
  - 正确：`C:/Users/Name/Documents/Vault`
  - 正确：`C:\\Users\\Name\\Documents\\Vault`
  - 错误：`C:\Users\Name\Documents\Vault`（单反斜杠在 Python 字符串中需要转义）

- **macOS/Linux**：使用正斜杠 `/`
  - 正确：`/Users/name/Documents/Vault`

### Obsidian 目录结构要求

你的 Obsidian Vault 需要包含以下目录结构：

```
你的Vault/
└── vibe_research/
    ├── 10_Daily/                    # 每日推荐笔记（自动创建）
    │   └── YYYY-MM-DD论文推荐.md
    ├── 20_Research/
    │   ├── Papers/                  # 论文详细笔记目录
    │   │   ├── 大模型/
    │   │   │   └── 论文标题.md
    │   │   │       └── images/      # 论文图片
    │   │   ├── 多模态技术/
    │   │   └── 智能体/
    │   └── PaperGraph/              # 知识图谱数据
    └── research_preference/
        └── preference.md            # 研究兴趣配置（复制 config.yaml 到这里）
```

## 使用方法

### 开始每天的论文推荐

在你的 Obsidian Vault 目录下打开终端，输入：

```bash
start my day
```

这会：
1. 搜索最近一个月和过去一年的高质量论文
2. 根据你的研究兴趣筛选和评分
3. 生成今日推荐笔记（保存到 `vibe_research/10_Daily/` 目录）
4. 对前三篇论文自动生成详细分析
5. 提取论文图片并插入笔记
6. 自动链接关键词到已有笔记

### 分析单篇论文

如果你想深入阅读某篇论文：

```bash
paper-analyze 2602.12345
# 或使用论文标题
paper-analyze "论文标题"
```

这会：
1. 下载论文 PDF
2. 提取图片
3. 生成详细的分析笔记
4. 更新知识图谱

### 提取论文图片

```bash
extract-paper-images 2602.12345
```

### 搜索已有论文

```bash
paper-search "关键词"
```

### 搜索顶会论文

```bash
conf-papers
# 使用 hci 预设
conf-papers hci
```

## 目录结构

```
evil-read-arxiv/
├── README.md                 # 本文件
├── QUICKSTART.md             # 快速开始指南
├── config.example.yaml       # 配置模板（需要复制并修改）
├── requirements.txt          # Python 依赖
├── start-my-day/             # 每日推荐技能
│   ├── SKILL.md              # 技能定义文件
│   └── scripts/
│       ├── search_arxiv.py   # arXiv/Semantic Scholar 搜索脚本
│       ├── scan_existing_notes.py  # 扫描现有笔记
│       └── link_keywords.py  # 关键词自动链接脚本
├── paper-analyze/            # 论文分析技能
│   ├── SKILL.md
│   └── scripts/
│       ├── generate_note.py  # 生成笔记模板
│       └── update_graph.py   # 更新知识图谱
├── extract-paper-images/     # 图片提取技能
│   ├── SKILL.md
│   └── scripts/
│       └── extract_images.py # 图片提取脚本
├── paper-search/             # 论文搜索技能
│   └── SKILL.md
├── conf-papers/              # 顶会论文搜索推荐技能
│   ├── SKILL.md              # 技能定义文件
│   ├── computer_conf_papers.yaml  # computer 预设配置
│   ├── hci_conf_papers.yaml       # hci 预设配置
│   └── scripts/
│       └── search_conf_papers.py  # DBLP搜索 + S2补充 + 评分
```

## 评分机制

论文推荐评分基于四个维度：

| 维度 | 权重 | 说明 |
|------|--------|------|
| 相关性 | 40% | 与研究兴趣的匹配程度 |
| 新近性 | 20% | 论文发布时间 |
| 热门度 | 30% | 引用数/影响力 |
| 质量 | 10% | 从摘要推断的方法质量 |

**评分细则**：
- **相关性**：标题关键词匹配（+0.5/个）、摘要关键词匹配（+0.3/个）、类别匹配（+1.0）
- **新近性**：30天内（+3）、30-90天（+2）、90-180天（+1）、180天以上（0）
- **热门度**：高影响力引用 > 100（+3）、50-100（+2）、< 50（+1）
- **质量**：多维度指标（强创新词 > 弱创新词 > 方法指标 > 量化结果 > 实验指标）

## 常用 arXiv 分类

| 分类代码 | 名称 | 说明 |
|----------|------|------|
| cs.AI | Artificial Intelligence | 人工智能 |
| cs.LG | Learning | 机器学习 |
| cs.CL | Computation and Language | 计算语言学/NLP |
| cs.CV | Computer Vision | 计算机视觉 |
| cs.MM | Multimedia | 多媒体 |
| cs.MA | Multiagent Systems | 多智能体系统 |
| cs.RO | Robotics | 机器人学 |

## 常见问题

### Q: 搜索没有结果？
A: 检查以下几点：
1. 确认网络连接正常
2. 检查配置文件中的关键词是否正确
3. 尝试扩大搜索的 arXiv 分类范围

### Q: 图片提取失败？
A:
1. 如果系统安装了 `uv`，进入 Obsidian Vault 目录；如果环境还不存在，先执行 `uv init`
2. 使用 `uv` 配置环境时，Python 版本必须大于 3.12
3. 在该环境中安装 MinerU：`uv add mineru`
4. 如果当前仓库里的 Python 版本小于 3.12，且执行 `uv add mineru` 失败，则删除当前项目下的 `.venv/` 与 `uv.lock` 后，使用符合要求的 Python 重新创建虚拟环境并重新安装所需依赖
5. 后续通过 `uv run python ...` 运行图片提取相关脚本
6. 如果没有 `uv`，再使用 `pip install mineru`
7. 检查 arXiv ID 格式是否正确（如 2602.12345）

### Q: 关键词自动链接不准确？
A: 可以在 `start-my-day/scripts/link_keywords.py` 中修改 `COMMON_WORDS` 集合，添加你不需要自动链接的词

### Q: "Papers directory not found" 错误？
A:
1. 检查 `OBSIDIAN_VAULT_PATH` 环境变量是否正确设置
2. 确认 Obsidian Vault 中的目录结构是否正确创建（`vibe_research/20_Research/Papers/`）

### Q: "未指定 vault 路径" 错误？
A: 设置 `OBSIDIAN_VAULT_PATH` 环境变量，或在调用脚本时通过 `--vault` / `--config` 参数指定路径。

## 高级配置

### 修改搜索的 arXiv 分类

在调用 `paper-search/scripts/search_arxiv.py` 时通过 `--categories` 参数指定：

```bash
uv run python paper-search/scripts/search_arxiv.py --categories "cs.AI,cs.LG,cs.CL,cs.CV"
```

### 修改每天推荐的论文数量

在调用 `paper-search/scripts/search_arxiv.py` 时通过 `--top-n` 参数指定：

```bash
uv run python paper-search/scripts/search_arxiv.py --top-n 15
```

### 修改评分权重

在 `paper-search/scripts/search_arxiv.py` 的 `calculate_recommendation_score` 函数中调整权重。

## 工作原理

```
用户输入 "start my day"
         ↓
    1. 加载研究配置
    2. 扫描现有笔记构建索引
         ↓
    3. 搜索 arXiv（最近30天）
    4. 搜索 Semantic Scholar（过去一年高热度）
         ↓
    5. 合并结果并去重
    6. 综合评分并排序
    7. 取前 N 篇
         ↓
    8. 生成今日推荐笔记
    9. 前三篇生成详细分析
    10. 自动链接关键词
```

## 贡献

欢迎提交 Issue 和 Pull Request！

如果你觉得这个项目对你有帮助，请给个 Star ⭐️ 支持一下！

[![Star History Chart](https://api.star-history.com/svg?repos=juliye2025/evil-read-arxiv&type=Date)](https://star-history.com/#juliye2025/evil-read-arxiv&Date)

## 许可证

MIT License

## 致谢

- [arXiv](https://arxiv.org/) - 开放获取的学术论文预印本平台
- [Semantic Scholar](https://www.semanticscholar.org/) - AI 驱动的学术研究平台
- [Claude Code](https://claude.ai/claude-code) - AI 辅助的代码和写作工具
- [Obsidian](https://obsidian.md/) - 强大的知识管理工具
