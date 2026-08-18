# Legal Citation Network Analysis of Financial Crimes in India

Honours project: citation-network analysis comparing Financial Fraud, Corruption,
and Digital Financial Fraud judgments from the Indian Supreme Court (1950-2024).

## Folder Structure & Pipeline Order

Each top-level folder is a pipeline stage. Work flows top to bottom:

```
data/                    All data, staged by how processed it is
├── raw/                 Pointer to the downloaded Kaggle dataset (PDFs stay cached, not committed)
├── extracted/           Raw text pulled from PDFs, one CSV per year
├── processed/           Cleaned/normalized/filtered text (post-preprocessing + retrieval)
└── final/               Final per-domain corpora, ready for citation extraction & graph building

extraction/               STAGE 1 - get the data
├── download/             Kaggle dataset download
├── pdf_extraction/       PDF -> text
└── metadata_extraction/  Case name, date, court, bench info extraction

preprocessing/             STAGE 2 - clean the data
├── cleaning/              Remove noise, boilerplate, headers/footers
├── normalization/         Standardize text (case, whitespace, etc.)
├── entity_extraction/     Extract named entities (parties, judges, statutes)
└── citation_extraction/   Extract case-to-case citations (regex-based)

ontology/                  STAGE 3 - the classification rulebook
├── financial_crime_ontology/   The frozen v1.0 ontology CSV
└── mappings/                    IPC<->BNS and other legal mapping references

retrieval/                  STAGE 4 - classify judgments into domains
├── keyword_retrieval/      Stage 1 high-recall keyword matching (primary method)
├── semantic_retrieval/     Optional: embedding-based retrieval (stretch goal)
└── citation_based_retrieval/  Optional: expand corpus via citation links

network/                    STAGE 5 - build and analyze the graph
├── graph_construction/     Build the 3 domain graphs (NetworkX)
├── citation_network/       Citation edge lists per domain
└── network_analysis/       Centrality, PageRank, temporal analysis

analysis/                   STAGE 6 - interpret results
├── case_analysis/           Top influential cases per domain
├── citation_analysis/       Citation pattern findings
└── financial_crime_analysis/ Cross-domain comparison (the core "finding")

output/                     STAGE 7 - final deliverables
├── tables/                  Comparison stats, CSVs for the report
├── graphs/                  Serialized graph files
├── visualizations/          Charts, network diagrams (pyvis/matplotlib)
└── reports/                 Written summaries, figures for the synopsis

notebooks/                  Exploration & experiments (not part of the pipeline proper)
├── exploration/
└── experiments/

src/utils/                  Shared helper functions used across stages
config/                     paths.py - all file paths in one place
tests/                      (optional/stretch) sanity checks on pipeline outputs
```

## Setup (VS Code)

1. Open this folder in VS Code
2. `python -m venv venv`
3. Activate: `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Mac/Linux)
4. `pip install -r requirements.txt`
5. Select the `venv` interpreter in VS Code (Ctrl+Shift+P -> "Python: Select Interpreter")

## Kaggle Authentication

`kagglehub` needs credentials once:
- kaggle.com -> Account -> Create New API Token (downloads `kaggle.json`)
- Place at `~/.kaggle/kaggle.json` (Mac/Linux) or `C:\Users\<you>\.kaggle\kaggle.json` (Windows)

## Workflow

Each stage folder (`extraction/`, `preprocessing/`, `retrieval/`, `network/`,
`analysis/`, `output/`) gets its own `README.md` as code is added to it -
check that folder's README for stage-specific run instructions and output
format. This top-level README only tracks overall setup and the run order
across stages.

## Running the Pipeline So Far

```
python extraction/download/download_dataset.py
python extraction/pdf_extraction/extract_text.py
python extraction/pdf_extraction/combine_years.py
```

Output lands in `data/extracted/` (per-year) and `data/processed/all_judgments_raw_text.csv` (combined).

See `extraction/download/README.md` and `extraction/pdf_extraction/README.md` for details on each script.

## Syncing to GitHub

```
git init
git add .
git commit -m "Project structure + ontology + PDF extraction pipeline"
git remote add origin <your-repo-url>
git push -u origin main
```

Data folders are gitignored except `.gitkeep` placeholders - only code, config,
and the ontology CSV get committed.

## Status

- [x] Domain selection: Financial Fraud, Corruption, Digital Financial Fraud
- [x] Source-backed ontology (v1.0, frozen) -> `ontology/financial_crime_ontology/`
- [x] Project structure finalized
- [ ] `extraction/download/` - Kaggle dataset download
- [ ] `extraction/pdf_extraction/` - PDF -> text
- [ ] `extraction/metadata_extraction/` - case metadata
- [ ] `preprocessing/` - cleaning, normalization, entity + citation extraction
- [ ] `retrieval/` - keyword-based domain classification
- [ ] Manual spot-check validation
- [ ] `network/` - graph construction & analysis
- [ ] `analysis/` - cross-domain comparison
- [ ] `output/` - visualizations, tables, report
