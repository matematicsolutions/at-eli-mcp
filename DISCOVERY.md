# Discovery: RIS API (data.bka.gv.at) - Austria

Date: 2026-06-24. **Status: CLOSED** for the federal-law MVP (confirmed by live probing).

Austrian RIS (Rechtsinformationssystem des Bundes), operated by the Bundeskanzleramt.
Open Government Data API, keyless. Structurally very different from NeuRIS/PL: a deeply
nested SOAP-derived OGD envelope with German keys, and ELI exposed as a full URL.

## Base API properties (CONFIRMED)

- **Base URL:** `https://data.bka.gv.at/ris/api/v2.6`
- **Help:** `/Help` (lists endpoints but per-endpoint docs are empty - the live API is the source of truth).
- **Authentication:** none (OGD, keyless).
- **Format:** JSON with `Accept: application/json` (XML otherwise). Same data, SOAP-derived shape.
- **ELI:** YES - full URL in the `Eli` field (e.g. `https://www.ris.bka.gv.at/eli/bgbl/I/2026/6/20260218`).
- **Endpoints (applications):** `Bundesrecht` (federal law), `Landesrecht` (state law), `Judikatur` (case law, ECLI), `Sonstige`, `Bezirke`, `Gemeinden`, `Version`.

## `Bundesrecht` search - parameters (CONFIRMED)

- `Suchworte` - free-text search words.
- `Titel` - title search.
- `DokumenteProSeite` - page size ENUM: `Ten` / `Twenty` / `Fifty` / `OneHundred` (NOT a number; `One` is invalid).
- `Seitennummer` - page number (1-based).

## Response envelope (CONFIRMED)

```
OgdSearchResult
  .OgdDocumentResults
    .Hits            {@pageNumber, @pageSize, #text = TOTAL}
    .OgdDocumentReference[]
      .Data
        .Metadaten
          .Technisch  {ID "BGBLA_2026_I_6", Applikation "BgblAuth", Organ}
          .Allgemein  {DokumentUrl = ELI landing page}
          .Bundesrecht {Kurztitel, Titel, Eli (full URL), BgblAuth.Bgblnummer "BGBl. I Nr. 6/2026", Ausgabedatum, Typ}
        .Dokumentliste
          .ContentReference {ContentType "MainDocument", Name "Hauptdokument"}
            .Urls.ContentUrl[]  {DataType: Xml|Html|Rtf|Authentisch(pdf), Url = absolute https://www.ris.bka.gv.at/Dokumente/.../X.html}
```

On error the API returns `OgdSearchResult.Error {Applikation, Message}` (e.g. enum validation).

## Citation contract (Article IV) - CLOSED for AT

- `eli_uri` = `Eli` (full ELI URL, e.g. `https://www.ris.bka.gv.at/eli/bgbl/I/2026/6/20260218`).
- `human_readable_citation` = `Kurztitel` + `Bgblnummer` (e.g. "Nachhaltigkeitsberichtsgesetz, BGBl. I Nr. 6/2026").
- `source_url` = `DokumentUrl` (the openable ELI landing page).

## Tool mapping - federal-law MVP

| Tool | Endpoint | Notes |
|---|---|---|
| `at_search` | `GET /Bundesrecht` (Suchworte/Titel + page) | enriches each ref with the contract + `content_urls` {html, xml} from Dokumentliste |
| `at_get_text` | `GET {content_url}` (absolute ris.bka.gv.at URL from search) | host-restricted to ris.bka.gv.at; html/xml |
| `at_list_collections` | static | the RIS applications (Bundesrecht/Landesrecht/Judikatur) - orientation, no dedicated endpoint |

**Deferred (need separate param confirmation):**
- `at_recent_changes` - RIS date-filter params (Kundmachung/Fassung) not yet confirmed; do not ship unverified.
- Case law (Judikatur, ECLI) - separate feature, like DE 002.
- Landesrecht (state law) - federal first.

## Differences vs DE/PL (the per-country work)

- ELI is a full URL, not a path -> `eli_uri` stored verbatim, no parsing/synthesis.
- Deeply nested envelope with German keys -> models + flattening are new.
- Full text via absolute content URLs in `Dokumentliste` (not a get-by-id endpoint) -> `at_get_text` takes a URL, host-restricted.
- Page size is an enum, not an integer.

## Decision: BUILD

ELI present, keyless, official, rich. Reuse from de-eli-mcp: `audit.py` + `cache.py` verbatim, `server.py` pattern.
New: `client.py` (RIS envelope), `citations.py` (RIS fields), `models.py` (OGD shapes). Confirms the line thesis again -
the second non-PL connector reuses everything but the source adapter.
