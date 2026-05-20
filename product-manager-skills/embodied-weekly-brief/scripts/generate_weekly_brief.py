#!/usr/bin/env python3
"""
具身智能行业周报生成器
读取 config.yaml + 周报数据 JSON → 输出 Obsidian-ready Markdown
"""

import argparse, json, os, sys
from datetime import datetime, timedelta
from pathlib import Path
import yaml


def load_config(skill_dir: Path) -> dict:
    with open(skill_dir / "config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_obsidian_output_path(config: dict, week_start: str, fallback_dir: Path) -> Path:
    """Determine output path: Obsidian vault if available, else skill reports dir."""
    vault = os.environ.get(
        config.get("obsidian", {}).get("vault_env_var", "OBSIDIAN_VAULT_PATH"), ""
    )
    if vault:
        folder = config.get("obsidian", {}).get("weekly_notes_folder", "vibe_research/10_Daily")
        subfolder = config.get("obsidian", {}).get("weekly_notes_subfolder", "Weekly_Briefs")
        template = config.get("obsidian", {}).get(
            "filename_template", "{YYYY-MM-DD}_具身智能周报.md"
        )
        filename = template.replace("{YYYY-MM-DD}", week_start)
        return Path(vault) / folder / subfolder / filename
    else:
        fallback_dir.mkdir(parents=True, exist_ok=True)
        return fallback_dir / f"{week_start}_具身智能周报.md"


def image_md(url_or_path: str, size: str = "400") -> str:
    """Format an image for Obsidian: remote URL or local wikilink."""
    if not url_or_path:
        return ""
    if url_or_path.startswith("http"):
        return f"![]({url_or_path}|{size})"
    else:
        return url_or_path  # already formatted by caller (e.g. ![[...|400]])


def generate_markdown(config: dict, data: dict) -> str:
    week_start = data.get("week_start", "")
    week_end = data.get("week_end", "")
    week_range = f"{week_start} ~ {week_end}"
    generated_at = data.get("generated_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
    next_week_start = data.get("next_week_start", "")

    company_tracker_link = config.get("obsidian", {}).get("link_to_skills", {}).get(
        "company_tracker", ""
    )
    tech_radar_link = config.get("obsidian", {}).get("link_to_skills", {}).get(
        "tech_radar", ""
    )

    # Fill in date placeholders in links
    try:
        ws_date = datetime.strptime(week_start, "%Y-%m-%d")
        month_key = ws_date.strftime("%Y-%m")
        # crude quarter calculation
        q = (ws_date.month - 1) // 3 + 1
        quarter_key = f"{ws_date.year}-Q{q}"
        company_tracker_link = company_tracker_link.replace("{YYYY-MM}", month_key)
        tech_radar_link = tech_radar_link.replace("{YYYY-QQ}", quarter_key)
    except ValueError:
        pass

    lines = []
    lines.append("---")
    lines.append(f'title: "具身智能行业周报 {week_start}"')
    lines.append(f'week: "{week_range}"')
    lines.append('tags: ["weekly-brief", "embodied-ai", "llm-generated"]')
    lines.append(f'created: {week_start}')
    lines.append("---\n")
    lines.append(f"# 具身智能行业周报 📊\n")
    lines.append(f"**{week_range}**\n")

    # Headlines
    headlines = data.get("headlines", [])
    if headlines:
        lines.append("---\n")
        lines.append("## 🔥 本周头条\n")
        for i, hl in enumerate(headlines[:3], 1):
            title = hl.get("title", f"头条 {i}")
            img = hl.get("image", "")
            description = hl.get("description", "")
            pm_take = hl.get("pm_takeaway", "")
            source = hl.get("source", "")

            lines.append(f"### {title}\n")
            if img:
                lines.append(image_md(img))
                lines.append("")
            if description:
                lines.append(description)
                lines.append("")
            if pm_take:
                lines.append(f"> **PM 看点**：{pm_take}")
                lines.append("")
            if source:
                lines.append(f"*来源：[{source}]({source})*")
                lines.append("")

    # Company radar
    company_items = data.get("company_radar", [])
    if company_items:
        lines.append("---\n")
        lines.append("## 🏢 公司动态速览\n")
        for item in company_items:
            name = item.get("company", "")
            brief = item.get("brief", "")
            link = item.get("wikilink", "")
            if link:
                lines.append(f"- **[[{link}|{name}]]**：{brief}" if link else f"- **{name}**：{brief}")
            else:
                lines.append(f"- **{name}**：{brief}")
        if company_tracker_link:
            lines.append(f"\n> 📊 详见 {company_tracker_link}\n")

    # Funding flash
    funding = data.get("funding_flash", [])
    if funding:
        lines.append("\n## 💰 融资快讯\n")
        lines.append("| 公司 | 轮次 | 金额 | 投资方 |")
        lines.append("|------|------|------|--------|")
        for f in funding:
            lines.append(f"| {f.get('company', '')} | {f.get('round', '')} | {f.get('amount', '')} | {f.get('investors', '')} |")
        lines.append("")

    # Tech signal
    tech = data.get("tech_signals", [])
    if tech:
        lines.append("---\n")
        lines.append("## 🔬 技术信号\n")
        for t in tech:
            lines.append(f"- **{t.get('title', '')}**：{t.get('description', '')}")
            if t.get("note_link"):
                lines.append(f"  → 详见 [[{t['note_link']}]]")
            if t.get("image"):
                lines.append(f"  {image_md(t['image'])}")
        lines.append("")

    # Product updates
    products = data.get("product_updates", [])
    if products:
        lines.append("---\n")
        lines.append("## 📦 产品动态\n")
        for p in products:
            lines.append(f"- **{p.get('company', '')}**：{p.get('title', '')}")
            if p.get("description"):
                lines.append(f"  {p['description']}")
            if p.get("image"):
                lines.append(f"  {image_md(p['image'])}")
        lines.append("")

    # What to watch
    watch = data.get("what_to_watch", [])
    if watch:
        lines.append("---\n")
        lines.append("## 📅 下周关注\n")
        for w in watch:
            lines.append(f"- {w}")
        lines.append("")

    # PM note
    pm_note = data.get("pm_note", "")
    if pm_note:
        lines.append("---\n")
        lines.append("## 💭 PM 随想\n")
        lines.append(f"> {pm_note}\n")

    # Footer
    lines.append("---\n")
    lines.append(f"*下期预告：{next_week_start}*  \n")
    related = []
    if company_tracker_link:
        related.append(f"月度公司追踪：{company_tracker_link}")
    if tech_radar_link:
        related.append(f"季度技术雷达：{tech_radar_link}")
    if related:
        lines.append(f"*相关报告：{' | '.join(related)}*")
    lines.append(f"\n*生成时间：{generated_at}*")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate weekly industry brief for Obsidian")
    parser.add_argument("--skill-dir", type=str, required=True)
    parser.add_argument("--input", type=str, required=True)
    parser.add_argument("--output", type=str, default="")
    args = parser.parse_args()

    skill_dir = Path(args.skill_dir)
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    config = load_config(skill_dir)

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    week_start = data.get("week_start", datetime.now().strftime("%Y-%m-%d"))

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = get_obsidian_output_path(
            config, week_start, skill_dir / "reports"
        )

    markdown = generate_markdown(config, data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"Weekly brief generated: {output_path}")


if __name__ == "__main__":
    main()
