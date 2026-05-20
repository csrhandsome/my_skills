#!/usr/bin/env python3
"""具身智能公司深度洞察报告生成器 — 四维度分析：团队/融资/业务模式/产品技术"""

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


def _section(title: str, lines: list[str]) -> None:
    lines.append(f"## {title}")
    lines.append("")


def _subsection(title: str, lines: list[str]) -> None:
    lines.append(f"### {title}")
    lines.append("")


def _table(headers: list[str], rows: list[list[str]], lines: list[str]) -> None:
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["------" for _ in headers]) + "|")
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    lines.append("")


def _kv_table(data: dict, lines: list[str]) -> None:
    for key, value in data.items():
        lines.append(f"| **{key}** | {value} |")
    lines.append("")


def render_team(team: dict, lines: list[str]) -> None:
    _section("👥 核心团队", lines)

    if team.get("summary"):
        lines.append(team["summary"])
        lines.append("")

    members = team.get("members", [])
    if members:
        headers = ["角色", "姓名", "背景", "关键经历"]
        rows = []
        for m in members:
            rows.append([
                m.get("role", ""),
                m.get("name", ""),
                m.get("background", ""),
                m.get("experience", ""),
            ])
        _table(headers, rows, lines)

    if team.get("team_size"):
        lines.append(f"**团队规模**: {team['team_size']}")
        lines.append("")
    if team.get("hiring_direction"):
        lines.append(f"**招聘方向**: {team['hiring_direction']}")
        lines.append("")
    if team.get("team_dna"):
        lines.append(f"**团队基因**: {team['team_dna']}")
        lines.append("")
    if team.get("pm_insight"):
        lines.append(f"> **PM 启示**: {team['pm_insight']}")
        lines.append("")


def render_funding(funding: dict, lines: list[str]) -> None:
    _section("💰 融资与估值时间线", lines)

    if funding.get("total_raised"):
        lines.append(f"**累计融资**: {funding['total_raised']}")
        lines.append("")
    if funding.get("latest_valuation"):
        lines.append(f"**最新估值**: {funding['latest_valuation']}")
        lines.append("")

    rounds = funding.get("rounds", [])
    if rounds:
        headers = ["时间", "轮次", "金额", "投资方", "估值", "备注"]
        rows = []
        for r in rounds:
            rows.append([
                r.get("date", ""),
                r.get("round", ""),
                r.get("amount", ""),
                r.get("investors", ""),
                r.get("valuation", ""),
                r.get("note", ""),
            ])
        _table(headers, rows, lines)

    if funding.get("pace_analysis"):
        _subsection("融资节奏分析", lines)
        lines.append(funding["pace_analysis"])
        lines.append("")

    if funding.get("investor_structure"):
        _subsection("投资方结构", lines)
        lines.append(funding["investor_structure"])
        lines.append("")

    if funding.get("valuation_analysis"):
        _subsection("估值分析", lines)
        lines.append(funding["valuation_analysis"])
        lines.append("")

    if funding.get("pm_insight"):
        lines.append(f"> **PM 启示**: {funding['pm_insight']}")
        lines.append("")


def render_business_model(biz: dict, lines: list[str]) -> None:
    _section("🏢 业务模式", lines)

    if biz.get("revenue_model"):
        _subsection("收入模式", lines)
        lines.append(biz["revenue_model"])
        lines.append("")

    if biz.get("target_customers"):
        _subsection("目标客户", lines)
        lines.append(biz["target_customers"])
        lines.append("")

    if biz.get("gtm_strategy"):
        _subsection("市场进入策略", lines)
        lines.append(biz["gtm_strategy"])
        lines.append("")

    if biz.get("commercialization_stage"):
        _subsection("商业化阶段", lines)
        lines.append(biz["commercialization_stage"])
        lines.append("")

    if biz.get("pricing"):
        _subsection("定价策略", lines)
        lines.append(biz["pricing"])
        lines.append("")

    if biz.get("pm_insight"):
        lines.append(f"> **PM 启示**: {biz['pm_insight']}")
        lines.append("")


def render_product_tech(pt: dict, lines: list[str]) -> None:
    _section("🤖 产品线与核心技术", lines)

    products = pt.get("products", [])
    if products:
        _subsection("产品矩阵", lines)
        headers = ["产品", "形态", "应用场景", "商业化状态"]
        rows = []
        for p in products:
            rows.append([
                p.get("name", ""),
                p.get("form_factor", ""),
                p.get("scenario", ""),
                p.get("commercial_status", ""),
            ])
        _table(headers, rows, lines)

    tech = pt.get("tech_stack", {})
    if tech:
        _subsection("核心技术栈", lines)
        headers = ["技术层", "自研/外购", "技术方案", "成熟度"]
        rows = []
        for layer_name, detail in tech.items():
            rows.append([
                layer_name,
                detail.get("make_or_buy", ""),
                detail.get("solution", ""),
                detail.get("maturity", ""),
            ])
        _table(headers, rows, lines)

    if pt.get("differentiation"):
        _subsection("技术差异化", lines)
        lines.append(pt["differentiation"])
        lines.append("")

    if pt.get("patents"):
        _subsection("知识产权/专利", lines)
        lines.append(pt["patents"])
        lines.append("")

    if pt.get("pm_insight"):
        lines.append(f"> **PM 启示**: {pt['pm_insight']}")
        lines.append("")


def render_competition(competition: dict, lines: list[str]) -> None:
    _section("⚔️ 竞争定位", lines)

    if competition.get("positioning"):
        lines.append(competition["positioning"])
        lines.append("")

    peers = competition.get("peers", [])
    if peers:
        headers = ["公司", "相似度", "核心差异"]
        rows = []
        for p in peers:
            rows.append([
                p.get("company", ""),
                p.get("similarity", ""),
                p.get("key_difference", ""),
            ])
        _table(headers, rows, lines)

    if competition.get("pm_insight"):
        lines.append(f"> **PM 启示**: {competition['pm_insight']}")
        lines.append("")


def generate_markdown(config: dict, data: dict, skill_dir: Path) -> str:
    company = data.get("company", {})
    company_name = company.get("name", "Unknown Company")
    company_name_cn = company.get("chinese_name", company_name)
    generated_at = data.get("generated_at", datetime.now().strftime("%Y-%m-%d %H:%M"))

    lines = []

    # Frontmatter
    lines.append("---")
    lines.append(f'title: "{company_name_cn} 深度洞察报告"')
    lines.append(f'company: "{company_name}"')
    lines.append(f'generated_at: "{generated_at}"')
    lines.append('tags: ["embodied-ai", "company-insight", "deep-dive"]')
    lines.append("---")
    lines.append("")
    lines.append(f"# {company_name_cn} 深度洞察报告")
    lines.append("")

    # Company snapshot
    _section("📋 公司速览", lines)
    snapshot_items = [
        ("公司名称", company.get("name", "") + (f" / {company_name_cn}" if company_name_cn != company.get("name", "") else "")),
        ("成立时间", str(company.get("founded", "未知"))),
        ("总部", company.get("headquarters", "未知")),
        ("区域", company.get("region", "未知")),
        ("团队规模", company.get("team_size", "未公开")),
        ("累计融资", company.get("total_raised", "未公开")),
        ("最新估值", company.get("latest_valuation", "未公开")),
        ("官网", company.get("website", "未公开")),
    ]
    lines.append("")
    for label, val in snapshot_items:
        lines.append(f"- **{label}**: {val}")
    lines.append("")

    # Four dimensions
    team = data.get("team", {})
    if team:
        render_team(team, lines)

    funding = data.get("funding", {})
    if funding:
        render_funding(funding, lines)

    biz = data.get("business_model", {})
    if biz:
        render_business_model(biz, lines)

    pt = data.get("product_tech", {})
    if pt:
        render_product_tech(pt, lines)

    competition = data.get("competition", {})
    if competition:
        render_competition(competition, lines)

    # PM summary
    pm_summary = data.get("pm_summary", [])
    if pm_summary:
        _section("💡 PM 行动启示汇总", lines)
        for item in pm_summary:
            lines.append(f"- {item}")
        lines.append("")

    # Data sources
    sources = data.get("sources", [])
    if sources:
        _section("📚 数据来源", lines)
        for src in sources:
            lines.append(f"- {src}")
        lines.append("")

    lines.append("---")
    lines.append(f"*报告生成时间: {generated_at}*")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="具身智能公司深度洞察报告生成器")
    parser.add_argument("--skill-dir", required=True, help="Skill directory path")
    parser.add_argument("--input", required=True, help="Input JSON with analysis data")
    parser.add_argument("--output", required=True, help="Output markdown file path")
    args = parser.parse_args()

    skill_dir = Path(args.skill_dir)
    config = load_config(skill_dir)

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    markdown = generate_markdown(config, data, skill_dir)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"Report generated: {output_path}")


if __name__ == "__main__":
    main()
