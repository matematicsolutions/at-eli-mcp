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

class CoverageFamily(_Tolerant):
    """One data family this connector exposes, with the date its snapshot was captured."""

    name: str = Field(description="Data family, e.g. 'Bundesrecht'.")
    tool: str = Field(description="Tool that reaches this family.")
    source: str = Field(description="Official source the data comes from.")
    captured_at: str | None = Field(
        default=None,
        description="Date this family was last captured (ISO). None when the tool queries the source live.",
    )
    live: bool = Field(default=False, description="True when queried live instead of from a snapshot.")


class CoverageGap(_Tolerant):
    """A known, named hole in this connector's coverage - plus how to work around it."""

    id: str = Field(description="Stable gap identifier, e.g. 'AT-001'.")
    family: str = Field(description="Which family the gap belongs to.")
    missing: str = Field(description="What is NOT available through this connector.")
    fallback: str = Field(description="Where the user must go instead.")


class Coverage(_Tolerant):
    """What this connector covers, when it was captured, and - explicitly - what it does not."""

    status: Literal["ok", "degraded", "failed"] = "ok"
    as_of_note: str = Field(
        description="States that dates say WHEN data was captured, not that it is still in force."
    )
    families: list[CoverageFamily] = Field(default_factory=list)
    known_gaps: list[CoverageGap] = Field(
        default_factory=list,
        description="Never empty. An empty list would mean 'not checked', not 'no gaps'.",
    )
