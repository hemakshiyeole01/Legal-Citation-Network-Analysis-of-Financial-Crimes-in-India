"""The five crime domains used throughout the project.

`name` must match the `domain` strings in output/tables/node_metrics.csv and the
`edge_prefix` must match the edge-list file names in network/citation_network/.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Domain:
    slug: str
    name: str
    edge_prefix: str | None  # None for the combined view
    color: str


DOMAINS: tuple[Domain, ...] = (
    Domain("financial_fraud", "Financial Fraud", "financial_fraud", "#445E81"),
    Domain("corruption", "Corruption", "corruption", "#BF6913"),
    Domain("digital_financial_fraud", "Digital Financial Fraud", "digital_financial_fraud", "#4EAD83"),
    Domain("organized_crime_extortion", "Organized Crime / Extortion", "organized_crime_extortion", "#7F4BA7"),
    Domain("violent_crime_homicide", "Violent Crime / Homicide", "violent_crime_homicide", "#F61A33"),
)

COMBINED = Domain("combined", "Combined (all domains)", None, "#5B6573")

ALL_VIEWS: tuple[Domain, ...] = DOMAINS + (COMBINED,)

_BY_SLUG = {d.slug: d for d in ALL_VIEWS}
_BY_NAME = {d.name.lower(): d for d in ALL_VIEWS}


class UnknownDomain(ValueError):
    def __init__(self, value: str):
        self.value = value
        valid = ", ".join(d.slug for d in ALL_VIEWS)
        super().__init__(f"Unknown domain '{value}'. Valid values: {valid}")


def resolve_domain(value: str, allow_combined: bool = True) -> Domain:
    """Accept a slug (corruption), a hyphenated slug (financial-fraud) or the display name."""
    key = (value or "").strip().lower()
    domain = _BY_SLUG.get(key.replace("-", "_").replace(" ", "_")) or _BY_NAME.get(key)
    if domain is None or (domain is COMBINED and not allow_combined):
        raise UnknownDomain(value)
    return domain


def domain_by_name(name: str) -> Domain:
    return _BY_NAME[name.lower()]
