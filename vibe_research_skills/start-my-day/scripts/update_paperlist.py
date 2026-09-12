#!/usr/bin/env python3
"""
更新 Paperlist.md，将本次推荐的论文追加/合并到汇总表格中。
Paperlist 与 preference 文件位于同一目录，文件名大小写敏感为 Paperlist.md。

更新策略：
- 按 arXiv ID 匹配，已存在的论文追加日期到"推荐来源"、追加得分到"原始得分"
- 新论文在表格末尾追加新行，编号自动递增
- 更新 frontmatter 中的 papers_count
"""

import argparse
import re
from datetime import datetime
from pathlib import Path


def extract_papers_from_daily_file(md_file: Path):
    """从 daily 推荐笔记中提取论文列表（含评分）。"""
    try:
        content = md_file.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"Error reading daily note: {e}")
        return []

    title_pattern = re.compile(r'^#{3,4}\s+(.*)$', re.MULTILINE)
    arxiv_pattern = re.compile(
        r'^-\s+\*\*arXiv\*\*\s*[：:]\s*(\d{4}\.\d{4,5})',
        re.MULTILINE | re.IGNORECASE,
    )
    score_pattern = re.compile(
        r'^-\s+\*\*推荐评分\*\*\s*[：:]\s*(\d+\.?\d*)/10',
        re.MULTILINE,
    )

    titles = title_pattern.findall(content)
    arxiv_ids = arxiv_pattern.findall(content)
    scores = score_pattern.findall(content)
    count = min(len(titles), len(arxiv_ids))

    papers = []
    for i in range(count):
        title = titles[i].strip()
        arxiv_id = arxiv_ids[i]
        score = scores[i] if i < len(scores) else '-'
        if title and arxiv_id:
            papers.append({'title': title, 'arxiv_id': arxiv_id, 'score': score})
    return papers


def extract_arxiv_id_from_link(link: str):
    """从论文链接列提取 arXiv ID。"""
    match = re.search(r'arXiv[:/](\d{4}\.\d{4,5})', link, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def parse_table(content: str):
    """
    解析 Paperlist.md 中的表格。
    返回 (header_lines, table_header_idx, table_lines, footer_lines, data_rows)
    """
    lines = content.split('\n')
    table_start = None
    table_end = None
    for i, line in enumerate(lines):
        if table_start is None and '| #' in line and '论文名称' in line:
            table_start = i
        elif table_start is not None and not line.strip().startswith('|'):
            table_end = i
            break

    if table_start is None:
        return None
    if table_end is None:
        table_end = len(lines)

    header_lines = lines[:table_start]
    table_section = lines[table_start:table_end]
    footer_lines = lines[table_end:]

    data_rows = []
    for line in table_section:
        if '| ---' in line or ('| #' in line and '论文名称' in line):
            continue
        if line.strip().startswith('|'):
            cells = [c.strip() for c in line.strip().split('|')[1:-1]]
            if len(cells) >= 7:
                data_rows.append({
                    'raw': line,
                    'number': cells[0],
                    'title': cells[1],
                    'sources': cells[2],
                    'link': cells[3],
                    'raw_score': cells[4],
                    'mapped_score': cells[5],
                    'read': cells[6],
                })

    return header_lines, table_start, table_section, footer_lines, data_rows


def rebuild_table_line(row: dict) -> str:
    """重建单行表格。"""
    return f"| {row['number']} | {row['title']} | {row['sources']} | {row['link']} | {row['raw_score']} | {row['mapped_score']} | {row['read']} |"


def update_paperlist(content: str, papers: list, date_str: str):
    """
    将新论文合并到 Paperlist 表格中。
    返回更新后的完整内容，以及新增/更新的论文数量。
    """
    result = parse_table(content)
    if result is None:
        # 无法解析表格，简单追加到末尾
        section = f"\n\n## {date_str} 推荐\n\n"
        for p in papers:
            section += f"- {p['title']} (`arXiv:{p['arxiv_id']}`) — 待读\n"
        return content + section, 0, len(papers)

    header_lines, table_start, table_section, footer_lines, data_rows = result

    # 建立 arXiv ID -> row 映射
    existing_by_arxiv = {}
    for row in data_rows:
        arxiv_id = extract_arxiv_id_from_link(row['link'])
        if arxiv_id:
            existing_by_arxiv[arxiv_id] = row

    # 计算当前最大编号
    max_num = 0
    for row in data_rows:
        try:
            num = int(row['number'].strip())
            max_num = max(max_num, num)
        except ValueError:
            pass

    added = 0
    updated = 0
    mm_dd = date_str[5:].replace('-', '-')  # 2026-06-01 -> 06-01

    for p in papers:
        arxiv_id = p['arxiv_id']
        score = p.get('score', '-')

        if arxiv_id in existing_by_arxiv:
            row = existing_by_arxiv[arxiv_id]
            # 更新推荐来源（追加日期）
            if mm_dd not in row['sources']:
                row['sources'] = f"{row['sources']}, {mm_dd}" if row['sources'].strip() else mm_dd
                updated += 1
            # 更新原始得分（追加分值）
            if score != '-' and score not in row['raw_score']:
                if row['raw_score'].strip() and row['raw_score'].strip() != '-':
                    row['raw_score'] = f"{row['raw_score']} · {score}"
                else:
                    row['raw_score'] = score
                row['mapped_score'] = f"**{row['raw_score']}**"
        else:
            max_num += 1
            data_rows.append({
                'number': str(max_num),
                'title': p['title'],
                'sources': mm_dd,
                'link': f"`arXiv:{arxiv_id}`",
                'raw_score': str(score) if score != '-' else '-',
                'mapped_score': f"**{score}**" if score != '-' else '-',
                'read': '[ ]',
            })
            added += 1

    # 重建表格
    new_table = []
    for line in table_section:
        if '| ---' in line or ('| #' in line and '论文名称' in line):
            new_table.append(line)
            continue
        # 数据行会被重建

    for row in data_rows:
        new_table.append(rebuild_table_line(row))

    # 重建完整内容
    new_lines = header_lines + new_table + footer_lines
    new_content = '\n'.join(new_lines)

    # 统计已读数量
    read_count = sum(1 for row in data_rows if '[x]' in row.get('read', '').lower())

    # 更新 frontmatter 中的 papers_count 和 read_count
    new_content = update_frontmatter_count(new_content, max_num, read_count)

    return new_content, added, updated


def update_frontmatter_count(content: str, count: int, read_count: int = None):
    """更新 frontmatter 中的 papers_count 和 read_count。"""
    if not content.startswith('---'):
        return content
    content = re.sub(
        r'^papers_count:\s*\d+',
        f'papers_count: {count}',
        content,
        flags=re.MULTILINE,
    )
    if read_count is not None:
        if re.search(r'^read_count:\s*\d+', content, re.MULTILINE):
            content = re.sub(
                r'^read_count:\s*\d+',
                f'read_count: {read_count}',
                content,
                flags=re.MULTILINE,
            )
        else:
            # Insert read_count after papers_count line
            content = re.sub(
                r'(^papers_count:\s*\d+)',
                r'\1\nread_count: ' + str(read_count),
                content,
                flags=re.MULTILINE,
            )
    return content


def main():
    parser = argparse.ArgumentParser(description='Update Paperlist.md with daily recommendations')
    parser.add_argument('--preference', required=True, help='Path to the preference file')
    parser.add_argument('--daily-note', required=True, help='Path to the daily recommendation markdown')
    parser.add_argument('--date', default=datetime.now().strftime('%Y-%m-%d'), help='Date string for this batch')
    args = parser.parse_args()

    pref_path = Path(args.preference).resolve()
    paperlist_path = pref_path.parent / 'Paperlist.md'
    daily_note_path = Path(args.daily_note).resolve()

    if not daily_note_path.exists():
        print(f"Daily note not found: {daily_note_path}")
        return

    papers = extract_papers_from_daily_file(daily_note_path)
    if not papers:
        print("No papers found in daily note, skipping Paperlist update.")
        return

    # 读取或创建 Paperlist
    if paperlist_path.exists():
        content = paperlist_path.read_text(encoding='utf-8')
    else:
        # 创建与示例一致的基础格式
        pref_dir_name = pref_path.parent.name
        content = f'''---
title: "{pref_dir_name} — 论文推荐汇总表"
date: "{args.date}"
tags:
  - paper-list
papers_count: 0
read_count: 0
---

# {pref_dir_name} — 论文推荐汇总表

> **数据来源**：`{pref_dir_name}/` 下推荐笔记
> **更新日期**：{args.date}

---

| #   | 论文名称 | 推荐来源 | 论文链接 | 原始得分 | 映射10分 | 已详读 |
| --- | -------- | -------- | -------- | -------- | -------- | ------ |

---

## 统计

| 指标 | 数值 |
|------|------|
| 论文总数 | 0 |
| 已详读 | 0 |
| >=9.0 分高优先级 | 0 |

## 相关笔记

- [[preference_{pref_dir_name.replace("vibe_research_", "")}|研究偏好配置]]
'''
        paperlist_path.write_text(content, encoding='utf-8')
        content = paperlist_path.read_text(encoding='utf-8')

    new_content, added, updated = update_paperlist(content, papers, args.date)

    paperlist_path.write_text(new_content, encoding='utf-8')
    print(f"Updated Paperlist: {paperlist_path} (+{added} new, ~{updated} updated)")


if __name__ == '__main__':
    main()
