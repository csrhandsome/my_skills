#!/usr/bin/env python3
"""
顶级会议论文搜索脚本
使用 DBLP API 获取论文列表 + Semantic Scholar API 补充引用数和摘要
支持 CVPR/ICCV/ECCV/ICLR/AAAI/NeurIPS/ICML 以及 CHI/UIST/CSCW/IUI/UbiComp/DIS 等顶会
"""

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)


def title_to_note_filename(title: str) -> str:
    """将论文标题转换为 Obsidian 笔记文件名（与 generate_note.py 保持一致）。

    使用与 paper-analyze/scripts/generate_note.py 完全相同的规则，
    确保 conf-papers 生成的 wikilink 路径能正确指向 paper-analyze 创建的文件。
    """
    filename = re.sub(r'[ /\\:*?"<>|]+', "_", title).strip("_")
    return filename


try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    logger.warning("requests library not found, using urllib")

# ---------------------------------------------------------------------------
# 复用 search_arxiv.py 的评分函数
# ---------------------------------------------------------------------------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_START_MY_DAY_SCRIPTS = os.path.join(
    os.path.dirname(os.path.dirname(_SCRIPT_DIR)), "start-my-day", "scripts"
)
if _START_MY_DAY_SCRIPTS not in sys.path:
    sys.path.insert(0, _START_MY_DAY_SCRIPTS)

from search_arxiv import (
    RELEVANCE_CATEGORY_MATCH_BOOST,
    RELEVANCE_SUMMARY_KEYWORD_BOOST,
    RELEVANCE_TITLE_KEYWORD_BOOST,
    S2_REQUEST_TIMEOUT,
    SCORE_MAX,
    build_s2_headers,
    calculate_quality_score,
    calculate_relevance_score,
    semantic_scholar_request,
    set_semantic_scholar_api_key,
)

# ---------------------------------------------------------------------------
# 会议配置
# ---------------------------------------------------------------------------
# DBLP toc key 映射：用于 toc:db/conf/... 查询格式
# value = (conf_path, toc_name_template)
# toc_name_template 中 {year} 会被替换为实际年份
# 对于无法用 toc 查询的会议（如 ECCV），使用 venue+year 备选查询
DBLP_VENUES = {
    "CVPR": {"toc": "conf/cvpr", "toc_name": "cvpr{year}"},
    "ICCV": {"toc": "conf/iccv", "toc_name": "iccv{year}"},
    "ECCV": {
        "toc": "conf/eccv",
        "toc_name": None,
        "venue_query": "ECCV",
    },  # ECCV toc 不可用，用 venue+year
    "ICLR": {"toc": "conf/iclr", "toc_name": "iclr{year}"},
    "AAAI": {"toc": "conf/aaai", "toc_name": "aaai{year}"},
    "NeurIPS": {"toc": "conf/nips", "toc_name": "neurips{year}"},
    "ICML": {"toc": "conf/icml", "toc_name": "icml{year}"},
    "MICCAI": {
        "toc": "conf/miccai",
        "toc_name": None,
        "venue_query": "MICCAI",
    },  # MICCAI toc 不稳定，用 venue+year
    "ACL": {"toc": "conf/acl", "toc_name": "acl{year}"},
    "EMNLP": {
        "toc": "conf/emnlp",
        "toc_name": None,
        "venue_query": "EMNLP",
    },  # EMNLP toc 不稳定，用 venue+year
    "CHI": {
        "toc": "conf/chi",
        "toc_name": "chi{year}",
        "venue_query": "CHI Conference on Human Factors in Computing Systems",
    },
    "UIST": {"toc": "conf/uist", "toc_name": "uist{year}"},
    "CSCW": {"toc": "conf/cscw", "toc_name": "cscw{year}", "venue_query": "CSCW"},
    "IUI": {"toc": "conf/iui", "toc_name": "iui{year}"},
    "UbiComp": {
        "toc": "conf/ubicomp",
        "toc_name": "ubicomp{year}",
        "venue_query": "UbiComp",
    },
    "DIS": {
        "toc": "conf/dis",
        "toc_name": "dis{year}",
        "venue_query": "Designing Interactive Systems",
    },
}

# 会议 -> arXiv 分类映射（用于相关性评分中的分类匹配加分）
VENUE_TO_CATEGORIES = {
    "CVPR": ["cs.CV"],
    "ICCV": ["cs.CV"],
    "ECCV": ["cs.CV"],
    "ICLR": ["cs.LG", "cs.AI"],
    "ICML": ["cs.LG"],
    "NeurIPS": ["cs.LG", "cs.AI", "cs.CL"],
    "AAAI": ["cs.AI"],
    "MICCAI": ["cs.CV", "eess.IV"],
    "ACL": ["cs.CL"],
    "EMNLP": ["cs.CL"],
    "CHI": ["cs.HC"],
    "UIST": ["cs.HC", "cs.GR"],
    "CSCW": ["cs.HC", "cs.CY"],
    "IUI": ["cs.HC", "cs.AI"],
    "UbiComp": ["cs.HC", "cs.CY"],
    "DIS": ["cs.HC"],
}

DEFAULT_PRESET = "computer"
PRESET_CONFIG_FILES = {
    "computer": "computer_conf_papers.yaml",
    "hci": "hci_conf_papers.yaml",
}
PRESET_ALIASES = {
    "computer": "computer",
    "computer_conf_papers": "computer",
    "cs": "computer",
    "default": "computer",
    "conf-papers": "computer",
    "hci": "hci",
    "hci_conf_papers": "hci",
    "hc": "hci",
    "human-computer-interaction": "hci",
    "human_computer_interaction": "hci",
}

# 评分权重（去掉新近性维度，因为年份由用户指定）
WEIGHTS_CONF = {
    "relevance": 0.40,
    "popularity": 0.40,
    "quality": 0.20,
}

# 热门度：高影响力引用满分基准
POPULARITY_INFLUENTIAL_CITATION_FULL_SCORE = 100

# Semantic Scholar 配置
S2_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
S2_PAPER_URL = "https://api.semanticscholar.org/graph/v1/paper"
S2_FIELDS = "title,abstract,citationCount,influentialCitationCount,externalIds,url,authors,authors.affiliations"
S2_BATCH_URL = "https://api.semanticscholar.org/graph/v1/paper/batch"
S2_BATCH_SIZE = 20
S2_CACHE_TTL_SECONDS = 30 * 24 * 60 * 60

# DBLP API 配置
DBLP_API_URL = "https://dblp.org/search/publ/api"

# ---------------------------------------------------------------------------
# DBLP 搜索
# ---------------------------------------------------------------------------


def search_dblp_conference(
    venue_key: str, year: int, max_results: int = 1000, max_retries: int = 3
) -> List[Dict]:
    """
    调用 DBLP Search API 搜索指定会议和年份的论文

    Args:
        venue_key: 会议名称（如 "CVPR"）
        year: 年份
        max_results: 最大返回数量
        max_retries: 最大重试次数

    Returns:
        论文列表，每篇包含 title, authors, dblp_url, year, conference
    """
    venue_info = DBLP_VENUES.get(venue_key)
    if not venue_info:
        logger.warning("[DBLP] Unknown venue: %s", venue_key)
        return []

    papers = []
    hits_fetched = 0
    batch_size = min(max_results, 1000)

    # 构建查询列表：优先 toc 格式，备选 venue+year
    queries_to_try = []
    toc_name = venue_info.get("toc_name")
    if toc_name:
        toc_path = venue_info["toc"]
        queries_to_try.append(f"toc:db/{toc_path}/{toc_name.format(year=year)}.bht:")
    # 总是添加 venue+year 作为备选
    venue_query = venue_info.get("venue_query", venue_key)
    queries_to_try.append(f"venue:{venue_query} year:{year}")

    for query_str in queries_to_try:
        papers = []
        hits_fetched = 0
        query_failed = False

        while hits_fetched < max_results:
            params = {
                "q": query_str,
                "format": "json",
                "h": batch_size,
                "f": hits_fetched,
            }

            url = f"{DBLP_API_URL}?{urllib.parse.urlencode(params)}"
            logger.info(
                "[DBLP] Searching %s %d (offset=%d, query=%s)",
                venue_key,
                year,
                hits_fetched,
                query_str[:60],
            )

            success = False
            for attempt in range(max_retries):
                try:
                    if HAS_REQUESTS:
                        resp = requests.get(
                            url, headers={"User-Agent": "ConfPapers/1.0"}, timeout=60
                        )
                        resp.raise_for_status()
                        data = resp.json()
                    else:
                        req = urllib.request.Request(
                            url, headers={"User-Agent": "ConfPapers/1.0"}
                        )
                        with urllib.request.urlopen(req, timeout=60) as response:
                            data = json.loads(response.read().decode("utf-8"))

                    result = data.get("result", {})
                    hits = result.get("hits", {})
                    total = int(hits.get("@total", 0))
                    hit_list = hits.get("hit", [])

                    if not hit_list:
                        logger.info(
                            "[DBLP] %s %d: no more results (total=%d)",
                            venue_key,
                            year,
                            total,
                        )
                        if papers:
                            logger.info(
                                "[DBLP] %s %d: found %d papers",
                                venue_key,
                                year,
                                len(papers),
                            )
                            return papers
                        # 0 results with this query, try next
                        query_failed = True
                        break

                    for hit in hit_list:
                        info = hit.get("info", {})
                        title = info.get("title", "").rstrip(".")
                        if not title:
                            continue

                        authors_info = info.get("authors", {}).get("author", [])
                        if isinstance(authors_info, dict):
                            authors_info = [authors_info]
                        authors = [
                            a.get("text", "") for a in authors_info if a.get("text")
                        ]

                        paper = {
                            "title": title,
                            "authors": authors,
                            "dblp_url": info.get("url", ""),
                            "year": int(info.get("year", year)),
                            "conference": venue_key,
                            "doi": info.get("doi", ""),
                            "venue": info.get("venue", venue_key),
                            "source": "dblp",
                        }
                        papers.append(paper)

                    hits_fetched += len(hit_list)
                    success = True

                    if hits_fetched >= total or hits_fetched >= max_results:
                        break

                    time.sleep(1)
                    break  # 成功，退出重试循环

                except Exception as e:
                    logger.warning(
                        "[DBLP] Error (attempt %d/%d): %s", attempt + 1, max_retries, e
                    )
                    if attempt < max_retries - 1:
                        wait_time = (2**attempt) * 3
                        logger.info("[DBLP] Retrying in %d seconds...", wait_time)
                        time.sleep(wait_time)
                    else:
                        logger.warning(
                            "[DBLP] Query failed for %s: %s", venue_key, query_str[:60]
                        )
                        query_failed = True

            if query_failed:
                break
            if hits_fetched >= max_results:
                break

        if papers:
            logger.info("[DBLP] %s %d: found %d papers", venue_key, year, len(papers))
            return papers
        elif query_failed:
            logger.info("[DBLP] Trying fallback query for %s %d...", venue_key, year)
            continue

    logger.warning("[DBLP] %s %d: no papers found with any query", venue_key, year)
    return []


def search_all_conferences(
    year: int, venues: List[str], max_per_venue: int = 1000
) -> List[Dict]:
    """
    遍历所有会议搜索论文，合并去重

    Args:
        year: 年份
        venues: 会议列表
        max_per_venue: 每个会议最大拉取数

    Returns:
        去重后的论文列表
    """
    all_papers = []
    seen_titles = set()

    for venue in venues:
        logger.info("=" * 50)
        logger.info("Searching %s %d...", venue, year)

        papers = search_dblp_conference(venue, year, max_results=max_per_venue)

        for p in papers:
            title_norm = re.sub(r"[^a-z0-9\s]", "", p["title"].lower()).strip()
            if title_norm not in seen_titles:
                seen_titles.add(title_norm)
                all_papers.append(p)

        logger.info("Total unique papers so far: %d", len(all_papers))
        time.sleep(1)  # 会议间延迟

    return all_papers


# ---------------------------------------------------------------------------
# 预设 / 配置
# ---------------------------------------------------------------------------


def normalize_preset_name(preset: Optional[str]) -> Optional[str]:
    """将用户输入的 preset 名称归一化为内置 preset。"""
    if not preset:
        return None

    normalized = preset.strip().lower()
    return PRESET_ALIASES.get(normalized)


def infer_preset_from_config_name(config_name: str) -> Optional[str]:
    """根据配置文件名推断 preset。"""
    if not config_name:
        return None

    basename = os.path.basename(config_name)
    stem = os.path.splitext(basename)[0].lower()
    return normalize_preset_name(stem)


def resolve_config_path(
    requested_config: Optional[str], preset: Optional[str]
) -> Tuple[str, str]:
    """
    解析配置文件路径。

    优先级：
    1. 显式存在的 --config 路径
    2. --config 传入的预设/旧别名（如 conf-papers.yaml）
    3. --preset 指定的内置预设
    4. 默认 computer 预设
    """
    skill_dir = os.path.dirname(_SCRIPT_DIR)
    normalized_preset = normalize_preset_name(preset)

    if preset and not normalized_preset:
        raise FileNotFoundError(
            f"未知 preset: {preset}（可选: {', '.join(PRESET_CONFIG_FILES.keys())}）"
        )

    if requested_config:
        candidates = [requested_config]
        if not os.path.isabs(requested_config):
            candidates.append(os.path.join(skill_dir, requested_config))

        for candidate in candidates:
            if os.path.exists(candidate):
                inferred_preset = infer_preset_from_config_name(candidate)
                return candidate, inferred_preset or normalized_preset or DEFAULT_PRESET

        inferred_preset = infer_preset_from_config_name(requested_config)
        if inferred_preset:
            return os.path.join(
                skill_dir, PRESET_CONFIG_FILES[inferred_preset]
            ), inferred_preset

        raise FileNotFoundError(f"配置文件不存在: {requested_config}")

    effective_preset = normalized_preset or DEFAULT_PRESET
    return os.path.join(
        skill_dir, PRESET_CONFIG_FILES[effective_preset]
    ), effective_preset


# ---------------------------------------------------------------------------
# 两阶段过滤：第一阶段 - 轻量关键词过滤
# ---------------------------------------------------------------------------


def load_conf_papers_config(config_path: str, preset: Optional[str] = None) -> Dict:
    """
    从 conf-papers 配置文件加载专用配置。

    Args:
        config_path: 配置文件路径
        preset: 已解析出的 preset（可选）

    Returns:
        {preset, keywords, excluded_keywords, default_year, default_conferences, top_n}
    """
    import yaml

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cp = yaml.safe_load(f) or {}
    except Exception as e:
        logger.error("Error loading conf-papers config: %s", e)
        cp = {}

    set_semantic_scholar_api_key(cp.get("semantic_scholar_api_key"))

    default_conferences = cp.get("default_conferences") or []
    if isinstance(default_conferences, str):
        default_conferences = [
            v.strip() for v in default_conferences.split(",") if v.strip()
        ]

    resolved_preset = (
        normalize_preset_name(cp.get("preset"))
        or preset
        or infer_preset_from_config_name(config_path)
        or DEFAULT_PRESET
    )

    return {
        "preset": resolved_preset,
        "keywords": cp.get("keywords", []),
        "excluded_keywords": cp.get("excluded_keywords", []),
        "default_year": cp.get("default_year"),
        "default_conferences": default_conferences,
        "top_n": cp.get("top_n", 10),
        "config_path": config_path,
        "semantic_scholar_cache_path": cp.get("semantic_scholar_cache_path"),
    }


def lightweight_keyword_filter(papers: List[Dict], cp_config: Dict) -> List[Dict]:
    """
    第一阶段：仅凭标题关键词做轻量相关性过滤
    使用当前 conf-papers 配置中的关键词

    Args:
        papers: DBLP 拉取的全部论文
        cp_config: conf-papers 专用配置

    Returns:
        通过关键词过滤的论文列表
    """
    # 收集所有关键词（小写）
    all_keywords = set(kw.lower() for kw in cp_config["keywords"])
    excluded_lower = set(kw.lower() for kw in cp_config["excluded_keywords"])

    filtered = []
    for paper in papers:
        title_lower = paper["title"].lower()

        # 检查排除关键词
        if any(ex in title_lower for ex in excluded_lower):
            continue

        # 检查是否匹配任何研究关键词
        matched = False
        matched_keywords = []
        for kw in all_keywords:
            if kw in title_lower:
                matched = True
                matched_keywords.append(kw)

        if matched:
            paper["_preliminary_keywords"] = matched_keywords
            filtered.append(paper)

    logger.info(
        "[Filter] Lightweight keyword filter: %d -> %d papers",
        len(papers),
        len(filtered),
    )
    return filtered


# ---------------------------------------------------------------------------
# Semantic Scholar 补充
# ---------------------------------------------------------------------------


def normalize_title_for_lookup(title: str) -> str:
    return re.sub(r"[^a-z0-9\s]", "", (title or "").lower()).strip()


def title_similarity(a: str, b: str) -> float:
    """
    归一化标题比较，用于 S2 匹配验证

    Returns:
        0.0-1.0 之间的相似度分数
    """
    a_norm = normalize_title_for_lookup(a)
    b_norm = normalize_title_for_lookup(b)

    if not a_norm or not b_norm:
        return 0.0

    # 使用词级别的 Jaccard 相似度
    words_a = set(a_norm.split())
    words_b = set(b_norm.split())

    if not words_a or not words_b:
        return 0.0

    intersection = words_a & words_b
    union = words_a | words_b

    return len(intersection) / len(union)


def chunked(items: List[Dict], size: int) -> Iterable[List[Dict]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def get_s2_cache_path(cp_config: Optional[Dict] = None) -> Path:
    configured = None
    if cp_config:
        configured = cp_config.get("semantic_scholar_cache_path")
    configured = configured or os.environ.get("VIBE_RESEARCH_S2_CACHE_PATH")
    if configured:
        return Path(os.path.expanduser(configured))

    xdg_cache_home = os.environ.get("XDG_CACHE_HOME")
    cache_root = (
        Path(xdg_cache_home).expanduser() if xdg_cache_home else Path.home() / ".cache"
    )
    return cache_root / "vibe_research_skills" / "semantic_scholar_cache.json"


def load_s2_cache(cache_path: Path) -> Dict[str, Dict]:
    try:
        if not cache_path.exists():
            return {}
        with open(cache_path, "r", encoding="utf-8") as f:
            raw_cache = json.load(f)
        if not isinstance(raw_cache, dict):
            return {}
        return raw_cache
    except Exception as e:
        logger.warning("[S2] Failed to load cache %s: %s", cache_path, e)
        return {}


def save_s2_cache(cache_path: Path, cache: Dict[str, Dict]) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("[S2] Failed to save cache %s: %s", cache_path, e)


def get_cache_keys_for_paper(paper: Dict) -> List[str]:
    keys = []
    doi = (paper.get("doi") or "").strip().lower()
    if doi:
        keys.append(f"doi:{doi}")

    title_key = normalize_title_for_lookup(paper.get("title", ""))
    if title_key:
        keys.append(f"title:{title_key}")
    return keys


def get_cache_keys_for_enrichment(paper: Dict, enrichment: Dict) -> List[str]:
    keys = set(get_cache_keys_for_paper(paper))
    doi = (enrichment.get("doi") or "").strip().lower()
    if doi:
        keys.add(f"doi:{doi}")

    matched_title = enrichment.get("matched_title") or paper.get("title", "")
    title_key = normalize_title_for_lookup(matched_title)
    if title_key:
        keys.add(f"title:{title_key}")

    return sorted(keys)


def get_cached_enrichment(cache: Dict[str, Dict], paper: Dict) -> Optional[Dict]:
    now = time.time()
    for key in get_cache_keys_for_paper(paper):
        entry = cache.get(key)
        if not entry:
            continue
        cached_at = entry.get("cached_at", 0)
        if now - cached_at > S2_CACHE_TTL_SECONDS:
            cache.pop(key, None)
            continue
        data = entry.get("data")
        if isinstance(data, dict):
            return data
    return None


def store_cached_enrichment(
    cache: Dict[str, Dict], paper: Dict, enrichment: Dict
) -> None:
    cache_entry = {
        "cached_at": int(time.time()),
        "data": enrichment,
    }
    for key in get_cache_keys_for_enrichment(paper, enrichment):
        cache[key] = cache_entry


def build_empty_enrichment(match_method: str) -> Dict[str, Any]:
    return {
        "abstract": None,
        "citationCount": 0,
        "influentialCitationCount": 0,
        "s2_url": "",
        "arxiv_id": None,
        "doi": "",
        "authors": [],
        "affiliations": [],
        "s2_matched": False,
        "s2_match_method": match_method,
    }


def extract_s2_authors(result: Optional[Dict]) -> List[str]:
    if not result:
        return []
    return [a.get("name", "") for a in result.get("authors", []) if a.get("name")]


def extract_s2_affiliations(result: Optional[Dict]) -> List[str]:
    affiliations = []
    if not result:
        return affiliations

    for author in result.get("authors", []):
        for affil in author.get("affiliations") or []:
            name = affil.get("name", "") if isinstance(affil, dict) else str(affil)
            if name and name not in affiliations:
                affiliations.append(name)
    return affiliations


def build_enrichment_from_s2_result(
    result: Optional[Dict],
    match_method: str,
    similarity: Optional[float] = None,
) -> Dict[str, Any]:
    if not result:
        return build_empty_enrichment(match_method)

    ext_ids = result.get("externalIds") or {}
    enrichment = {
        "abstract": result.get("abstract"),
        "citationCount": result.get("citationCount") or 0,
        "influentialCitationCount": result.get("influentialCitationCount") or 0,
        "s2_url": result.get("url", ""),
        "arxiv_id": ext_ids.get("ArXiv"),
        "doi": ext_ids.get("DOI", ""),
        "authors": extract_s2_authors(result),
        "affiliations": extract_s2_affiliations(result),
        "matched_title": result.get("title", ""),
        "s2_matched": True,
        "s2_match_method": match_method,
    }
    if similarity is not None:
        enrichment["s2_title_similarity"] = round(similarity, 2)
    return enrichment


def apply_s2_enrichment(paper: Dict, enrichment: Dict) -> None:
    paper["abstract"] = enrichment.get("abstract")
    paper["citationCount"] = enrichment.get("citationCount", 0) or 0
    paper["influentialCitationCount"] = (
        enrichment.get("influentialCitationCount", 0) or 0
    )
    paper["s2_matched"] = enrichment.get("s2_matched", False)
    paper["s2_match_method"] = enrichment.get("s2_match_method", "")

    if enrichment.get("s2_url"):
        paper["s2_url"] = enrichment["s2_url"]
    else:
        paper.pop("s2_url", None)

    if enrichment.get("arxiv_id"):
        paper["arxiv_id"] = enrichment["arxiv_id"]
    if enrichment.get("doi"):
        paper["doi"] = paper.get("doi") or enrichment["doi"]
    if enrichment.get("authors") and not paper.get("authors"):
        paper["authors"] = enrichment["authors"]
    if enrichment.get("affiliations"):
        paper["affiliations"] = enrichment["affiliations"]

    if "s2_title_similarity" in enrichment:
        paper["s2_title_similarity"] = enrichment["s2_title_similarity"]
    else:
        paper.pop("s2_title_similarity", None)


def get_exact_s2_identifier(paper: Dict) -> Optional[str]:
    doi = (paper.get("doi") or "").strip()
    return doi or None


def fetch_s2_batch_by_identifier(
    identifiers: List[str],
    max_retries: int = 3,
) -> Optional[List[Optional[Dict]]]:
    if not identifiers:
        return []

    try:
        data = semantic_scholar_request(
            S2_BATCH_URL,
            params={"fields": S2_FIELDS},
            json_body={"ids": identifiers},
            method="POST",
            headers=build_s2_headers("ConfPapers/1.0"),
            timeout=S2_REQUEST_TIMEOUT,
            max_retries=max_retries,
        )
    except Exception as e:
        logger.warning("[S2] Batch lookup failed for %d ids: %s", len(identifiers), e)
        return None

    if isinstance(data, dict) and isinstance(data.get("data"), list):
        data = data["data"]
    if isinstance(data, list):
        return data

    logger.warning("[S2] Unexpected batch response type: %s", type(data).__name__)
    return None


def fetch_s2_paper_by_identifier(
    identifier: str, max_retries: int = 3
) -> Optional[Dict]:
    try:
        return semantic_scholar_request(
            f"{S2_PAPER_URL}/{urllib.parse.quote(identifier, safe='')}",
            params={"fields": S2_FIELDS},
            headers=build_s2_headers("ConfPapers/1.0"),
            timeout=S2_REQUEST_TIMEOUT,
            max_retries=max_retries,
        )
    except Exception as e:
        logger.debug("[S2] Exact lookup failed for %s: %s", identifier, e)
        return None


def fetch_s2_best_title_match(title: str, max_retries: int = 3) -> Dict[str, Any]:
    try:
        data = semantic_scholar_request(
            S2_API_URL,
            params={
                "query": title,
                "limit": 3,
                "fields": S2_FIELDS,
            },
            headers=build_s2_headers("ConfPapers/1.0"),
            timeout=S2_REQUEST_TIMEOUT,
            max_retries=max_retries,
        )
    except Exception as e:
        logger.debug("[S2] Title search failed for %s: %s", title[:80], e)
        return build_empty_enrichment("title_search")

    results = data.get("data", []) if isinstance(data, dict) else []
    if not results:
        return build_empty_enrichment("title_search")

    best_match = None
    best_sim = 0.0
    for result in results:
        sim = title_similarity(title, result.get("title", ""))
        if sim > best_sim:
            best_sim = sim
            best_match = result

    if best_match and best_sim >= 0.6:
        return build_enrichment_from_s2_result(
            best_match,
            match_method="title_search",
            similarity=best_sim,
        )

    return build_empty_enrichment("title_search")


def enrich_with_semantic_scholar(
    papers: List[Dict],
    cp_config: Optional[Dict] = None,
    max_retries: int = 3,
) -> List[Dict]:
    """
    使用 S2 补充 abstract/citations/arxiv_id。
    优先走 cache -> DOI 精确查询/批量 -> 标题搜索回退。

    Args:
        papers: 需要补充信息的论文列表
        cp_config: conf-papers 配置（用于读取 cache 路径）
        max_retries: 每次请求的最大重试次数

    Returns:
        补充信息后的论文列表
    """
    total = len(papers)
    cache_path = get_s2_cache_path(cp_config)
    cache = load_s2_cache(cache_path)
    cache_hits = 0
    exact_matches = 0
    title_matches = 0

    unresolved = []
    for paper in papers:
        cached = get_cached_enrichment(cache, paper)
        if cached is not None:
            apply_s2_enrichment(paper, cached)
            cache_hits += 1
        else:
            unresolved.append(paper)

    logger.info(
        "[S2] Cache hits: %d/%d, unresolved after cache: %d",
        cache_hits,
        total,
        len(unresolved),
    )

    exact_candidates = [paper for paper in unresolved if get_exact_s2_identifier(paper)]
    title_fallback = [
        paper for paper in unresolved if not get_exact_s2_identifier(paper)
    ]

    if exact_candidates:
        logger.info("[S2] DOI exact candidates: %d", len(exact_candidates))

    for batch in chunked(exact_candidates, S2_BATCH_SIZE):
        identifiers = [get_exact_s2_identifier(paper) for paper in batch]
        batch_results = fetch_s2_batch_by_identifier(
            identifiers, max_retries=max_retries
        )

        if batch_results is None or len(batch_results) != len(batch):
            batch_results = [None] * len(batch)

        for paper, identifier, batch_result in zip(batch, identifiers, batch_results):
            enrichment = None
            if batch_result:
                enrichment = build_enrichment_from_s2_result(batch_result, "doi_batch")
            elif identifier:
                single_result = fetch_s2_paper_by_identifier(
                    identifier, max_retries=max_retries
                )
                if single_result:
                    enrichment = build_enrichment_from_s2_result(
                        single_result, "doi_exact"
                    )

            if enrichment is not None:
                apply_s2_enrichment(paper, enrichment)
                store_cached_enrichment(cache, paper, enrichment)
                if enrichment.get("s2_matched"):
                    exact_matches += 1
            else:
                title_fallback.append(paper)

    title_search_cache = {}
    for i, paper in enumerate(title_fallback):
        title = paper.get("title", "").strip()
        if not title:
            enrichment = build_empty_enrichment("title_search")
        else:
            title_key = hashlib.sha1(title.encode("utf-8")).hexdigest()
            if title_key not in title_search_cache:
                title_search_cache[title_key] = fetch_s2_best_title_match(
                    title,
                    max_retries=max_retries,
                )
            enrichment = title_search_cache[title_key]

        apply_s2_enrichment(paper, enrichment)
        store_cached_enrichment(cache, paper, enrichment)
        if enrichment.get("s2_matched"):
            title_matches += 1

        if (i + 1) % 10 == 0:
            logger.info(
                "[S2] Title fallback progress: %d/%d",
                i + 1,
                len(title_fallback),
            )

    save_s2_cache(cache_path, cache)

    logger.info(
        "[S2] Enrichment complete: cache=%d, exact=%d, title=%d, total=%d",
        cache_hits,
        exact_matches,
        title_matches,
        total,
    )
    return papers


# ---------------------------------------------------------------------------
# 评分
# ---------------------------------------------------------------------------


def calculate_popularity_score(paper: Dict) -> float:
    """
    基于 influentialCitationCount 和 citationCount 计算热门度

    Args:
        paper: 论文信息

    Returns:
        热门度评分 (0-SCORE_MAX)
    """
    inf_cit = paper.get("influentialCitationCount", 0)
    cit = paper.get("citationCount", 0)

    if inf_cit > 0:
        # 高影响力引用：归一化到 0-SCORE_MAX
        score = min(
            inf_cit / (POPULARITY_INFLUENTIAL_CITATION_FULL_SCORE / SCORE_MAX),
            SCORE_MAX,
        )
    elif cit > 0:
        # 普通引用：更保守的评分
        score = min(cit / 200 * SCORE_MAX, SCORE_MAX * 0.7)
    else:
        score = 0.0

    return score


def filter_and_score_papers(
    papers: List[Dict], cp_config: Dict, top_n: int = 10
) -> List[Dict]:
    """
    对论文进行完整的三维评分（相关性+热门度+质量），排序取 top N
    使用当前 conf-papers 配置的关键词构建虚拟 domain 用于评分

    Args:
        papers: 论文列表（已经过 S2 补充）
        cp_config: conf-papers 专用配置
        top_n: 返回前 N 篇

    Returns:
        评分排序后的论文列表
    """
    # 构建虚拟 domain 供 calculate_relevance_score 使用
    domains = {
        "conf_papers": {
            "keywords": cp_config["keywords"],
            "arxiv_categories": ["cs.AI", "cs.CL", "cs.LG"],
        }
    }
    excluded_keywords = cp_config["excluded_keywords"]

    scored_papers = []

    for paper in papers:
        # 为了复用 calculate_relevance_score，需要为顶会论文补充 categories
        # 使用会议到分类的映射
        venue = paper.get("conference", "")
        venue_categories = VENUE_TO_CATEGORIES.get(venue, [])
        paper["categories"] = venue_categories

        # 用 abstract 替代 summary（兼容 calculate_relevance_score）
        if paper.get("abstract") and not paper.get("summary"):
            paper["summary"] = paper["abstract"]

        # 计算相关性
        relevance, matched_domain, matched_keywords = calculate_relevance_score(
            paper, domains, excluded_keywords
        )

        if relevance == 0:
            continue

        # 计算热门度
        popularity = calculate_popularity_score(paper)

        # 计算质量
        summary = paper.get("summary", "") or paper.get("abstract", "") or ""
        quality = calculate_quality_score(summary)

        # 计算综合评分（三维度）
        normalized = {
            "relevance": (relevance / SCORE_MAX) * 10,
            "popularity": (popularity / SCORE_MAX) * 10,
            "quality": (quality / SCORE_MAX) * 10,
        }
        final_score = sum(normalized[k] * WEIGHTS_CONF[k] for k in WEIGHTS_CONF)
        final_score = round(final_score, 2)

        paper["scores"] = {
            "relevance": round(relevance, 2),
            "popularity": round(popularity, 2),
            "quality": round(quality, 2),
            "recommendation": final_score,
        }
        paper["matched_domain"] = matched_domain
        paper["matched_keywords"] = matched_keywords

        scored_papers.append(paper)

    # 按推荐评分排序
    scored_papers.sort(key=lambda x: x["scores"]["recommendation"], reverse=True)

    logger.info("[Score] %d papers scored, returning top %d", len(scored_papers), top_n)
    return scored_papers[:top_n]


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Search top conference papers via DBLP + Semantic Scholar"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to config file, or one of the built-in preset filenames",
    )
    parser.add_argument(
        "--preset", type=str, default=None, help="Built-in preset name: computer or hci"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="conf_papers_filtered.json",
        help="Output JSON file path",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Conference year to search (default: from config)",
    )
    parser.add_argument(
        "--conferences",
        type=str,
        default=None,
        help="Comma-separated conference names (default: from config)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=None,
        help="Number of top papers to return (default: from config)",
    )
    parser.add_argument(
        "--max-per-venue",
        type=int,
        default=1000,
        help="Max papers to fetch per venue from DBLP",
    )
    parser.add_argument(
        "--skip-enrichment",
        action="store_true",
        help="Skip Semantic Scholar enrichment (for debugging)",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

    try:
        config_path, resolved_preset = resolve_config_path(args.config, args.preset)
    except FileNotFoundError as e:
        logger.error(str(e))
        return 1

    logger.info("Loading conf-papers config from: %s", config_path)
    cp_config = load_conf_papers_config(config_path, preset=resolved_preset)
    logger.info("Preset: %s", cp_config["preset"])
    logger.info(
        "Config: %d keywords, %d excluded",
        len(cp_config["keywords"]),
        len(cp_config["excluded_keywords"]),
    )
    logger.info(
        "Semantic Scholar API key: %s",
        "configured"
        if "x-api-key" in build_s2_headers("ConfPapers/1.0")
        else "not configured",
    )
    logger.info("Semantic Scholar cache: %s", get_s2_cache_path(cp_config))

    # 确定年份：命令行 > 配置 > 报错
    year = args.year or cp_config.get("default_year")
    if not year:
        logger.error("未指定搜索年份。请通过 --year 参数或配置文件 default_year 设置。")
        return 1

    # 确定 top_n：命令行 > 配置 > 默认 10
    top_n = args.top_n or cp_config.get("top_n", 10)

    # 确定要搜索的会议：命令行 > 配置 > 全部支持的会议
    if args.conferences:
        venues = [v.strip() for v in args.conferences.split(",")]
    elif cp_config.get("default_conferences"):
        venues = list(cp_config["default_conferences"])
    else:
        venues = list(DBLP_VENUES.keys())

    # 验证会议名（大小写不敏感匹配）
    venue_name_map = {k.upper(): k for k in DBLP_VENUES}
    valid_venues = []
    for v in venues:
        canonical = venue_name_map.get(v.upper())
        if canonical:
            valid_venues.append(canonical)
        else:
            logger.warning(
                "Unknown conference: %s (available: %s)",
                v,
                ", ".join(DBLP_VENUES.keys()),
            )
    venues = valid_venues

    if not venues:
        logger.error("No valid conferences specified")
        return 1

    logger.info("Conferences: %s", ", ".join(venues))
    logger.info("Year: %d", year)

    # ========== 第一步：DBLP 搜索 ==========
    logger.info("=" * 70)
    logger.info("Step 1: Searching papers from DBLP")
    logger.info("=" * 70)

    all_papers = search_all_conferences(year, venues, max_per_venue=args.max_per_venue)
    total_found = len(all_papers)
    logger.info("Total papers found from DBLP: %d", total_found)

    if not all_papers:
        logger.warning("No papers found from DBLP!")
        # 输出空结果
        output = {
            "preset": cp_config.get("preset"),
            "config_path": config_path,
            "year": year,
            "conferences_searched": venues,
            "total_found": 0,
            "total_filtered": 0,
            "total_enriched": 0,
            "total_unique": 0,
            "top_papers": [],
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0

    # ========== 第二步：轻量关键词过滤 ==========
    logger.info("=" * 70)
    logger.info("Step 2: Lightweight keyword filtering")
    logger.info("=" * 70)

    filtered_papers = lightweight_keyword_filter(all_papers, cp_config)
    total_filtered = len(filtered_papers)

    if not filtered_papers:
        logger.warning("No papers passed keyword filter!")
        output = {
            "preset": cp_config.get("preset"),
            "config_path": config_path,
            "year": year,
            "conferences_searched": venues,
            "total_found": total_found,
            "total_filtered": 0,
            "total_enriched": 0,
            "total_unique": 0,
            "top_papers": [],
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0

    # ========== 第三步：Semantic Scholar 补充 ==========
    total_enriched = 0
    if not args.skip_enrichment:
        logger.info("=" * 70)
        logger.info(
            "Step 3: Enriching with Semantic Scholar (%d papers)", len(filtered_papers)
        )
        logger.info("=" * 70)

        filtered_papers = enrich_with_semantic_scholar(
            filtered_papers, cp_config=cp_config
        )
        total_enriched = sum(1 for p in filtered_papers if p.get("s2_matched"))
    else:
        logger.info("Skipping Semantic Scholar enrichment (--skip-enrichment)")

    # ========== 第四步：评分排序 ==========
    logger.info("=" * 70)
    logger.info("Step 4: Scoring and ranking")
    logger.info("=" * 70)

    top_papers = filter_and_score_papers(filtered_papers, cp_config, top_n=top_n)

    # 清理输出中的内部字段
    for p in top_papers:
        p.pop("_preliminary_keywords", None)
        p.pop("s2_matched", None)
        p.pop("s2_title_similarity", None)
        p.pop("categories", None)
        p.pop("summary", None)  # 保留 abstract，去掉重复的 summary
        # 为每篇论文补充 note_filename，与 generate_note.py 的文件名规则保持一致
        # 这样 conf-papers 生成的 wikilink 可以直接使用此字段，无需自行推断
        p["note_filename"] = title_to_note_filename(p.get("title", ""))

    # 准备输出
    output = {
        "preset": cp_config.get("preset"),
        "config_path": config_path,
        "year": year,
        "conferences_searched": venues,
        "total_found": total_found,
        "total_filtered": total_filtered,
        "total_enriched": total_enriched,
        "top_papers": top_papers,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    logger.info("Results saved to: %s", args.output)
    logger.info("Top %d papers:", len(top_papers))
    for i, p in enumerate(top_papers, 1):
        cit = p.get("citationCount", 0)
        logger.info(
            "  %d. [%s] %s... (Score: %s, Citations: %d)",
            i,
            p.get("conference", "?"),
            p.get("title", "N/A")[:50],
            p["scores"]["recommendation"],
            cit,
        )

    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
