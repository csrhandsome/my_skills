#!/usr/bin/env python3
"""
arXiv + Semantic Scholar 混合架构论文搜索脚本
用于 start-my-day skill，搜索最近一个月和最近一年的极火、极热门、极优质论文
"""

import xml.etree.ElementTree as ET
import json
import re
import os
import sys
import time
import random
import logging
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import List, Dict, Set, Optional, Tuple, Any
from pathlib import Path
import urllib.request
import urllib.parse
import urllib.error

logger = logging.getLogger(__name__)


def title_to_note_filename(title: str) -> str:
    """将论文标题转换为 Obsidian 笔记文件名（与 generate_note.py 保持一致）。

    使用与 paper-analyze/scripts/generate_note.py 完全相同的规则，
    确保 start-my-day 生成的 wikilink 路径能正确指向 paper-analyze 创建的文件。
    """
    filename = re.sub(r'[ /\\:*?"<>|]+', '_', title).strip('_')
    return filename


def normalize_arxiv_id(value: Optional[str]) -> Optional[str]:
    """统一 arXiv ID 表示，去掉前缀和版本号。"""
    if not value:
        return None

    match = ARXIV_ID_RE.search(str(value))
    if not match:
        return None
    return match.group(1)


def normalize_title_alias(text: str) -> str:
    """将标题/文件名归一化为稳定的轻量别名。"""
    return re.sub(r'\s+', ' ', re.sub(r'[\W_]+', ' ', (text or '').lower())).strip()


def build_arxiv_query(categories: List[str], start_date: datetime, end_date: datetime) -> str:
    category_query = " OR ".join([f"cat:{cat}" for cat in categories])
    date_query = f"submittedDate:[{start_date.strftime('%Y%m%d')}0000 TO {end_date.strftime('%Y%m%d')}2359]"
    return f"({category_query}) AND {date_query}"


def arxiv_result_to_paper(result: Any) -> Dict[str, Any]:
    """将 `arxiv` 库的 Result 对象转换为现有工作流使用的论文结构。"""
    arxiv_id = normalize_arxiv_id(result.get_short_id())
    published = result.published
    updated = result.updated

    paper = {
        'id': result.entry_id,
        'arxiv_id': arxiv_id,
        'title': ' '.join((result.title or '').split()),
        'summary': ' '.join((result.summary or '').split()),
        'authors': [author.name for author in result.authors],
        'affiliations': [],
        'published': published.isoformat() if published else None,
        'published_date': published,
        'updated': updated.isoformat() if updated else None,
        'categories': list(result.categories or []),
        'pdf_url': result.pdf_url,
        'url': result.entry_id,
        'source': 'arxiv',
    }
    return paper


def build_empty_existing_corpus(index_path: Optional[str] = None) -> Dict[str, Any]:
    return {
        'notes_scanned': 0,
        'seen_arxiv_ids': set(),
        'seen_title_aliases': set(),
        'note_paths_by_alias': {},
        'note_paths_by_arxiv_id': {},
        'index_path': index_path,
    }


def load_existing_corpus(index_path: Optional[str]) -> Dict[str, Any]:
    """加载已有笔记索引，用于搜索前排重。"""
    corpus = build_empty_existing_corpus(index_path=index_path)
    if not index_path:
        return corpus

    with open(index_path, 'r', encoding='utf-8') as f:
        index_data = json.load(f) or {}

    notes = index_data.get('notes', []) or []
    seen_arxiv_ids = set(index_data.get('seen_arxiv_ids', []) or [])
    seen_title_aliases = set(index_data.get('seen_title_aliases', []) or [])

    note_paths_by_alias = {
        alias: list(paths)
        for alias, paths in (index_data.get('note_paths_by_alias', {}) or {}).items()
    }
    note_paths_by_arxiv_id = {
        arxiv_id: list(paths)
        for arxiv_id, paths in (index_data.get('note_paths_by_arxiv_id', {}) or {}).items()
    }

    for note in notes:
        path = note.get('path')
        if not path:
            continue

        alias_candidates = set(note.get('aliases', []) or [])
        for raw_alias in (
            note.get('title_alias'),
            note.get('short_name_alias'),
            note.get('title'),
            note.get('short_name'),
            Path(str(note.get('filename', '') or '')).stem,
        ):
            alias = normalize_title_alias(str(raw_alias or ''))
            if alias:
                alias_candidates.add(alias)

        for alias in alias_candidates:
            seen_title_aliases.add(alias)
            note_paths_by_alias.setdefault(alias, [])
            if path not in note_paths_by_alias[alias]:
                note_paths_by_alias[alias].append(path)

        arxiv_id_candidates = set(note.get('arxiv_ids', []) or [])
        for raw_value in (
            note.get('title'),
            note.get('short_name'),
            note.get('filename'),
            note.get('path'),
        ):
            arxiv_id = normalize_arxiv_id(raw_value)
            if arxiv_id:
                arxiv_id_candidates.add(arxiv_id)

        for arxiv_id in arxiv_id_candidates:
            seen_arxiv_ids.add(arxiv_id)
            note_paths_by_arxiv_id.setdefault(arxiv_id, [])
            if path not in note_paths_by_arxiv_id[arxiv_id]:
                note_paths_by_arxiv_id[arxiv_id].append(path)

    corpus.update(
        {
            'notes_scanned': len(notes),
            'seen_arxiv_ids': seen_arxiv_ids,
            'seen_title_aliases': seen_title_aliases,
            'note_paths_by_alias': note_paths_by_alias,
            'note_paths_by_arxiv_id': note_paths_by_arxiv_id,
        }
    )
    return corpus


def mark_duplicate_status(paper: Dict[str, Any], existing_corpus: Dict[str, Any]) -> Dict[str, Any]:
    """标记论文是否已在当前知识库中存在。"""
    arxiv_id = normalize_arxiv_id(paper.get('arxiv_id') or paper.get('arxivId'))
    title_alias = normalize_title_alias(paper.get('title', ''))
    note_filename_alias = normalize_title_alias(title_to_note_filename(paper.get('title', '')))

    duplicate_status = {
        'is_duplicate': False,
        'match_type': None,
        'matched_note_paths': [],
    }

    if arxiv_id and arxiv_id in existing_corpus['seen_arxiv_ids']:
        duplicate_status['is_duplicate'] = True
        duplicate_status['match_type'] = 'arxiv_id'
        duplicate_status['matched_note_paths'] = sorted(
            existing_corpus['note_paths_by_arxiv_id'].get(arxiv_id, [])
        )
    elif title_alias and title_alias in existing_corpus['seen_title_aliases']:
        duplicate_status['is_duplicate'] = True
        duplicate_status['match_type'] = 'title_alias'
        duplicate_status['matched_note_paths'] = sorted(
            existing_corpus['note_paths_by_alias'].get(title_alias, [])
        )
    elif note_filename_alias and note_filename_alias in existing_corpus['seen_title_aliases']:
        duplicate_status['is_duplicate'] = True
        duplicate_status['match_type'] = 'note_filename'
        duplicate_status['matched_note_paths'] = sorted(
            existing_corpus['note_paths_by_alias'].get(note_filename_alias, [])
        )

    paper['duplicate_status'] = duplicate_status
    return paper


def deduplicate_candidate_pool(papers: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """合并 recent/hot 结果时做稳定去重。"""
    seen_ids = set()
    seen_titles = set()
    unique_papers = []
    removed = 0

    for paper in papers:
        arxiv_id = normalize_arxiv_id(paper.get('arxiv_id') or paper.get('arxivId'))
        title_alias = normalize_title_alias(paper.get('title', ''))

        if arxiv_id:
            if arxiv_id in seen_ids:
                removed += 1
                continue
            seen_ids.add(arxiv_id)

        if title_alias:
            if title_alias in seen_titles:
                removed += 1
                continue
            seen_titles.add(title_alias)

        if arxiv_id:
            paper['arxiv_id'] = arxiv_id
        unique_papers.append(paper)

    return unique_papers, removed


def split_existing_duplicates(
    papers: List[Dict[str, Any]], existing_corpus: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """用已有笔记索引做搜索前排重。"""
    if not existing_corpus['index_path']:
        for paper in papers:
            mark_duplicate_status(paper, existing_corpus)
        return papers, []

    kept: List[Dict[str, Any]] = []
    excluded: List[Dict[str, Any]] = []

    for paper in papers:
        annotated = mark_duplicate_status(paper, existing_corpus)
        if annotated['duplicate_status']['is_duplicate']:
            excluded.append(annotated)
        else:
            kept.append(annotated)

    return kept, excluded

try:
    import requests
    HAS_REQUESTS = True
    S2_SESSION = requests.Session()
except ImportError:
    HAS_REQUESTS = False
    S2_SESSION = None
    logger.warning("requests library not found, using urllib for Semantic Scholar API")

try:
    import arxiv
    HAS_ARXIV = True
except ImportError:
    arxiv = None
    HAS_ARXIV = False
    logger.warning("arxiv library not found, install it with `uv add arxiv` or `pip install arxiv`")

# ---------------------------------------------------------------------------
# API 配置
# ---------------------------------------------------------------------------
ARXIV_NS = {
    'atom': 'http://www.w3.org/2005/Atom',
    'arxiv': 'http://arxiv.org/schemas/atom'
}
DEFAULT_PREFERENCE_RELATIVE_PATH = os.path.join(
    'vibe_research', 'research_preference', 'preference.md'
)

SEMANTIC_SCHOLAR_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
SEMANTIC_SCHOLAR_FIELDS = "title,abstract,publicationDate,citationCount,influentialCitationCount,url,authors,authors.affiliations,externalIds"
OPENALEX_API_URL = "https://api.openalex.org/works"
ARXIV_ID_RE = re.compile(r'(?<!\d)(\d{4}\.\d{4,5})(?:v\d+)?(?!\d)', re.IGNORECASE)
ARXIV_PAGE_SIZE = 100
ARXIV_REQUEST_DELAY_SECONDS = 3.0

# 默认分类关键词映射（当配置中无用户自定义关键词时使用）
ARXIV_CATEGORY_KEYWORDS = {
    "cs.AI": "artificial intelligence",
    "cs.LG": "machine learning",
    "cs.CL": "computational linguistics natural language processing",
    "cs.CV": "computer vision",
    "cs.MM": "multimedia",
    "cs.MA": "multi-agent systems",
    "cs.RO": "robotics"
}

# ---------------------------------------------------------------------------
# 评分常量  —— 修改权重时只需编辑这里
# ---------------------------------------------------------------------------

# 各维度原始评分的满分值（归一化基准）
SCORE_MAX = 3.0

# 相关性评分：关键词在标题 / 摘要中匹配的加分
RELEVANCE_TITLE_KEYWORD_BOOST = 0.5
RELEVANCE_SUMMARY_KEYWORD_BOOST = 0.3
RELEVANCE_CATEGORY_MATCH_BOOST = 1.0
RELEVANCE_PRIORITY_BOOST_PER_LEVEL = 0.05
# 相关性准入阈值（避免弱相关论文仅靠热门度上榜）
MIN_RELEVANCE_THRESHOLD = 0.8

# 新近性阈值（天） -> 对应评分
RECENCY_THRESHOLDS = [
    (30, 3.0),
    (90, 2.0),
    (180, 1.0),
]
RECENCY_DEFAULT = 0.0

# 热门度：高影响力引用数归一化到 0-SCORE_MAX
# 含义：达到此引用数时视为满分
POPULARITY_INFLUENTIAL_CITATION_FULL_SCORE = 100

# 综合推荐评分权重（普通论文）
WEIGHTS_NORMAL = {
    'relevance': 0.40,
    'recency': 0.20,
    'popularity': 0.30,
    'quality': 0.10,
}
# 综合推荐评分权重（高影响力论文：保持相关性优先，避免仅凭热门度上榜）
WEIGHTS_HOT = {
    'relevance': 0.50,
    'recency': 0.10,
    'popularity': 0.30,
    'quality': 0.10,
}

# Semantic Scholar 速率限制等待时间（秒）
S2_RATE_LIMIT_WAIT = 30
S2_CATEGORY_REQUEST_INTERVAL = 3
S2_AUTH_MIN_INTERVAL = 1.2
S2_UNAUTH_MIN_INTERVAL = 4.0
S2_MAX_RETRY_WAIT = 120
S2_JITTER_MAX = 0.5
S2_REQUEST_TIMEOUT = 15

# Semantic Scholar API Key（可选，从配置文件读取）
S2_API_KEY = None
S2_LAST_REQUEST_TS = 0.0


def load_research_config(config_path: str) -> Dict:
    """
    从 YAML 文件加载研究兴趣配置

    Args:
        config_path: 配置文件路径

    Returns:
        研究配置字典
    """
    import yaml

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f) or {}

    # 读取 Semantic Scholar API Key（如果配置了）
    set_semantic_scholar_api_key(config.get('semantic_scholar_api_key'))

    research_domains = config.get('research_domains')
    if not isinstance(research_domains, dict) or not research_domains:
        raise ValueError(
            f"Invalid preference config: 'research_domains' is required and must be a non-empty mapping ({config_path})"
        )

    return config


def set_semantic_scholar_api_key(api_key: Optional[str] = None) -> Optional[str]:
    """设置 Semantic Scholar API Key，优先使用配置，其次读取环境变量。"""
    global S2_API_KEY

    resolved = api_key or os.environ.get('SEMANTIC_SCHOLAR_API_KEY')
    if isinstance(resolved, str):
        resolved = resolved.strip()
    S2_API_KEY = resolved or None
    return S2_API_KEY


def get_s2_request_interval() -> float:
    """带 API key 时按 1 req/s 保守控制，无 key 时进一步放慢。"""
    return S2_AUTH_MIN_INTERVAL if S2_API_KEY else S2_UNAUTH_MIN_INTERVAL


def build_s2_headers(user_agent: str) -> Dict[str, str]:
    headers = {"User-Agent": user_agent}
    if S2_API_KEY:
        headers["x-api-key"] = S2_API_KEY
    return headers


def parse_retry_after_seconds(retry_after: Optional[str]) -> Optional[float]:
    """解析 Retry-After 头，兼容秒数和 HTTP 日期。"""
    if not retry_after:
        return None

    retry_after = retry_after.strip()
    try:
        return max(float(retry_after), 0.0)
    except ValueError:
        pass

    try:
        retry_dt = parsedate_to_datetime(retry_after)
        wait_seconds = (retry_dt - datetime.now(retry_dt.tzinfo)).total_seconds()
        return max(wait_seconds, 0.0)
    except Exception:
        return None


def wait_for_s2_slot() -> None:
    """全局串行限速，避免不同调用点彼此打架。"""
    interval = get_s2_request_interval()
    if S2_LAST_REQUEST_TS <= 0:
        return

    elapsed = time.monotonic() - S2_LAST_REQUEST_TS
    if elapsed < interval:
        time.sleep(interval - elapsed)


def mark_s2_request_sent() -> None:
    global S2_LAST_REQUEST_TS
    S2_LAST_REQUEST_TS = time.monotonic()


def compute_s2_backoff(
    attempt: int,
    status_code: Optional[int] = None,
    retry_after: Optional[float] = None,
) -> float:
    if retry_after is not None and retry_after > 0:
        return min(retry_after, S2_MAX_RETRY_WAIT)
    if status_code == 429:
        return min(S2_RATE_LIMIT_WAIT + attempt * 15, S2_MAX_RETRY_WAIT)
    return min((2 ** attempt) * 2, S2_MAX_RETRY_WAIT)


def semantic_scholar_request(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    timeout: int = S2_REQUEST_TIMEOUT,
    max_retries: int = 3,
) -> Any:
    """
    Semantic Scholar 请求封装：
    - 全局限速
    - 尊重 Retry-After
    - 429 / 5xx 指数退避 + jitter
    """
    method = method.upper()
    request_headers = dict(headers or {})
    if "User-Agent" not in request_headers:
        request_headers["User-Agent"] = "SemanticScholarClient/1.0"
    if S2_API_KEY and "x-api-key" not in request_headers:
        request_headers["x-api-key"] = S2_API_KEY

    last_error = None

    for attempt in range(max_retries):
        wait_for_s2_slot()
        try:
            if HAS_REQUESTS:
                response = S2_SESSION.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    headers=request_headers,
                    timeout=timeout,
                )
                mark_s2_request_sent()

                if response.status_code == 429 and attempt < max_retries - 1:
                    retry_after = parse_retry_after_seconds(response.headers.get("Retry-After"))
                    wait_time = compute_s2_backoff(
                        attempt,
                        status_code=429,
                        retry_after=retry_after,
                    ) + random.uniform(0, S2_JITTER_MAX)
                    logger.warning("[S2] 429 received. Waiting %.1f seconds before retry...", wait_time)
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                return response.json()

            request_url = url
            if params:
                query_string = urllib.parse.urlencode(params)
                separator = '&' if '?' in request_url else '?'
                request_url = f"{request_url}{separator}{query_string}"

            request_data = None
            if json_body is not None:
                request_data = json.dumps(json_body).encode('utf-8')
                request_headers.setdefault("Content-Type", "application/json")

            request = urllib.request.Request(
                request_url,
                data=request_data,
                headers=request_headers,
                method=method,
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                mark_s2_request_sent()
                return json.loads(response.read().decode('utf-8'))

        except urllib.error.HTTPError as e:
            mark_s2_request_sent()
            last_error = e
            retry_after = parse_retry_after_seconds(e.headers.get("Retry-After")) if e.headers else None
            is_retryable = e.code in (429, 500, 502, 503, 504)
            if is_retryable and attempt < max_retries - 1:
                wait_time = compute_s2_backoff(
                    attempt,
                    status_code=e.code,
                    retry_after=retry_after,
                ) + random.uniform(0, S2_JITTER_MAX)
                logger.warning("[S2] HTTP %s. Waiting %.1f seconds before retry...", e.code, wait_time)
                time.sleep(wait_time)
                continue
            raise

        except Exception as e:
            last_error = e
            response = getattr(e, 'response', None)
            status_code = getattr(response, 'status_code', None)
            retry_after = None
            if response is not None:
                mark_s2_request_sent()
                retry_after = parse_retry_after_seconds(response.headers.get("Retry-After"))

            error_msg = str(e)
            is_retryable = status_code in (429, 500, 502, 503, 504)
            if not is_retryable:
                is_retryable = "429" in error_msg or "Too Many Requests" in error_msg
                if is_retryable and status_code is None:
                    status_code = 429

            if attempt < max_retries - 1 and (is_retryable or status_code is None):
                wait_time = compute_s2_backoff(
                    attempt,
                    status_code=status_code,
                    retry_after=retry_after,
                ) + random.uniform(0, S2_JITTER_MAX)
                logger.warning("[S2] Request failed (%s). Waiting %.1f seconds before retry...", e, wait_time)
                time.sleep(wait_time)
                continue
            raise

    if last_error:
        raise last_error
    return None


def calculate_date_windows(target_date: Optional[datetime] = None) -> Tuple[datetime, datetime, datetime, datetime]:
    """
    计算两个时间窗口：最近30天和过去一年（除去最近30天）
    
    Args:
        target_date: 基准日期，如果为 None 则使用当前日期
        
    Returns:
        (window_30d_start, window_30d_end, window_1y_start, window_1y_end)
        - window_30d_start: 30天窗口开始日期
        - window_30d_end: 30天窗口结束日期（即 target_date）
        - window_1y_start: 一年窗口开始日期
        - window_1y_end: 一年窗口结束日期（即 31天前）
    """
    if target_date is None:
        target_date = datetime.now()
    
    # 最近30天窗口: [target_date - 30 days, target_date]
    window_30d_start = target_date - timedelta(days=30)
    window_30d_end = target_date
    
    # 过去一年窗口（除去最近30天）: [target_date - 365 days, target_date - 31 days]
    window_1y_start = target_date - timedelta(days=365)
    window_1y_end = target_date - timedelta(days=31)
    
    return window_30d_start, window_30d_end, window_1y_start, window_1y_end


def search_arxiv_by_date_range(
    categories: List[str],
    start_date: datetime,
    end_date: datetime,
    max_results: int = 200,
    max_retries: int = 3
) -> List[Dict]:
    """
    使用 `arxiv` Python 库搜索指定日期范围内的论文

    Args:
        categories: arXiv 分类列表
        start_date: 开始日期
        end_date: 结束日期
        max_results: 最大结果数
        max_retries: 最大重试次数
        
    Returns:
        论文列表
    """
    if not HAS_ARXIV:
        logger.error("Missing `arxiv` library. Install it with `uv add arxiv` or `pip install arxiv`.")
        return []

    full_query = build_arxiv_query(categories, start_date, end_date)
    client = arxiv.Client(
        page_size=min(max_results, ARXIV_PAGE_SIZE),
        delay_seconds=ARXIV_REQUEST_DELAY_SECONDS,
        num_retries=max_retries,
    )
    search = arxiv.Search(
        query=full_query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    start_bound = start_date.replace(tzinfo=timezone.utc) if start_date.tzinfo is None else start_date
    end_bound = end_date.replace(tzinfo=timezone.utc) if end_date.tzinfo is None else end_date

    logger.info("[arXiv] Searching papers from %s to %s", start_date.date(), end_date.date())
    logger.debug("[arXiv] Query: %s", full_query)
    
    for attempt in range(max_retries):
        try:
            papers: List[Dict[str, Any]] = []
            for result in client.results(search):
                paper = arxiv_result_to_paper(result)
                published_date = paper.get('published_date')
                if published_date and not (start_bound <= published_date <= end_bound):
                    continue
                papers.append(paper)

            logger.info("[arXiv] Found %d papers", len(papers))
            return papers
        except Exception as e:
            logger.warning("[arXiv] Error (attempt %d/%d): %s", attempt + 1, max_retries, e)
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 2
                logger.info("[arXiv] Retrying in %d seconds...", wait_time)
                time.sleep(wait_time)
            else:
                logger.error("[arXiv] Failed after %d attempts", max_retries)
                return []
    
    return []


def search_semantic_scholar_hot_papers(
    query: str,
    start_date: datetime,
    end_date: datetime,
    top_k: int = 20,
    max_retries: int = 3
) -> List[Dict]:
    """
    使用 Semantic Scholar API 搜索指定时间范围内的高影响力论文
    
    Args:
        query: 搜索关键词
        start_date: 开始日期
        end_date: 结束日期
        top_k: 返回前 K 篇高影响力论文
        max_retries: 最大重试次数
        
    Returns:
        按高影响力引用数排序的论文列表
    """
    # 构建日期范围 (Semantic Scholar 使用 YYYY-MM-DD:YYYY-MM-DD 格式)
    date_range = f"{start_date.strftime('%Y-%m-%d')}:{end_date.strftime('%Y-%m-%d')}"
    
    # 构建请求参数
    params = {
        "query": query,
        "publicationDateOrYear": date_range,
        "limit": 100,  # 先拉取100篇相关度最高的
        "fields": SEMANTIC_SCHOLAR_FIELDS
    }
    
    headers = build_s2_headers("StartMyDay-PaperFetcher/1.0")
    
    logger.info("[S2] Searching hot papers from %s to %s", start_date.date(), end_date.date())
    logger.info("[S2] Query: '%s'", query)
    
    try:
        data = semantic_scholar_request(
            SEMANTIC_SCHOLAR_API_URL,
            params=params,
            headers=headers,
            timeout=S2_REQUEST_TIMEOUT,
            max_retries=max_retries,
        )
    except Exception as e:
        logger.error("[S2] Failed after %d attempts: %s", max_retries, e)
        return []

    papers = data.get("data", []) if isinstance(data, dict) else []
    if not papers:
        logger.info("[S2] No papers found")
        return []

    # 本地二次过滤与排序
    valid_papers = []
    for p in papers:
        # 过滤掉没有标题或摘要的无效条目
        if not p.get("title") or not p.get("abstract"):
            continue

        # 处理可能的 None 值
        inf_cit = p.get("influentialCitationCount") or 0
        cit = p.get("citationCount") or 0

        p["influentialCitationCount"] = inf_cit
        p["citationCount"] = cit

        # 标记来源
        p["source"] = "semantic_scholar"
        p["hot_score"] = inf_cit  # 使用高影响力引用数作为热度分数

        # 提取 affiliation 信息
        if p.get('authors') and not p.get('affiliations'):
            affiliations = []
            for a in p['authors']:
                for affil in (a.get('affiliations') or []):
                    name = affil.get('name', '') if isinstance(affil, dict) else str(affil)
                    if name and name not in affiliations:
                        affiliations.append(name)
            p['affiliations'] = affiliations

        valid_papers.append(p)

    # 按高影响力引用数倒序排列
    sorted_papers = sorted(
        valid_papers,
        key=lambda x: x["influentialCitationCount"],
        reverse=True
    )

    logger.info("[S2] Found %d valid papers, returning top %d", len(sorted_papers), top_k)
    return sorted_papers[:top_k]


def search_hot_papers_from_openalex(
    query: str,
    start_date: datetime,
    end_date: datetime,
    top_k: int = 20,
    max_retries: int = 3,
) -> List[Dict]:
    """使用 OpenAlex 作为 Semantic Scholar 的兜底热度来源。"""
    filter_expr = (
        f"from_publication_date:{start_date.strftime('%Y-%m-%d')},"
        f"to_publication_date:{end_date.strftime('%Y-%m-%d')}"
    )
    params = {
        'search': query,
        'filter': ''.join(filter_expr),
        'per-page': min(max(top_k * 3, 20), 100),
        'sort': 'cited_by_count:desc',
    }
    request_url = f"{OPENALEX_API_URL}?{urllib.parse.urlencode(params)}"
    logger.info("[OpenAlex] Query: '%s'", query)

    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(request_url, timeout=60) as response:
                data = json.loads(response.read().decode('utf-8'))
            results = data.get('results', []) if isinstance(data, dict) else []
            papers = []
            for item in results:
                title = item.get('title')
                abstract_index = item.get('abstract_inverted_index') or {}
                if not title:
                    continue

                abstract = ''
                if abstract_index:
                    terms_by_pos = []
                    for term, positions in abstract_index.items():
                        for pos in positions:
                            terms_by_pos.append((pos, term))
                    terms_by_pos.sort(key=lambda x: x[0])
                    abstract = ' '.join(term for _, term in terms_by_pos)

                authors = []
                affiliations = []
                for authorship in item.get('authorships', []) or []:
                    author = authorship.get('author') or {}
                    display_name = author.get('display_name')
                    if display_name:
                        authors.append(display_name)
                    for institution in authorship.get('institutions', []) or []:
                        inst_name = institution.get('display_name')
                        if inst_name and inst_name not in affiliations:
                            affiliations.append(inst_name)

                arxiv_id = None
                primary_loc = item.get('primary_location') or {}
                landing_page_url = primary_loc.get('landing_page_url') or item.get('ids', {}).get('openalex')
                doi = item.get('doi')
                if landing_page_url:
                    match = re.search(r'arxiv\.org/(abs|pdf)/(\d{4}\.\d+)', landing_page_url)
                    if match:
                        arxiv_id = match.group(2)

                papers.append({
                    'title': title.strip(),
                    'abstract': abstract.strip(),
                    'publicationDate': item.get('publication_date') or str(item.get('publication_year') or ''),
                    'citationCount': item.get('cited_by_count') or 0,
                    'influentialCitationCount': item.get('cited_by_count') or 0,
                    'authors': authors,
                    'affiliations': affiliations,
                    'externalIds': {
                        'ArXiv': arxiv_id,
                        'DOI': doi,
                        'OpenAlex': item.get('id'),
                    },
                    'arxiv_id': arxiv_id,
                    'url': landing_page_url,
                    'source': 'openalex',
                    'hot_score': item.get('cited_by_count') or 0,
                })

            logger.info("[OpenAlex] Found %d valid papers, returning top %d", len(papers), top_k)
            return papers[:top_k]
        except Exception as e:
            logger.warning("[OpenAlex] Error (attempt %d/%d): %s", attempt + 1, max_retries, e)
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 2
                time.sleep(wait_time)
            else:
                logger.error("[OpenAlex] Failed after %d attempts", max_retries)
                return []

    return []


def search_hot_papers_from_categories(
    categories: List[str],
    start_date: datetime,
    end_date: datetime,
    top_k_per_category: int = 5,
    config: Optional[Dict] = None
) -> Tuple[List[Dict], Dict[str, Any]]:
    """
    为多个 arXiv 分类搜索高影响力论文

    Args:
        categories: arXiv 分类列表
        start_date: 开始日期
        end_date: 结束日期
        top_k_per_category: 每个分类返回的论文数
        config: 研究配置（用于提取用户自定义关键词）

    Returns:
        (合并后的高影响力论文列表, 搜索状态)
    """
    all_hot_papers = []
    seen_arxiv_ids = set()
    status = {
        'enabled': True,
        'source': 'none',
        'degraded': False,
        'reason': 'no_results',
    }

    # 从配置中提取用户自定义的搜索关键词（更精准）
    user_queries = []
    if config:
        domains = config.get('research_domains', {})
        for domain_name, domain_config in domains.items():
            keywords = domain_config.get('keywords', [])
            # 取每个域的前3个关键词组合为查询
            if keywords:
                query = ' '.join(keywords[:3])
                user_queries.append(query)

    # 如果没有用户关键词，回退到分类关键词
    if not user_queries:
        user_queries = [ARXIV_CATEGORY_KEYWORDS.get(cat, cat) for cat in categories]

    # 去重查询
    seen_queries = set()
    unique_queries = []
    for q in user_queries:
        q_lower = q.lower()
        if q_lower not in seen_queries:
            seen_queries.add(q_lower)
            unique_queries.append(q)

    for query in unique_queries:
        source_used = None
        papers = search_semantic_scholar_hot_papers(
            query=query,
            start_date=start_date,
            end_date=end_date,
            top_k=top_k_per_category
        )
        if papers:
            source_used = 'semantic_scholar'
        else:
            papers = search_hot_papers_from_openalex(
                query=query,
                start_date=start_date,
                end_date=end_date,
                top_k=top_k_per_category,
            )
            if papers:
                source_used = 'openalex'
                status['degraded'] = True
                status['reason'] = 's2_failed_or_empty'

        if source_used and status['source'] == 'none':
            status['source'] = source_used
            if source_used == 'semantic_scholar':
                status['reason'] = 'ok'

        # 去重（基于 arXiv ID）
        for p in papers:
            # 安全地从 externalIds 字典中提取 ArXiv 编号
            arxiv_id = p.get("externalIds", {}).get("ArXiv") if p.get("externalIds") else None
            if not arxiv_id:
                arxiv_id = p.get('arxiv_id')

            # 统一写入 arxiv_id 字段，方便最后 Step 3 的全局去重
            p["arxiv_id"] = arxiv_id

            if arxiv_id and arxiv_id not in seen_arxiv_ids:
                seen_arxiv_ids.add(arxiv_id)
                all_hot_papers.append(p)
            elif not arxiv_id:
                # 没有 arXiv ID 的也保留（可能是其他来源的论文）
                all_hot_papers.append(p)

        if query != unique_queries[-1]:
            time.sleep(max(S2_CATEGORY_REQUEST_INTERVAL, get_s2_request_interval()))

    # 最终按影响力引用数排序
    all_hot_papers.sort(key=lambda x: x.get("influentialCitationCount", 0), reverse=True)
    if not all_hot_papers:
        status['source'] = 'none'
        status['degraded'] = True
    return all_hot_papers, status


def parse_arxiv_xml(xml_content: str) -> List[Dict]:
    """
    解析 arXiv XML 结果
    
    Args:
        xml_content: XML 内容
        
    Returns:
        论文列表，每篇论文包含 ID、标题、作者、摘要等信息
    """
    papers = []
    
    try:
        root = ET.fromstring(xml_content)
        
        # 查找所有 entry 元素
        for entry in root.findall('atom:entry', ARXIV_NS):
            paper = {}
            
            # 提取 ID
            id_elem = entry.find('atom:id', ARXIV_NS)
            if id_elem is not None:
                paper['id'] = id_elem.text
                # 提取 arXiv ID（从 URL 中提取）
                match = re.search(r'arXiv:(\d+\.\d+)', paper['id'])
                if match:
                    paper['arxiv_id'] = match.group(1)
                else:
                    match = re.search(r'/(\d+\.\d+)$', paper['id'])
                    if match:
                        paper['arxiv_id'] = match.group(1)
            
            # 提取标题
            title_elem = entry.find('atom:title', ARXIV_NS)
            if title_elem is not None:
                paper['title'] = title_elem.text.strip()
            
            # 提取摘要
            summary_elem = entry.find('atom:summary', ARXIV_NS)
            if summary_elem is not None:
                paper['summary'] = summary_elem.text.strip()
            
            # 提取作者（及可选的 affiliation）
            authors = []
            affiliations = []
            for author in entry.findall('atom:author', ARXIV_NS):
                name_elem = author.find('atom:name', ARXIV_NS)
                if name_elem is not None:
                    authors.append(name_elem.text)
                affil_elem = author.find('arxiv:affiliation', ARXIV_NS)
                if affil_elem is not None and affil_elem.text:
                    affil = affil_elem.text.strip()
                    if affil and affil not in affiliations:
                        affiliations.append(affil)
            paper['authors'] = authors
            paper['affiliations'] = affiliations  # 可能为空列表
            
            # 提取发布日期
            published_elem = entry.find('atom:published', ARXIV_NS)
            if published_elem is not None:
                paper['published'] = published_elem.text
                # 解析日期
                try:
                    paper['published_date'] = datetime.fromisoformat(
                        paper['published'].replace('Z', '+00:00')
                    )
                except (ValueError, TypeError):
                    paper['published_date'] = None
            
            # 提取更新日期
            updated_elem = entry.find('atom:updated', ARXIV_NS)
            if updated_elem is not None:
                paper['updated'] = updated_elem.text
            
            # 提取分类
            categories = []
            for category in entry.findall('atom:category', ARXIV_NS):
                term = category.get('term')
                if term:
                    categories.append(term)
            paper['categories'] = categories
            
            # 提取 PDF 链接
            for link in entry.findall('atom:link', ARXIV_NS):
                if link.get('title') == 'pdf':
                    paper['pdf_url'] = link.get('href')
                    break
            
            # 提取主页面链接
            if 'id' in paper:
                paper['url'] = paper['id']
            
            # 标记来源
            paper['source'] = 'arxiv'
            
            papers.append(paper)
            
    except ET.ParseError as e:
        logger.error("Error parsing XML: %s", e)
        raise
    
    return papers


def normalize_relevance_text(text: str) -> str:
    """将文本归一化为适合做边界匹配的形式。"""
    return re.sub(r'[^a-z0-9]+', ' ', (text or '').lower()).strip()


def keyword_in_text(keyword: str, normalized_text: str) -> bool:
    """
    更严格的关键词匹配：
    - 默认按词边界 / 短语边界匹配，避免简单子串误命中
    - 对短关键词（如 CT、MRI）要求独立 token 命中
    """
    keyword_segments = re.findall(r'[a-z0-9]+', (keyword or '').lower())
    if not keyword_segments:
        return False

    if not normalized_text:
        return False

    if len(keyword_segments) == 1:
        token = keyword_segments[0]
        pattern = rf'(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])'
        return re.search(pattern, normalized_text) is not None

    phrase = r'\s+'.join(re.escape(seg) for seg in keyword_segments)
    pattern = rf'(?<![a-z0-9]){phrase}(?![a-z0-9])'
    return re.search(pattern, normalized_text) is not None


def calculate_relevance_score(
    paper: Dict,
    domains: Dict,
    excluded_keywords: List[str]
) -> Tuple[float, Optional[str], List[str]]:
    """
    计算论文与研究兴趣的相关性评分
    
    Args:
        paper: 论文信息
        domains: 研究领域配置
        excluded_keywords: 排除关键词
        
    Returns:
        (相关性评分, 匹配的领域, 匹配的关键词列表)
    """
    title = paper.get('title', '').lower()
    summary = paper.get('summary', '').lower() if 'summary' in paper else paper.get('abstract', '').lower()
    normalized_title = normalize_relevance_text(title)
    normalized_summary = normalize_relevance_text(summary)
    categories = set(paper.get('categories', []))
    
    # 检查排除关键词
    for keyword in excluded_keywords:
        if keyword.lower() in title or keyword.lower() in summary:
            return 0, None, []
    
    max_score = 0
    best_domain = None
    matched_keywords = []
    
    # 遍历所有领域
    for domain_name, domain_config in domains.items():
        keyword_score = 0.0
        category_score = 0.0
        domain_matched_keywords = []
        
        # 关键词匹配
        keywords = domain_config.get('keywords', [])
        for keyword in keywords:
            if keyword_in_text(keyword, normalized_title):
                keyword_score += RELEVANCE_TITLE_KEYWORD_BOOST
                domain_matched_keywords.append(keyword)
            elif keyword_in_text(keyword, normalized_summary):
                keyword_score += RELEVANCE_SUMMARY_KEYWORD_BOOST
                domain_matched_keywords.append(keyword)

        # 没有关键词命中时直接跳过该 domain。
        # 仅靠 arXiv category 过筛会把同大类下的大量噪声论文放进来。
        if keyword_score == 0:
            continue
        
        # 类别匹配
        domain_categories = domain_config.get('arxiv_categories', [])
        for cat in domain_categories:
            if cat in categories:
                category_score += RELEVANCE_CATEGORY_MATCH_BOOST
                domain_matched_keywords.append(cat)

        score = keyword_score + category_score

        # 使用 priority 作为轻量排序因子，而不是放宽准入门槛
        priority = domain_config.get('priority', 0) or 0
        if priority > 0:
            score += min(priority, 10) * RELEVANCE_PRIORITY_BOOST_PER_LEVEL
        
        if score > max_score:
            max_score = score
            best_domain = domain_name
            matched_keywords = domain_matched_keywords
    
    return max_score, best_domain, matched_keywords


def calculate_recency_score(published_date: Optional[datetime]) -> float:
    """
    根据发布日期计算新近性评分
    
    Args:
        published_date: 发布日期
        
    Returns:
        新近性评分 (0-3)
    """
    if published_date is None:
        return 0
    
    now = datetime.now(published_date.tzinfo) if published_date.tzinfo else datetime.now()
    days_diff = (now - published_date).days
    
    for max_days, score in RECENCY_THRESHOLDS:
        if days_diff <= max_days:
            return score
    return RECENCY_DEFAULT


def calculate_quality_score(summary: str) -> float:
    """
    从摘要推断质量评分

    采用更细粒度的指标：强创新词权重高于弱创新词，
    量化结果和对比实验也加分。

    Args:
        summary: 论文摘要

    Returns:
        质量评分 (0-3)
    """
    if not summary:
        return 0.0
    score = 0.0
    summary_lower = summary.lower()

    strong_innovation = [
        'state-of-the-art', 'sota', 'breakthrough', 'first',
        'surpass', 'outperform', 'pioneering'
    ]
    weak_innovation = [
        'novel', 'propose', 'introduce', 'new approach',
        'new method', 'innovative'
    ]
    method_indicators = [
        'framework', 'architecture', 'algorithm', 'mechanism',
        'pipeline', 'end-to-end'
    ]
    quantitative_indicators = [
        'outperforms', 'improves by', 'achieves', 'accuracy',
        'f1', 'bleu', 'rouge', 'beats', 'surpasses'
    ]
    experiment_indicators = [
        'experiment', 'evaluation', 'benchmark', 'ablation',
        'baseline', 'comparison'
    ]

    strong_count = sum(1 for ind in strong_innovation if ind in summary_lower)
    if strong_count >= 2:
        score += 1.0
    elif strong_count == 1:
        score += 0.7
    else:
        weak_count = sum(1 for ind in weak_innovation if ind in summary_lower)
        if weak_count > 0:
            score += 0.3

    if any(ind in summary_lower for ind in method_indicators):
        score += 0.5

    if any(ind in summary_lower for ind in quantitative_indicators):
        score += 0.8
    elif any(ind in summary_lower for ind in experiment_indicators):
        score += 0.4

    return min(score, SCORE_MAX)


def calculate_recommendation_score(
    relevance_score: float,
    recency_score: float,
    popularity_score: float,
    quality_score: float,
    is_hot_paper: bool = False
) -> float:
    """
    计算综合推荐评分

    权重定义在模块顶部常量 WEIGHTS_NORMAL / WEIGHTS_HOT 中。
    对于高影响力论文（来自 Semantic Scholar），使用 WEIGHTS_HOT 提高热门度权重。

    Args:
        relevance_score: 相关性评分 (0-SCORE_MAX)
        recency_score: 新近性评分 (0-SCORE_MAX)
        popularity_score: 热门度评分 (0-SCORE_MAX)
        quality_score: 质量评分 (0-SCORE_MAX)
        is_hot_paper: 是否是高影响力论文

    Returns:
        综合推荐评分 (0-10)
    """
    scores = {
        'relevance': relevance_score,
        'recency': recency_score,
        'popularity': popularity_score,
        'quality': quality_score,
    }
    # 归一化到 0-10 分
    normalized = {k: (v / SCORE_MAX) * 10 for k, v in scores.items()}

    weights = WEIGHTS_HOT if is_hot_paper else WEIGHTS_NORMAL
    final_score = sum(normalized[k] * weights[k] for k in weights)

    return round(final_score, 2)


def filter_and_score_papers(
    papers: List[Dict],
    config: Dict,
    target_date: Optional[datetime] = None,
    is_hot_paper_batch: bool = False
) -> List[Dict]:
    """
    筛选和评分论文

    Args:
        papers: 论文列表
        config: 研究配置
        target_date: 目标日期（用于计算新近性）
        is_hot_paper_batch: 是否是高影响力论文批次

    Returns:
        筛选和评分后的论文列表
    """
    domains = config.get('research_domains', {})
    excluded_keywords = config.get('excluded_keywords', [])

    scored_papers = []

    for paper in papers:
        # 计算相关性
        relevance, matched_domain, matched_keywords = calculate_relevance_score(
            paper, domains, excluded_keywords
        )

        # 如果相关性低于阈值，跳过
        if relevance < MIN_RELEVANCE_THRESHOLD:
            continue

        # 计算新近性
        if 'published_date' in paper:
            recency = calculate_recency_score(paper.get('published_date'))
        else:
            # 对于 Semantic Scholar 的论文，使用 publicationDate
            pub_date_str = paper.get('publicationDate')
            if pub_date_str:
                pub_date = None
                for fmt in ('%Y-%m-%d', '%Y-%m', '%Y'):
                    try:
                        pub_date = datetime.strptime(pub_date_str, fmt)
                        break
                    except (ValueError, TypeError):
                        continue
                recency = calculate_recency_score(pub_date) if pub_date else 0
            else:
                recency = 0

        # 计算热门度
        if is_hot_paper_batch:
            # 高影响力论文：使用 influentialCitationCount
            inf_cit = paper.get('influentialCitationCount', 0)
            popularity = min(
                inf_cit / (POPULARITY_INFLUENTIAL_CITATION_FULL_SCORE / SCORE_MAX),
                SCORE_MAX,
            )
        else:
            # 普通论文（无引用数据）：基于新近性给一个中间热门度
            # 最近7天的新论文可能有更高的"潜在热度"
            if 'published_date' in paper and paper['published_date']:
                pub = paper['published_date']
                now = datetime.now(pub.tzinfo) if pub.tzinfo else datetime.now()
                days_old = (now - pub).days
                if days_old <= 7:
                    popularity = 2.0  # 非常新的论文有潜在热度
                elif days_old <= 14:
                    popularity = 1.5
                elif days_old <= 30:
                    popularity = 1.0
                else:
                    popularity = 0.5
            else:
                popularity = 0.5  # 无日期信息时给一个保守值

        # 计算质量
        summary = paper.get('summary', '') if 'summary' in paper else paper.get('abstract', '')
        quality = calculate_quality_score(summary)

        # 计算综合推荐评分
        recommendation_score = calculate_recommendation_score(
            relevance, recency, popularity, quality, is_hot_paper_batch
        )

        # 添加评分信息
        paper['scores'] = {
            'relevance': round(relevance, 2),
            'recency': round(recency, 2),
            'popularity': round(popularity, 2),
            'quality': round(quality, 2),
            'recommendation': recommendation_score
        }
        paper['selection_reason'] = {
            'matched_domain': matched_domain,
            'matched_keywords': matched_keywords,
            'relevance_threshold': MIN_RELEVANCE_THRESHOLD,
        }
        paper['matched_domain'] = matched_domain
        paper['matched_keywords'] = matched_keywords
        paper['is_hot_paper'] = is_hot_paper_batch

        scored_papers.append(paper)

    # 按推荐评分排序
    scored_papers.sort(key=lambda x: x['scores']['recommendation'], reverse=True)

    return scored_papers


def resolve_categories_from_config(config: Dict) -> List[str]:
    """从 preference 配置聚合 arXiv categories。"""
    domains = config.get('research_domains', {})
    categories: List[str] = []
    seen = set()

    if not isinstance(domains, dict):
        return categories

    for domain_config in domains.values():
        if not isinstance(domain_config, dict):
            continue
        for cat in domain_config.get('arxiv_categories', []) or []:
            cat_str = str(cat).strip()
            if not cat_str or cat_str in seen:
                continue
            seen.add(cat_str)
            categories.append(cat_str)

    return categories


def main():
    """主函数"""
    import argparse

    default_config = os.environ.get('OBSIDIAN_VAULT_PATH', '')
    if default_config:
        default_config = os.path.join(default_config, DEFAULT_PREFERENCE_RELATIVE_PATH)

    parser = argparse.ArgumentParser(description='Search and filter arXiv papers with Semantic Scholar integration')
    parser.add_argument('--config', type=str,
                        default=default_config or None,
                        help='Path to preference config file (or set OBSIDIAN_VAULT_PATH env var)')
    parser.add_argument('--output', type=str, default='arxiv_filtered.json',
                        help='Output JSON file path')
    parser.add_argument('--max-results', type=int, default=200,
                        help='Maximum number of results to fetch from arXiv')
    parser.add_argument('--top-n', type=int, default=10,
                        help='Number of top papers to return')
    parser.add_argument('--target-date', type=str, default=None,
                        help='Target date (YYYY-MM-DD) for filtering')
    parser.add_argument('--existing-index', type=str, default=None,
                        help='Optional existing note index JSON for deterministic deduplication')
    parser.add_argument('--categories', type=str,
                        default=None,
                        help='Comma-separated list of arXiv categories (optional; default derives from preference config)')
    parser.add_argument('--output-format', type=str, default='start-my-day',
                        choices=['start-my-day', 'paper-search'],
                        help='Output schema for downstream workflow')
    parser.add_argument('--selected-output', type=str, default=None,
                        help='Optional path to also write a fixed top-5 selection JSON')
    parser.add_argument('--skip-hot-papers', action='store_true',
                        help='Skip searching hot papers from Semantic Scholar')

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        stream=sys.stderr,
    )

    if not args.config:
        logger.error("未指定配置文件路径。请通过 --config 参数或 OBSIDIAN_VAULT_PATH 环境变量设置。")
        return 1

    logger.info("Loading config from: %s", args.config)
    try:
        config = load_research_config(args.config)
    except Exception as e:
        logger.error("Failed to load preference config: %s", e)
        return 1

    logger.info(
        "Semantic Scholar API key: %s",
        "configured" if S2_API_KEY else "not configured",
    )

    # 解析目标日期
    target_date = None
    if args.target_date:
        try:
            target_date = datetime.strptime(args.target_date, '%Y-%m-%d')
            logger.info("Target date: %s", args.target_date)
        except ValueError:
            logger.error("Invalid target date format: %s", args.target_date)
            return 1
    else:
        target_date = datetime.now()
        logger.info("Using current date: %s", target_date.strftime('%Y-%m-%d'))

    window_30d_start, window_30d_end, window_1y_start, window_1y_end = calculate_date_windows(target_date)
    logger.info("Date windows:")
    logger.info("  Recent 30 days: %s to %s", window_30d_start.date(), window_30d_end.date())
    logger.info("  Past year (31-365 days): %s to %s", window_1y_start.date(), window_1y_end.date())

    # 解析分类：默认从 preference 配置聚合，CLI 显式传入时覆盖
    if args.categories:
        categories = [c.strip() for c in args.categories.split(',') if c.strip()]
    else:
        categories = resolve_categories_from_config(config)

    if not categories:
        logger.error("No arXiv categories resolved. Please set research_domains.*.arxiv_categories in preference.md or pass --categories.")
        return 1

    try:
        existing_corpus = load_existing_corpus(args.existing_index)
    except Exception as e:
        logger.error("Failed to load existing index: %s", e)
        return 1

    all_scored_papers = []
    recent_papers = []
    hot_papers = []
    hot_search_status = {
        'enabled': not args.skip_hot_papers,
        'source': 'none',
        'degraded': False,
        'reason': 'skipped_by_user' if args.skip_hot_papers else 'not_run',
    }

    # ========== 第一步：搜索最近30天的论文（arXiv）==========
    logger.info("=" * 70)
    logger.info("Step 1: Searching recent papers (last 30 days) from arXiv")
    logger.info("=" * 70)
    
    recent_papers = search_arxiv_by_date_range(
        categories=categories,
        start_date=window_30d_start,
        end_date=window_30d_end,
        max_results=args.max_results
    )
    
    if recent_papers:
        scored_recent = filter_and_score_papers(
            papers=recent_papers,
            config=config,
            target_date=target_date,
            is_hot_paper_batch=False
        )
        logger.info("Scored %d recent papers", len(scored_recent))
        all_scored_papers.extend(scored_recent)
    else:
        logger.warning("No recent papers found")

    # ========== 第二步：搜索过去一年的高影响力论文（Semantic Scholar）==========
    if not args.skip_hot_papers:
        logger.info("=" * 70)
        logger.info("Step 2: Searching hot papers (past year) from Semantic Scholar")
        logger.info("=" * 70)
        
        hot_papers, hot_search_status = search_hot_papers_from_categories(
            categories=categories,
            start_date=window_1y_start,
            end_date=window_1y_end,
            top_k_per_category=5,
            config=config
        )
        
        if hot_papers:
            scored_hot = filter_and_score_papers(
                papers=hot_papers,
                config=config,
                target_date=target_date,
                is_hot_paper_batch=True
            )
            logger.info("Scored %d hot papers", len(scored_hot))
            all_scored_papers.extend(scored_hot)
        else:
            logger.warning("No hot papers found from Semantic Scholar")
    else:
        logger.info("Skipping hot paper search (disabled by user)")

    # ========== 第三步：合并结果并排序 ==========
    logger.info("=" * 70)
    logger.info("Step 3: Merging and ranking results")
    logger.info("=" * 70)
    
    # 按推荐评分排序
    all_scored_papers.sort(key=lambda x: x['scores']['recommendation'], reverse=True)

    unique_papers, internal_duplicates_removed = deduplicate_candidate_pool(all_scored_papers)
    logger.info("Total unique papers after internal deduplication: %d", len(unique_papers))

    candidate_papers, excluded_duplicates = split_existing_duplicates(unique_papers, existing_corpus)
    logger.info("Candidates after existing-note deduplication: %d", len(candidate_papers))

    if len(candidate_papers) == 0:
        logger.warning("No papers matched the criteria!")
        return 1

    # 取前 N 篇
    top_papers = candidate_papers[:args.top_n]

    # 为每篇论文补充 note_filename，与 generate_note.py 的文件名规则保持一致
    # 这样 start-my-day 生成的 wikilink 可以直接使用此字段，无需自行推断
    for paper in candidate_papers:
        paper['paper_id'] = f"arxiv:{paper['arxiv_id']}" if paper.get('arxiv_id') else None
        paper['title_normalized'] = normalize_title_alias(paper.get('title', ''))
        paper['note_filename'] = title_to_note_filename(paper.get('title', ''))

    search_modes = ['recent_arxiv']
    if not args.skip_hot_papers:
        if hot_search_status.get('source') == 'semantic_scholar':
            search_modes.append('hot_semantic_scholar')
        elif hot_search_status.get('source') == 'openalex':
            search_modes.append('hot_openalex')

    if args.output_format == 'paper-search':
        output = {
            'query_context': {
                'target_date': args.target_date or target_date.strftime('%Y-%m-%d'),
                'config_path': args.config,
                'categories': categories,
                'max_results': args.max_results,
                'candidate_pool_size': args.top_n,
                'search_modes': search_modes,
            },
            'existing_corpus': {
                'notes_scanned': existing_corpus['notes_scanned'],
                'seen_arxiv_ids': sorted(existing_corpus['seen_arxiv_ids']),
                'seen_title_aliases': sorted(existing_corpus['seen_title_aliases']),
                'index_path': existing_corpus['index_path'],
            },
            'filter_summary': {
                'retrieved_recent': len(recent_papers),
                'retrieved_hot': len(hot_papers),
                'scored_total': len(all_scored_papers),
                'pre_filtered_duplicates': len(excluded_duplicates),
                'post_filtered_duplicates': internal_duplicates_removed,
                'remaining_candidates': len(top_papers),
            },
            'hot_search_status': hot_search_status,
            'candidates': top_papers,
            'excluded_duplicates': excluded_duplicates,
        }
    else:
        output = {
            'target_date': args.target_date or target_date.strftime('%Y-%m-%d'),
            'date_windows': {
                'recent_30d': {
                    'start': window_30d_start.strftime('%Y-%m-%d'),
                    'end': window_30d_end.strftime('%Y-%m-%d')
                },
                'past_year': {
                    'start': window_1y_start.strftime('%Y-%m-%d'),
                    'end': window_1y_end.strftime('%Y-%m-%d')
                }
            },
            'hot_search_status': hot_search_status,
            'total_recent': len(recent_papers),
            'total_hot': len(hot_papers),
            'total_unique': len(candidate_papers),
            'excluded_duplicates': excluded_duplicates,
            'top_papers': top_papers
        }

    # 保存结果
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    if args.selected_output:
        selected_output = {
            'target_date': args.target_date or target_date.strftime('%Y-%m-%d'),
            'selected_papers': candidate_papers[:5],
        }
        with open(args.selected_output, 'w', encoding='utf-8') as f:
            json.dump(selected_output, f, ensure_ascii=False, indent=2, default=str)
        logger.info("Selected papers saved to: %s", args.selected_output)

    logger.info("Results saved to: %s", args.output)
    logger.info("Top %d papers:", len(top_papers))
    for i, p in enumerate(top_papers, 1):
        hot_marker = " [HOT]" if p.get('is_hot_paper') else ""
        logger.info("  %d. %s... (Score: %s)%s", i, p.get('title', 'N/A')[:60], p['scores']['recommendation'], hot_marker)

    # 同时输出到 stdout
    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))

    return 0


if __name__ == '__main__':
    sys.exit(main())
