# Domain list refactor - one source of truth

You were right that `retrieve_domains.py` wasn't the only file hardcoding
the 3-domain list. Found and fixed the same pattern in 6 files total:

- `retrieval/keyword_retrieval/retrieve_domains.py` (fixed earlier)
- `retrieval/keyword_retrieval/prepare_spot_check.py`
- `preprocessing/citation_extraction/extract_citations.py`
- `network/citation_network/build_edges.py`
- `network/graph_construction/build_graphs.py`
- `network/graph_construction/build_cross_domain_graph.py`
- `output/visualizations/visualize_graphs.py`

## New file: `config/domains.py`
Single source of truth, imported by all 7 scripts above:
- `get_domains()` - reads the ontology's `crime_category` column, returns
  the current domain list. Add a domain by editing the ontology CSV only.
- `domain_to_filename(domain)` - consistent slug. Handles `" / "` as one
  unit before handling remaining spaces, so `"Organized Crime / Extortion"`
  becomes `"organized_crime_extortion"`, not `"organized_crime_/_extortion"`.
- `corpus_filename(domain)` - the `_corpus.csv` filename for a domain.
- `get_domain_colors()` - auto-assigns a color per domain from a 7-color
  palette (cycles if you ever exceed 7 domains), replacing the old
  hardcoded 3-entry `DOMAIN_COLORS` dict in the visualization script.

## The bug this fixes
Every one of those 6 files built filenames with
`domain.lower().replace(' ', '_')` - which only touches spaces. For
`"Organized Crime / Extortion"` this produces
`"organized_crime_/_extortion_corpus.csv"` - a literal slash in a
filename. That's invalid on Windows (where you're running this) and
would be read as a path separator on Unix, either crashing outright or
silently writing/reading from the wrong location depending on the OS and
which script hit it first.

Verified on real data: ran all 7 scripts end-to-end after the fix -
every domain (including both new ones) produces a correctly-slugged
filename with no slash, no crash, across the full chain from retrieval
through visualization.

## What you need to do
Nothing beyond dropping these files in and re-running the pipeline - no
config changes needed. If you add a 6th domain later, it's ontology-CSV-only
again, same as the original retrieve_domains.py refactor promised.
