# at-eli-mcp

<!-- mcp-name: io.github.matematicsolutions/at-eli-mcp -->


## Install (one command)

Published on PyPI + MCP Registry (`io.github.matematicsolutions/at-eli-mcp`). Run without cloning:

```bash
uvx at-eli-mcp
```

Configure your MCP client (stdio):

```json
{ "mcpServers": { "at-eli-mcp": { "command": "uvx", "args": ["at-eli-mcp"] } } }
```

### Windows 11 with Smart App Control

Smart App Control blocks unsigned executables, and `uvx.exe`, `pip.exe` and the
`at-eli-mcp.exe` launcher generated at install time are not signed. `python.exe` from
python.org is signed by the Python Software Foundation, so running the module
directly bypasses the block:

```bash
python -m pip install at-eli-mcp
python -m at_eli_mcp
```

```json
{ "mcpServers": { "at-eli-mcp": { "command": "python", "args": ["-m", "at_eli_mcp"] } } }
```

Do not turn Smart App Control off to work around this - it cannot be re-enabled
without reinstalling Windows.

(Building from source - below.)

An MCP server for **RIS** (`data.bka.gv.at`), Austria's official legal information system
(Rechtsinformationssystem des Bundes, operated by the Bundeskanzleramt). It searches and
retrieves Austrian federal legislation (Bundesrecht) and case law (Judikatur) with verifiable ELI
identifiers, native ECLI for decisions, and Austrian citations.

Part of the MateMatic `eu-legal-mcp` production line - the Austrian member, after the Polish
`sejm-eli-mcp` and the German `de-eli-mcp`. Same architecture and citation contract, RIS source.

> **Scope.** Covers Austrian **federal law** (Bundesrecht) and **case law** (Judikatur, with a
> native ECLI). State law (Landesrecht) is a later feature. Every response carries a `dataset_note`.
>
> **Licence.** Austrian Bundesgesetzblatt content and statutes are official works in the public
> domain; RIS is published as Open Government Data (keyless). This connector relays that public
> content with attribution and a `source_url`.

## The tools

| Tool | What it does |
|---|---|
| `at_search` | Search federal law (`GET /Bundesrecht`) by free text and/or title. |
| `at_get_text` | Fetch an act's full text (`html` or `xml`) from a hit's content URL. |
| `at_case_search` | Search case law (`GET /Judikatur`) by free text, choosing a court (`applikation`). Hits carry a native `ecli`. |
| `at_get_case_text` | Fetch a decision's full text from a case hit's content URL. |
| `at_list_collections` | List the RIS collections and which are exposed. |

Every response carries the contract: `eli_uri` (a full ELI URL, e.g.
`https://www.ris.bka.gv.at/eli/bgbl/I/2026/6/20260218`), `human_readable_citation`
(e.g. `Datenschutzgesetz, BGBl. I Nr. 165/1999`), and `source_url`.

## Install

```bash
cd at-eli-mcp
pip install -e .
```

## Configure (Claude Code / any MCP client)

```json
{
  "mcpServers": {
    "at-eli-mcp": { "command": "at-eli-mcp" }
  }
}
```

Environment:

- `AT_ELI_BASE_URL` - default `https://data.bka.gv.at/ris/api/v2.6`
- `AT_ELI_CACHE_DIR` - default `~/.matematic/cache/at-eli`
- `AT_ELI_AUDIT_DIR` - default `~/.matematic/audit`

No API key. RIS is keyless Open Government Data.

## Governance

- **Public data only** - read-only against RIS; no client data leaves the machine beyond search parameters.
- **Audit log** - every tool call appends one JSON line to `~/.matematic/audit/at-eli-mcp.jsonl`.
- **Vendor-neutral** - talks only to `data.bka.gv.at` and (for full text) `ris.bka.gv.at`; no LLM provider, no telemetry.
- **Host-restricted text** - full text is fetched only from `ris.bka.gv.at`.

See `CONSTITUTION.md` and `DISCOVERY.md`.

## Tests

```bash
pip install -e ".[dev]"
pytest tests/test_instructions_drift.py -v   # offline
pytest tests/test_smoke.py -v                # hits live RIS
```

## Licence

Apache-2.0. © Matematic Solutions / Wieslaw Mazur.
