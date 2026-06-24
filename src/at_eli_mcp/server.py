"""FastMCP entry point - Austrian RIS federal-law tools.

Run:

    python -m at_eli_mcp.server

Configuration via env:

- ``AT_ELI_CACHE_DIR`` (default ``~/.matematic/cache/at-eli``)
- ``AT_ELI_AUDIT_DIR`` (default ``~/.matematic/audit``)
- ``AT_ELI_BASE_URL`` (default ``https://data.bka.gv.at/ris/api/v2.6``)
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .audit import AuditLogger, hash_input, timer
from .citations import flatten_case_reference, flatten_reference
from .client import DEFAULT_BASE_URL, RisClient, RisError, extract_references
from .models import (
    CaseRef,
    CaseSearchQuery,
    CaseSearchResult,
    CaseText,
    Collection,
    LawRef,
    LawText,
    SearchQuery,
    SearchResult,
    TextFormat,
)

INSTRUCTIONS = """\
This MCP server exposes the Austrian RIS API (data.bka.gv.at), the official legal information system of the Republic of Austria, operated by the Bundeskanzleramt. It covers federal law (Bundesrecht) and case law (Judikatur). Legislation carries the citation contract `eli_uri` / `human_readable_citation` / `source_url`; case law carries a native `ecli` instead of an ELI.

## Call order

1. `at_search` - search federal law by `suchworte` (free text) and/or `titel`. Returns hits, each with `eli_uri` (a full ELI URL), `human_readable_citation` (e.g. "Datenschutzgesetz, BGBl. I Nr. 165/1999"), `source_url`, and `content_urls` ({html, xml}).
2. `at_get_text` - fetch the full text of an act. Pass a `content_url` taken from a hit's `content_urls` (html or xml). Also pass that hit's `eli_uri` and `human_readable_citation` so the text response stays citable.
3. `at_case_search` - search case law (Judikatur) by `suchworte`, choosing an `applikation` (court): Justiz (incl. OGH), Vfgh, Vwgh, Bvwg, Lvwg, Dsk and others. Each hit carries a native `ecli` (e.g. "ECLI:AT:OGH0002:1981:RS0030792"), `human_readable_citation`, `source_url`, and `content_urls`.
4. `at_get_case_text` - fetch the full text of a decision. Pass a `content_url` from a case hit's `content_urls`; also pass its `ecli` and `human_readable_citation` so the text stays citable.
5. `at_list_collections` - the RIS collections (Bundesrecht and Judikatur are exposed; Landesrecht is not yet).

## Hard constraints

- **ELI / ECLI are the keys to citability** - RIS returns a full ELI URL for legislation and a native ECLI for case law; do not invent either.
- **Every response has `human_readable_citation` + `source_url`** - cite both to the user.
- **No modification of official text** - returned verbatim from RIS.
- **Landesrecht not covered** - relay the `dataset_note`; state law is not exposed yet.
- **Audit log JSONL** - every tool call appends to `~/.matematic/audit/at-eli-mcp.jsonl`.
- **Full text is fetched only from ris.bka.gv.at** - any other host is refused.

## Error iteration

Tools return a structured error with a `[code]` prefix:
- `invalid_arg` - a parameter is missing or invalid (e.g. empty query, a content_url that is not a ris.bka.gv.at URL).
- `not_found` - nothing matched, or the document text does not exist.
- `unsupported_format` - a `content_url` for `at_get_text` / `at_get_case_text` must end in `.html` or `.xml`.
- `upstream_error` - a RIS API error (HTTP, timeout, schema validation). Retry once before surfacing.

## Response style

- Cite acts as `human_readable_citation` with the ELI URL: "Datenschutzgesetz, BGBl. I Nr. 165/1999 (https://www.ris.bka.gv.at/eli/...)".
- Cite decisions with their `ecli` and `source_url`.
- NEVER invent an ELI, an ECLI, a BGBl number or a date - take each from the search hit.
- Relay the `dataset_note` when scope matters to the answer.
"""


class ToolError(Exception):
    """Structured error for at-eli MCP tools - visible to the LLM with a [code] prefix."""

    VALID_CODES = frozenset({
        "invalid_arg",
        "not_found",
        "unsupported_format",
        "upstream_error",
    })

    def __init__(self, code: str, message: str):
        if code not in self.VALID_CODES:
            raise ValueError(f"Unknown ToolError code: {code}. Valid: {sorted(self.VALID_CODES)}")
        self.code = code
        super().__init__(f"[{code}] {message}")


READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    idempotentHint=True,
    destructiveHint=False,
    openWorldHint=True,
)

_COLLECTIONS: list[dict[str, str]] = [
    {"code": "Bundesrecht", "name": "Federal law (consolidated + BGBl)", "note": "Exposed by at_search."},
    {"code": "Landesrecht", "name": "State law (Bundeslaender)", "note": "Not yet exposed (later feature)."},
    {"code": "Judikatur", "name": "Case law (ECLI)", "note": "Exposed by at_case_search / at_get_case_text."},
]

mcp: FastMCP = FastMCP(name="at-eli-mcp", instructions=INSTRUCTIONS)


def _base_url() -> str:
    return os.environ.get("AT_ELI_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _audit() -> AuditLogger:
    return AuditLogger()


def _map_upstream(exc: Exception) -> Exception:
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 404:
        return ToolError("not_found", "Document not found in RIS.")
    if isinstance(exc, (RisError, httpx.HTTPStatusError, httpx.TransportError, httpx.TimeoutException)):
        return ToolError("upstream_error", f"RIS API error: {type(exc).__name__}: {exc}")
    return exc


# ---------------------------------------------------------------------------
# at_search
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def at_search(query: SearchQuery) -> SearchResult:
    """Search Austrian federal law (RIS Bundesrecht).

    Maps to ``GET /Bundesrecht``. Each hit gets ``eli_uri``, ``human_readable_citation``,
    ``source_url`` and ``content_urls`` (html/xml).

    Args:
        query: ``SearchQuery`` - suchworte, titel, page_size (Ten/Twenty/Fifty/OneHundred), page_number.

    Returns:
        ``SearchResult`` with ``total`` and ``items: list[LawRef]``.
    """
    audit = _audit()
    input_hash = hash_input(query.model_dump(mode="json"))
    base = _base_url()

    if not (query.suchworte or query.titel):
        raise ToolError("invalid_arg", "Provide at least one of: suchworte, titel.")

    params: dict[str, Any] = {
        "Suchworte": query.suchworte,
        "Titel": query.titel,
        "DokumenteProSeite": query.page_size,
        "Seitennummer": query.page_number,
    }

    with timer() as t:
        try:
            async with RisClient(base_url=base) as client:
                result = await client.bundesrecht_search(params)
        except Exception as exc:
            audit.log(
                tool="at_search",
                input_hash=input_hash,
                output_count_or_size=0,
                duration_ms=t.duration_ms if t.duration_ms else 0,
                status="error",
                error=f"{type(exc).__name__}: {exc}",
            )
            raise _map_upstream(exc) from exc

    total, refs = extract_references(result)
    items = [LawRef.model_validate(flatten_reference(r, base_url=base)) for r in refs]
    out = SearchResult(total=total, items=items, query_echo=query)

    audit.log(
        tool="at_search",
        input_hash=input_hash,
        output_count_or_size=len(items),
        duration_ms=t.duration_ms,
        status="ok",
    )
    return out


# ---------------------------------------------------------------------------
# at_get_text
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def at_get_text(
    content_url: str,
    eli_uri: str | None = None,
    human_readable_citation: str | None = None,
) -> LawText:
    """Fetch the full text of an act from a RIS content URL.

    Args:
        content_url: an absolute ris.bka.gv.at URL from a search hit's ``content_urls`` (``.html`` or ``.xml``).
        eli_uri: the hit's ELI URL, passed through so the text stays citable.
        human_readable_citation: the hit's citation, passed through.

    Returns:
        ``LawText`` with ``source_url``, ``format``, ``content`` (and the passed-through citation).
    """
    audit = _audit()
    input_hash = hash_input({"content_url": content_url})
    base = _base_url()

    if not content_url or not content_url.strip():
        raise ToolError("invalid_arg", "content_url must not be empty.")
    url = content_url.strip()
    fmt: TextFormat
    if url.lower().endswith(".xml"):
        fmt = "xml"
    elif url.lower().endswith(".html"):
        fmt = "html"
    else:
        raise ToolError("unsupported_format", "content_url must end in .html or .xml.")

    with timer() as t:
        try:
            async with RisClient(base_url=base) as client:
                text, ct = await client.get_text_url(url)
        except ValueError as exc:  # host not allowed
            audit.log(
                tool="at_get_text",
                input_hash=input_hash,
                output_count_or_size=0,
                duration_ms=t.duration_ms if t.duration_ms else 0,
                status="error",
            )
            raise ToolError("invalid_arg", str(exc)) from exc
        except Exception as exc:
            audit.log(
                tool="at_get_text",
                input_hash=input_hash,
                output_count_or_size=0,
                duration_ms=t.duration_ms if t.duration_ms else 0,
                status="error",
                error=f"{type(exc).__name__}: {exc}",
            )
            raise _map_upstream(exc) from exc

    result = LawText(
        source_url=url,
        format=fmt,
        eli_uri=eli_uri,
        human_readable_citation=human_readable_citation,
        content=text,
        content_type=ct,
        byte_size=len(text.encode("utf-8")),
    )

    audit.log(
        tool="at_get_text",
        input_hash=input_hash,
        output_count_or_size=result.byte_size or 0,
        duration_ms=t.duration_ms,
        status="ok",
    )
    return result


# ---------------------------------------------------------------------------
# at_case_search
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def at_case_search(query: CaseSearchQuery) -> CaseSearchResult:
    """Search Austrian case law (RIS Judikatur).

    Maps to ``GET /Judikatur``. Each hit gets a native ``ecli``, ``human_readable_citation``,
    ``source_url`` and ``content_urls`` (html/xml).

    Args:
        query: ``CaseSearchQuery`` - suchworte, applikation (Justiz/Vfgh/Vwgh/...), page_size, page_number.

    Returns:
        ``CaseSearchResult`` with ``total`` and ``items: list[CaseRef]``.
    """
    audit = _audit()
    input_hash = hash_input(query.model_dump(mode="json"))
    base = _base_url()

    if not query.suchworte or not query.suchworte.strip():
        raise ToolError("invalid_arg", "Provide suchworte (free-text query) for case-law search.")

    params: dict[str, Any] = {
        "Applikation": query.applikation,
        "Suchworte": query.suchworte,
        "DokumenteProSeite": query.page_size,
        "Seitennummer": query.page_number,
    }

    with timer() as t:
        try:
            async with RisClient(base_url=base) as client:
                result = await client.judikatur_search(params)
        except Exception as exc:
            audit.log(
                tool="at_case_search",
                input_hash=input_hash,
                output_count_or_size=0,
                duration_ms=t.duration_ms if t.duration_ms else 0,
                status="error",
                error=f"{type(exc).__name__}: {exc}",
            )
            raise _map_upstream(exc) from exc

    total, refs = extract_references(result)
    items = [CaseRef.model_validate(flatten_case_reference(r, base_url=base)) for r in refs]
    out = CaseSearchResult(total=total, items=items, query_echo=query)

    audit.log(
        tool="at_case_search",
        input_hash=input_hash,
        output_count_or_size=len(items),
        duration_ms=t.duration_ms,
        status="ok",
    )
    return out


# ---------------------------------------------------------------------------
# at_get_case_text
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def at_get_case_text(
    content_url: str,
    ecli: str | None = None,
    human_readable_citation: str | None = None,
) -> CaseText:
    """Fetch the full text of a decision from a RIS content URL.

    Args:
        content_url: an absolute ris.bka.gv.at URL from a case hit's ``content_urls`` (``.html`` or ``.xml``).
        ecli: the hit's ECLI, passed through so the text stays citable.
        human_readable_citation: the hit's citation, passed through.

    Returns:
        ``CaseText`` with ``source_url``, ``format``, ``content`` (and the passed-through ECLI/citation).
    """
    audit = _audit()
    input_hash = hash_input({"content_url": content_url})
    base = _base_url()

    if not content_url or not content_url.strip():
        raise ToolError("invalid_arg", "content_url must not be empty.")
    url = content_url.strip()
    fmt: TextFormat
    if url.lower().endswith(".xml"):
        fmt = "xml"
    elif url.lower().endswith(".html"):
        fmt = "html"
    else:
        raise ToolError("unsupported_format", "content_url must end in .html or .xml.")

    with timer() as t:
        try:
            async with RisClient(base_url=base) as client:
                text, ct = await client.get_text_url(url)
        except ValueError as exc:  # host not allowed
            audit.log(
                tool="at_get_case_text",
                input_hash=input_hash,
                output_count_or_size=0,
                duration_ms=t.duration_ms if t.duration_ms else 0,
                status="error",
            )
            raise ToolError("invalid_arg", str(exc)) from exc
        except Exception as exc:
            audit.log(
                tool="at_get_case_text",
                input_hash=input_hash,
                output_count_or_size=0,
                duration_ms=t.duration_ms if t.duration_ms else 0,
                status="error",
                error=f"{type(exc).__name__}: {exc}",
            )
            raise _map_upstream(exc) from exc

    result = CaseText(
        source_url=url,
        format=fmt,
        ecli=ecli,
        human_readable_citation=human_readable_citation,
        content=text,
        content_type=ct,
        byte_size=len(text.encode("utf-8")),
    )

    audit.log(
        tool="at_get_case_text",
        input_hash=input_hash,
        output_count_or_size=result.byte_size or 0,
        duration_ms=t.duration_ms,
        status="ok",
    )
    return result


# ---------------------------------------------------------------------------
# at_list_collections
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
async def at_list_collections() -> list[Collection]:
    """List the RIS collections and which are exposed by this connector.

    Returns:
        List of ``Collection`` (code, name, note).
    """
    audit = _audit()
    input_hash = hash_input({})

    with timer() as t:
        collections = [Collection(code=c["code"], name=c["name"], note=c["note"]) for c in _COLLECTIONS]

    audit.log(
        tool="at_list_collections",
        input_hash=input_hash,
        output_count_or_size=len(collections),
        duration_ms=t.duration_ms,
        status="ok",
    )
    return collections


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the MCP server over stdio (default for Claude Code)."""
    mcp.run()


if __name__ == "__main__":
    main()
