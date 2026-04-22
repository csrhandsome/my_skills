#!/usr/bin/env python3
"""对 paper-search 产生的候选 JSON 做最终确定性排重。"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def normalize_title_alias(title: str) -> str:
    import re
    normalized = (title or '').lower()
    normalized = re.sub(r'[\W_]+', ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


def title_to_note_filename(title: str) -> str:
    import re
    return re.sub(r'[ /\\:*?"<>|]+', '_', title).strip('_')


def load_json(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f'JSON root must be an object: {path}')
    return data


def match_existing_paper(paper: Dict[str, Any], duplicate_metadata: Dict[str, Any]) -> Dict[str, Any]:
    arxiv_id = paper.get('arxiv_id') or paper.get('arxivId') or ''
    title_alias = normalize_title_alias(paper.get('title', ''))
    note_filename_alias = normalize_title_alias(title_to_note_filename(paper.get('title', '')))

    seen_arxiv_ids = duplicate_metadata.get('seen_arxiv_ids', {}) or {}
    seen_title_aliases = duplicate_metadata.get('seen_title_aliases', {}) or {}
    note_paths_by_alias = duplicate_metadata.get('note_paths_by_alias', {}) or {}

    if arxiv_id and arxiv_id in seen_arxiv_ids:
        return {
            'is_duplicate': True,
            'match_type': 'arxiv_id',
            'matched_note_paths': seen_arxiv_ids.get(arxiv_id, []),
        }

    if title_alias and title_alias in seen_title_aliases:
        return {
            'is_duplicate': True,
            'match_type': 'title_alias',
            'matched_note_paths': seen_title_aliases.get(title_alias, []),
        }

    if note_filename_alias and note_filename_alias in note_paths_by_alias:
        return {
            'is_duplicate': True,
            'match_type': 'note_filename_alias',
            'matched_note_paths': note_paths_by_alias.get(note_filename_alias, []),
        }

    return {
        'is_duplicate': False,
        'match_type': None,
        'matched_note_paths': [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Filter duplicate papers from paper-search candidate JSON')
    parser.add_argument('--input', required=True, help='Input candidate JSON from paper-search')
    parser.add_argument('--existing-index', required=True, help='Path to existing_notes_index.json')
    parser.add_argument('--output', required=True, help='Output filtered JSON path')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        stream=sys.stderr,
    )

    candidate_data = load_json(args.input)
    existing_index = load_json(args.existing_index)
    duplicate_metadata = existing_index.get('duplicate_metadata', {}) or {}

    filtered_candidates = []
    newly_excluded = []

    for paper in candidate_data.get('candidates', []):
        duplicate_status = match_existing_paper(paper, duplicate_metadata)
        paper['duplicate_status'] = duplicate_status
        if duplicate_status['is_duplicate']:
            newly_excluded.append(paper)
        else:
            filtered_candidates.append(paper)

    excluded_duplicates = list(candidate_data.get('excluded_duplicates', [])) + newly_excluded
    candidate_data['candidates'] = filtered_candidates
    candidate_data['excluded_duplicates'] = excluded_duplicates

    filter_summary = candidate_data.get('filter_summary', {})
    previous_post = int(filter_summary.get('post_filtered_duplicates', 0) or 0)
    filter_summary['post_filtered_duplicates'] = previous_post + len(newly_excluded)
    filter_summary['remaining_candidates'] = len(filtered_candidates)
    candidate_data['filter_summary'] = filter_summary

    output_path = Path(args.output)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(candidate_data, f, ensure_ascii=False, indent=2, default=str)

    logger.info('Filtered candidates saved to: %s', output_path)
    logger.info('Remaining candidates: %d', len(filtered_candidates))
    logger.info('Newly excluded duplicates: %d', len(newly_excluded))

    print(json.dumps(candidate_data, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == '__main__':
    sys.exit(main())
