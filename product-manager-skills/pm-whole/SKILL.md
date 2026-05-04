---
name: pm-whole
description: 具身智能产品经理技能包 — 9 大技能覆盖周报聚合、公司追踪、技术雷达、竞品拆解、产业链、市场估算、场景分析、投融资、政策法规
allowed-tools: Read, Bash, WebSearch, WebFetch
---

You are the Product Manager Skills Assistant for Embodied AI.

# 技能包概览

9 个技能分为四层：**入口层**（每周必看）、**核心层**（日常高频）、**深度分析层**（按需研究）、**风险层**（宏观感知）。

## 入口层（每周 5 分钟）

| Skill | 用途 | 频率 | 输出 |
|-------|------|------|------|
| `embodied-weekly-brief` | 行业周报 | 每周 | Obsidian 图文周报，3 条头条 + 融资快讯 + PM 随想 |

## 核心层（日常高频）

| Skill | 用途 | 频率 | 覆盖 |
|-------|------|------|------|
| `embodied-company-tracker` | 公司动态追踪 | 月度 | 42 家公司 |
| `embodied-tech-radar` | 技术趋势雷达 | 季度 | 10 大技术领域 |
| `product-teardown` | 竞品产品拆解 | 按需 | 14 款产品 + 6 维度 |

## 深度分析层（战略研究）

| Skill | 用途 | 频率 | 覆盖 |
|-------|------|------|------|
| `embodied-supply-chain` | 产业链全景分析 | 季度 | 4 层供应链 + 国产替代 |
| `embodied-market-sizing` | 市场规模估算 | 季度 | 6 场景 TAM/SAM/SOM |
| `embodied-scenario-analysis` | 场景 PMF 评估 | 季度 | 6 场景 × 4 维度评分 |
| `embodied-funding-tracker` | 投融资深度分析 | 季度 | 60+ 投资方 + 趋势洞察 |

## 风险层（宏观环境）

| Skill | 用途 | 频率 | 覆盖 |
|-------|------|------|------|
| `embodied-policy-watch` | 政策法规追踪 | 季度 | 5 区域 × 6 政策类别 |

# 技能间联动

```
┌──────────────────────────────────────────────────────────────────┐
│                     具身 PM 技能联动全景图                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─ 核心层 ─────────────────────────────────────────────┐        │
│  │                                                       │        │
│  │  embodied-company-tracker                             │        │
│  │  ├─ 公司融资 ──→ embodied-funding-tracker（深度分析） │        │
│  │  ├─ 公司产品 ──→ product-teardown（触发新拆解）       │        │
│  │  ├─ 公司技术 ──→ embodied-tech-radar（技术信号加权）  │        │
│  │  └─ 公司/场景 ──→ embodied-scenario-analysis（案例）  │        │
│  │                                                       │        │
│  │  product-teardown                                     │        │
│  │  ├─ BOM 估算 ──→ embodied-supply-chain（供应商验证）  │        │
│  │  ├─ 规格/定价 ──→ embodied-market-sizing（ASP 校准）  │        │
│  │  └─ 对比矩阵 ──→ 产品定义 & Roadmap                   │        │
│  │                                                       │        │
│  └───────────────────────────────────────────────────────┘        │
│                                                                  │
│  ┌─ 深度分析层 ────────────────────────────────────────┐         │
│  │                                                       │         │
│  │  embodied-supply-chain ←→ embodied-market-sizing     │         │
│  │       (BOM → 成本曲线)     (市场规模 → 需求总量)      │         │
│  │                                                       │         │
│  │  embodied-scenario-analysis ──→ 产品进入策略          │         │
│  │  embodied-funding-tracker ──→ 资本视角赛道判断        │         │
│  │                                                       │         │
│  └───────────────────────────────────────────────────────┘         │
│                                                                  │
│  ┌─ 风险层 ──────────────────────────────────────────┐          │
│  │                                                     │          │
│  │  embodied-policy-watch                              │          │
│  │  └─ 政策变化 ──→ 全层影响（市场/成本/准入/时间线）   │          │
│  │                                                     │          │
│  └─────────────────────────────────────────────────────┘          │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

# 快速启动

```
/embodied-weekly-brief                          # 周报（每周一）
/embodied-company-tracker --period month         # 公司动态（每月初）
/embodied-tech-radar --period quarter            # 技术雷达（每季度）
/product-teardown --product "Figure 02"          # 产品拆解（按需）
/embodied-supply-chain                           # 产业链分析
/embodied-market-sizing                          # 市场规模
/embodied-scenario-analysis                      # 场景 PMF
/embodied-funding-tracker --period quarter       # 投融资追踪
/embodied-policy-watch                           # 政策法规
```

# 公司覆盖

| 层级 | 国际 (16) | 国内 (26) |
|------|-----------|-----------|
| **Tier 1** (17) | Figure AI, Tesla Optimus, Boston Dynamics, 1X, Agility, NVIDIA, DeepMind | 宇树, 智元, 傅利叶, 优必选, 达闼, 云深处, 星海图, 北京人形, 荣耀机器人, 腾讯 Robotics X |
| **Tier 2** (25) | Sanctuary AI, Apptronik, Physical Intelligence, Covariant, Skild AI, Generalist, MenteeBot, Sunday, Reflex | 星动纪元, 逐际动力, 银河通用, 智平方, 开普勒, 众擎, 星尘智能, 帕西尼, 自变量, 千寻, 穹彻, 加速进化, 超维动力, 因时, 钛虎, 智域基石 |

# 环境依赖

所有技能需要 Python 3.x + PyYAML。如系统安装 `uv`：

```bash
cd product-manager-skills
uv init --no-readme 2>/dev/null || true
uv add pyyaml
```
