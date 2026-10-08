"""
Single source of truth for the domain list and domain->filename slugging.

Every pipeline script used to hardcode its own DOMAIN_FILES dict and its
own `domain.lower().replace(' ', '_')` slugging. That meant adding a
domain required editing 6+ files by hand - and one of those files always
used the naive replace, which breaks for domain names containing " / "
(e.g. "Organized Crime / Extortion" -> "organized_crime_/_extortion",
a literal slash in a filename, invalid on Windows and liable to be
misread as a path separator on Unix).

Now every script imports get_domains() and domain_to_filename() from
here. Add a domain by editing the ontology CSV only - no script changes.
"""

import pandas as pd
from config.paths import ONTOLOGY_PATH


def get_domains() -> list:
    """Returns the sorted list of domain names from the ontology's
    crime_category column."""
    df = pd.read_csv(ONTOLOGY_PATH)
    return sorted(df["crime_category"].unique().tolist())


def domain_to_filename(domain: str) -> str:
    """'Organized Crime / Extortion' -> 'organized_crime_extortion'
    'Financial Fraud' -> 'financial_fraud'
    Handles ' / ' first (as one unit) so it collapses to a single
    underscore instead of leaving a stray slash or double underscore."""
    return domain.lower().replace(" / ", "_").replace(" ", "_")


def corpus_filename(domain: str) -> str:
    return f"{domain_to_filename(domain)}_corpus.csv"


# Distinct, colorblind-reasonable palette (seaborn "deep" order). Cycles if
# there are ever more domains than colors, so this never breaks on count.
_COLOR_PALETTE = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B2", "#937860", "#DA8BC3"]


def get_domain_colors() -> dict:
    """domain name -> hex color, assigned in sorted domain order so the
    same domain always gets the same color across runs."""
    domains = get_domains()
    return {d: _COLOR_PALETTE[i % len(_COLOR_PALETTE)] for i, d in enumerate(domains)}
