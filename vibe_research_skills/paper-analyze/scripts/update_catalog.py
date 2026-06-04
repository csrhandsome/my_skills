#!/usr/bin/env python3
"""
更新 Paper 目录下的整理大纲，并给论文文件夹加编号。

约定结构：
  Vault/
    ├── Paper/
    │   ├── 整理大纲.md
    │   ├── 1-论文A/
    │   ├── 2-论文B/
    │   └── short_name/   ← 待编号的新论文
    └── ...
"""

import argparse
import re
from pathlib import Path


def get_next_number(paper_root: Path) -> int:
    """从 Paper 目录下的文件夹名中提取最大编号。"""
    max_num = 0
    for item in paper_root.iterdir():
        if not item.is_dir():
            continue
        match = re.match(r'^(\d+)[-_]', item.name)
        if match:
            max_num = max(max_num, int(match.group(1)))
    return max_num + 1


def extract_year_from_paper_id(paper_id: str) -> str:
    """从 arXiv ID 中提取年份（如 2501.00001 -> 2025）。"""
    if not paper_id:
        return "N/A"
    match = re.match(r'^(\d{2})(\d{2})\.', paper_id)
    if match:
        year = int(match.group(1))
        if year >= 90:
            return str(1900 + year)
        else:
            return str(2000 + year)
    return "N/A"


def append_to_catalog(catalog_path: Path, number: int, title: str, year: str,
                       keywords: str, main_content: str, score: str):
    """在整理大纲表格中追加一行。"""
    if not catalog_path.exists():
        # 创建基本结构
        content = "\n| Number | Title | Year | Keywords | Main Content | 总分 |\n"
        content += "| ------ | ----- | ---- | -------- | ------------ | --- |\n"
    else:
        content = catalog_path.read_text(encoding='utf-8')

    # 检查是否已有相同标题的条目
    if title in content:
        print(f"Catalog already contains entry for '{title}', skipping append.")
        return

    lines = content.split('\n')
    insert_idx = len(lines)
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip().startswith('|'):
            insert_idx = i + 1
            break

    new_line = f"| =={number}==  | {title} | {year} | {keywords} | {main_content} | {score} "
    lines.insert(insert_idx, new_line)

    catalog_path.write_text('\n'.join(lines), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description='Update catalog and number paper folder')
    parser.add_argument('--paper-dir', required=True,
                        help='论文分析输出目录（如 Vault/Paper/short_name）')
    parser.add_argument('--vault', default=None,
                        help='Vault 路径（用于定位 Paper 目录，如无法推导则必填）')
    parser.add_argument('--title', required=True, help='论文标题')
    parser.add_argument('--paper-id', default='', help='arXiv ID，用于推导年份')
    parser.add_argument('--keywords', default='待补充', help='关键词')
    parser.add_argument('--main-content', default='待分析', help='主要内容摘要')
    parser.add_argument('--score', default='-', help='总分')
    args = parser.parse_args()

    paper_dir = Path(args.paper_dir).resolve()
    if not paper_dir.exists():
        raise FileNotFoundError(f"Paper directory not found: {paper_dir}")

    # 推导 Paper 根目录
    paper_root = None
    if args.vault:
        vault_path = Path(args.vault).resolve()
        vault_paper = vault_path / 'Paper'
        if vault_paper.exists():
            paper_root = vault_paper

    if not paper_root:
        if paper_dir.parent.name == 'Paper':
            paper_root = paper_dir.parent

    if not paper_root:
        vault_path = Path(args.vault).resolve() if args.vault else paper_dir.parent.parent
        for candidate in vault_path.rglob('Paper'):
            if candidate.is_dir():
                try:
                    paper_dir.relative_to(candidate)
                    paper_root = candidate
                    break
                except ValueError:
                    rel = candidate.relative_to(vault_path)
                    if len(rel.parts) <= 2:
                        paper_root = candidate
                        break

    # 确定编号
    has_number_prefix = bool(re.match(r'^(\d+)[-_]', paper_dir.name))
    if has_number_prefix:
        match = re.match(r'^(\d+)[-_]', paper_dir.name)
        next_num = int(match.group(1))
        print(f"Folder already numbered: {paper_dir.name} (using #{next_num})")
    else:
        if paper_root:
            next_num = get_next_number(paper_root)
        else:
            # 没有 Paper 目录时，从同级目录中推断编号
            next_num = get_next_number(paper_dir.parent)

    # 重命名文件夹
    if has_number_prefix:
        new_dir = paper_dir
    else:
        # 去掉名称中可能已有的编号前缀后重新编号
        clean_name = re.sub(r'^(\d+)[-_]', '', paper_dir.name)
        new_name = f"{next_num}_{clean_name}"
        if paper_root:
            new_dir = paper_root / new_name
        else:
            new_dir = paper_dir.parent / new_name
        paper_dir.rename(new_dir)
        print(f"Renamed folder: {paper_dir.name} -> {new_name}")

    # 更新整理大纲（仅在有 Paper 目录时）
    if paper_root:
        catalog_path = paper_root / '整理大纲.md'
        year = extract_year_from_paper_id(args.paper_id)
        append_to_catalog(catalog_path, next_num, args.title, year,
                          args.keywords, args.main_content, args.score)
        print(f"Updated catalog: {catalog_path} (entry #{next_num})")
    else:
        print(f"Paper directory not found, skipped catalog update. Folder renamed in-place.")

    # 输出新目录路径，供调用方更新后续引用
    print(f"new_paper_dir: {new_dir}")


if __name__ == '__main__':
    main()
