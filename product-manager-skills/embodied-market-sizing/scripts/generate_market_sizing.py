#!/usr/bin/env python3
"""具身智能市场规模估算报告生成器"""

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
    scenarios = config.get("scenarios", [])
    regions = config.get("regions", [])
    timeline = config.get("timeline", [])
    lines = []

    lines.append("---")
    lines.append(f'title: "具身智能市场规模估算 - {period}"')
    lines.append(f'generated_at: "{generated_at}"')
    lines.append('tags: ["embodied-ai", "market-sizing", "pm-research"]')
    lines.append("---\n")
    lines.append(f"# 具身智能市场规模估算 — {period}\n")

    # Methodology
    meth = config.get("methodology", {})
    lines.append("## 方法论\n")
    lines.append(f"- **TAM**: {meth.get('tam_definition', '')}")
    lines.append(f"- **SAM**: {meth.get('sam_definition', '')}")
    lines.append(f"- **SOM**: {meth.get('som_definition', '')}")
    lines.append(f"- **估算方法**: {meth.get('estimation_approach', '')}\n")

    # Summary table
    lines.append("## 市场概览\n")
    lines.append("| 场景 | 全球市场 | TAM 渗透% | SAM 渗透% | ASP | PMF阶段 |")
    lines.append("|------|----------|-----------|-----------|-----|---------|")
    for s in scenarios:
        lines.append(f"| {s['name_cn']} | {s['global_market_size']} | {s['robot_penetration_tam']}% | {s['robot_penetration_sam']}% | {s['unit_asp']} | {s.get('pmf_stage', '—')} |")
    lines.append("")

    # Timeline
    lines.append("## 出货量与收入预测\n")
    lines.append("| 年份 | 全球出货量 | 收入 | 阶段 |")
    lines.append("|------|-----------|------|------|")
    for t in timeline:
        lines.append(f"| {t['year']} | {t['global_units']} | {t['revenue']} | {t['stage']} |")
    lines.append("")

    # Regional breakdown
    lines.append("## 区域分析\n")
    lines.append("| 区域 | 权重 | 驱动力 |")
    lines.append("|------|------|--------|")
    for r in regions:
        drivers = "; ".join(r.get("drivers", [])[:2])
        lines.append(f"| {r['name']} | {r['weight']:.0%} | {drivers} |")
    lines.append("")

    # Key assumptions
    assumptions = data.get("assumptions", [])
    if assumptions:
        lines.append("## 关键假设与敏感性\n")
        for a in assumptions:
            lines.append(f"- {a}")
        lines.append("")

    # Scenario deep dive
    lines.append("## 场景市场规模分解\n")
    for s in scenarios:
        lines.append(f"### {s['name_cn']}\n")
        lines.append(f"- 全球基准市场: {s['global_market_size']}")
        lines.append(f"- TAM 渗透率: {s['robot_penetration_tam']}% → SAM: {s['robot_penetration_sam']}% → SOM(3年): {s['robot_penetration_som_3y']}%")
        lines.append(f"- ASP: {s['unit_asp']}")
        lines.append(f"- 驱动力: {'; '.join(s.get('key_drivers', []))}")
        lines.append(f"- 障碍: {'; '.join(s.get('key_barriers', []))}\n")

    # Data sources
    lines.append("## 数据源\n")
    for src in config.get("data_sources", []):
        lines.append(f"- {src}")
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
