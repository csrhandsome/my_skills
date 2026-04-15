#!/usr/bin/env python3
"""
Prepare paper asset manifests by downloading PDFs for selected papers.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

CURRENT_DIR = Path(__file__).resolve().parent
SKILLS_ROOT = CURRENT_DIR.parent.parent
if str(SKILLS_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLS_ROOT))

from shared_workflow_utils import (
    build_selected_paper_record,
    download_file,
    get_vault_path,
    load_json_file,
    resolve_paper_dir,
    write_json_file,
)

logger = logging.getLogger(__name__)


def load_selected_entries(selected_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    papers = selected_payload.get('papers')
    if isinstance(papers, list):
        return papers
    candidates = selected_payload.get('selected_papers')
    if isinstance(candidates, list):
        return candidates
    raise ValueError('Selected papers payload must contain a papers or selected_papers list.')


def prepare_paper_asset(paper: Dict[str, Any], vault_root: str, force: bool = False) -> Dict[str, Any]:
    prepared = build_selected_paper_record(paper, vault_root=vault_root)
    paper_dir = Path(prepared.get('paper_dir') or resolve_paper_dir(vault_root, prepared.get('domain', '其他'), prepared.get('title', '')))
    paper_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = paper_dir / 'paper.pdf'
    prepared['paper_dir'] = str(paper_dir)
    prepared['pdf_path'] = str(pdf_path)

    pdf_url = prepared.get('pdf_url') or ''
    if not pdf_url:
        arxiv_id = prepared.get('arxiv_id') or prepared.get('arxivId') or ''
        if arxiv_id:
            pdf_url = f'https://arxiv.org/pdf/{arxiv_id}.pdf'
    prepared['pdf_url'] = pdf_url

    if pdf_path.exists() and not force:
        prepared['download_status'] = 'cached'
        prepared['download_bytes'] = pdf_path.stat().st_size
    elif pdf_url:
        result = download_file(pdf_url, pdf_path)
        prepared['download_status'] = result.get('status', 'error')
        prepared['download_bytes'] = result.get('bytes', 0)
        if result.get('error'):
            prepared['download_error'] = result['error']
    else:
        prepared['download_status'] = 'missing_pdf_url'
        prepared['download_error'] = 'No pdf_url available for paper.'

    prepared['images_dir'] = str(paper_dir / 'images')
    prepared['images_index_path'] = str(paper_dir / 'images' / 'index.md')
    prepared['text_dir'] = str(paper_dir / 'text')
    return prepared


def main() -> int:
    parser = argparse.ArgumentParser(description='Download PDFs for selected papers and prepare asset manifests')
    parser.add_argument('--selected', required=True, help='Path to selected_papers.json')
    parser.add_argument('--output', default='paper_assets_manifest.json', help='Output manifest path')
    parser.add_argument('--vault-root', default=None, help='Obsidian vault root')
    parser.add_argument('--force', action='store_true', help='Re-download PDFs even if cached')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        stream=sys.stderr,
    )

    vault_root = get_vault_path(args.vault_root, os.environ)
    selected_payload = load_json_file(args.selected)
    if not isinstance(selected_payload, dict):
        raise ValueError('Selected papers file must contain a JSON object.')

    papers = load_selected_entries(selected_payload)
    prepared_papers = [prepare_paper_asset(paper, vault_root=vault_root, force=args.force) for paper in papers]

    manifest = {
        'selected_path': args.selected,
        'vault_root': vault_root,
        'paper_count': len(prepared_papers),
        'papers': prepared_papers,
    }
    write_json_file(args.output, manifest)

    logger.info('Prepared paper asset manifest: %s', args.output)
    for paper in prepared_papers:
        logger.info('  %s -> %s (%s)', paper.get('paper_id'), paper.get('pdf_path'), paper.get('download_status'))
    print(args.output)
    return 0


if __name__ == '__main__':
    sys.exit(main())
