#!/usr/bin/env python3
"""
paper-search 的统一检索入口。

实际搜索、打分和 arXiv 查询逻辑复用 start-my-day/scripts/search_arxiv.py，
这里只负责切换到 paper-search 的输出格式。
"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
START_MY_DAY_SCRIPTS = os.path.join(
    os.path.dirname(os.path.dirname(SCRIPT_DIR)),
    'start-my-day',
    'scripts',
)

if START_MY_DAY_SCRIPTS not in sys.path:
    sys.path.insert(0, START_MY_DAY_SCRIPTS)

from search_arxiv import main as search_main


def ensure_cli_defaults() -> None:
    args = sys.argv[1:]

    if '--output-format' not in args:
        sys.argv.extend(['--output-format', 'paper-search'])

    if '--top-n' not in args:
        sys.argv.extend(['--top-n', '25'])

    if '--output' not in args:
        sys.argv.extend(['--output', 'paper_search_candidates.json'])


if __name__ == '__main__':
    ensure_cli_defaults()
    sys.exit(search_main())
