#!/usr/bin/env python3
"""具身智能产业链分析报告生成器"""

import argparse, json, sys
from datetime import datetime
from pathlib import Path
import yaml

def load_config(skill_dir: Path) -> dict:
    with open(skill_dir / "config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def generate_markdown(config: dict, data: dict, skill_dir: Path) -> str:
    period = data.get("period", datetime.now().strftime("%Y-%m"))
    generated_at = data.get("generated_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
    supply_chain = config.get("supply_chain", [])
    chain_analysis = config.get("chain_analysis", {})
    updates = data.get("tier_updates", {})
    lines = []
    lines.append("---")
    lines.append(f'title: "具身智能产业链分析 - {period}"')
    lines.append(f'generated_at: "{generated_at}"')
    lines.append('tags: ["embodied-ai", "supply-chain", "pm-research"]')
    lines.append("---\n")
    lines.append(f"# 具身智能产业链分析 — {period}\n")

    # Overview
    overview = data.get("overview", {})
    if overview:
        lines.append("## 概览\n")
        lines.append(f"- **分析周期**: {period}")
        for k, v in overview.items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")

    # Supplier matrix per tier
    for tier in supply_chain:
        if tier["tier_id"] == "midstream-integration":
            lines.append(f"## {tier['tier']}\n")
            lines.append(f"> {tier.get('note', '参见 company-tracker')}\n")
            continue

        lines.append(f"## {tier['tier']}\n")
        for seg in tier.get("segments", []):
            name = seg.get("name_cn", seg["name"])
            importance = seg.get("importance", "")
            imp_icon = {"critical": "🔴", "high": "🟡", "medium": "🟢", "emerging": "🆕"}.get(importance, "")
            lines.append(f"### {imp_icon} {name}\n")

            tier_updates_key = f"{tier['tier_id']}_{seg['name']}"
            seg_updates = updates.get(tier_updates_key, {})

            lines.append("**国际供应商**:")
            for s in seg.get("suppliers", {}).get("international", []):
                lines.append(f"- {s}")
            lines.append("")
            lines.append("**国内供应商**:")
            for s in seg.get("suppliers", {}).get("domestic", []):
                lines.append(f"- {s}")
            lines.append("")

            if seg.get("watch_signals"):
                lines.append("**关注信号**:")
                for w in seg["watch_signals"]:
                    lines.append(f"- {w}")
                lines.append("")

            if seg_updates:
                lines.append("**本期动态**:")
                for u in seg_updates:
                    lines.append(f"- {u}")
                lines.append("")

    # Bottleneck analysis
    lines.append("---\n")
    lines.append("## 卡脖子环节评估\n")
    bottlenecks = chain_analysis.get("bottleneck_areas", [])
    if bottlenecks:
        for i, b in enumerate(bottlenecks, 1):
            lines.append(f"{i}. {b}")
    lines.append("")

    # Domestic substitution heatmap
    lines.append("## 国产替代进度\n")
    lines.append("| 领域 | 进度 | 差距 |")
    lines.append("|------|------|------|")
    for item in chain_analysis.get("domestic_substitution", []):
        lines.append(f"| {item['area']} | {item['progress']} | {item['gap']} |")
    lines.append("")

    # PM takeaways
    takeaways = data.get("pm_takeaways", [])
    if takeaways:
        lines.append("---\n")
        lines.append("## 产品经理启示\n")
        for t in takeaways:
            lines.append(f"- {t}")
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
