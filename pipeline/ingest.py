"""Ingest a single job posting by URL."""

import re
from urllib.parse import urlparse
import httpx

_DOMAIN_SOURCES = {
    "greenhouse.io": "Greenhouse",
    "ashbyhq.com": "Ashby",
    "lever.co": "Lever",
}


def _derive_source(url: str) -> str:
    hostname = urlparse(url).hostname or ""
    for pattern, name in _DOMAIN_SOURCES.items():
        if pattern in hostname:
            return name
    return hostname


def _extract_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if match:
        title = match.group(1).strip()
        title = re.sub(r"\s*[-|–]\s*(Greenhouse|Ashby|Lever).*$", "", title, flags=re.IGNORECASE)
        return title
    return "Untitled"


def _extract_body_text(html: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:10000]


def fetch_job_from_url(url: str) -> dict:
    resp = httpx.get(url, follow_redirects=True, timeout=30)
    resp.raise_for_status()
    html = resp.text
    return {
        "title": _extract_title(html),
        "url": url,
        "description": _extract_body_text(html),
        "source": _derive_source(url),
        "feed": "Manual Ingest",
    }
