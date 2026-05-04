#!/usr/bin/env python3
"""具身智能公司追踪报告生成器 — 读取 config.yaml + 事件 JSON，输出 Markdown 报告"""

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


def generate_markdown(config: dict, data: dict, skill_dir: Path) -> str:
    period = data.get("period", "Unknown Period")
    generated_at = data.get("generated_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
    summary = data.get("summary", {})
    events_by_company = data.get("events_by_company", {})
    funding_events = data.get("funding_events", [])
    product_launches = data.get("product_launches", [])
    tech_trends = data.get("tech_trends", [])

    companies = config.get("companies", {})
    total_companies = sum(len(v) for v in companies.values())
    lines = []

    lines.append("---")
    lines.append(f'title: "具身智能公司动态追踪 - {period}"')
    lines.append(f'generated_at: "{generated_at}"')
    lines.append(f"companies_tracked: {total_companies}")
    lines.append('tags: ["embodied-ai", "company-tracker", "pm-research"]')
    lines.append("---")
    lines.append("")
    lines.append(f"# 具身智能公司动态追踪 — {period}")
    lines.append("")
    lines.append("## 概览")
    lines.append("")
    lines.append(f"- **追踪周期**: {period}")
    lines.append(f"- **覆盖公司**: {total_companies} 家（国际 Tier1/2 + 国内 Tier1/2）")
    lines.append(f"- **本月关键事件**: {summary.get('total_events', 0)} 件")
    lines.append(f"- **融资动态**: {summary.get('funding_count', 0)} 起")
    lines.append(f"- **产品发布**: {summary.get('product_launches', 0)} 个")
    lines.append(f"- **技术突破/合作**: {summary.get('tech_breakthroughs', 0)} 项")
    lines.append("")

    if summary.get("highlights"):
        lines.append("### 本月核心看点")
        lines.append("")
        for hl in summary["highlights"]:
            lines.append(f"- {hl}")
        lines.append("")

    # Render each company group
    for group_key, group_label in [
        ("international_tier1", "国际 Tier 1 — 头部平台/整机厂"),
        ("international_tier2", "国际 Tier 2 — 新锐/垂直领域"),
    ]:
        lines.append("---")
        lines.append("")
        lines.append("## 国际公司动态")
        lines.append("")
        lines.append(f"### {group_label}")
        lines.append("")
        _render_company_group(lines, companies.get(group_key, []), events_by_company)

    for group_key, group_label in [
        ("domestic_tier1", "国内 Tier 1 — 成熟整机厂/平台"),
        ("domestic_tier2", "国内 Tier 2 — 新锐/近期融资活跃"),
    ]:
        lines.append("---")
        lines.append("")
        lines.append("## 国内公司动态")
        lines.append("")
        lines.append(f"### {group_label}")
        lines.append("")
        _render_company_group(lines, companies.get(group_key, []), events_by_company)

    if funding_events:
        lines.append("---")
        lines.append("")
        lines.append("## 融资事件汇总")
        lines.append("")
        lines.append("| 公司 | 轮次 | 金额 | 投资方 | 时间 | 备注 |")
        lines.append("|------|------|------|--------|------|------|")
        for fe in funding_events:
            lines.append(
                f"| {fe.get('company', '')} | {fe.get('round', '')} | {fe.get('amount', '')} | "
                f"{fe.get('investors', '')} | {fe.get('date', '')} | {fe.get('note', '')} |"
            )
        lines.append("")

    if product_launches:
        lines.append("---")
        lines.append("")
        lines.append("## 产品发布汇总")
        lines.append("")
        lines.append("| 公司 | 产品 | 类型 | 关键特性 | 时间 |")
        lines.append("|------|------|------|----------|------|")
        for pl in product_launches:
            lines.append(
                f"| {pl.get('company', '')} | {pl.get('product', '')} | {pl.get('type', '')} | "
                f"{pl.get('key_features', '')} | {pl.get('date', '')} |"
            )
        lines.append("")

    if tech_trends:
        lines.append("---")
        lines.append("")
        lines.append("## 技术趋势观察")
        lines.append("")
        for i, trend in enumerate(tech_trends, 1):
            lines.append(f"{i}. **{trend.get('title', '')}**")
            if trend.get("description"):
                lines.append(f"   - {trend['description']}")
            if trend.get("implications"):
                lines.append(f"   - 产品影响: {trend['implications']}")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 追踪方法论")
    lines.append("")
    lines.append(f"- 数据来源: WebSearch 聚合搜索（英文+中文），覆盖公司官网、TechCrunch、36氪、投中网等")
    lines.append(f"- 覆盖范围: 国际 Tier1({len(companies.get('international_tier1', []))}) + "
                 f"Tier2({len(companies.get('international_tier2', []))}) + "
                 f"国内 Tier1({len(companies.get('domestic_tier1', []))}) + "
                 f"Tier2({len(companies.get('domestic_tier2', []))}) = {total_companies} 家")
    lines.append(f"- 报告生成时间: {generated_at}")
    lines.append("")

    return "\n".join(lines)


def _render_company_group(lines: list, companies: list, events_by_company: dict):
    for company in companies:
        name = company["name"]
        cn = company.get("chinese_name", "")
        display = f"{cn} ({name})" if cn else name
        focus = company.get("focus", "")
        lines.append(f"#### {display}")
        lines.append("")
        lines.append(f"- **定位**: {focus}")
        if company.get("valuation_note"):
            lines.append(f"- **备注**: {company['valuation_note']}")

        comp_events = events_by_company.get(name, [])
        if not comp_events and cn:
            comp_events = events_by_company.get(cn, [])

        if comp_events:
            lines.append("- **本月动态**:")
            for ev in comp_events:
                date = ev.get("date", "")
                etype = ev.get("type", "")
                title = ev.get("title", "")
                desc = ev.get("description", "")
                source = ev.get("source", "")
                date_str = f"[{date}] " if date else ""
                type_str = f"({etype}) " if etype else ""
                lines.append(f"  - {date_str}{type_str}{title}")
                if desc:
                    lines.append(f"    - {desc}")
                if source:
                    lines.append(f"    - 来源: {source}")
        else:
            lines.append("- **本月动态**: 暂无显著公开动态")
        lines.append("")


def main():
    parser = argparse.ArgumentParser(description="Generate embodied company tracker report")
    parser.add_argument("--skill-dir", type=str, required=True)
    parser.add_argument("--input", type=str, required=True, help="Path to events JSON file")
    parser.add_argument("--output", type=str, required=True, help="Path to output markdown file")
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
