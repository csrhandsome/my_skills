#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Paper analyze orchestration entrypoint.
This script is the only supported execution path for the paper-analyze skill.
"""

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

CURRENT_DIR = Path(__file__).resolve().parent
SKILLS_ROOT = CURRENT_DIR.parent.parent
EXTRACT_IMAGES_SCRIPT = SKILLS_ROOT / "extract-paper-images" / "scripts" / "extract_images.py"
GENERATE_NOTE_SCRIPT = CURRENT_DIR / "generate_note.py"
UPDATE_GRAPH_SCRIPT = CURRENT_DIR / "update_graph.py"


def get_vault_path(cli_vault=None):
    if cli_vault:
        return Path(cli_vault).expanduser().resolve()
    env_path = os.environ.get("OBSIDIAN_VAULT_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()
    raise RuntimeError("未指定 vault 路径。请通过 --vault 参数或 OBSIDIAN_VAULT_PATH 环境变量设置。")


def detect_language(vault_root, cli_language=None):
    if cli_language:
        return cli_language

    pref_path = vault_root / "vibe_research" / "research_preference" / "preference.md"
    if not pref_path.exists():
        return "zh"

    try:
        content = pref_path.read_text(encoding="utf-8")
    except OSError:
        return "zh"

    match = re.search(r'^\s*language:\s*"?([a-z]{2})"?', content, re.MULTILINE | re.IGNORECASE)
    if match:
        language = match.group(1).lower()
        if language in {"zh", "en"}:
            return language
    return "zh"


def normalize_paper_id(value):
    if not value:
        return ""
    paper_id = value.strip()
    if paper_id.lower().startswith("arxiv:"):
        paper_id = paper_id.split(":", 1)[1].strip()
    return paper_id


def sanitize_title(title):
    safe = re.sub(r'[ /\\:*?"<>|]+', "_", title).strip("_")
    return safe or "untitled_paper"


def resolve_pdf_path(value):
    if not value:
        return None

    path = Path(value).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    else:
        path = path.resolve()

    if not path.is_file():
        raise RuntimeError(f"本地 PDF 不存在: {path}")
    return path


def download_arxiv_pdf(paper_id, work_dir):
    if not paper_id:
        return None

    pdf_url = f"https://arxiv.org/pdf/{paper_id}.pdf"
    pdf_path = work_dir / f"{paper_id}.pdf"
    logger.info("下载 arXiv PDF: %s", pdf_url)

    try:
        with urllib.request.urlopen(pdf_url, timeout=60) as resp:
            data = resp.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"下载 PDF 失败: HTTP {exc.code}") from exc
    except OSError as exc:
        raise RuntimeError(f"下载 PDF 失败: {exc}") from exc

    pdf_path.write_bytes(data)
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        raise RuntimeError(f"下载 PDF 后文件为空: {pdf_path}")
    return pdf_path


def ensure_tool_exists(tool_name):
    if shutil.which(tool_name):
        return
    raise RuntimeError(f"未找到必需命令: {tool_name}")


def shlex_quote(text):
    if re.fullmatch(r"[A-Za-z0-9_./:=+-]+", text):
        return text
    return "'" + text.replace("'", "'\"'\"'") + "'"


def run_command(label, command, cwd=None):
    printable = " ".join(shlex_quote(part) for part in command)
    logger.info("[%s] %s", label, printable)
    result = subprocess.run(command, cwd=str(cwd) if cwd else None)
    if result.returncode != 0:
        raise RuntimeError(f"{label} 执行失败，退出码 {result.returncode}")


def find_markdown_output(extract_dir, pdf_stem):
    candidate = extract_dir / f"{pdf_stem}.md"
    if candidate.exists():
        return candidate

    markdown_files = sorted(extract_dir.glob("*.md"))
    if markdown_files:
        return markdown_files[0]
    return None


def count_images_from_index(index_path):
    if not index_path.exists():
        return -1
    try:
        content = index_path.read_text(encoding="utf-8")
    except OSError:
        return -1
    match = re.search(r"总计：(\d+) 张图片", content)
    if match:
        return int(match.group(1))
    return -1


def find_existing_note(notes_root, paper_id, title):
    if not notes_root.exists():
        return None

    title_safe = sanitize_title(title) if title else ""
    paper_id_candidates = {paper_id, f"arXiv:{paper_id}"} if paper_id else set()

    for note_path in notes_root.rglob("*.md"):
        if title_safe and note_path.stem == title_safe:
            return note_path

        if not paper_id_candidates:
            continue

        try:
            frontmatter = note_path.read_text(encoding="utf-8")
        except OSError:
            continue

        match = re.search(r'^paper_id:\s*"?([^"\n]+)"?', frontmatter, re.MULTILINE)
        if match and match.group(1).strip() in paper_id_candidates:
            return note_path

    return None


def write_manifest(manifest_path, payload):
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def copy_file_to(src_path, dst_path):
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    if src_path.resolve() != dst_path.resolve():
        shutil.copy2(src_path, dst_path)
    return dst_path


def sync_directory(src_dir, dst_dir):
    if not src_dir.exists():
        return None
    dst_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
    return dst_dir


def prepare_daily_workspace(vault_root, title, note_path, images_dir, pdf_path, keep_local_pdf):
    date_str = datetime.now().strftime("%Y-%m-%d")
    daily_root = vault_root / "vibe_research" / "10_Daily"
    daily_dir = daily_root / f"{date_str}_{sanitize_title(title)}"
    daily_dir.mkdir(parents=True, exist_ok=True)

    daily_report_path = copy_file_to(note_path, daily_dir / note_path.name)
    daily_images_dir = sync_directory(images_dir, daily_dir / "images")

    daily_pdf_path = None
    if keep_local_pdf and pdf_path.exists():
        daily_pdf_path = copy_file_to(pdf_path, daily_dir / pdf_path.name)

    return {
        "daily_dir": daily_dir,
        "daily_report_path": daily_report_path,
        "daily_images_dir": daily_images_dir or (daily_dir / "images"),
        "daily_pdf_path": daily_pdf_path,
    }


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

    parser = argparse.ArgumentParser(description="执行 paper-analyze 的强制编排入口")
    parser.add_argument("paper_input", nargs="?", default="", help="可选：arXiv ID 或本地 PDF 路径")
    parser.add_argument("--paper-id", default="", help="论文 arXiv ID")
    parser.add_argument("--pdf-path", default="", help="本地 PDF 路径")
    parser.add_argument("--title", default="", help="论文标题")
    parser.add_argument("--authors", default="", help="论文作者")
    parser.add_argument("--domain", default="", help="论文领域")
    parser.add_argument("--vault", default=None, help="Obsidian vault 路径")
    parser.add_argument("--language", default=None, choices=["zh", "en"], help="输出语言")
    parser.add_argument("--mineru-language", default="en", help="MinerU 文档语言参数")
    parser.add_argument("--timeout", type=int, default=1800, help="MinerU extract 超时时间")
    parser.add_argument("--score", type=float, default=0.0, help="知识图谱分数")
    parser.add_argument("--work-dir", default="/tmp/paper_analysis", help="临时工作目录")
    parser.add_argument("--related", nargs="*", default=[], help="相关论文 ID")
    parser.add_argument("--skip-graph", action="store_true", help="跳过图谱更新")
    args = parser.parse_args()

    paper_id = normalize_paper_id(args.paper_id)
    paper_input = args.paper_input.strip()

    if paper_input:
        candidate = Path(paper_input).expanduser()
        if candidate.is_file() or (not candidate.is_absolute() and (Path.cwd() / candidate).is_file()):
            args.pdf_path = paper_input
        elif not paper_id:
            paper_id = normalize_paper_id(paper_input)

    vault_root = get_vault_path(args.vault)
    language = detect_language(vault_root, args.language)
    notes_root = vault_root / "vibe_research" / "20_Research" / "Papers"
    work_dir = Path(args.work_dir).expanduser().resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    local_pdf_input = bool(args.pdf_path)

    pdf_path = resolve_pdf_path(args.pdf_path) if args.pdf_path else None
    run_id = paper_id or (pdf_path.stem if pdf_path else "paper_analyze")
    run_root = work_dir / sanitize_title(run_id)
    run_root.mkdir(parents=True, exist_ok=True)

    if pdf_path is None:
        if not paper_id:
            raise RuntimeError("必须提供 --pdf-path、本地 PDF 路径，或 --paper-id。")
        pdf_path = download_arxiv_pdf(paper_id, run_root)

    ensure_tool_exists("mineru-open-api")

    title = args.title.strip() or pdf_path.stem or paper_id or ("未命名论文" if language == "zh" else "Untitled Paper")
    authors = args.authors.strip() or ("待定作者" if language == "zh" else "Unknown Authors")
    domain = args.domain.strip() or ("其他" if language == "zh" else "Other")

    existing_note = find_existing_note(notes_root, paper_id, title)
    note_path = existing_note

    extract_dir = run_root / "mineru_extract"
    run_command(
        "mineru_extract",
        [
            "mineru-open-api",
            "extract",
            str(pdf_path),
            "-o",
            str(extract_dir),
            "--language",
            args.mineru_language,
            "--timeout",
            str(args.timeout),
        ],
    )

    markdown_path = find_markdown_output(extract_dir, pdf_path.stem)
    if markdown_path is None:
        raise RuntimeError(f"MinerU 未生成 markdown 文件: {extract_dir}")

    if note_path is None:
        run_command(
            "generate_note",
            [
                sys.executable,
                str(GENERATE_NOTE_SCRIPT),
                "--paper-id",
                paper_id or pdf_path.stem,
                "--title",
                title,
                "--authors",
                authors,
                "--domain",
                domain,
                "--vault",
                str(vault_root),
                "--language",
                language,
            ],
        )
        note_path = notes_root / domain / f"{sanitize_title(title)}.md"
        if not note_path.exists():
            raise RuntimeError(f"笔记生成后未找到输出文件: {note_path}")
    else:
        logger.info("复用已有笔记: %s", note_path)

    note_root = note_path.with_suffix("")
    images_dir = note_root / "images"
    index_path = images_dir / "index.md"
    image_input = paper_id or str(pdf_path)

    run_command(
        "extract_images",
        [
            sys.executable,
            str(EXTRACT_IMAGES_SCRIPT),
            image_input,
            str(images_dir),
            str(index_path),
        ],
    )

    image_count = count_images_from_index(index_path)
    if image_count == 0 and paper_id and pdf_path:
        logger.warning("按 arXiv ID 提图结果为空，回退到本地 PDF 再试一次。")
        run_command(
            "extract_images_pdf_fallback",
            [
                sys.executable,
                str(EXTRACT_IMAGES_SCRIPT),
                str(pdf_path),
                str(images_dir),
                str(index_path),
            ],
        )
        image_count = count_images_from_index(index_path)

    if not index_path.exists():
        raise RuntimeError(f"图片索引未生成: {index_path}")

    graph_path = vault_root / "vibe_research" / "20_Research" / "PaperGraph" / "graph_data.json"
    if not args.skip_graph:
        graph_command = [
            sys.executable,
            str(UPDATE_GRAPH_SCRIPT),
            "--paper-id",
            paper_id or pdf_path.stem,
            "--title",
            title,
            "--domain",
            domain,
            "--score",
            str(args.score),
            "--vault",
            str(vault_root),
            "--language",
            language,
        ]
        if args.related:
            graph_command.extend(["--related", *args.related])
        run_command("update_graph", graph_command)
        if not graph_path.exists():
            raise RuntimeError(f"图谱文件未生成: {graph_path}")

    daily_outputs = prepare_daily_workspace(
        vault_root=vault_root,
        title=title,
        note_path=note_path,
        images_dir=images_dir,
        pdf_path=pdf_path,
        keep_local_pdf=local_pdf_input,
    )

    manifest = {
        "paper_id": paper_id or pdf_path.stem,
        "pdf_path": str(pdf_path),
        "input_mode": "local_pdf" if local_pdf_input else "downloaded_pdf",
        "search_policy": "prefer_local_allow_external" if local_pdf_input else "allow_external_if_needed",
        "language": language,
        "domain": domain,
        "title": title,
        "authors": authors,
        "markdown_path": str(markdown_path),
        "note_path": str(note_path),
        "images_dir": str(images_dir),
        "index_path": str(index_path),
        "image_count": image_count,
        "graph_path": str(graph_path) if graph_path.exists() else "",
        "daily_dir": str(daily_outputs["daily_dir"]),
        "daily_report_path": str(daily_outputs["daily_report_path"]),
        "daily_images_dir": str(daily_outputs["daily_images_dir"]),
        "daily_pdf_path": str(daily_outputs["daily_pdf_path"]) if daily_outputs["daily_pdf_path"] else "",
    }
    manifest_path = run_root / "analysis_run.json"
    write_manifest(manifest_path, manifest)
    daily_manifest_path = daily_outputs["daily_dir"] / "analysis_run.json"
    write_manifest(daily_manifest_path, manifest)

    print(f"analysis_run.json: {manifest_path}")
    print(f"markdown_path: {markdown_path}")
    print(f"note_path: {note_path}")
    print(f"index_path: {index_path}")
    print(f"image_count: {image_count}")
    print(f"daily_dir: {daily_outputs['daily_dir']}")
    print(f"daily_report_path: {daily_outputs['daily_report_path']}")
    print(f"daily_images_dir: {daily_outputs['daily_images_dir']}")
    if daily_outputs["daily_pdf_path"]:
        print(f"daily_pdf_path: {daily_outputs['daily_pdf_path']}")
    print(f"daily_manifest_path: {daily_manifest_path}")
    if not args.skip_graph:
        print(f"graph_path: {graph_path}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        logger.error("%s", exc)
        sys.exit(1)
