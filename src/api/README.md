# API and query interface (Person B)

A FastAPI service plus a one-page web interface for exploring the citation network of
Indian Supreme Court judgments in five crime domains (Financial Fraud, Corruption,
Digital Financial Fraud, Organized Crime / Extortion, Violent Crime / Homicide).

## Run it

From the repository root:

```
pip install -r requirements-api.txt
uvicorn src.api.main:app --reload
```

| Address | What it is |
|---|---|
| http://127.0.0.1:8000/ | Query interface: search judgments, browse domains, draw citation graphs |
| http://127.0.0.1:8000/docs | Interactive API documentation (try every endpoint in the browser) |

The graph views load the `vis-network` library from a CDN, so they need an internet
connection. Everything else works offline.

## Data it reads

| File | Used for |
|---|---|
| `output/tables/node_metrics.csv` | Case index: title, year, domains, in/out-degree, PageRank per domain and combined |
| `network/citation_network/*_edges_all.csv` | Who cites whom, including cases outside the five domains and unresolved citations |
| `network/citation_network/*_edges_internal.csv` | Each domain's own graph |
| `output/tables/*.csv` | Served as-is by `/tables` |
| `data/final/*_corpus.csv` (optional) | Source for the full-text search index (see below) |
| Original PDFs (optional) | `/cases/{file_name}/pdf` and the PDF buttons |

Paths live in `config/settings.py`. Override any of them with an environment variable
(`LCN_NODE_METRICS`, `LCN_EDGES_DIR`, `LCN_TABLES_DIR`, `LCN_PDF_DIRS`, `LCN_CORPUS_DIR`, `LCN_FTS_DB`).

### Full-text search

Searching inside the judgments uses a SQLite full-text index built from the five corpus CSVs.
Build it once (about 30 seconds, one file of about 280 MB, not committed to Git):

```
python scripts/build_search_index.py
```

Re-run it whenever the corpus files change; a running API picks up the new file on its next request.
Until it is built, case-name search works as before and the full-text option in the interface is
greyed out (the API answers `503` with the command to run).

How queries behave:

- Every word must appear in the judgment. Words in "double quotes" must appear together, in order.
- Word forms match (`forging` finds "forged", `documents` finds "document").
- Filler words such as "the", "of" and "to" are ignored unless they are inside a quoted phrase that
  also has a real word, so `section 420 of ipc` searches for section, 420 and ipc. A query made only of
  filler words is rejected with a short explanation (422).
- Operators typed by a user (`OR`, `NEAR`, `*`, `-`, `col:x`) are treated as ordinary words and never
  cause an error. There is no OR search; run two searches instead.
- Results are ranked by relevance (BM25) unless another `sort` is chosen. Each result carries a short
  highlighted extract.

### Original PDFs

The PDFs are not in the repository. The API looks for them in `data/final/pdfs/` first
and in `data/raw/sc_judgments/` second, matching on file name (case-insensitive). If a
PDF is missing, the interface shows "PDF not on this server" and the endpoint returns 404;
nothing else is affected.

To share only the PDFs the project needs (about 4,200 instead of the full 6.9 GB), run this on
the machine that has the raw data:

```
python scripts/collect_pdfs.py --dry-run     # check first
python scripts/collect_pdfs.py               # copies into data/final/pdfs/
```

## Endpoints

| Method and path | Returns |
|---|---|
| `GET /health` | Status and what data was loaded |
| `GET /domains` | The five domains plus `combined`, each with summary statistics |
| `GET /domains/{domain}` | One domain's statistics |
| `GET /domains/{domain}/top-cases?metric=pagerank\|in_degree&limit=10` | Most influential cases (limit 1 to 100) |
| `GET /domains/{domain}/decades` | Cases per decade |
| `GET /domains/{domain}/graph?top_n=50&metric=&year_from=&year_to=&connected_only=true` | Nodes and edges as JSON |
| `GET /search?q=&scope=title\|text&domain=&year_from=&year_to=&sort=&limit=20&offset=0` | Paged search: `scope=title` (default) searches case names, `scope=text` searches inside the judgments and returns highlighted snippets |
| `GET /cases/{file_name}` | Case detail with `cites` and `cited_by` lists |
| `GET /cases/{file_name}/neighbourhood?limit=30&include_outside=false` | Graph around one case |
| `GET /cases/{file_name}/pdf?download=false` | The original judgment PDF |
| `GET /tables` and `GET /tables/{name}?limit=50&offset=0` | The CSV tables in `output/tables/` |

`{domain}` is `financial_fraud`, `corruption`, `digital_financial_fraud`,
`organized_crime_extortion`, `violent_crime_homicide` or `combined` (hyphens are accepted).
`sort` is one of `relevance`, `cited_by`, `pagerank`, `year_desc`, `year_asc`, `title`.

Errors: unknown domain in the URL path gives 404; unknown domain, a bad year range, an invalid
`sort` or `scope`, or a full-text query with nothing to search for gives 422; unknown case or table
gives 404; `scope=text` before the index is built gives 503.

### Example: search

`GET /search?q=kartar+singh&limit=1`

```json
{
  "query": "kartar singh", "scope": "title", "domain": null, "sort": "relevance",
  "total": 4, "limit": 1, "offset": 0,
  "results": [{
    "file_name": "Kartar_Singh_vs_State_Of_Punjab_on_11_March_1994_1.PDF",
    "title": "Kartar Singh vs State Of Punjab",
    "decision_date": "1994-03-11", "year": 1994,
    "domains": ["Corruption", "Organized Crime / Extortion"],
    "cited_by_count": 46, "cites_count": 15,
    "pagerank": 0.005491, "pagerank_rank": 6,
    "self_citation": false, "pdf_available": false
  }]
}
```

### Example: full-text search

`GET /search?scope=text&q="criminal breach of trust" bank&limit=1`

```json
{
  "query": "\"criminal breach of trust\" bank", "scope": "text", "sort": "relevance",
  "total": 98, "limit": 1, "offset": 0,
  "results": [{
    "file_name": "Central_Bureau_Of_Investigation_vs_Duncans_Agro_Industries_Ltd_Calcutta_on_9_July_1996_1.PDF",
    "title": "Central Bureau Of Investigation vs Duncans Agro Industries Ltd Calcutta",
    "year": 1996, "cited_by_count": 0, "cites_count": 0, "pdf_available": false,
    "snippet": [
      { "text": "… by ", "match": false },
      { "text": "Bank", "match": true },
      { "text": " officials.\" Mr. Shanti Bhushan has submitted that the above allegations did not make out any offence of ", "match": false },
      { "text": "criminal breach of trust", "match": true },
      { "text": ". According …", "match": false }
    ]
  }]
}
```

`snippet` is a list of parts, not HTML: render the parts with `match: true` highlighted. Titles and
snippets come from judgment text, so a client should always escape them (the bundled interface does).

### Example: domain summary

`GET /domains/corruption` (abridged)

```json
{
  "slug": "corruption", "cases": 548, "edges": 85, "self_loops": 2,
  "edges_excluding_self_loops": 83, "density": 0.000284,
  "mean_in_degree": 0.155, "pct_cited_at_least_once": 5.474, "pct_isolated": 83.942,
  "first_year": 1953, "median_year": 2003.0, "last_year": 2025,
  "has_internal_citations": true,
  "top_case": { "title": "R Balakrishna Pillai vs State Of Kerala Anr", "rank": 1, "in_degree": 5, "self_citation": true }
}
```

### Example: case detail

`GET /cases/Mrs_Maneka_Gandhi_vs_Union_Of_India_Uoi_And_Anr_on_25_January_1978_1.PDF` (abridged)

```json
{
  "case": { "title": "Mrs Maneka Gandhi vs Union Of India Uoi And Anr", "year": 1978,
            "cited_by_count": 76, "cites_count": 2, "pdf_available": false },
  "domain_metrics": [{ "domain": "Organized Crime / Extortion", "in_degree": 39, "pagerank_rank": 3 }],
  "cites": [{ "title": "A K Gopalan vs The State Of Madras Union Of India", "year": 1950, "relation": "same_domain" }],
  "cited_by": [{ "title": "Kartar Singh vs State Of Punjab", "year": 1994, "relation": "same_domain" }],
  "cites_outside_scope": [],
  "citations_total": 5, "citations_unresolved": 2,
  "pdf_url": null
}
```

## How the numbers are defined

- **Domain statistics** (`/domains`) are computed from `node_metrics.csv` and reproduce the figures
  in `network_metrics_by_domain.csv` (checked by `tests/test_real_data.py`).
- **`cited_by_count` / `cites_count`** on a case count distinct judgments across all five domains
  (the combined graph), so they can be larger than the per-domain `in_degree`.
- **`cites_outside_scope`** lists Supreme Court judgments the case cites that exist in the full
  26,688-judgment collection but are not in any of the five domains. Their titles and dates are read
  from the file names.
- **`citations_unresolved`** counts distinct citation strings that could not be matched to any
  judgment in the collection (High Court cases, pre-1950 cases and so on).

## Known data issue: self-citations

36 rows in the `*_edges_internal.csv` files (35 distinct judgments in the combined graph) have a
judgment citing itself, for example a case whose text contains its own SCC reference. The
Phase 0 README says this was fixed, but the current edge files still contain them. The API leaves
these rows out of every citation list and flags the case with `self_citation: true`. The
`in_degree` and PageRank values in `node_metrics.csv` were computed with those rows included, so
a few top cases are one higher than their real count (for example R Balakrishna Pillai: 5 in the
table, 4 without the self-link). The fix belongs in `preprocessing/citation_extraction/` or
`network/citation_network/build_edges.py` (drop rows where citing equals cited), followed by a
re-run of the network analysis.

## Tests

```
pytest                 # about 125 tests on a small synthetic dataset, no real data needed
```

If the real data files are present at the paths in `config/settings.py`, `tests/test_real_data.py`
checks the API against the published network-analysis numbers, and `tests/test_fulltext.py` also builds
a full-text index from the real corpus CSVs (about 30 seconds) and checks real searches; otherwise those
tests are skipped.

## Layout

```
config/settings.py          paths and API settings (environment overrides)
src/utils/                  domains, formatting helpers, PDF locator, full-text index, in-memory data store
src/api/factory.py          create_app(): builds the app and loads the data
src/api/main.py             ASGI entry point (uvicorn src.api.main:app)
src/api/routers/            domains, search, cases, tables
src/api/schemas.py          response models (also drive /docs)
src/api/static/index.html   the query interface
scripts/collect_pdfs.py     copy only the needed PDFs into data/final/pdfs/
scripts/build_search_index.py   build the full-text index (data/index/fulltext.db)
tests/                      unit, API and real-data tests
```
