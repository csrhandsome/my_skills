#!/usr/bin/env python3
"""
Shared helpers for the vibe research paper workflow.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import urllib.error
import urllib.request


PAPERS_ROOT_RELATIVE = Path("vibe_research") / "20_Research" / "Papers"


def sanitize_paper_title(title: str) -> str:
    return re.sub(r'[ /\\:*?"<>|]+', '_', title or '').strip('_')


def title_to_note_filename(title: str) -> str:
    return sanitize_paper_title(title)


def normalize_title_alias(title: str) -> str:
    normalized = (title or '').lower()
    normalized = re.sub(r'[\W_]+', ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


def get_vault_path(cli_vault: Optional[str] = None, env: Optional[Dict[str, str]] = None) -> str:
    if cli_vault:
        return cli_vault
    env = env or {}
    env_path = env.get('OBSIDIAN_VAULT_PATH')
    if env_path:
        return env_path
    raise ValueError('Missing vault path. Pass --vault or set OBSIDIAN_VAULT_PATH.')


def resolve_paper_dir(vault_root: str, domain: str, title: str) -> Path:
    safe_title = sanitize_paper_title(title)
    safe_domain = domain or '其他'
    return Path(vault_root) / PAPERS_ROOT_RELATIVE / safe_domain / safe_title


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_json_file(path: str | Path, default: Any = None) -> Any:
    file_path = Path(path)
    if not file_path.exists():
        return default
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def write_json_file(path: str | Path, payload: Any) -> None:
    file_path = Path(path)
    ensure_parent_dir(file_path)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)


def build_selected_paper_record(paper: Dict[str, Any], vault_root: Optional[str] = None) -> Dict[str, Any]:
    title = paper.get('title', '')
    record = dict(paper)
    record['note_filename'] = record.get('note_filename') or title_to_note_filename(title)
    record['title_normalized'] = record.get('title_normalized') or normalize_title_alias(title)
    arxiv_id = record.get('arxiv_id') or record.get('arxivId') or ''
    record['paper_id'] = record.get('paper_id') or f"arxiv:{arxiv_id or record['title_normalized']}"
    domain = record.get('matched_domain') or record.get('domain') or '其他'
    record['domain'] = domain
    if vault_root:
        paper_dir = resolve_paper_dir(vault_root, domain, title)
        record['paper_dir'] = str(paper_dir)
        record['pdf_path'] = str(paper_dir / 'paper.pdf')
    return record


def enrich_selected_papers(papers: Iterable[Dict[str, Any]], vault_root: Optional[str] = None) -> List[Dict[str, Any]]:
    return [build_selected_paper_record(paper, vault_root=vault_root) for paper in papers]


def download_file(url: str, output_path: str | Path, timeout: int = 60, user_agent: str = 'VibeResearchWorkflow/1.0') -> Dict[str, Any]:
    destination = Path(output_path)
    ensure_parent_dir(destination)
    request = urllib.request.Request(url, headers={'User-Agent': user_agent})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content = response.read()
            status = getattr(response, 'status', 200)
        with open(destination, 'wb') as f:
            f.write(content)
        return {
            'status': 'downloaded',
            'path': str(destination),
            'bytes': len(content),
            'http_status': status,
        }
    except urllib.error.HTTPError as e:
        return {
            'status': 'error',
            'path': str(destination),
            'error': f'HTTP {e.code}: {e.reason}',
            'http_status': e.code,
        }
    except Exception as e:
        return {
            'status': 'error',
            'path': str(destination),
            'error': str(e),
        }
