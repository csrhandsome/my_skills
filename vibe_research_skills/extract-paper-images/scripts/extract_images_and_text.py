#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified paper asset preparation script.
Reads a paper asset manifest, extracts images and text, and writes prepared_paper_assets.json.
"""

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Dict, List

CURRENT_DIR = Path(__file__).resolve().parent
SKILLS_ROOT = CURRENT_DIR.parent.parent
if str(SKILLS_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLS_ROOT))

from shared_workflow_utils import load_json_file, write_json_file

logger = logging.getLogger(__name__)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.request
    HAS_REQUESTS = False
    logger.warning("requests not found, using urllib")

MINERU_CLI = os.environ.get('MINERU_CLI', 'mineru')
MINERU_BACKEND = os.environ.get('MINERU_BACKEND', 'pipeline')
MINERU_METHOD = os.environ.get('MINERU_METHOD', 'auto')
MINERU_LANG = os.environ.get('MINERU_LANG', 'en')
ALLOWED_IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}
TEXT_SECTION_PATTERNS = [
    (r'^abstract$', 'abstract'),
    (r'^introduction$', 'introduction'),
    (r'^(related work|background)$', 'related_work'),
    (r'^(method|methods|approach|proposed method)$', 'method'),
    (r'^(experiment|experiments|evaluation)$', 'experiments'),
    (r'^(results|main results)$', 'results'),
    (r'^(conclusion|conclusions)$', 'conclusion'),
]


def extract_arxiv_source(arxiv_id, temp_dir):
    source_url = f"https://arxiv.org/e-print/{arxiv_id}"
    logger.info("Downloading arXiv source: %s", source_url)
    try:
        if HAS_REQUESTS:
            response = requests.get(source_url, timeout=60)
            content = response.content if response.status_code == 200 else None
            status = response.status_code
        else:
            try:
                req = urllib.request.urlopen(source_url, timeout=60)
                content = req.read()
                status = req.status
            except urllib.error.HTTPError as http_err:
                logger.error("Source HTTP error %d: %s", http_err.code, http_err.reason)
                return False

        if status == 200 and content:
            tar_path = os.path.join(temp_dir, f"{arxiv_id}.tar.gz")
            with open(tar_path, 'wb') as f:
                f.write(content)
            with tarfile.open(tar_path, 'r:gz') as tar:
                safe_members = []
                for member in tar.getmembers():
                    if member.name.startswith('/') or '..' in member.name:
                        continue
                    if member.issym() or member.islnk():
                        continue
                    safe_members.append(member)
                tar.extractall(path=temp_dir, members=safe_members)
            return True
        return False
    except Exception as e:
        logger.error("Failed to download source package: %s", e)
        return False


def find_figures_from_source(temp_dir):
    figures = []
    seen_files = set()
    figure_dirs = ['pics', 'figures', 'fig', 'images', 'img']
    for fig_dir in figure_dirs:
        fig_path = os.path.join(temp_dir, fig_dir)
        if os.path.exists(fig_path):
            for filename in os.listdir(fig_path):
                file_path = os.path.join(fig_path, filename)
                if os.path.isfile(file_path) and filename not in seen_files:
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in ['.png', '.jpg', '.jpeg', '.pdf', '.eps', '.svg']:
                        seen_files.add(filename)
                        figures.append({
                            'source': 'arxiv-source',
                            'path': file_path,
                            'filename': filename,
                        })
    return figures


def ensure_mineru_available():
    if shutil.which(MINERU_CLI):
        return True
    logger.error("MinerU CLI not found: %s", MINERU_CLI)
    return False


def run_mineru(pdf_path, work_dir):
    if not ensure_mineru_available():
        return None
    output_root = Path(work_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    pdf_path = Path(pdf_path)
    command = [
        MINERU_CLI, '-p', str(pdf_path), '-o', str(output_root), '-b', MINERU_BACKEND, '-m', MINERU_METHOD, '-l', MINERU_LANG,
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("MinerU failed: %s", result.stderr.strip() or result.stdout.strip())
        return None
    parse_dir = output_root / pdf_path.stem / MINERU_METHOD
    if not parse_dir.exists() and MINERU_BACKEND.startswith('hybrid'):
        parse_dir = output_root / pdf_path.stem / f'hybrid_{MINERU_METHOD}'
    if not parse_dir.exists() and MINERU_BACKEND.startswith('vlm'):
        parse_dir = output_root / pdf_path.stem / 'vlm'
    if not parse_dir.exists():
        return None
    return parse_dir


def collect_page_image_refs(middle_json_path):
    try:
        with open(middle_json_path, 'r', encoding='utf-8') as f:
            payload = json.load(f)
    except Exception:
        return {}
    pdf_info = payload.get('pdf_info')
    if not isinstance(pdf_info, list):
        return {}
    refs_by_page = {}

    def walk(node, collector):
        if isinstance(node, dict):
            image_path = node.get('image_path')
            if isinstance(image_path, str) and image_path:
                collector.append(image_path)
            for value in node.values():
                walk(value, collector)
        elif isinstance(node, list):
            for item in node:
                walk(item, collector)

    for page_index, page_data in enumerate(pdf_info, start=1):
        collector = []
        walk(page_data, collector)
        ordered = []
        seen = set()
        for path in collector:
            if path not in seen:
                seen.add(path)
                ordered.append(path)
        refs_by_page[page_index] = ordered
    return refs_by_page


def build_image_index_from_dir(images_dir):
    return [path for path in sorted(images_dir.iterdir()) if path.is_file() and path.suffix.lower() in ALLOWED_IMAGE_EXTS]


def normalize_mineru_outputs(parse_dir, output_dir, prefix_mode='page'):
    images_dir = Path(parse_dir) / 'images'
    if not images_dir.exists():
        return []
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    image_files = build_image_index_from_dir(images_dir)
    refs_by_page = collect_page_image_refs(Path(parse_dir) / f'{Path(parse_dir).parent.name}_middle.json')
    normalized = []
    used = set()
    if prefix_mode == 'page':
        for page_num in sorted(refs_by_page):
            page_refs = refs_by_page[page_num]
            fig_idx = 1
            for rel_path in page_refs:
                src = images_dir / Path(rel_path).name
                if not src.exists() or src in used:
                    continue
                used.add(src)
                ext = src.suffix.lower().lstrip('.') or 'png'
                dest_name = f'page{page_num}_fig{fig_idx}.{ext}'
                dest_path = output_dir / dest_name
                shutil.copy2(src, dest_path)
                normalized.append({
                    'page': page_num,
                    'index': fig_idx,
                    'filename': dest_name,
                    'path': f'images/{dest_name}',
                    'size': dest_path.stat().st_size,
                    'ext': ext,
                })
                fig_idx += 1
    remaining = [path for path in image_files if path not in used]
    if remaining:
        base_name = Path(parse_dir).parent.name
        for idx, src in enumerate(remaining, start=1):
            ext = src.suffix.lower().lstrip('.') or 'png'
            dest_name = f'page0_fig{idx}.{ext}' if prefix_mode == 'page' else f'{base_name}_page{idx}.{ext}'
            dest_path = output_dir / dest_name
            shutil.copy2(src, dest_path)
            normalized.append({
                'filename': dest_name,
                'path': f'images/{dest_name}',
                'size': dest_path.stat().st_size,
                'ext': ext,
            })
    return normalized


def extract_pdf_figures(pdf_path, output_dir, min_bytes=5000):
    with tempfile.TemporaryDirectory() as mineru_dir:
        parse_dir = run_mineru(pdf_path, mineru_dir)
        if parse_dir is None:
            return []
        image_list = normalize_mineru_outputs(parse_dir, output_dir, prefix_mode='page')
    return [item for item in image_list if item['size'] >= min_bytes]


def extract_from_pdf_figures(figures_pdf, output_dir):
    with tempfile.TemporaryDirectory() as mineru_dir:
        parse_dir = run_mineru(figures_pdf, mineru_dir)
        if parse_dir is None:
            return []
        return normalize_mineru_outputs(parse_dir, output_dir, prefix_mode='figure')


def role_from_filename(filename: str) -> str:
    lowered = filename.lower()
    if any(token in lowered for token in ('arch', 'framework', 'pipeline', 'overview', 'method')):
        return 'method'
    if any(token in lowered for token in ('result', 'benchmark', 'performance')):
        return 'results'
    if any(token in lowered for token in ('qualitative', 'case', 'example')):
        return 'qualitative'
    if any(token in lowered for token in ('ablation', 'study')):
        return 'ablation'
    if any(token in lowered for token in ('logo', 'icon')):
        return 'noise'
    return 'unknown'


def split_text_into_sections(text: str) -> Dict[str, str]:
    lines = [line.rstrip() for line in text.splitlines()]
    sections: Dict[str, List[str]] = {'full_text': []}
    current_key = 'full_text'
    for line in lines:
        stripped = line.strip()
        matched_key = None
        for pattern, section_key in TEXT_SECTION_PATTERNS:
            if re.match(pattern, stripped.lower()):
                matched_key = section_key
                break
        if matched_key:
            current_key = matched_key
            sections.setdefault(current_key, [])
            continue
        sections.setdefault(current_key, []).append(line)
    return {key: '\n'.join(value).strip() for key, value in sections.items() if '\n'.join(value).strip()}


def extract_text_outputs(pdf_path: Path, text_dir: Path) -> Dict[str, Any]:
    text_dir.mkdir(parents=True, exist_ok=True)
    raw_text = ''
    method = 'none'
    if ensure_mineru_available():
        with tempfile.TemporaryDirectory() as mineru_dir:
            parse_dir = run_mineru(pdf_path, mineru_dir)
            if parse_dir is not None:
                md_path = Path(parse_dir) / f'{pdf_path.stem}.md'
                if md_path.exists():
                    raw_text = md_path.read_text(encoding='utf-8')
                    method = 'mineru_markdown'
    if not raw_text:
        try:
            import fitz  # type: ignore
            doc = fitz.open(pdf_path)
            raw_text = '\n\n'.join(page.get_text('text') for page in doc)
            method = 'pymupdf_text'
        except Exception as e:
            logger.warning('PyMuPDF text extraction failed for %s: %s', pdf_path, e)
    sections = split_text_into_sections(raw_text)
    full_text_path = text_dir / 'full_text.md'
    sections_path = text_dir / 'sections.json'
    figure_context_path = text_dir / 'figure_context.json'
    full_text_path.write_text(raw_text, encoding='utf-8')
    with open(sections_path, 'w', encoding='utf-8') as f:
        json.dump(sections, f, ensure_ascii=False, indent=2)
    figure_context = []
    for match in re.finditer(r'(figure|fig\.?|table)\s+\d+', raw_text, flags=re.IGNORECASE):
        start = max(0, match.start() - 160)
        end = min(len(raw_text), match.end() + 320)
        figure_context.append({
            'anchor': match.group(0),
            'context': raw_text[start:end].strip(),
        })
    with open(figure_context_path, 'w', encoding='utf-8') as f:
        json.dump(figure_context, f, ensure_ascii=False, indent=2)
    return {
        'full_text_path': str(full_text_path),
        'sections_path': str(sections_path),
        'figure_context_path': str(figure_context_path),
        'extraction_method': method,
        'status': 'ok' if raw_text else 'empty',
    }


def write_image_index(index_path: Path, figures: List[Dict[str, Any]]) -> None:
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write('# 图片索引\n\n')
        f.write(f'总计：{len(figures)} 张图片\n\n')
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for fig in figures:
            grouped.setdefault(fig.get('source', 'unknown'), []).append(fig)
        for source, items in grouped.items():
            f.write(f'## 来源: {source}\n')
            for fig in items:
                f.write(f'- 文件名：{fig["filename"]}\n')
                f.write(f'- 路径：{fig["path"]}\n')
                f.write(f'- 大小：{fig["size"] / 1024:.1f} KB\n')
                f.write(f'- 格式：{fig["ext"]}\n')
                f.write(f'- 角色：{fig.get("role", "unknown")}\n\n')


def prepare_single_paper(paper: Dict[str, Any]) -> Dict[str, Any]:
    paper_dir = Path(paper['paper_dir'])
    pdf_path = Path(paper['pdf_path'])
    images_dir = paper_dir / 'images'
    text_dir = paper_dir / 'text'
    images_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    all_figures: List[Dict[str, Any]] = []
    arxiv_id = paper.get('arxiv_id') or paper.get('arxivId') or ''
    with tempfile.TemporaryDirectory() as temp_dir:
        source_extracted = False
        if arxiv_id:
            source_extracted = extract_arxiv_source(arxiv_id, temp_dir)
            if source_extracted:
                source_figures = find_figures_from_source(temp_dir)
                for fig in source_figures:
                    output_file = images_dir / fig['filename']
                    shutil.copy2(fig['path'], output_file)
                    all_figures.append({
                        'filename': fig['filename'],
                        'path': f'images/{fig["filename"]}',
                        'size': output_file.stat().st_size,
                        'ext': output_file.suffix.lower().lstrip('.'),
                        'source': fig['source'],
                        'role': role_from_filename(fig['filename']),
                    })
        if source_extracted and os.path.exists(temp_dir):
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    if file.endswith('.pdf') and 'logo' not in file.lower() and file != f'{arxiv_id}.tar.gz':
                        extracted = extract_from_pdf_figures(os.path.join(root, file), images_dir)
                        for fig in extracted:
                            fig['source'] = 'pdf-figure'
                            fig['role'] = role_from_filename(fig['filename'])
                            all_figures.append(fig)
        if len(all_figures) < 3 and pdf_path.exists():
            pdf_figures = extract_pdf_figures(pdf_path, images_dir)
            for fig in pdf_figures:
                fig['source'] = 'pdf-extraction'
                fig['role'] = role_from_filename(fig['filename'])
                all_figures.append(fig)

    index_path = images_dir / 'index.md'
    write_image_index(index_path, all_figures)
    text_info = extract_text_outputs(pdf_path, text_dir) if pdf_path.exists() else {
        'full_text_path': str(text_dir / 'full_text.md'),
        'sections_path': str(text_dir / 'sections.json'),
        'figure_context_path': str(text_dir / 'figure_context.json'),
        'extraction_method': 'missing_pdf',
        'status': 'missing_pdf',
    }

    return {
        'paper_id': paper.get('paper_id'),
        'title': paper.get('title'),
        'paper_dir': str(paper_dir),
        'pdf_path': str(pdf_path),
        'images_dir': str(images_dir),
        'images_index_path': str(index_path),
        'images': all_figures,
        'text': text_info,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Extract images and text for prepared paper assets')
    parser.add_argument('--manifest', required=True, help='Path to paper_assets_manifest.json')
    parser.add_argument('--output', default='prepared_paper_assets.json', help='Prepared assets output path')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        stream=sys.stderr,
    )

    manifest = load_json_file(args.manifest)
    if not isinstance(manifest, dict):
        raise ValueError('Manifest must be a JSON object.')
    papers = manifest.get('papers')
    if not isinstance(papers, list):
        raise ValueError('Manifest must contain a papers list.')

    prepared = [prepare_single_paper(paper) for paper in papers]
    payload = {
        'manifest_path': args.manifest,
        'paper_count': len(prepared),
        'papers': prepared,
    }
    write_json_file(args.output, payload)
    logger.info('Prepared multimodal paper assets: %s', args.output)
    print(args.output)
    return 0


if __name__ == '__main__':
    sys.exit(main())
