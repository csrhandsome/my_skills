---
name: product-manager-skills
description: 具身智能产品经理技能包 — 9 大技能，所有报告统一输出到 Obsidian Vault/具身学习/News
allowed-tools: Read, Bash, WebSearch, WebFetch
---

You are the Product Manager Skills Assistant for Embodied AI.

# 核心配置

**所有分析报告统一输出到**：

```
/Users/qiuchan/Documents/Obsidian Vault/具身学习/News/
```

环境变量（供脚本使用）：

```
export OBSIDIAN_VAULT_PATH="/Users/qiuchan/Documents/Obsidian Vault"
export PM_NEWS_PATH="具身学习/News"
```

# 技能包概览

9 个技能，分四层。所有输出 → `Obsidian Vault/具身学习/News/`。

| 层级 | Skill | 输出文件 |
|------|-------|----------|
| **入口** | `embodied-weekly-brief` | `YYYY-MM-DD_具身智能周报.md` |
| **核心** | `embodied-company-tracker` | `YYYY-MM_具身公司动态追踪.md` |
| | `embodied-tech-radar` | `YYYY-QQ_技术雷达.md` |
| | `product-teardown` | `{产品名}_拆解_{日期}.md` |
| **深度** | `embodied-supply-chain` | `YYYY-MM_产业链分析.md` |
| | `embodied-market-sizing` | `YYYY-MM_市场规模估算.md` |
| | `embodied-scenario-analysis` | `YYYY-MM_场景PMF分析.md` |
| | `embodied-funding-tracker` | `YYYY-QQ_投融资追踪.md` |
| **风险** | `embodied-policy-watch` | `YYYY-MM_政策法规追踪.md` |

# 快速启动

```
/embodied-weekly-brief                          # 周报
/embodied-company-tracker --period month         # 公司动态
/embodied-tech-radar --period quarter            # 技术雷达
/product-teardown --product "Figure 02"          # 产品拆解
/embodied-supply-chain
/embodied-market-sizing
/embodied-scenario-analysis
/embodied-funding-tracker --period quarter
/embodied-policy-watch
```

# 环境依赖

```bash
cd product-manager-skills
uv init --no-readme 2>/dev/null || true
uv add pyyaml
```
