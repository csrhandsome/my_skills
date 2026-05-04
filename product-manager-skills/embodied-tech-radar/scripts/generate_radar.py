#!/usr/bin/env python3
"""
具身智能技术趋势雷达报告生成器
读取 config.yaml 和技术信号数据，输出格式化 Markdown 雷达报告
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import yaml


def load_config(skill_dir: Path) -> dict:
    config_path = skill_dir / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


MATURITY_ORDER = {"research": 1, "emerging": 2, "productizing": 3, "scaling": 4}

MATURITY_LABELS = {
    "research": "🔬 研究阶段",
    "emerging": "🌱 新兴阶段",
    "productizing": "🚀 产品化阶段",
    "scaling": "📈 规模化阶段",
}

TREND_ICONS = {
    "accelerating": "⬆️ 加速上升",
    "stable": "➡️ 趋于稳定",
    "decelerating": "⬇️ 增速放缓",
}


def build_radar_quadrants(tech_areas: list) -> str:
    """生成文本版技术成熟度象限"""
    lines = []
    lines.append("```")
    lines.append("                        signal_strength →")
    lines.append("          low(1-2)        medium(3)        high(4-5)")
    lines.append("")
    lines.append("  scaling")
    lines.append("    ↑")
    lines.append("    |")
    for mat, label in [
        ("scaling", "  scaling  "),
        ("productizing", "  product."),
        ("emerging", "  emerging "),
        ("research", "  research "),
    ]:
        mat_techs = [t for t in tech_areas if t.get("maturity", "") == mat]
        row = label
        parts = []
        for strength_range in [(1, 2), (3, 3), (4, 5)]:
            lo, hi = strength_range
            cell_techs = [
                t["name_cn"][:6]
                for t in mat_techs
                if lo <= t.get("signal_strength", 0) <= hi
            ]
            parts.append(" | ".join(cell_techs) if cell_techs else "—")
        row += "  " + "  │  ".join(parts)
        lines.append(row)
    lines.append("```")
    return "\n".join(lines)


def generate_markdown(config: dict, data: dict, skill_dir: Path) -> str:
    period = data.get("period", "Unknown")
    generated_at = data.get("generated_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
    overall_trend = data.get("overall_trend", "")
    tech_areas_data = data.get("tech_areas", [])

    lines = []
    lines.append("---")
    lines.append(f'title: "具身智能技术雷达 - {period}"')
    lines.append(f'generated_at: "{generated_at}"')
    lines.append("tags: [\"embodied-ai\", \"tech-radar\", \"pm-research\"]")
    lines.append("---")
    lines.append("")
    lines.append(f"# 具身智能技术趋势雷达 — {period}")
    lines.append("")

    # Overview
    lines.append("## 概览")
    lines.append("")
    lines.append(f"**总体趋势判断**：{overall_trend}")
    lines.append("")
    lines.append(f"**扫描覆盖**: 10 个技术领域，信号来源包括学术论文、公司产品发布、融资动态")
    lines.append(f"**报告生成时间**: {generated_at}")
    lines.append("")

    # Radar Quadrant Chart
    lines.append("### 技术成熟度象限")
    lines.append("")
    lines.append(build_radar_quadrants(tech_areas_data))
    lines.append("")

    # Scorecard
    lines.append("---")
    lines.append("")
    lines.append("## 技术领域 Scorecard")
    lines.append("")
    lines.append("| 技术领域 | 成熟度 | 信号强度 | 趋势 | 论文 | 公司 | 融资 | 媒体 | 综合 |")
    lines.append("|----------|--------|----------|------|------|------|------|------|------|")
    for ta in sorted(tech_areas_data, key=lambda t: t.get("combined_score", 0), reverse=True):
        name = ta.get("name_cn", ta.get("id", ""))
        mat_label = MATURITY_LABELS.get(ta.get("maturity", ""), ta.get("maturity", ""))
        sig = "🟢" * ta.get("signal_strength", 0)
        trend_icon = TREND_ICONS.get(ta.get("trend", ""), "➡️")
        ps = ta.get("paper_score", "-")
        cs = ta.get("company_score", "-")
        fs = ta.get("funding_score", "-")
        ms = ta.get("media_score", "-")
        com = f"{ta.get('combined_score', 0):.1f}"
        lines.append(
            f"| {name} | {mat_label} | {sig} | {trend_icon} | {ps} | {cs} | {fs} | {ms} | {com} |"
        )
    lines.append("")

    # Key findings section
    if overall_trend:
        lines.append("---")
        lines.append("")
        lines.append("## 关键发现")
        lines.append("")
        lines.append(overall_trend)
        lines.append("")

    # Deep dive into top 3
    lines.append("---")
    lines.append("")
    lines.append("## 重点技术深度分析")
    lines.append("")
    sorted_areas = sorted(tech_areas_data, key=lambda t: t.get("combined_score", 0), reverse=True)
    for i, ta in enumerate(sorted_areas[:3]):
        name = ta.get("name_cn", ta.get("id", ""))
        lines.append(f"### {i+1}. {name}")
        lines.append("")
        lines.append(f"- **成熟度**: {MATURITY_LABELS.get(ta.get('maturity', ''))} (上次: {ta.get('maturity_prev', 'N/A')})")
        lines.append(f"- **趋势**: {TREND_ICONS.get(ta.get('trend', ''))}")
        lines.append(f"- **综合评分**: {ta.get('combined_score', 0):.1f}/5")

        rationale = ta.get("maturity_rationale", "")
        if rationale:
            lines.append(f"- **成熟度判定依据**: {rationale}")
        lines.append("")

        events = ta.get("key_events", [])
        if events:
            lines.append("**本月关键信号**:")
            for ev in events:
                date = ev.get("date", "")
                etype = ev.get("type", "")
                title = ev.get("title", "")
                impact = ev.get("impact", "")
                desc = ev.get("description", "")
                impact_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(impact, "")
                lines.append(f"- [{date}] {impact_icon} ({etype}) {title}")
                if desc:
                    lines.append(f"  - {desc}")
            lines.append("")

        pm_imp = ta.get("pm_implications", "")
        if pm_imp:
            lines.append("**产品经理启示**:")
            lines.append("")
            lines.append(f"> {pm_imp}")
            lines.append("")

    # PM action recommendations
    lines.append("---")
    lines.append("")
    lines.append("## 产品经理行动建议")
    lines.append("")

    lines.append("### 现在就该关注的")
    for ta in sorted_areas:
        if ta.get("signal_strength", 0) >= 4 and ta.get("trend") == "accelerating":
            name = ta.get("name_cn", "")
            pm_imp = ta.get("pm_implications", "")
            lines.append(f"- **{name}**: {pm_imp or '信号强烈，建议深入研究'}")
    if not any(t.get("signal_strength", 0) >= 4 and t.get("trend") == "accelerating" for t in sorted_areas):
        lines.append("- 本月暂无明显需要紧急关注的方向")
    lines.append("")

    lines.append("### 6 个月内应布局")
    for ta in sorted_areas:
        if ta.get("maturity") in ("emerging",) and ta.get("signal_strength", 0) >= 3:
            name = ta.get("name_cn", "")
            pm_imp = ta.get("pm_implications", "")
            lines.append(f"- **{name}**: {pm_imp or '值得开始技术预研'}")
    lines.append("")

    lines.append("### 12 个月窗口期的机会")
    for ta in sorted_areas:
        if ta.get("maturity") in ("research", "emerging") and ta.get("signal_strength", 0) <= 2:
            name = ta.get("name_cn", "")
            pm_imp = ta.get("pm_implications", "")
            lines.append(f"- **{name}**: {pm_imp or '长期关注，暂不投入'}")

    lines.append("")

    # Methodology
    lines.append("---")
    lines.append("")
    lines.append("## 方法论说明")
    lines.append("")
    lines.append("- **信号模型**: 论文(30%) + 公司(35%) + 融资(20%) + 媒体(15%) = 综合热度")
    lines.append("- **成熟度定义**:")
    for level, label in MATURITY_LABELS.items():
        desc = config.get("maturity_levels", {}).get(level, "")
        lines.append(f"  - {label}: {desc}")
    lines.append("- **更新建议**: 季度更新，配合月度简要 check-in")
    lines.append(f"- **生成时间**: {generated_at}")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate embodied tech radar report")
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
