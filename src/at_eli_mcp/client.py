"""Async httpx client for the Austrian RIS API (data.bka.gv.at) with cache.

RIS is keyless OGD. Search returns a nested ``OgdSearchResult`` envelope; full text lives at
absolute ``ris.bka.gv.at`` URLs listed in each hit's ``Dokumentliste``. We keep our own backoff
+ cache (rate-limit is undocumented).
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode, urlparse

import anyio
import httpx

from .cache import HttpCache
from .citations import ALLOWED_TEXT_HOST

DEFAULT_BASE_URL = "https://data.bka.gv.at/ris/api/v2.6"
DEFAULT_TIMEOUT = httpx.Timeout(40.0, connect=10.0)
USER_AGENT = "at-eli-mcp/0.2.0 (+https://github.com/matematicsolutions/at-eli-mcp)"

_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
_MAX_ATTEMPTS = 3


class RisError(Exception):
    """Raised when RIS returns an ``OgdSearchResult.Error`` block."""


class RisClient:
    """Async client. Use as ``async with RisClient() as c: ...``."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        cache: HttpCache | None = None,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._cache = cache or HttpCache()
        self._http = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )

    async def __aenter__(self) -> RisClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()
        self._cache.close()

    # ----- low-level ---------------------------------------------------------

    def _cache_key(self, url: str, params: dict[str, Any] | None) -> str:
        if not params:
            return url
        items = sorted((k, v) for k, v in params.items() if v is not None)
        return f"{url}?{urlencode(items, doseq=True)}"

    async def _request_with_backoff(
        self, url: str, params: dict[str, Any] | None, *, accept: str
    ) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                resp = await self._http.get(url, params=params, headers={"Accept": accept})
                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code not in _RETRY_STATUS or attempt == _MAX_ATTEMPTS - 1:
                    raise
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt == _MAX_ATTEMPTS - 1:
                    raise
            await anyio.sleep(0.5 * (2**attempt))
        assert last_exc is not None
        raise last_exc

    # ----- typed endpoints ---------------------------------------------------

    async def bundesrecht_search(self, params: dict[str, Any]) -> dict[str, Any]:
        """GET /Bundesrecht. Returns the OgdSearchResult dict; raises RisError on an Error block."""
        url = f"{self.base_url}/Bundesrecht"
        key = self._cache_key(url, params)
        cached = self._cache.get(key)
        if cached is None:
            clean = {k: v for k, v in params.items() if v is not None}
            resp = await self._request_with_backoff(url, clean or None, accept="application/json")
            cached = resp.json()
            self._cache.set(key, cached, ttl=HttpCache.ttl_for("search"))
        result = cached.get("OgdSearchResult", {}) if isinstance(cached, dict) else {}
        if isinstance(result, dict) and isinstance(result.get("Error"), dict):
            raise RisError(str(result["Error"].get("Message", "RIS error")))
        return result if isinstance(result, dict) else {}

    async def judikatur_search(self, params: dict[str, Any]) -> dict[str, Any]:
        """GET /Judikatur. Returns the OgdSearchResult dict; raises RisError on an Error block."""
        url = f"{self.base_url}/Judikatur"
        key = self._cache_key(url, params)
        cached = self._cache.get(key)
        if cached is None:
            clean = {k: v for k, v in params.items() if v is not None}
            resp = await self._request_with_backoff(url, clean or None, accept="application/json")
            cached = resp.json()
            self._cache.set(key, cached, ttl=HttpCache.ttl_for("search"))
        result = cached.get("OgdSearchResult", {}) if isinstance(cached, dict) else {}
        if isinstance(result, dict) and isinstance(result.get("Error"), dict):
            raise RisError(str(result["Error"].get("Message", "RIS error")))
        return result if isinstance(result, dict) else {}

    async def get_text_url(self, url: str) -> tuple[str, str | None]:
        """Fetch full text at an absolute ris.bka.gv.at URL (host-restricted)."""
        host = urlparse(url).netloc.lower()
        if ALLOWED_TEXT_HOST not in host:
            raise ValueError(f"Refusing to fetch non-RIS host: {host!r}")
        key = "text::" + url
        cached = self._cache.get(key)
        if cached is not None and isinstance(cached, list) and len(cached) == 2:
            return cached[0], cached[1]
        resp = await self._request_with_backoff(url, None, accept="*/*")
        text = resp.text
        ct = resp.headers.get("content-type")
        self._cache.set(key, [text, ct], ttl=HttpCache.ttl_for("act"))
        return text, ct


def extract_references(result: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
    """Flatten OgdSearchResult into (total, [OgdDocumentReference dicts])."""
    doc_results = result.get("OgdDocumentResults", {}) if isinstance(result, dict) else {}
    if not isinstance(doc_results, dict):
        return 0, []
    refs = doc_results.get("OgdDocumentReference")
    items = refs if isinstance(refs, list) else ([refs] if isinstance(refs, dict) else [])
    items = [r for r in items if isinstance(r, dict)]
    total = 0
    hits = doc_results.get("Hits")
    if isinstance(hits, dict):
        text = hits.get("#text")
        if isinstance(text, str) and text.isdigit():
            total = int(text)
        elif isinstance(text, int):
            total = text
    if total == 0:
        total = len(items)
    return total, items
