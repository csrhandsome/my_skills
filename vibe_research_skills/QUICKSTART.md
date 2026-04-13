# 快速开始指南

这是使用 evil-read-arxiv 的三步快速设置指南。

## 第一步：安装依赖

在终端运行：

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

## 第二步：配置

### 2.1 设置环境变量

设置 `OBSIDIAN_VAULT_PATH` 环境变量，指向你的 Obsidian Vault 路径。所有脚本会自动读取此变量，无需手动修改脚本中的路径。

```bash
# Windows PowerShell（永久生效，设置后需重启终端）
[System.Environment]::SetEnvironmentVariable("OBSIDIAN_VAULT_PATH", "C:/Users/YourName/Documents/Obsidian Vault", "User")

# macOS/Linux（添加到 ~/.bashrc 或 ~/.zshrc）
echo 'export OBSIDIAN_VAULT_PATH="/Users/yourname/Documents/Obsidian Vault"' >> ~/.bashrc
source ~/.bashrc
```

### 2.1.1 Python 虚拟环境（推荐）

如果系统安装了 `uv`，优先在 Obsidian Vault 目录下初始化项目环境，后续所有 skill 用到的 Python 命令都通过 `uv run python ...` 在这个环境中运行：

```bash
cd "$OBSIDIAN_VAULT_PATH"
if command -v uv >/dev/null 2>&1; then
  [ -f pyproject.toml ] || uv init
  uv add -r "/path/to/evil-read-arxiv/requirements.txt"
fi
```

如果需要补额外依赖，统一使用 `uv add 包名`；如果系统没有 `uv`，再退回使用全局 `pip install -r requirements.txt`。

### 2.2 创建配置文件

```bash
cd evil-read-arxiv
cp config.example.yaml config.yaml
```

编辑 `config.yaml`，修改：

```yaml
# 将此路径改为你的 Obsidian Vault 路径
vault_path: "/path/to/your/obsidian/vault"

# 根据你的研究兴趣修改关键词
research_domains:
  "你的研究领域1":
    keywords:
      - "keyword1"
      - "keyword2"
```

### 2.3 将配置文件放入 Vault

```bash
# macOS/Linux
mkdir -p "$OBSIDIAN_VAULT_PATH/vibe_research/research_preference"
cp config.yaml "$OBSIDIAN_VAULT_PATH/vibe_research/research_preference/preference.md"

# Windows PowerShell
New-Item -ItemType Directory -Force "$env:OBSIDIAN_VAULT_PATH\vibe_research\research_preference" | Out-Null
Copy-Item config.yaml "$env:OBSIDIAN_VAULT_PATH\vibe_research\research_preference\preference.md"
```

### 2.4 将技能安装到 Claude Code

将 evil-read-arxiv 目录中的四个技能文件夹复制到你的 Claude Code skills 目录：

```bash
# macOS/Linux
cp -r evil-read-arxiv/start-my-day ~/.claude/skills/
cp -r evil-read-arxiv/paper-analyze ~/.claude/skills/
cp -r evil-read-arxiv/extract-paper-images ~/.claude/skills/
cp -r evil-read-arxiv/paper-search ~/.claude/skills/

# Windows PowerShell
Copy-Item -Recurse evil-read-arxiv\start-my-day $env:USERPROFILE\.claude\skills\
Copy-Item -Recurse evil-read-arxiv\paper-analyze $env:USERPROFILE\.claude\skills\
Copy-Item -Recurse evil-read-arxiv\extract-paper-images $env:USERPROFILE\.claude\skills\
Copy-Item -Recurse evil-read-arxiv\paper-search $env:USERPROFILE\.claude\skills\
```

## 第三步：创建 Obsidian 目录结构

在你的 Obsidian Vault 中创建以下目录：

```
你的Vault/
└── vibe_research/
    ├── 10_Daily/
    ├── 20_Research/
    │   ├── Papers/
    │   └── PaperGraph/
    └── research_preference/
        └── preference.md  # 第二步中已复制
```

## 开始使用

### 1. 打开 Claude Code

在你的 Obsidian Vault 目录中打开终端：

```bash
# 切换到你的 Obsidian Vault 目录
cd "$OBSIDIAN_VAULT_PATH"

# 启动 Claude Code
claude-code
```

### 2. 开始每日论文推荐

在 Claude Code 中输入：

```
start my day
```

### 3. 分析单篇论文

在 Claude Code 中输入：

```
paper-analyze 2602.12345
```

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

## 故障排除

### 问题："未指定 vault 路径" 或 "Papers directory not found"

**解决**：
1. 确认环境变量已设置：
   ```bash
   # Windows PowerShell
   echo $env:OBSIDIAN_VAULT_PATH

   # macOS/Linux
   echo $OBSIDIAN_VAULT_PATH
   ```
2. 如果为空，回到第二步设置环境变量
3. 确认目录结构已正确创建，尤其是 `vibe_research/20_Research/Papers/`

### 问题：论文图片提取失败

**解决**：
1. 如果系统安装了 `uv`，进入 Obsidian Vault 目录；如果还没有环境，先执行 `uv init`
2. 在该环境中安装 PyMuPDF：`uv add PyMuPDF`
3. 后续通过 `uv run python ...` 运行图片提取相关脚本
4. 如果没有 `uv`，再使用 `pip install PyMuPDF`
5. 检查 arXiv ID 格式是否正确（如 2602.12345）

### 问题：关键词自动链接不准确

**解决**：编辑 `start-my-day/scripts/link_keywords.py` 中的 `COMMON_WORDS` 集合，添加你不需要自动链接的词。

## 需要帮助？

- 查看 [README.md](README.md) 获取详细说明
- 提交 Issue 到 GitHub 仓库
