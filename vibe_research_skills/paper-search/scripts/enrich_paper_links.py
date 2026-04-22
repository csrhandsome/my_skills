#!/usr/bin/env python3
"""
Post-process paper-search candidates and enrich them with repo/project/code links.
"""

import argparse
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from search_arxiv import (
    S2_REQUEST_TIMEOUT,
    build_s2_headers,
    load_research_config,
    semantic_scholar_request,
    set_semantic_scholar_api_key,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 20
DEFAULT_RETRIES = 2
CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
S2_FIELDS = "title,url,externalIds"
S2_PAPER_URL = "https://api.semanticscholar.org/graph/v1/paper"
S2_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
MAX_HTML_BYTES = 2 * 1024 * 1024

BLOCKED_DOMAINS = {
    "arxiv.org",
    "doi.org",
    "dx.doi.org",
    "semanticscholar.org",
    "api.semanticscholar.org",
    "openalex.org",
    "dblp.org",
    "researchtrend.ai",
    "twitter.com",
    "x.com",
    "facebook.com",
    "linkedin.com",
    "instagram.com",
    "t.co",
    "alphaxiv.org",
    "core.ac.uk",
    "dagshub.com",
    "influencemap.cmlab.dev",
    "paperswithcode.com",
    "reddit.com",
    "scholar.google.com",
    "sciencecast.org",
    "tech.cornell.edu",
    "ui.adsabs.harvard.edu",
    "connectedpapers.com",
    "cornell.edu",
    "litmaps.co",
    "scite.ai",
    "gotit.pub",
    "madskills.com",
    "purl.org",
    "w3.org",
}

RESOURCE_HINT_KEYWORDS = {
    "github",
    "gitlab",
    "bitbucket",
    "huggingface",
    "project",
    "code",
    "demo",
    "dataset",
    "benchmark",
    "model",
    "checkpoint",
    "weights",
    "gradio",
    "replicate",
    "colab",
    "space",
    "spaces",
}

BLOCKED_PATH_KEYWORDS = {
    "privacy",
    "terms",
    "policy",
    "cookie",
    "cookies",
    "citation",
    "bibtex",
    "login",
    "signin",
    "signup",
    "register",
    "downloadcitation",
    "references",
}

ASSET_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".css",
    ".js",
    ".ico",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
}


def normalize_title_for_lookup(title: str) -> str:
    return re.sub(r"[^a-z0-9\s]", "", (title or "").lower()).strip()


def title_similarity(a: str, b: str) -> float:
    a_norm = normalize_title_for_lookup(a)
    b_norm = normalize_title_for_lookup(b)
    if not a_norm or not b_norm:
        return 0.0

    words_a = set(a_norm.split())
    words_b = set(b_norm.split())
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def get_cache_path(config: Optional[Dict[str, Any]] = None) -> Path:
    configured = None
    if config:
        configured = config.get("paper_link_cache_path") or config.get("semantic_scholar_cache_path")
    configured = configured or os.environ.get("VIBE_RESEARCH_PAPER_LINK_CACHE_PATH")
    if configured:
        return Path(os.path.expanduser(configured))

    xdg_cache_home = os.environ.get("XDG_CACHE_HOME")
    cache_root = Path(xdg_cache_home).expanduser() if xdg_cache_home else Path.home() / ".cache"
    return cache_root / "vibe_research_skills" / "paper_link_enrichment_cache.json"


def load_cache(cache_path: Path) -> Dict[str, Dict[str, Any]]:
    try:
        if not cache_path.exists():
            return {}
        with open(cache_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return raw if isinstance(raw, dict) else {}
    except Exception as e:
        logger.warning("Failed to load cache %s: %s", cache_path, e)
        return {}


def save_cache(cache_path: Path, cache: Dict[str, Dict[str, Any]]) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("Failed to save cache %s: %s", cache_path, e)


def get_cache_keys_for_paper(paper: Dict[str, Any]) -> List[str]:
    keys = []
    arxiv_id = extract_arxiv_id(paper)
    doi = extract_doi(paper)
    title_key = normalize_title_for_lookup(paper.get("title", ""))
    if arxiv_id:
        keys.append(f"arxiv:{arxiv_id}")
    if doi:
        keys.append(f"doi:{doi.lower()}")
    if title_key:
        keys.append(f"title:{title_key}")
    return keys


def get_cached_enrichment(cache: Dict[str, Dict[str, Any]], paper: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    now = time.time()
    for key in get_cache_keys_for_paper(paper):
        entry = cache.get(key)
        if not entry:
            continue
        cached_at = entry.get("cached_at", 0)
        if now - cached_at > CACHE_TTL_SECONDS:
            cache.pop(key, None)
            continue
        data = entry.get("data")
        if isinstance(data, dict):
            return data
    return None


def store_cached_enrichment(cache: Dict[str, Dict[str, Any]], paper: Dict[str, Any], enrichment: Dict[str, Any]) -> None:
    entry = {"cached_at": int(time.time()), "data": enrichment}
    for key in get_cache_keys_for_paper(paper):
        cache[key] = entry


def build_empty_enrichment() -> Dict[str, Any]:
    return {
        "status": "none",
        "sources_attempted": [],
        "primary_repo_url": "",
        "primary_repo_platform": "",
        "project_url": "",
        "code_urls": [],
        "demo_urls": [],
        "model_urls": [],
        "dataset_urls": [],
        "paper_urls": [],
        "confidence": "none",
        "match_method": "",
        "warnings": [],
        "last_checked_at": "",
    }


def build_automation_links(enrichment: Dict[str, Any]) -> Dict[str, str]:
    repo = enrichment.get("primary_repo_url") or ""
    project = enrichment.get("project_url") or ""
    code = repo or first_item(enrichment.get("code_urls", [])) or ""
    demo = first_item(enrichment.get("demo_urls", [])) or ""
    return {
        "repo": repo,
        "project": project,
        "code": code,
        "demo": demo,
    }


def first_item(items: List[str]) -> str:
    return items[0] if items else ""


def extract_arxiv_id(paper: Dict[str, Any]) -> str:
    candidates = [
        paper.get("arxiv_id"),
        paper.get("arxivId"),
        paper.get("paper_id"),
        paper.get("id"),
        paper.get("url"),
    ]
    for value in candidates:
        if not value:
            continue
        text = str(value)
        match = re.search(r"(\d{4}\.\d{4,5})(v\d+)?", text)
        if match:
            return match.group(1)
    external_ids = paper.get("externalIds") or {}
    arxiv = external_ids.get("ArXiv") if isinstance(external_ids, dict) else None
    return str(arxiv or "").strip()


def extract_doi(paper: Dict[str, Any]) -> str:
    doi = str(paper.get("doi") or "").strip()
    if doi:
        return doi
    external_ids = paper.get("externalIds") or {}
    if isinstance(external_ids, dict):
        return str(external_ids.get("DOI") or "").strip()
    return ""


def infer_default_output_path(input_path: str) -> str:
    path = Path(input_path)
    if path.suffix == ".json":
        return str(path.with_name(f"{path.stem}_enriched.json"))
    return f"{input_path}_enriched.json"


def fetch_text(url: str, timeout: int, user_agent: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "")
        raw = response.read(MAX_HTML_BYTES)
        charset = response.headers.get_content_charset() or "utf-8"
        text = raw.decode(charset, errors="replace")
        if "html" not in content_type.lower() and "text" not in content_type.lower():
            logger.debug("Fetched non-HTML/text content from %s (%s)", url, content_type)
        return text


def fetch_text_with_retries(url: str, timeout: int, retries: int, user_agent: str) -> str:
    last_error = None
    for attempt in range(retries + 1):
        try:
            return fetch_text(url, timeout=timeout, user_agent=user_agent)
        except Exception as e:
            last_error = e
            if attempt >= retries:
                raise
            wait_seconds = min(2 ** attempt, 5)
            logger.debug("Retrying %s after error: %s", url, e)
            time.sleep(wait_seconds)
    if last_error:
        raise last_error
    return ""


def extract_href_urls(html: str, base_url: str) -> Set[str]:
    urls = set()
    for match in re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.IGNORECASE):
        candidate = match.strip()
        if not candidate or candidate.startswith(("#", "javascript:", "mailto:")):
            continue
        urls.add(urllib.parse.urljoin(base_url, unescape(candidate)))
    return urls


def extract_plain_urls(text: str) -> Set[str]:
    urls = set()
    for match in re.findall(r"https?://[^\s\"'<>\\]+", text, flags=re.IGNORECASE):
        cleaned = match.rstrip(").,;:!?]")
        urls.add(unescape(cleaned))
    return urls


def should_skip_url(url: str, page_url: Optional[str] = None) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return True

    if parsed.scheme not in {"http", "https"}:
        return True

    host = parsed.netloc.lower()
    path = parsed.path.lower()
    normalized = url.lower()
    if not host:
        return True
    if any(host == blocked or host.endswith(f".{blocked}") for blocked in BLOCKED_DOMAINS):
        return True
    if not any(keyword in normalized for keyword in RESOURCE_HINT_KEYWORDS):
        return True
    if any(keyword in path for keyword in BLOCKED_PATH_KEYWORDS):
        return True
    if Path(path).suffix.lower() in ASSET_EXTENSIONS:
        return True
    if page_url:
        page_host = urllib.parse.urlparse(page_url).netloc.lower()
        if page_host and host == page_host and "github" not in host and "huggingface" not in host:
            return True
    return False


def normalize_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    path = re.sub(r"/+", "/", parsed.path or "/")

    if "github.com" in host or "gitlab.com" in host or "bitbucket.org" in host:
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2:
            path = "/" + "/".join(parts[:2])
        elif parts:
            path = "/" + "/".join(parts)
        else:
            path = "/"
        return urllib.parse.urlunparse(("https", host, path, "", "", ""))

    if "huggingface.co" in host:
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2 and parts[0] in {"datasets", "spaces"}:
            path = "/" + "/".join(parts[:2])
        elif parts:
            path = "/" + "/".join(parts[:2])
        else:
            path = "/"
        return urllib.parse.urlunparse(("https", host, path, "", "", ""))

    cleaned_path = path.rstrip("/") or "/"
    return urllib.parse.urlunparse(("https", host, cleaned_path, "", "", ""))


def classify_url(url: str) -> Optional[str]:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    url_lower = url.lower()

    if any(domain in host for domain in ("github.com", "gitlab.com", "bitbucket.org")):
        return "code"
    if "huggingface.co" in host:
        if "/datasets/" in path or path.startswith("/datasets/"):
            return "dataset"
        if "/spaces/" in path or path.startswith("/spaces/"):
            return "demo"
        return "model"
    if any(token in url_lower for token in ("demo", "gradio", "replicate", "colab.research.google.com")):
        return "demo"
    if any(token in url_lower for token in ("dataset", "data", "benchmark")):
        return "dataset"
    if any(token in url_lower for token in ("model", "checkpoint", "weights")):
        return "model"
    if any(token in url_lower for token in ("project", "homepage", "home-page")):
        return "project"
    return "project"


def add_classified_url(enrichment: Dict[str, Any], url: str) -> None:
    normalized = normalize_url(url)
    category = classify_url(normalized)
    if not category:
        return

    key_map = {
        "code": "code_urls",
        "project": "project_url",
        "demo": "demo_urls",
        "model": "model_urls",
        "dataset": "dataset_urls",
    }
    key = key_map[category]

    if key == "project_url":
        if not enrichment["project_url"]:
            enrichment["project_url"] = normalized
        elif enrichment["project_url"] != normalized:
            enrichment["paper_urls"].append(normalized)
        return

    target = enrichment[key]
    if normalized not in target:
        target.append(normalized)


def finalize_enrichment(enrichment: Dict[str, Any]) -> Dict[str, Any]:
    dedupe_list_fields = ["code_urls", "demo_urls", "model_urls", "dataset_urls", "paper_urls", "warnings", "sources_attempted"]
    for field in dedupe_list_fields:
        enrichment[field] = dedupe_preserve_order(enrichment.get(field, []))

    primary_repo = first_item(enrichment["code_urls"])
    enrichment["primary_repo_url"] = primary_repo
    enrichment["primary_repo_platform"] = detect_repo_platform(primary_repo)

    if primary_repo:
        enrichment["status"] = "ok"
    elif enrichment.get("project_url") or enrichment["demo_urls"] or enrichment["model_urls"] or enrichment["dataset_urls"]:
        enrichment["status"] = "partial"
    elif enrichment["warnings"]:
        enrichment["status"] = "error"
    else:
        enrichment["status"] = "none"

    if primary_repo:
        enrichment["confidence"] = "high" if "arxiv_abs_html" in enrichment["sources_attempted"] or "doi_landing_page" in enrichment["sources_attempted"] else "medium"
    elif enrichment.get("project_url"):
        enrichment["confidence"] = "medium"
    elif enrichment["demo_urls"] or enrichment["model_urls"] or enrichment["dataset_urls"]:
        enrichment["confidence"] = "low"
    else:
        enrichment["confidence"] = "none"

    if not enrichment.get("match_method"):
        enrichment["match_method"] = ",".join(enrichment["sources_attempted"])

    enrichment["last_checked_at"] = datetime.now(timezone.utc).isoformat()
    return enrichment


def detect_repo_platform(url: str) -> str:
    host = urllib.parse.urlparse(url).netloc.lower()
    if "github.com" in host:
        return "github"
    if "gitlab.com" in host:
        return "gitlab"
    if "bitbucket.org" in host:
        return "bitbucket"
    return ""


def dedupe_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    output = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            output.append(item)
    return output


def enrich_from_html(enrichment: Dict[str, Any], html: str, page_url: str, source_name: str) -> None:
    discovered = set()
    discovered.update(extract_href_urls(html, page_url))
    discovered.update(extract_plain_urls(html))

    found_any = False
    for url in sorted(discovered):
        if should_skip_url(url, page_url=page_url):
            continue
        add_classified_url(enrichment, url)
        found_any = True

    if source_name not in enrichment["sources_attempted"]:
        enrichment["sources_attempted"].append(source_name)
    if found_any and not enrichment.get("match_method"):
        enrichment["match_method"] = source_name


def enrich_from_arxiv_abs(paper: Dict[str, Any], enrichment: Dict[str, Any], timeout: int, retries: int) -> None:
    arxiv_id = extract_arxiv_id(paper)
    if not arxiv_id:
        return
    url = f"https://arxiv.org/abs/{arxiv_id}"
    html = fetch_text_with_retries(url, timeout=timeout, retries=retries, user_agent="PaperLinkEnricher/1.0")
    enrich_from_html(enrichment, html, url, "arxiv_abs_html")


def enrich_from_doi(paper: Dict[str, Any], enrichment: Dict[str, Any], timeout: int, retries: int) -> None:
    doi = extract_doi(paper)
    if not doi:
        return
    url = f"https://doi.org/{urllib.parse.quote(doi, safe='/')}"
    html = fetch_text_with_retries(url, timeout=timeout, retries=retries, user_agent="PaperLinkEnricher/1.0")
    enrich_from_html(enrichment, html, url, "doi_landing_page")


def fetch_s2_result_by_identifier(identifier: str, timeout: int, retries: int) -> Optional[Dict[str, Any]]:
    if not identifier:
        return None
    try:
        return semantic_scholar_request(
            f"{S2_PAPER_URL}/{urllib.parse.quote(identifier, safe='')}",
            params={"fields": S2_FIELDS},
            headers=build_s2_headers("PaperLinkEnricher/1.0"),
            timeout=timeout or S2_REQUEST_TIMEOUT,
            max_retries=retries + 1,
        )
    except urllib.error.HTTPError as e:
        if e.code == 404:
            logger.debug("S2 identifier lookup returned 404 for %s", identifier)
            return None
        logger.debug("S2 identifier lookup failed for %s: %s", identifier, e)
        return None
    except Exception as e:
        logger.debug("S2 identifier lookup failed for %s: %s", identifier, e)
        return None


def fetch_s2_best_title_match(paper: Dict[str, Any], timeout: int, retries: int) -> Optional[Dict[str, Any]]:
    title = (paper.get("title") or "").strip()
    if not title:
        return None
    try:
        data = semantic_scholar_request(
            S2_SEARCH_URL,
            params={"query": title, "limit": 5, "fields": S2_FIELDS},
            headers=build_s2_headers("PaperLinkEnricher/1.0"),
            timeout=timeout or S2_REQUEST_TIMEOUT,
            max_retries=retries + 1,
        )
    except urllib.error.HTTPError as e:
        if e.code == 404:
            logger.debug("S2 title search returned 404 for %s", title)
            return None
        logger.debug("S2 title search failed for %s: %s", title, e)
        return None
    except Exception as e:
        logger.debug("S2 title search failed for %s: %s", title, e)
        return None

    candidates = data.get("data") if isinstance(data, dict) else None
    if not isinstance(candidates, list):
        return None

    best_result = None
    best_similarity = 0.0
    for candidate in candidates:
        similarity = title_similarity(title, candidate.get("title", ""))
        if similarity > best_similarity:
            best_similarity = similarity
            best_result = candidate
    if best_similarity >= 0.8:
        best_result = dict(best_result)
        best_result["_title_similarity"] = best_similarity
        return best_result
    return None


def enrich_via_semantic_scholar(paper: Dict[str, Any], enrichment: Dict[str, Any], timeout: int, retries: int) -> None:
    result = None
    doi = extract_doi(paper)
    arxiv_id = extract_arxiv_id(paper)

    if doi:
        result = fetch_s2_result_by_identifier(f"DOI:{doi}", timeout, retries)
        if result and "semantic_scholar_doi" not in enrichment["sources_attempted"]:
            enrichment["sources_attempted"].append("semantic_scholar_doi")
    if not result and arxiv_id:
        result = fetch_s2_result_by_identifier(f"ARXIV:{arxiv_id}", timeout, retries)
        if result and "semantic_scholar_arxiv" not in enrichment["sources_attempted"]:
            enrichment["sources_attempted"].append("semantic_scholar_arxiv")
    if not result:
        result = fetch_s2_best_title_match(paper, timeout, retries)
        if result and "semantic_scholar_title" not in enrichment["sources_attempted"]:
            enrichment["sources_attempted"].append("semantic_scholar_title")

    if not result:
        return

    ext_ids = result.get("externalIds") or {}
    if not paper.get("doi") and ext_ids.get("DOI"):
        paper["doi"] = ext_ids["DOI"]
    if not paper.get("arxiv_id") and ext_ids.get("ArXiv"):
        paper["arxiv_id"] = ext_ids["ArXiv"]
    if not enrichment.get("match_method"):
        enrichment["match_method"] = first_item(enrichment["sources_attempted"]) or "semantic_scholar"


def enrich_single_paper(
    paper: Dict[str, Any],
    timeout: int,
    retries: int,
    cache: Dict[str, Dict[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    cached = get_cached_enrichment(cache, paper)
    if cached:
        enrichment = finalize_enrichment(dict(cached))
        return enrichment, build_automation_links(enrichment)

    enrichment = build_empty_enrichment()

    try:
        enrich_from_arxiv_abs(paper, enrichment, timeout, retries)
    except Exception as e:
        enrichment["warnings"].append(f"arxiv_abs_html_failed: {e}")

    try:
        enrich_from_doi(paper, enrichment, timeout, retries)
    except Exception as e:
        enrichment["warnings"].append(f"doi_landing_page_failed: {e}")

    try:
        enrich_via_semantic_scholar(paper, enrichment, timeout, retries)
    except Exception as e:
        enrichment["warnings"].append(f"semantic_scholar_failed: {e}")

    if not enrichment["code_urls"] and not enrichment.get("project_url") and extract_doi(paper):
        try:
            enrich_from_doi(paper, enrichment, timeout, retries)
        except Exception as e:
            enrichment["warnings"].append(f"doi_retry_failed: {e}")

    enrichment = finalize_enrichment(enrichment)
    automation_links = build_automation_links(enrichment)
    store_cached_enrichment(cache, paper, enrichment)
    return enrichment, automation_links


def build_summary(papers: List[Dict[str, Any]]) -> Dict[str, Any]:
    status_counts = {"ok": 0, "partial": 0, "none": 0, "error": 0}
    sources_used = set()
    for paper in papers:
        enrichment = paper.get("link_enrichment") or {}
        status = enrichment.get("status", "none")
        status_counts[status] = status_counts.get(status, 0) + 1
        for source in enrichment.get("sources_attempted", []):
            sources_used.add(source)

    return {
        "total_processed": len(papers),
        "enriched_ok": status_counts.get("ok", 0),
        "partial": status_counts.get("partial", 0),
        "none": status_counts.get("none", 0),
        "error": status_counts.get("error", 0),
        "sources_used": sorted(sources_used),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich paper-search candidates with repo/project/code links")
    parser.add_argument("--input", required=True, help="Input JSON path from paper-search/scripts/search_arxiv.py")
    parser.add_argument("--output", default=None, help="Output enriched JSON path")
    parser.add_argument("--config", default=None, help="Optional preference config for API key and cache settings")
    parser.add_argument("--max-papers", type=int, default=None, help="Limit candidate papers for debugging")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Network timeout in seconds")
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES, help="Retry count per network source")
    parser.add_argument("--cache-path", default=None, help="Optional cache file path")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

    output_path = args.output or infer_default_output_path(args.input)

    config = {}
    if args.config:
        try:
            config = load_research_config(args.config)
        except Exception as e:
            logger.error("Failed to load config %s: %s", args.config, e)
            return 1
    else:
        set_semantic_scholar_api_key(None)

    cache_path = Path(os.path.expanduser(args.cache_path)) if args.cache_path else get_cache_path(config)
    cache = load_cache(cache_path)

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as e:
        logger.error("Failed to read input JSON %s: %s", args.input, e)
        return 1

    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        logger.error("Input JSON missing 'candidates' list: %s", args.input)
        return 1

    selected_candidates = candidates[: args.max_papers] if args.max_papers else candidates
    for index, paper in enumerate(selected_candidates, start=1):
        logger.info("Enriching paper %d/%d: %s", index, len(selected_candidates), paper.get("title", "<untitled>"))
        enrichment, automation_links = enrich_single_paper(
            paper=paper,
            timeout=args.timeout,
            retries=args.retries,
            cache=cache,
        )
        paper["link_enrichment"] = enrichment
        paper["automation_links"] = automation_links

    payload["enrichment_summary"] = build_summary(selected_candidates)

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        logger.error("Failed to write output JSON %s: %s", output_path, e)
        return 1

    save_cache(cache_path, cache)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    logger.info("Enriched results saved to: %s", output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
