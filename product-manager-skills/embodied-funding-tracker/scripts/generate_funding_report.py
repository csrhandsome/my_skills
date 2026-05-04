#!/usr/bin/env python3
"""具身智能投融资专项追踪报告生成器"""

import argparse, json, sys
from datetime import datetime
from pathlib import Path
import yaml

def load_config(skill_dir: Path) -> dict:
    with open(skill_dir / "config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def generate_markdown(config: dict, data: dict, skill_dir: Path) -> str:
    period = data.get("period", datetime.now().strftime("%Y-Q%q"))
    generated_at = data.get("generated_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
    lines = []

    lines.append("---")
    lines.append(f'title: "具身智能投融资追踪 - {period}"')
    lines.append(f'generated_at: "{generated_at}"')
    lines.append('tags: ["embodied-ai", "funding-tracker", "pm-research"]')
    lines.append("---\n")
    lines.append(f"# 具身智能投融资追踪 — {period}\n")

    # Overview stats
    stats = data.get("stats", {})
    lines.append("## 融资概览\n")
    lines.append(f"| 指标 | 本周期 | 上周期 | 变化 |")
    lines.append(f"|------|--------|--------|------|")
    for k in ["total_amount", "deal_count", "avg_deal_size", "largest_round"]:
        cur = stats.get(k, {}).get("current", "")
        prev = stats.get(k, {}).get("previous", "")
        chg = stats.get(k, {}).get("change", "")
        lines.append(f"| {k} | {cur} | {prev} | {chg} |")
    lines.append("")

    # Top deals
    deals = data.get("top_deals", [])
    if deals:
        lines.append("## 重点融资事件\n")
        for i, d in enumerate(deals[:5], 1):
            lines.append(f"### {i}. {d.get('company', '')} — {d.get('round', '')} {d.get('amount', '')}\n")
            lines.append(f"- **估值**: {d.get('valuation', '未公开')}")
            lines.append(f"- **投资方**: {d.get('investors', '')}")
            lines.append(f"- **资金用途**: {d.get('use_of_proceeds', '未公开')}")
            if d.get("significance"):
                lines.append(f"- **信号意义**: {d['significance']}")
            lines.append("")

    # Stage distribution
    stage_dist = data.get("stage_distribution", {})
    if stage_dist:
        lines.append("## 阶段分布\n")
        lines.append("| 阶段 | 金额 | 笔数 | 占比 |")
        lines.append("|------|------|------|------|")
        for stage, info in stage_dist.items():
            lines.append(f"| {stage} | {info.get('amount', '')} | {info.get('count', '')} | {info.get('share', '')} |")
        lines.append("")

    # Investor activity
    investors = data.get("investor_activity", [])
    if investors:
        lines.append("## 投资方动向\n")
        lines.append("### 最活跃投资方\n")
        for inv in investors[:10]:
            lines.append(f"- **{inv['name']}**: {inv.get('deals', '')} 笔, 聚焦 {inv.get('focus', '')}")
        lines.append("")

    # Trend insights
    insights = data.get("trend_insights", [])
    if insights:
        lines.append("## 趋势洞察\n")
        for i in insights:
            lines.append(f"- {i}")
        lines.append("")

    # M&A signals
    ma = data.get("ma_signals", [])
    if ma:
        lines.append("## 并购/整合信号\n")
        for m in ma:
            lines.append(f"- {m}")
        lines.append("")

    lines.append(f"*报告生成时间: {generated_at}*")
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill-dir", type=str, required=True)
    parser.add_argument("--input", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    args = parser.parse_args()
    skill_dir = Path(args.skill_dir)
    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)
    config = load_config(skill_dir)
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    markdown = generate_markdown(config, data, skill_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown)
    print(f"Report generated: {output_path}")

if __name__ == "__main__":
    main()
