#!/usr/bin/env python3
"""具身智能场景PMF分析报告生成器"""

import argparse, json, sys
from datetime import datetime
from pathlib import Path
import yaml

def load_config(skill_dir: Path) -> dict:
    with open(skill_dir / "config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

PMF_STAGE_ICONS = {
    "exploratory": "🔍 探索期", "emerging": "🌱 萌芽期",
    "early-adopter": "🚀 早期采用", "early-deployment": "📈 早期部署", "scaling": "🏭 规模化"
}

def generate_markdown(config: dict, data: dict, skill_dir: Path) -> str:
    period = data.get("period", datetime.now().strftime("%Y-%m"))
    generated_at = data.get("generated_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
    scenarios = config.get("scenarios", [])
    dims = config.get("pmf_dimensions", [])
    lines = []

    lines.append("---")
    lines.append(f'title: "具身智能场景PMF分析 - {period}"')
    lines.append(f'generated_at: "{generated_at}"')
    lines.append('tags: ["embodied-ai", "scenario-analysis", "pmf", "pm-research"]')
    lines.append("---\n")
    lines.append(f"# 具身智能场景 PMF 分析 — {period}\n")

    # PMF Matrix
    lines.append("## PMF 矩阵\n")
    lines.append("| 场景 | " + " | ".join(d["label"] for d in dims) + " | PMF总分 | 阶段 |")
    lines.append("|------|" + "|".join(["------"] * len(dims)) + "|------|------|")
    for s in sorted(scenarios, key=lambda x: x.get("pmf_score", 0), reverse=True):
        scores = [f"{s.get(d['id'], 0):.1f}" for d in dims]
        stage = PMF_STAGE_ICONS.get(s.get("pmf_stage", ""), "")
        lines.append(f"| {s['name_cn']} | {' | '.join(scores)} | **{s['pmf_score']:.1f}** | {stage} |")
    lines.append("")

    # Scenario deep cards
    for s in sorted(scenarios, key=lambda x: x.get("pmf_score", 0), reverse=True):
        lines.append(f"## {s['name_cn']} — {PMF_STAGE_ICONS.get(s.get('pmf_stage', ''), '')}\n")
        lines.append(f"**分类**: {s.get('category', '')}")
        lines.append(f"**PMF 评分**: {s['pmf_score']:.1f}/5.0\n")

        lines.append("### 痛点")
        for p in s.get("pain_points", []):
            lines.append(f"- {p}")
        lines.append("")

        lines.append("### 关键需求")
        for r in s.get("key_requirements", []):
            lines.append(f"- {r}")
        lines.append("")

        if s.get("early_cases"):
            lines.append("### 早期案例")
            for c in s["early_cases"]:
                lines.append(f"- {c}")
            lines.append("")

        lines.append(f"**预期时间线**: {s.get('timeline', '未知')}\n")

    # PM recommendations
    recs = data.get("pm_recommendations", [])
    if recs:
        lines.append("---\n")
        lines.append("## PM 行动建议\n")
        lines.append("### 推荐进入策略\n")
        for r in recs:
            lines.append(f"- {r}")
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
