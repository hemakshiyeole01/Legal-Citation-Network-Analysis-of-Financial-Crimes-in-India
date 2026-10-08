"""
Central config for paths used across the pipeline.
Every script imports from here instead of hardcoding paths -
so if the folder structure ever changes, this is the only file to update.
"""

import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- Data stages ---
DATA_RAW = os.path.join(PROJECT_ROOT, "data", "raw")
DATA_EXTRACTED = os.path.join(PROJECT_ROOT, "data", "extracted")
DATA_PROCESSED = os.path.join(PROJECT_ROOT, "data", "processed")
DATA_FINAL = os.path.join(PROJECT_ROOT, "data", "final")

# --- Ontology ---
# v1.0 is kept in the repo as the frozen, multi-round-reviewed 3-domain
# version. v1.1 adds Violent Crime/Homicide and Organized Crime/Extortion
# per the guide's request, plus a required_context column.
ONTOLOGY_PATH = os.path.join(
    PROJECT_ROOT, "ontology", "financial_crime_ontology", "legal_crime_ontology_v1_2.csv"
)
CONTEXT_GROUPS_PATH = os.path.join(
    PROJECT_ROOT, "ontology", "mappings", "context_groups.csv"
)

# --- Output ---
OUTPUT_TABLES = os.path.join(PROJECT_ROOT, "output", "tables")
OUTPUT_GRAPHS = os.path.join(PROJECT_ROOT, "output", "graphs")
OUTPUT_VISUALIZATIONS = os.path.join(PROJECT_ROOT, "output", "visualizations")
OUTPUT_REPORTS = os.path.join(PROJECT_ROOT, "output", "reports")

# --- Kaggle dataset ---
KAGGLE_DATASET_ID = "adarshsingh0903/legal-dataset-sc-judgments-india-19502024"

for path in [DATA_RAW, DATA_EXTRACTED, DATA_PROCESSED, DATA_FINAL,
             OUTPUT_TABLES, OUTPUT_GRAPHS, OUTPUT_VISUALIZATIONS, OUTPUT_REPORTS]:
    os.makedirs(path, exist_ok=True)
