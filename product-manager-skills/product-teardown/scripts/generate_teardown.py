#!/usr/bin/env python3
"""
具身智能竞品产品拆解报告生成器
读取 config.yaml 和拆解数据，输出格式化 Markdown 对比报告
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


def load_config(skill_dir: Path) -> dict:
    config_path = skill_dir / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def format_value(val: Any) -> str:
    if val is None:
        return "—"
    if isinstance(val, bool):
        return "✅" if val else "❌"
    return str(val)


def generate_single_teardown(config: dict, data: dict, skill_dir: Path) -> str:
    """单产品深度拆解报告"""
    product = data.get("product", {})
    name = product.get("name", "Unknown")
    company = product.get("company", "Unknown")
    category = product.get("category", "")
    line = []
    line.append(f"# {name} 深度拆解")
    line.append("")
    line.append("## 产品概览")
    line.append("")

    overview = data.get("overview", {})
    for key, label in [
        ("company", "公司"),
        ("region", "地区"),
        ("category", "类别"),
        ("generation", "代际"),
        ("released", "发布/公开时间"),
        ("positioning", "产品定位"),
        ("target_scenario", "目标场景"),
    ]:
        val = overview.get(key, product.get(key, ""))
        if val:
            line.append(f"- **{label}**: {val}")

    highlights = overview.get("highlights", [])
    if highlights:
        line.append("")
        line.append("### 核心亮点")
        for h in highlights:
            line.append(f"- {h}")

    pain_points = overview.get("pain_points", [])
    if pain_points:
        line.append("")
        line.append("### 已知短板")
        for p in pain_points:
            line.append(f"- {p}")

    line.append("")

    # Hardware
    line.append("## 硬件架构")
    line.append("")
    for section, fields in [
        ("执行器与传动", ["actuator_type", "gear_type", "self_developed", "backdrivability", "joint_torque"]),
        ("自由度", ["dof_total", "dof_arms", "dof_hands"]),
        ("物理参数", ["height", "weight", "payload_per_arm", "battery_life", "speed"]),
        ("传感器", ["cameras", "depth_sensor", "tactile", "imu", "force_torque", "proprioception"]),
        ("计算平台", ["onboard_chip", "compute_tops", "edge_cloud_split", "inference_latency"]),
    ]:
        line.append(f"### {section}")
        specs = product.get("specs", {})
        for field in fields:
            val = specs.get(field)
            if val is not None:
                label = field
                line.append(f"- **{label}**: {format_value(val)}")
        line.append("")

    # Software
    line.append("## 软件栈")
    line.append("")
    for field in ["foundation_model", "training_paradigm", "sim_platform", "autonomy_level", "multi_modal", "api_openness"]:
        val = product.get("specs", {}).get(field)
        if val:
            line.append(f"- **{field}**: {val}")
    line.append("")

    # BOM estimate
    bom = data.get("bom_estimate", {})
    if bom:
        line.append("## 成本估算 (BOM)")
        line.append("")
        line.append("| 组件类别 | 估算成本 | 估算依据 |")
        line.append("|----------|----------|----------|")
        total = 0
        for item in bom.get("items", []):
            comp = item.get("component", "")
            cost = item.get("cost", "")
            basis = item.get("basis", "")
            line.append(f"| {comp} | {cost} | {basis} |")
        if bom.get("total"):
            line.append(f"| **合计** | **{bom['total']}** | |")
        line.append("")
        if bom.get("note"):
            line.append(f"> {bom['note']}")
            line.append("")

    # SWOT-style analysis
    swot = data.get("swot", {})
    if swot:
        line.append("## 优劣势分析")
        line.append("")
        line.append("### 技术优势")
        for s in swot.get("strengths", []):
            line.append(f"- {s}")
        line.append("")
        line.append("### 技术短板")
        for w in swot.get("weaknesses", []):
            line.append(f"- {w}")
        line.append("")
        line.append("### 差异化竞争力")
        for o in swot.get("differentiators", []):
            line.append(f"- {o}")
        line.append("")

    # PM insights
    insights = data.get("pm_insights", {})
    if insights:
        line.append("## 产品经理启示")
        line.append("")
        line.append("### 可借鉴的设计决策")
        for d in insights.get("design_learnings", []):
            line.append(f"- {d}")
        line.append("")
        line.append("### 供应链风险")
        for r in insights.get("supply_chain_risks", []):
            line.append(f"- {r}")
        line.append("")
        line.append("### 对标建议")
        for b in insights.get("benchmark_suggestions", []):
            line.append(f"- {b}")
        line.append("")

    line.append("---")
    line.append(f"*报告生成时间: {data.get('generated_at', '')}*")
    line.append(f"*数据来源: {data.get('sources_note', 'WebSearch + config.yaml')}*")
    line.append("")

    return "\n".join(line)


def generate_comparison(config: dict, data: dict, skill_dir: Path) -> str:
    """多产品横向对比报告"""
    mode = data.get("mode", "comparison")
    products = data.get("products", [])
    dimension_configs = config.get("dimensions", {})

    lines = []
    lines.append(f"# {data.get('title', '产品横向对比')}")
    lines.append("")

    # Overview
    lines.append("## 对比产品")
    lines.append("")
    for p in products:
        lines.append(f"- **{p.get('name')}** ({p.get('company')}, {p.get('region', '')}) — {p.get('category', '')}")
    lines.append("")

    # Spec matrix - by dimension
    for dim_key in ["hardware", "actuation", "sensing", "compute", "software", "commercial"]:
        dim_config = dimension_configs.get(dim_key, {})
        dim_label = dim_config.get("label", dim_key)
        dim_fields = dim_config.get("fields", [])
        lines.append(f"## {dim_label} 对比")
        lines.append("")
        header = "| 规格 | " + " | ".join(p.get("name", "") for p in products) + " |"
        lines.append(header)
        lines.append("|------|" + "|".join(["------"] * len(products)) + "|")
        for field in dim_fields:
            vals = []
            for p in products:
                specs = p.get("specs", {})
                vals.append(format_value(specs.get(field, "")))
            lines.append(f"| {field} | {' | '.join(vals)} |")
        lines.append("")

    # Dimension scoring
    if data.get("scoring"):
        lines.append("## 综合评分对比")
        lines.append("")
        header = "| 维度 (权重) | " + " | ".join(p.get("name", "") for p in products) + " |"
        lines.append(header)
        lines.append("|------|" + "|".join(["------"] * len(products)) + "|")
        for dim_key in ["hardware", "actuation", "sensing", "compute", "software", "commercial"]:
            dim = dimension_configs.get(dim_key, {})
            label = dim.get("label", "")
            weight = dim.get("weight", 0)
            scores = []
            for p in products:
                s = p.get("scoring", {}).get(dim_key, "-")
                if isinstance(s, (int, float)):
                    scores.append(f"{s:.1f}")
                else:
                    scores.append(str(s))
            lines.append(f"| {label} ({weight:.0%}) | {' | '.join(scores)} |")
        lines.append("")

    # Analysis
    analysis = data.get("analysis", {})
    if analysis:
        lines.append("## 综合分析")
        lines.append("")
        lines.append("### 技术路线对比")
        for t in analysis.get("tech_routes", []):
            lines.append(f"- {t}")
        lines.append("")
        lines.append("### 市场定位差异")
        for m in analysis.get("market_positioning", []):
            lines.append(f"- {m}")
        lines.append("")
        lines.append("### 性价比分析")
        for v in analysis.get("value_analysis", []):
            lines.append(f"- {v}")
        lines.append("")
        lines.append("### 场景选型建议")
        for s in analysis.get("scenario_recommendations", []):
            lines.append(f"- {s}")
        lines.append("")

    # PM takeaways
    takeaways = data.get("pm_takeaways", [])
    if takeaways:
        lines.append("---")
        lines.append("")
        lines.append("## 产品经理启示")
        lines.append("")
        for t in takeaways:
            lines.append(f"- {t}")
        lines.append("")

    lines.append(f"*报告生成时间: {data.get('generated_at', '')}*")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate product teardown report")
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

    mode = data.get("mode", "single")
    if mode == "comparison":
        markdown = generate_comparison(config, data, skill_dir)
    else:
        markdown = generate_single_teardown(config, data, skill_dir)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"Report generated: {output_path}")


if __name__ == "__main__":
    main()
