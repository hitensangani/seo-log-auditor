"""Sitemap fetcher that handles plain sitemaps, sitemap indexes, and gzip."""

from __future__ import annotations

import gzip
import io
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from urllib.parse import urlparse

import requests

_SM_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
_USER_AGENT = "seo-log-auditor/0.1.2 (+https://github.com/hitensangani/seo-log-auditor)"
_TIMEOUT = 30


@dataclass
class SitemapResult:
    urls: list[str] = field(default_factory=list)
    fetched: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _fetch(url: str) -> bytes:
    resp = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=_TIMEOUT)
    resp.raise_for_status()
    body = resp.content
    if url.endswith(".gz") or resp.headers.get("Content-Type", "").startswith("application/x-gzip"):
        body = gzip.decompress(body)
    return body


def _parse_xml(xml_bytes: bytes) -> tuple[str, list[str]]:
    """Returns (root_tag, list_of_locs). Root tag is ``urlset`` or ``sitemapindex``."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid XML: {exc}") from exc
    tag = root.tag.replace(_SM_NS, "")
    locs: list[str] = []
    for child in root:
        # IMPORTANT: don't use `find(a) or find(b)` -- xml.etree Elements with
        # no children are falsy, so the `or` would silently drop every leaf
        # `<loc>` and skip the whole sitemap.
        loc_el = child.find(f"{_SM_NS}loc")
        if loc_el is None:
            loc_el = child.find("loc")
        if loc_el is not None and loc_el.text:
            locs.append(loc_el.text.strip())
    return tag, locs


def fetch_sitemap(url: str, max_depth: int = 3) -> SitemapResult:
    """Fetch a sitemap or sitemap index, recursing into child sitemaps.

    ``max_depth`` caps recursion to avoid runaway behaviour on misconfigured
    indexes that point at themselves.
    """
    result = SitemapResult()
    seen: set[str] = set()
    queue: list[tuple[str, int]] = [(url, 0)]

    while queue:
        current, depth = queue.pop(0)
        if current in seen or depth > max_depth:
            continue
        seen.add(current)
        try:
            body = _fetch(current)
            tag, locs = _parse_xml(body)
            result.fetched.append(current)
        except (requests.RequestException, ValueError) as exc:
            result.errors.append(f"{current}: {exc}")
            continue

        if tag == "sitemapindex":
            queue.extend((loc, depth + 1) for loc in locs)
        else:  # urlset
            result.urls.extend(locs)

    # Deduplicate while preserving order
    seen_urls: set[str] = set()
    deduped: list[str] = []
    for u in result.urls:
        if u not in seen_urls:
            seen_urls.add(u)
            deduped.append(u)
    result.urls = deduped
    return result


def to_paths(urls: list[str], base_host: str | None = None) -> list[str]:
    """Reduce full URLs to ``path?query`` form so they can be compared with
    log entries (which lack the host).

    If ``base_host`` is given, only URLs whose host shares an apex domain with
    ``base_host`` are kept (so ``www.example.com`` and ``example.com`` are
    treated as the same site). Pass ``None`` to skip host filtering entirely.
    """
    base_apex = _apex(base_host) if base_host else None
    out: list[str] = []
    for u in urls:
        try:
            parsed = urlparse(u)
        except ValueError:
            continue
        if not parsed.path:
            continue
        if base_apex and parsed.netloc and _apex(parsed.netloc) != base_apex:
            continue
        out.append(parsed.path + (f"?{parsed.query}" if parsed.query else ""))
    return out


def _apex(host: str) -> str:
    """Crude apex-domain extraction without a public suffix list. Strips the
    leading ``www.`` and keeps the last two labels for everything else.
    Good enough to make ``example.com`` == ``www.example.com`` ==
    ``shop.example.com`` for our matching purposes; users with multi-TLD
    setups can disable host filtering entirely.
    """
    host = host.lower().split(":", 1)[0]  # strip port
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host
