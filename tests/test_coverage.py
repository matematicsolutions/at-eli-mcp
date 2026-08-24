"""Element 9 of the MateMatic MCP canon - the connector must declare its own holes.

The load-bearing assertion is ``known_gaps`` being non-empty. A gate over an empty list
passes every time and reads as a clean result, which is exactly how silent incompleteness
gets shipped: no legal corpus is complete, so an empty gap list means "nobody checked",
not "there are no gaps".
"""

from __future__ import annotations

import asyncio

from at_eli_mcp.server import at_coverage


def _coverage():
    fn = getattr(at_coverage, "fn", at_coverage)
    return asyncio.run(fn())


def test_families_are_named():
    cov = _coverage()
    assert cov.families, "empty denominator - a gate with nothing to check passes always"
    for fam in cov.families:
        assert fam.name and fam.tool and fam.source


def test_known_gaps_never_silently_empty():
    cov = _coverage()
    assert cov.known_gaps, (
        "EMPTY known_gaps = BLOCK. No legal corpus is complete; an empty list means "
        "'not checked', not 'no gaps'."
    )


def test_every_gap_has_id_and_a_way_out():
    cov = _coverage()
    ids = [g.id for g in cov.known_gaps]
    assert len(ids) == len(set(ids)), f"duplicate gap ids: {ids}"
    for gap in cov.known_gaps:
        assert gap.id and gap.family and gap.missing
        assert gap.fallback, f"gap {gap.id} names a hole but no way around it"


def test_snapshot_families_carry_a_capture_date():
    """A non-live family without a capture date is an undated claim about freshness."""
    cov = _coverage()
    for fam in cov.families:
        if not fam.live:
            assert fam.captured_at, f"family {fam.name} is a snapshot but carries no captured_at"


def test_status_is_tristate():
    assert _coverage().status in {"ok", "degraded", "failed"}
