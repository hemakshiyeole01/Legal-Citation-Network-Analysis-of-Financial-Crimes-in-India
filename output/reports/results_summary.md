# Results summary (auto-generated draft)

Generated 2026-10-10 by `analysis/financial_crime_analysis/compare_domains.py` from `output/tables/`. Every number below is computed; the wording is a draft to review and edit. Re-run after any pipeline change.

## 1. Scope

- 4,172 Supreme Court judgments (1950-2025) were classified into at least one of 5 domains. A judgment can belong to more than one domain, so the per-domain counts add up to 4,622.
- Influence and citation counts use only citations **between these judgments**. Citations from the other ~22,000 judgments in the dataset are not counted.
- Domain assignment is rule-based (statute sections + keywords + context terms), not hand-labelled. In manual spot-checks of 20 judgments per domain, four domains had no clear errors; Digital Financial Fraud had 6 of 20 clear errors before the final gate fix, and the corrected Digital corpus has not been fully audited.

## 2. Domain comparison

| Domain | Cases | Citations received per case (95% CI) | % of cases cited | Own-domain citation rate vs chance (95% CI) | Median citation lag, yrs (95% CI) | Median year |
|---|---|---|---|---|---|---|
| Violent Crime / Homicide | 2,294 | 0.249 (0.198-0.308) | 7.3% | 1.39 (1.32-1.44) | 29 (28-31) | 2002 |
| Organized Crime / Extortion | 955 | 0.276 (0.165-0.410) | 5.7% | 2.97 (2.68-3.23) | 27 (25-29) | 2005 |
| Financial Fraud | 783 | 0.083 (0.047-0.128) | 3.8% | 1.75 (1.34-2.21) | 33 (23-45) | 2005 |
| Corruption | 548 | 0.155 (0.089-0.237) | 5.5% | 2.78 (2.19-3.43) | 29 (26-32) | 2003 |
| Digital Financial Fraud | 42 | 0 (none observed) | 0.0% | n/a | n/a | 2021 |

Own-domain citation rate vs chance: 1.0 means the domain cites its own cases exactly as often as random choice among older cases would predict; above 1 means it prefers its own domain.

## 3. What the data shows

- **Size.** Violent Crime / Homicide is the largest domain (2,294 cases); the smallest ranked domain is Corruption (548).
- **How often cases are cited.** Between 3.8% (Financial Fraud) and 7.3% (Violent Crime / Homicide) of cases are cited at least once by another case in the same domain. This raw figure favours larger domains; see the next point.
- **Own-domain citation, adjusted for size and era.** Organized Crime / Extortion 2.97; Corruption 2.78; Financial Fraud 1.75; Violent Crime / Homicide 1.39. Highest: Organized Crime / Extortion; lowest: Violent Crime / Homicide. Their intervals do not overlap, so this difference is unlikely to be chance.
- **Age of the precedent relied on.** The median gap between a case and the case it cites is 27 years (Organized Crime / Extortion) to 33 years (Financial Fraud); check the intervals in the table before calling any difference real.
- **Reliance on precedent outside the five domains.** 50% (Violent Crime / Homicide) to 65% (Organized Crime / Extortion) of each domain's resolved citations point to judgments that belong to none of the five domains (e.g. general criminal-procedure or constitutional rulings).
- **Digital Financial Fraud** has only 42 cases and 0 citation links among them, so it is described but not ranked or tested. Own-domain rate vs chance is not reported: 0 observed against only 0.2 expected by chance, too few for a ratio to mean anything. Of its 64 resolved citation links, 0% go to its own domain, 53% to the other four, 47% outside the five.

## 4. Hypothesis check

**Stated hypothesis:** the domain built on the oldest law (Financial Fraud) shows a denser, older citation network than the domain built on the newest law (Digital Financial Fraud).

**Not testable with this data.** Digital Financial Fraud has 42 cases and 0 internal citation links. A network with no internal links cannot be called less dense in any meaningful sense - the comparison is undefined, not a result. Two explanations are possible and this analysis does not separate them: either few Supreme Court judgments on digital financial fraud exist in this corpus up to 2025, or the classification rules capture only part of them. (The rules were tightened after spot-checks found false positives, which shrank the domain; the corrected corpus has not been fully audited.)

For context, Financial Fraud has 783 cases, 65 internal links, a median citation lag of 33 years and a median judgment year of 2005.

**What can be said instead.** With five domains and different statutes underneath each, there are too few points to test a trend against statute age. The comparison that the data can support is the descriptive one in section 3: how each domain cites within itself, across domains, and outside the five.

## 5. Limitations

- Only citations between the five domain corpora are counted; influence is therefore measured within these domains, not across the whole Supreme Court record.
- Older cases have had longer to be cited; raw citation counts favour them. The temporal tables (Phase 3) and the era adjustment in the own-domain rate partly address this.
- The own-domain rate assumes a citation could have landed on any older case in the five domains with equal probability. Real citing is not random (subject matter, court bench), so the 'expected' figure is a baseline, not a model of citing behaviour.
- Most cases in every domain are never cited by another case in the study (see % cited). That is a property of the data, not a calculation error.
- Citations are matched by their printed reporter reference (AIR/SCC/SCR). Citations to cases that are not in the dataset, or in formats the extractor does not recognise, are unresolved and excluded.

## 6. How to reproduce

```
python network/network_analysis/analyze_networks.py
python analysis/case_analysis/analyze_cases.py
python analysis/citation_analysis/analyze_citations.py
python analysis/financial_crime_analysis/compare_domains.py
```
