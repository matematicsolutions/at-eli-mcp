"""Smoke tests - require internet, hit the live RIS API.

Run manually:

    pytest tests/test_smoke.py -v
"""

from __future__ import annotations

import pytest

from at_eli_mcp.models import CaseSearchQuery, SearchQuery
from at_eli_mcp.server import (
    at_case_search,
    at_get_case_text,
    at_get_text,
    at_list_collections,
    at_search,
)


@pytest.mark.asyncio
async def test_smoke_list_collections() -> None:
    cols = await at_list_collections()
    codes = {c.code for c in cols}
    assert "Bundesrecht" in codes, f"expected Bundesrecht, got {codes}"


@pytest.mark.asyncio
async def test_smoke_search_datenschutz() -> None:
    result = await at_search(SearchQuery(suchworte="Datenschutzgesetz", page_size="Ten"))
    assert result.total > 0, "expected hits for 'Datenschutzgesetz'"
    assert len(result.items) > 0
    for item in result.items:
        assert item.eli_uri is not None, "missing eli_uri"
        assert "ris.bka.gv.at/eli" in item.eli_uri, f"bad eli: {item.eli_uri!r}"
        assert item.human_readable_citation is not None
        assert item.source_url is not None


@pytest.mark.asyncio
async def test_smoke_get_text_chained() -> None:
    result = await at_search(SearchQuery(suchworte="Datenschutzgesetz", page_size="Ten"))
    html_url = None
    for item in result.items:
        if item.content_urls.get("html"):
            html_url = item.content_urls["html"]
            break
    assert html_url is not None, "no html content_url found in search hits"
    text = await at_get_text(html_url, eli_uri="x", human_readable_citation="y")
    assert text.format == "html"
    assert text.content is not None and len(text.content) > 0
    assert "ris.bka.gv.at" in text.source_url
    assert text.byte_size and text.byte_size > 0


@pytest.mark.asyncio
async def test_smoke_case_search_native_ecli() -> None:
    result = await at_case_search(CaseSearchQuery(suchworte="Schadenersatz", applikation="Justiz"))
    assert result.total > 0, "expected Judikatur hits for 'Schadenersatz'"
    assert len(result.items) > 0
    for item in result.items:
        assert item.ecli and item.ecli.startswith("ECLI:AT:"), f"bad ecli: {item.ecli!r}"
        assert item.human_readable_citation is not None
        assert item.source_url is not None


@pytest.mark.asyncio
async def test_smoke_get_case_text_chained() -> None:
    result = await at_case_search(CaseSearchQuery(suchworte="Schadenersatz", applikation="Justiz"))
    url = None
    ecli = None
    for item in result.items:
        if item.content_urls.get("html") or item.content_urls.get("xml"):
            url = item.content_urls.get("html") or item.content_urls.get("xml")
            ecli = item.ecli
            break
    assert url is not None, "no content_url found in case hits"
    text = await at_get_case_text(url, ecli=ecli, human_readable_citation="y")
    assert text.content is not None and len(text.content) > 0
    assert "ris.bka.gv.at" in text.source_url
    assert text.ecli == ecli
