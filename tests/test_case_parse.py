"""Offline parse test - flatten a saved RIS Judikatur fixture (no network)."""

from __future__ import annotations

import json
from pathlib import Path

from at_eli_mcp.citations import flatten_case_reference
from at_eli_mcp.client import extract_references

FIXTURES = Path(__file__).parent / "fixtures"
BASE = "https://data.bka.gv.at/ris/api/v2.6"


def _result() -> dict:
    payload = json.loads((FIXTURES / "judikatur_justiz.json").read_text(encoding="utf-8"))
    return payload["OgdSearchResult"]


def test_extract_and_flatten_case():
    total, refs = extract_references(_result())
    assert total > 0
    assert refs, "expected at least one Judikatur reference"
    rec = flatten_case_reference(refs[0], base_url=BASE)
    assert rec["ecli"] and rec["ecli"].startswith("ECLI:AT:")
    assert rec["gericht"]
    assert rec["geschaeftszahl"] and ";" not in rec["geschaeftszahl"], "first Geschaeftszahl only"
    assert rec["entscheidungsdatum"]
    assert rec["human_readable_citation"]
    assert rec["source_url"]
    # content URLs must stay on the RIS host.
    for url in rec["content_urls"].values():
        assert "ris.bka.gv.at" in url


def test_case_record_has_no_fabricated_eli():
    _total, refs = extract_references(_result())
    rec = flatten_case_reference(refs[0], base_url=BASE)
    # Case law carries ECLI, not ELI - we must not invent an eli_uri.
    assert "eli_uri" not in rec or rec.get("eli_uri") is None
