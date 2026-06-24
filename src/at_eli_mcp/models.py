"""Pydantic v2 models for the Austrian RIS API + at-eli-mcp.

We flatten the deeply nested RIS envelope into flat, snake_case records, so unlike the
German connector there is no JSON-LD field mirroring here. Models stay tolerant
(``extra="allow"``) for forward compatibility.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TextFormat = Literal["html", "xml"]
PageSize = Literal["Ten", "Twenty", "Fifty", "OneHundred"]

# Federal law (Bundesrecht) and case law (Judikatur) are exposed; state law (Landesrecht) is not.
DATASET_NOTE = (
    "This connector exposes Austrian federal law (Bundesrecht, via at_search) and case law "
    "(Judikatur, via at_case_search). State law (Landesrecht) is not yet covered."
)

CASE_DATASET_NOTE = (
    "Austrian case law (Judikatur) via RIS. Decisions carry a native ECLI (no ELI). Choose an "
    "'applikation': Justiz (ordinary courts incl. OGH), Vfgh (constitutional), Vwgh "
    "(administrative), Bvwg, Lvwg, Dsk, and others. Landesrecht is not yet covered."
)

# RIS Judikatur applications (courts) the connector accepts.
CaseApplikation = Literal["Justiz", "Vfgh", "Vwgh", "Bvwg", "Lvwg", "Dsk", "Gbk", "Pvak", "Pdok"]


class _Tolerant(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class LawRef(_Tolerant):
    """A flattened Austrian federal-law reference (a search hit)."""

    id: str | None = None
    applikation: str | None = None
    organ: str | None = None
    kurztitel: str | None = None
    titel: str | None = None
    typ: str | None = None
    bgblnummer: str | None = None
    content_urls: dict[str, str] = Field(default_factory=dict)

    # Citation contract (Art. 4 CONSTITUTION).
    eli_uri: str | None = None
    human_readable_citation: str | None = None
    source_url: str | None = None


class SearchQuery(_Tolerant):
    """Arguments for the ``at_search`` tool (RIS Bundesrecht)."""

    suchworte: str | None = None
    titel: str | None = None
    page_size: PageSize = "Ten"
    page_number: int = Field(default=1, ge=1)


class SearchResult(_Tolerant):
    """Result of ``at_search``."""

    total: int
    items: list[LawRef] = Field(default_factory=list)
    query_echo: SearchQuery | None = None
    dataset_note: str = DATASET_NOTE


class LawText(_Tolerant):
    """Result of ``at_get_text``."""

    source_url: str
    format: TextFormat
    eli_uri: str | None = None
    human_readable_citation: str | None = None
    content: str | None = None
    content_type: str | None = None
    byte_size: int | None = None
    dataset_note: str = DATASET_NOTE


class CaseRef(_Tolerant):
    """A flattened Austrian case-law reference (a Judikatur search hit)."""

    id: str | None = None
    applikation: str | None = None
    gericht: str | None = None
    dokumenttyp: str | None = None
    geschaeftszahl: str | None = None
    entscheidungsdatum: str | None = None
    norm: str | None = None
    content_urls: dict[str, str] = Field(default_factory=dict)

    # Citation contract: case law carries a native ECLI (no ELI).
    ecli: str | None = None
    human_readable_citation: str | None = None
    source_url: str | None = None


class CaseSearchQuery(_Tolerant):
    """Arguments for the ``at_case_search`` tool (RIS Judikatur)."""

    suchworte: str | None = None
    applikation: CaseApplikation = "Justiz"
    page_size: PageSize = "Ten"
    page_number: int = Field(default=1, ge=1)


class CaseSearchResult(_Tolerant):
    """Result of ``at_case_search``."""

    total: int
    items: list[CaseRef] = Field(default_factory=list)
    query_echo: CaseSearchQuery | None = None
    dataset_note: str = CASE_DATASET_NOTE


class CaseText(_Tolerant):
    """Result of ``at_get_case_text``."""

    source_url: str
    format: TextFormat
    ecli: str | None = None
    human_readable_citation: str | None = None
    content: str | None = None
    content_type: str | None = None
    byte_size: int | None = None
    dataset_note: str = CASE_DATASET_NOTE


class Collection(_Tolerant):
    """A RIS application/collection (orientation for ``at_list_collections``)."""

    code: str
    name: str | None = None
    note: str | None = None
