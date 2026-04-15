#!/usr/bin/env python3
"""
扫描现有笔记构建索引
用于 start-my-day skill，扫描 vault 中的现有笔记并构建关键词到笔记路径的映射表
"""

import os
import re
import json
import sys
import argparse
import logging
from pathlib import Path, PurePosixPath
from typing import List, Dict, Set, Tuple, Any
import yaml

from common_words import COMMON_WORDS

logger = logging.getLogger(__name__)


def parse_frontmatter(content: str) -> Dict:
    """
    解析 frontmatter (YAML 格式)

    Args:
        content: markdown 文件内容

    Returns:
        frontmatter 字典
    """
    # 查找 frontmatter 开始和结束标记
    frontmatch = re.match(r'^---\s*\n(.*?)^---\s*\n', content, re.MULTILINE | re.DOTALL)

    if not frontmatch:
        return {}

    try:
        frontmatter_str = frontmatch.group(1)
        frontmatter_data = yaml.safe_load(frontmatter_str)
        return frontmatter_data or {}
    except Exception as e:
        logger.warning("Error parsing frontmatter: %s", e)
        return {}


def extract_keywords_from_title(title: str) -> List[str]:
    """
    从标题中提取关键词

    Args:
        title: 论文标题

    Returns:
        关键词列表
    """
    if not title:
        return []

    keywords = []

    # 主要策略：提取论文的缩写或专有名词（大写开头的词）
    # 例如：从 "BLIP: Bootstrapping..." 提取 "BLIP"
    main_keyword = re.match(r'^([A-Z]{2,})(?:\s*:|\s+)', title)
    if main_keyword:
        keywords.append(main_keyword.group(1))

    # 策略2：提取冒号前的完整标题（如果是缩写+冒号格式）
    colon_match = title.split(':')
    if len(colon_match) >= 2 and len(colon_match[0].strip()) > 2:
        before_colon = colon_match[0].strip()
        # 只添加长度在3-20之间的
        if 3 <= len(before_colon) <= 20:
            keywords.append(before_colon)

    # 策略3：提取带连字符的术语（如 Vision-Language, Fine-Tuning, In-Context）
    # 只匹配明确的技术术语，避免过度分割
    tech_terms = re.findall(r'\b[A-Z][a-z]*(?:-[A-Z][a-z]*)+\b', title)
    for term in tech_terms:
        term_clean = term.strip()
        # 只添加长度在3-20之间的技术术语
        if 3 <= len(term_clean) <= 20:
            # 过滤掉通用词
            if term_clean.lower() not in COMMON_WORDS:
                keywords.append(term_clean)

    # 去重
    keywords = list(dict.fromkeys(keywords))

    return keywords


def normalize_alias(text: str) -> str:
    """将标题/文件名规范化为稳定的轻量别名。"""
    normalized = text.lower()
    normalized = re.sub(r'[\W_]+', ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


def extract_arxiv_ids(*values: Any) -> List[str]:
    """从 frontmatter / 文件名 / 文本片段中提取 arXiv ID。"""
    pattern = re.compile(r'(?:(?:arxiv:)|(?:abs/)|(?:pdf/))?(\d{4}\.\d{4,5})(?:v\d+)?', re.IGNORECASE)
    found: List[str] = []

    def _walk(value: Any):
        if value is None:
            return
        if isinstance(value, str):
            for match in pattern.findall(value):
                found.append(match)
            return
        if isinstance(value, dict):
            for nested in value.values():
                _walk(nested)
            return
        if isinstance(value, (list, tuple, set)):
            for nested in value:
                _walk(nested)

    for value in values:
        _walk(value)

    return list(dict.fromkeys(found))


def build_duplicate_metadata(notes: List[Dict]) -> Dict[str, Any]:
    """构建用于重复论文筛除的稳定索引。"""
    seen_arxiv_ids: Dict[str, List[str]] = {}
    seen_title_aliases: Dict[str, List[str]] = {}
    seen_short_aliases: Dict[str, List[str]] = {}
    note_paths_by_alias: Dict[str, List[str]] = {}

    def _add(mapping: Dict[str, List[str]], key: str, path: str):
        if not key:
            return
        if key not in mapping:
            mapping[key] = []
        if path not in mapping[key]:
            mapping[key].append(path)

    for note in notes:
        path = note.get('path', '')
        for arxiv_id in note.get('arxiv_ids', []):
            _add(seen_arxiv_ids, arxiv_id, path)

        title_alias = note.get('title_alias', '')
        if title_alias:
            _add(seen_title_aliases, title_alias, path)
            _add(note_paths_by_alias, title_alias, path)

        short_alias = note.get('short_name_alias', '')
        if short_alias:
            _add(seen_short_aliases, short_alias, path)
            _add(note_paths_by_alias, short_alias, path)

    return {
        'notes_scanned': len(notes),
        'seen_arxiv_ids': seen_arxiv_ids,
        'seen_title_aliases': seen_title_aliases,
        'seen_short_aliases': seen_short_aliases,
        'note_paths_by_alias': note_paths_by_alias,
    }


def should_exclude_note(md_file: Path, papers_dir: Path) -> bool:
    """排除图片目录和自动生成索引等不应进入论文索引的 markdown。"""
    try:
        rel_path = md_file.relative_to(papers_dir)
    except ValueError:
        return False

    rel_posix = PurePosixPath(rel_path.as_posix())
    parts_lower = [part.lower() for part in rel_posix.parts]
    name_lower = rel_posix.name.lower()

    if 'images' in parts_lower:
        return True
    if name_lower == 'index.md':
        return True
    if name_lower.startswith('tmp_') or name_lower.startswith('temp_'):
        return True
    return False


def scan_notes_directory(papers_dir: Path) -> List[Dict]:
    """
    扫描 Papers 目录下的所有笔记

    Args:
        papers_dir: Papers 目录路径

    Returns:
        笔记列表
    """
    notes = []

    # 递归查找所有 .md 文件
    for md_file in papers_dir.rglob('*.md'):
        if should_exclude_note(md_file, papers_dir):
            continue
        try:
            with open(md_file, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()

            # 解析 frontmatter
            frontmatter = parse_frontmatter(content)

            # 提取信息
            # 计算相对于vault的路径（使用正斜杠）
            rel_path = md_file.relative_to(papers_dir.parent.parent)
            note_info = {
                'path': str(rel_path).replace('\\', '/'),  # 使用正斜杠
                'filename': md_file.name,
                'short_name': md_file.stem,  # 文件名（不含.md扩展名），用于短链接
                'path_str': str(rel_path),  # 添加路径的字符串表示，用于正确编码
                'title': frontmatter.get('title', md_file.stem),
                'tags': frontmatter.get('tags', []),
            }

            note_info['title_alias'] = normalize_alias(note_info['title'])
            note_info['short_name_alias'] = normalize_alias(note_info['short_name'])
            note_info['arxiv_ids'] = extract_arxiv_ids(
                note_info['title'],
                note_info['short_name'],
                frontmatter,
                content,
            )

            # 从标题提取关键词
            title_keywords = extract_keywords_from_title(note_info['title'])
            note_info['title_keywords'] = title_keywords

            # 从 tags 提取关键词（保留有意义的tag）
            tag_keywords = []
            for tag in note_info['tags']:
                if isinstance(tag, list):
                    for sub_tag in tag:
                        if isinstance(sub_tag, str):
                            # 只添加长度3-20的tag，过滤通用词
                            if 3 <= len(sub_tag) <= 20 and sub_tag.lower() not in COMMON_WORDS:
                                tag_keywords.append(sub_tag)
                elif isinstance(tag, str):
                    if 3 <= len(tag) <= 20 and tag.lower() not in COMMON_WORDS:
                        tag_keywords.append(tag)

            note_info['tag_keywords'] = tag_keywords

            notes.append(note_info)

        except Exception as e:
            logger.warning("Error reading %s: %s", md_file, e)
            continue

    return notes


def build_keyword_index(notes: List[Dict]) -> Dict[str, List[str]]:
    """
    构建关键词到笔记路径的映射表

    Args:
        notes: 笔记列表

    Returns:
        关键词映射字典
    """
    # 使用 set 进行去重，避免 O(n) 的 list in 操作
    keyword_sets: Dict[str, set] = {}

    def _add_keyword(keyword_lower: str, path: str):
        if 3 <= len(keyword_lower) <= 30 and keyword_lower not in COMMON_WORDS:
            if keyword_lower not in keyword_sets:
                keyword_sets[keyword_lower] = set()
            keyword_sets[keyword_lower].add(path)

    for note in notes:
        # Only use title-extracted keywords (acronyms, model names) — NOT tags.
        # Tags are organizational labels that appear across many papers (e.g. "evaluation",
        # "faithfulness", "LLM") and must not be linked to a specific paper path.
        for keyword in note['title_keywords']:
            _add_keyword(keyword.lower(), note['path'])
            normalized_keyword = normalize_alias(keyword)
            if normalized_keyword and normalized_keyword != keyword.lower():
                _add_keyword(normalized_keyword, note['path'])

        title_alias = normalize_alias(note.get('title', ''))
        if title_alias:
            _add_keyword(title_alias, note['path'])

        # 使用短名称（文件名）作为关键词，但只添加主要部分
        if 'short_name' in note:
            short_name = note['short_name']
            # 移除版本号和常见后缀
            clean_short = re.sub(r'(-\d{4}\.\d{4,5}|-v\d+)$', '', short_name)

            # 如果清理后的短名称长度合适，添加到索引
            if 3 <= len(clean_short) <= 40 and clean_short.lower() not in COMMON_WORDS:
                _add_keyword(clean_short.lower(), note['path'])
                normalized_short = normalize_alias(clean_short)
                if normalized_short and normalized_short != clean_short.lower():
                    _add_keyword(normalized_short, note['path'])

    # 将 set 转换为 list 输出
    keyword_index = {k: list(v) for k, v in keyword_sets.items()}
    return keyword_index


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Scan existing notes and build keyword index')
    parser.add_argument('--vault', type=str,
                        default=os.environ.get('OBSIDIAN_VAULT_PATH', ''),
                        help='Path to Obsidian vault (or set OBSIDIAN_VAULT_PATH env var)')
    parser.add_argument('--output', type=str, default='existing_notes_index.json',
                        help='Output JSON file path')
    parser.add_argument('--papers-dir', type=str,
                        default='vibe_research/20_Research/Papers',
                        help='Relative path to Papers directory')

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        stream=sys.stderr,
    )

    if not args.vault:
        logger.error("未指定 vault 路径。请通过 --vault 参数或 OBSIDIAN_VAULT_PATH 环境变量设置。")
        sys.exit(1)

    vault_path = Path(args.vault)
    papers_dir = vault_path / args.papers_dir

    if not papers_dir.exists():
        logger.error("Papers directory not found: %s", papers_dir)
        logger.error("Using vault path: %s", vault_path)
        sys.exit(1)

    logger.info("Scanning notes in: %s", papers_dir)

    notes = scan_notes_directory(papers_dir)
    logger.info("Found %d notes", len(notes))

    keyword_index = build_keyword_index(notes)
    logger.info("Built index with %d keywords", len(keyword_index))

    duplicate_metadata = build_duplicate_metadata(notes)
    logger.info(
        "Built duplicate metadata: %d arXiv IDs, %d title aliases",
        len(duplicate_metadata['seen_arxiv_ids']),
        len(duplicate_metadata['seen_title_aliases']),
    )

    # 准备输出
    output = {
        'notes': notes,
        'keyword_to_notes': keyword_index,
        'duplicate_metadata': duplicate_metadata,
    }

    # 保存结果
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    logger.info("Index saved to: %s", args.output)

    logger.info("=== Keyword Index Statistics ===")
    logger.info("Total notes: %d", len(notes))
    logger.info("Total keywords: %d", len(keyword_index))

    if len(keyword_index) > 0:
        logger.info("=== Sample Keywords ===")
        sample_keywords = sorted(keyword_index.items())[:10]
        for keyword, paths in sample_keywords:
            logger.info("  %s: %d notes", keyword, len(paths))


if __name__ == '__main__':
    main()
