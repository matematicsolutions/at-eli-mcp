"""Austrian RIS reference flattening + citation helpers.

RIS returns a deeply nested OGD envelope (SOAP-derived) with German keys. Each search hit
is an ``OgdDocumentReference`` whose ``Data.Metadaten`` carries the descriptive fields and
whose ``Data.Dokumentliste`` carries the full-text manifestation URLs. ELI is exposed as a
full URL in the ``Eli`` field (stored verbatim, not synthesized).

The citation contract fields we attach:
- ``eli_uri``: the ``Eli`` URL (e.g. ``https://www.ris.bka.gv.at/eli/bgbl/I/2026/6/20260218``).
- ``human_readable_citation``: ``Kurztitel`` + ``Bgblnummer``
  (e.g. "Datenschutzgesetz, BGBl. I Nr. 165/1999").
- ``source_url``: ``DokumentUrl`` (the openable ELI landing page).
"""

from __future__ import annotations

from typing import Any

# Only these hosts may be fetched for full text (Art. 1 / Art. 3 - no open proxy).
ALLOWED_TEXT_HOST = "ris.bka.gv.at"

_DATATYPE_TO_FORMAT = {"Html": "html", "Xml": "xml"}


def _as_list(value: Any) -> list[Any]:
    """RIS uses a single object or a list interchangeably; normalize to a list."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _find_law_block(metadaten: dict[str, Any]) -> dict[str, Any]:
    """Return the descriptive sub-block (e.g. 'Bundesrecht') that carries Eli/Kurztitel."""
    for value in metadaten.values():
        if isinstance(value, dict) and ("Eli" in value or "Kurztitel" in value):
            return value
    return {}


def _find_first(payload: Any, key: str) -> Any:
    """Depth-first search for the first value under ``key`` in nested dicts/lists."""
    if isinstance(payload, dict):
        if key in payload:
            return payload[key]
        for v in payload.values():
            found = _find_first(v, key)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _find_first(item, key)
            if found is not None:
                return found
    return None


def content_urls(reference: dict[str, Any]) -> dict[str, str]:
    """Map format -> absolute content URL from a reference's Dokumentliste.

    Prefers the MainDocument ContentReference; only ris.bka.gv.at URLs are kept.
    """
    dokumentliste = reference.get("Data", {}).get("Dokumentliste", {})
    refs = _as_list(dokumentliste.get("ContentReference"))
    main = next(
        (r for r in refs if isinstance(r, dict) and r.get("ContentType") == "MainDocument"),
        None,
    )
    chosen = main or (refs[0] if refs else None)
    out: dict[str, str] = {}
    if not isinstance(chosen, dict):
        return out
    for cu in _as_list(chosen.get("Urls", {}).get("ContentUrl")):
        if not isinstance(cu, dict):
            continue
        fmt = _DATATYPE_TO_FORMAT.get(cu.get("DataType", ""))
        url = cu.get("Url")
        if fmt and isinstance(url, str) and ALLOWED_TEXT_HOST in url:
            out[fmt] = url
    return out


def human_readable_citation(law_block: dict[str, Any]) -> str | None:
    """Austrian citation: 'Kurztitel, BGBl. I Nr. 165/1999'."""
    label = None
    for key in ("Kurztitel", "Titel"):
        v = law_block.get(key)
        if isinstance(v, str) and v.strip():
            label = v.strip()
            break
    bgbl = _find_first(law_block, "Bgblnummer")
    bgbl_s = bgbl.strip() if isinstance(bgbl, str) and bgbl.strip() else None
    if label and bgbl_s:
        return f"{label}, {bgbl_s}"
    return label or bgbl_s


def flatten_reference(reference: dict[str, Any], base_url: str) -> dict[str, Any]:
    """Flatten an OgdDocumentReference into a contract-bearing record."""
    metadaten = reference.get("Data", {}).get("Metadaten", {})
    technisch = metadaten.get("Technisch", {}) if isinstance(metadaten, dict) else {}
    allgemein = metadaten.get("Allgemein", {}) if isinstance(metadaten, dict) else {}
    law = _find_law_block(metadaten) if isinstance(metadaten, dict) else {}

    eli = law.get("Eli") or allgemein.get("DokumentUrl")
    dokument_url = allgemein.get("DokumentUrl") or eli
    urls = content_urls(reference)

    out: dict[str, Any] = {
        "id": technisch.get("ID"),
        "applikation": technisch.get("Applikation"),
        "organ": technisch.get("Organ"),
        "kurztitel": law.get("Kurztitel"),
        "titel": law.get("Titel"),
        "typ": _find_first(law, "Typ"),
        "bgblnummer": _find_first(law, "Bgblnummer"),
        "content_urls": urls,
    }
    if isinstance(eli, str) and eli.strip():
        out["eli_uri"] = eli.strip()
    citation = human_readable_citation(law)
    if citation is not None:
        out["human_readable_citation"] = citation
    out["source_url"] = (
        dokument_url if isinstance(dokument_url, str) and dokument_url.strip() else base_url
    )
    return out
