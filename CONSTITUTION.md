# Constitution of at-eli-mcp

Version: 0.1.0
Date: 2026-06-24
Licence: Apache-2.0

`at-eli-mcp` is an MCP server for the Austrian RIS API (`data.bka.gv.at/ris/api`, the
Rechtsinformationssystem des Bundes) operated by the Bundeskanzleramt. It searches and
retrieves Austrian federal legislation (Bundesrecht) with verifiable ELI citations. The MVP
covers federal-law search and full text; case law (Judikatur, ECLI) and state law (Landesrecht)
are later features.

The 4 principles below are inherited from the `eu-legal-mcp` line Constitution (Article IV).

---

## Art. 1. Public data only

The RIS Open Government Data API is the official, public source of Austrian law. Legal status of
the data: Austrian Bundesgesetzblatt content and statutes are official works in the public domain;
RIS is published as Open Government Data (keyless OGD). The server is read-only against RIS and
sends nothing beyond search parameters.

## Art. 2. Mandatory audit log

Every tool call MUST append one JSON line to `~/.matematic/audit/at-eli-mcp.jsonl`
(ts / tool / input_hash SHA-256 / output_count_or_size / duration_ms / status). Inability to
write = the tool returns an error, it does not silently skip.

## Art. 3. Vendor neutrality

No tool hardcodes an LLM provider, assumes a model, or adds commercial telemetry. The server talks
only to RIS (`data.bka.gv.at`) and, for full text, to `ris.bka.gv.at` (host-restricted), plus the
local filesystem. Authentication: none (OGD); own backoff + cache regardless.

## Art. 4. ELI citations and a human-readable citation are mandatory

Every response MUST carry three fields:
- `eli_uri`: the canonical ELI. RIS exposes it as a full URL in the `Eli` field (stored verbatim).
- `human_readable_citation`: Austrian convention - `Kurztitel` + `Bgblnummer`
  (e.g. "Nachhaltigkeitsberichtsgesetz, BGBl. I Nr. 6/2026").
- `source_url`: the openable RIS document URL (`DokumentUrl`, the ELI landing page).

---

## Open points

1. **Date filtering for `at_recent_changes`** - RIS Kundmachung/Fassung params not yet confirmed; the tool is deferred, not shipped unverified.
2. **Case law (Judikatur, ECLI)** and **Landesrecht** - later features.

## Ewolucja konstytucji

Changes to art. 1-4 follow SEMVER + an entry in `CHANGELOG.md` + a `pyproject.toml` bump.

First version: 2026-06-24. Author: Wieslaw Mazur / MateMatic.
