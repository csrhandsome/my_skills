#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
论文图片提取脚本 - 支持从 arXiv 源码包优先提取。
优先级：
1. arXiv 源码包中的 pics/ 或 figures/ 目录（真正的论文图片）
2. 源码包中的 figure PDF，使用 MinerU 提取/检测图片
3. 论文 PDF，使用 MinerU 提取/检测图片（最后备选）
"""

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


def extract_arxiv_source(arxiv_id, temp_dir):
    """下载并提取 arXiv 源码包。"""
    source_url = f"https://arxiv.org/e-print/{arxiv_id}"
    print(f"正在下载arXiv源码包: {source_url}")

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
                logger.error("HTTP错误 %d: %s", http_err.code, http_err.reason)
                return False

        if status == 200 and content:
            tar_path = os.path.join(temp_dir, f"{arxiv_id}.tar.gz")
            with open(tar_path, 'wb') as f:
                f.write(content)
            print(f"源码包已下载: {tar_path}")

            with tarfile.open(tar_path, 'r:gz') as tar:
                safe_members = []
                for member in tar.getmembers():
                    if member.name.startswith('/') or '..' in member.name:
                        continue
                    if member.issym() or member.islnk():
                        continue
                    safe_members.append(member)
                tar.extractall(path=temp_dir, members=safe_members)
            print(f"源码已提取到: {temp_dir}")
            return True

        print(f"下载失败: HTTP {status}")
        return False
    except Exception as e:
        logger.error("下载源码包失败: %s", e)
        return False


def download_arxiv_pdf(arxiv_id, temp_dir):
    """下载 arXiv PDF 作为兜底输入。"""
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    pdf_path = os.path.join(temp_dir, f"{arxiv_id}.pdf")
    print(f"正在下载arXiv PDF: {pdf_url}")

    try:
        if HAS_REQUESTS:
            response = requests.get(pdf_url, timeout=60)
            content = response.content if response.status_code == 200 else None
            status = response.status_code
        else:
            try:
                req = urllib.request.urlopen(pdf_url, timeout=60)
                content = req.read()
                status = req.status
            except urllib.error.HTTPError as http_err:
                logger.error("PDF HTTP错误 %d: %s", http_err.code, http_err.reason)
                return None

        if status != 200 or not content:
            print(f"PDF下载失败: HTTP {status}")
            return None

        with open(pdf_path, 'wb') as f:
            f.write(content)
        print(f"PDF已下载: {pdf_path}")
        return pdf_path
    except Exception as e:
        logger.error("下载 arXiv PDF 失败: %s", e)
        return None


def find_figures_from_source(temp_dir):
    """从源码目录中查找图片（搜索所有匹配的目录）。"""
    figures = []
    seen_files = set()

    figure_dirs = ['pics', 'figures', 'fig', 'images', 'img']

    for fig_dir in figure_dirs:
        fig_path = os.path.join(temp_dir, fig_dir)
        if os.path.exists(fig_path):
            print(f"找到图片目录: {fig_path}")
            for filename in os.listdir(fig_path):
                file_path = os.path.join(fig_path, filename)
                if os.path.isfile(file_path) and filename not in seen_files:
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in ['.png', '.jpg', '.jpeg', '.pdf', '.eps', '.svg']:
                        seen_files.add(filename)
                        figures.append({
                            'type': 'source',
                            'source': 'arxiv-source',
                            'path': file_path,
                            'filename': filename,
                        })

    if not figures:
        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            if os.path.isfile(file_path):
                ext = os.path.splitext(filename)[1].lower()
                if ext in ['.png', '.jpg', '.jpeg'] and 'logo' not in filename.lower() and 'icon' not in filename.lower():
                    figures.append({
                        'type': 'source',
                        'source': 'arxiv-source',
                        'path': file_path,
                        'filename': filename,
                    })

    return figures


def ensure_mineru_available():
    if shutil.which(MINERU_CLI):
        return True
    logger.error("未找到 MinerU CLI: %s", MINERU_CLI)
    logger.error("请先安装 mineru，并确保 `mineru` 命令在当前环境中可用。")
    return False


def run_mineru(pdf_path, work_dir):
    """运行 MinerU 处理单个 PDF，并返回解析目录。"""
    if not ensure_mineru_available():
        return None

    output_root = Path(work_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    pdf_path = Path(pdf_path)

    command = [
        MINERU_CLI,
        '-p',
        str(pdf_path),
        '-o',
        str(output_root),
        '-b',
        MINERU_BACKEND,
        '-m',
        MINERU_METHOD,
        '-l',
        MINERU_LANG,
    ]

    print(f"运行 MinerU: {' '.join(command)}")
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("MinerU 执行失败: %s", result.stderr.strip() or result.stdout.strip())
        return None

    parse_dir = output_root / pdf_path.stem / MINERU_METHOD
    if not parse_dir.exists() and MINERU_BACKEND.startswith('hybrid'):
        parse_dir = output_root / pdf_path.stem / f'hybrid_{MINERU_METHOD}'
    if not parse_dir.exists() and MINERU_BACKEND.startswith('vlm'):
        parse_dir = output_root / pdf_path.stem / 'vlm'

    if not parse_dir.exists():
        logger.error("MinerU 输出目录不存在: %s", parse_dir)
        return None

    return parse_dir


def collect_page_image_refs(middle_json_path):
    """从 MinerU middle.json 中提取按页分组的 image_path。"""
    try:
        with open(middle_json_path, 'r', encoding='utf-8') as f:
            payload = json.load(f)
    except Exception as e:
        logger.warning("读取 middle.json 失败: %s", e)
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
    image_files = []
    for path in sorted(images_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in ALLOWED_IMAGE_EXTS:
            image_files.append(path)
    return image_files


def normalize_mineru_outputs(parse_dir, output_dir, prefix_mode='page'):
    """将 MinerU 输出归一化为当前脚本使用的命名和结构。"""
    images_dir = Path(parse_dir) / 'images'
    if not images_dir.exists():
        logger.warning("MinerU 未生成 images 目录: %s", images_dir)
        return []

    output_dir = Path(output_dir)
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
            if prefix_mode == 'page':
                dest_name = f'page0_fig{idx}.{ext}'
            else:
                dest_name = f'{base_name}_page{idx}.{ext}'
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
    """使用 MinerU 从 PDF 中提取/检测图片（备选方案）。"""
    print("使用 MinerU 从 PDF 提取图片（备选方案）...")

    with tempfile.TemporaryDirectory() as mineru_dir:
        parse_dir = run_mineru(pdf_path, mineru_dir)
        if parse_dir is None:
            return []
        image_list = normalize_mineru_outputs(parse_dir, output_dir, prefix_mode='page')

    filtered = []
    skipped = 0
    for item in image_list:
        if item['size'] < min_bytes:
            skipped += 1
            continue
        filtered.append(item)

    if skipped:
        print(f"  已过滤 {skipped} 张过小图片 (< {min_bytes / 1024:.0f}KB)")

    return filtered


def extract_from_pdf_figures(figures_pdf, output_dir):
    """使用 MinerU 从 figure PDF 中提取图片。"""
    print(f"从 PDF 图片文件提取: {os.path.basename(figures_pdf)}")

    with tempfile.TemporaryDirectory() as mineru_dir:
        parse_dir = run_mineru(figures_pdf, mineru_dir)
        if parse_dir is None:
            return []
        return normalize_mineru_outputs(parse_dir, output_dir, prefix_mode='figure')


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        stream=sys.stderr,
    )

    if len(sys.argv) < 4:
        print("Usage: python extract_images.py <paper_id> <output_dir> <index_file>")
        print("  paper_id: arXiv ID (如: 2510.24701) 或本地PDF路径")
        print("  output_dir: 输出目录")
        print("  index_file: 索引文件路径")
        sys.exit(1)

    paper_input = sys.argv[1]
    output_dir = sys.argv[2]
    index_file = sys.argv[3]

    os.makedirs(output_dir, exist_ok=True)

    is_pdf_file = os.path.isfile(paper_input)
    arxiv_id = None
    pdf_path = None

    if is_pdf_file:
        pdf_path = paper_input
        filename = os.path.basename(pdf_path)
        match = re.search(r'(\d{4}\.\d+)', filename)
        if match:
            arxiv_id = match.group(1)
            print(f"检测到arXiv ID: {arxiv_id}")
    else:
        arxiv_id = paper_input

    with tempfile.TemporaryDirectory() as temp_dir:
        all_figures = []
        source_extracted = False

        if arxiv_id:
            source_extracted = extract_arxiv_source(arxiv_id, temp_dir)
            if source_extracted:
                source_figures = find_figures_from_source(temp_dir)
                if source_figures:
                    print(f"\n从arXiv源码找到 {len(source_figures)} 个图片文件")
                    for fig in source_figures:
                        output_file = os.path.join(output_dir, fig['filename'])
                        shutil.copy2(fig['path'], output_file)

                        all_figures.append({
                            'filename': fig['filename'],
                            'path': f'images/{fig["filename"]}',
                            'size': os.path.getsize(output_file),
                            'ext': os.path.splitext(fig['filename'])[1][1:].lower(),
                            'source': fig['source'],
                        })
                        print(f"  - {fig['filename']}")

        if source_extracted and os.path.exists(temp_dir):
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file.endswith('.pdf') and 'logo' not in file.lower() and file != f'{arxiv_id}.tar.gz':
                        pdf_fig_path = os.path.join(root, file)
                        try:
                            extracted = extract_from_pdf_figures(pdf_fig_path, output_dir)
                            for fig in extracted:
                                fig['source'] = 'pdf-figure'
                                all_figures.append(fig)
                        except Exception as e:
                            logger.warning("  跳过无法处理的PDF: %s (%s)", file, e)

        if len(all_figures) < 3 and not pdf_path and arxiv_id:
            pdf_path = download_arxiv_pdf(arxiv_id, temp_dir)

        if len(all_figures) < 3 and pdf_path:
            print("\n找到的图片数量较少，从PDF直接提取...")
            pdf_figures = extract_pdf_figures(pdf_path, output_dir)
            for fig in pdf_figures:
                fig['source'] = 'pdf-extraction'
                all_figures.append(fig)

    with open(index_file, 'w', encoding='utf-8') as f:
        f.write('# 图片索引\n\n')
        f.write(f'总计：{len(all_figures)} 张图片\n\n')

        sources = {}
        for fig in all_figures:
            source = fig.get('source', 'unknown')
            if source not in sources:
                sources[source] = []
            sources[source].append(fig)

        for source, figs in sources.items():
            f.write(f'\n## 来源: {source}\n')
            for fig in figs:
                f.write(f'- 文件名：{fig["filename"]}\n')
                f.write(f'- 路径：{fig["path"]}\n')
                f.write(f'- 大小：{fig["size"] / 1024:.1f} KB\n')
                f.write(f'- 格式：{fig["ext"]}\n\n')

    print(f'\n成功提取 {len(all_figures)} 张图片')
    print(f'保存目录：{output_dir}')
    print(f'索引文件：{index_file}')
    print('\n图片列表：')
    for fig in all_figures:
        print(f'  - {fig["path"]} ({fig.get("source", "unknown")})')

    print('\nImage paths:')
    for fig in all_figures:
        print(fig['path'])


if __name__ == '__main__':
    main()
