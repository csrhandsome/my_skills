#!/usr/bin/env python3
"""具身智能政策法规追踪报告生成器"""

import argparse, json, sys
from datetime import datetime
from pathlib import Path
import yaml

def load_config(skill_dir: Path) -> dict:
    with open(skill_dir / "config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

RISK_ICONS = {"critical": "🔴", "high": "🟡", "medium": "🟢", "low": "⚪"}

def generate_markdown(config: dict, data: dict, skill_dir: Path) -> str:
    period = data.get("period", datetime.now().strftime("%Y-%m"))
    generated_at = data.get("generated_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
    regions = config.get("regions", [])
    categories = config.get("policy_categories", [])
    lines = []

    lines.append("---")
    lines.append(f'title: "具身智能政策法规追踪 - {period}"')
    lines.append(f'generated_at: "{generated_at}"')
    lines.append('tags: ["embodied-ai", "policy-watch", "pm-research"]')
    lines.append("---\n")
    lines.append(f"# 具身智能政策法规追踪 — {period}\n")

    # Summary
    highlights = data.get("highlights", [])
    if highlights:
        lines.append("## 本期关键政策变化\n")
        for h in highlights:
            risk = RISK_ICONS.get(h.get("risk_level", "low"), "")
            lines.append(f"- {risk} **{h.get('region', '')}** — {h.get('title', '')}: {h.get('summary', '')}")
        lines.append("")

    # Impact matrix
    impacts = data.get("high_impact_policies", [])
    if impacts:
        lines.append("## 高影响政策深度解读\n")
        for i, p in enumerate(impacts[:3], 1):
            lines.append(f"### {i}. {p.get('title', '')}\n")
            lines.append(f"- **区域**: {p.get('region', '')}")
            lines.append(f"- **类别**: {p.get('category', '')}")
            lines.append(f"- **风险等级**: {RISK_ICONS.get(p.get('risk_level', 'low'), '')} {p.get('risk_level', '')}")
            lines.append(f"- **时间窗口**: {p.get('time_window', '')}")
            lines.append(f"- **直接产品影响**: {p.get('direct_impact', '')}")
            lines.append(f"- **PM 应对建议**: {p.get('pm_response', '')}\n")

    # Regional tracking
    for region in regions:
        lines.append(f"## {region['name_cn']} ({region['name']})\n")
        lines.append(f"**监管机构**: {'; '.join(region.get('regulatory_bodies', []))}")
        lines.append("")
        lines.append("**关注事项**:")
        for w in region.get("watch_items", []):
            lines.append(f"- {w}")
        lines.append("")

        region_updates = data.get("region_updates", {}).get(region["name"], [])
        if region_updates:
            lines.append("**本期动态**:")
            for u in region_updates:
                lines.append(f"- {u}")
            lines.append("")

    # Category overview
    lines.append("---\n")
    lines.append("## 政策分类追踪\n")
    lines.append("| 类别 | 影响级别 | 建议追踪频率 |")
    lines.append("|------|----------|------------|")
    for cat in categories:
        imp = {"critical": "🔴 关键", "high": "🟡 高", "medium": "🟢 中", "low": "⚪ 低"}.get(cat.get("impact_level", ""), "")
        lines.append(f"| {cat['name_cn']} | {imp} | {cat.get('watch_frequency', '')} |")
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
