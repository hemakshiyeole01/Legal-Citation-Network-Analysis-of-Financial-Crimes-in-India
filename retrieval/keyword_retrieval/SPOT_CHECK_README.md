# retrieval/keyword_retrieval - Manual Spot-Check (Step 10)

## Run (after retrieve_domains.py)
```
python retrieval/keyword_retrieval/prepare_spot_check.py
```

Samples 50 judgments per domain (150 total), shuffled, with a text
snippet around the first matched signal, into `data/final/spot_check_sample.csv`.

## How to review
1. Open `data/final/spot_check_sample.csv` in **VS Code**, not Excel
2. For each row, read the snippet (and file name / matched_subcategories
   for context) and fill the `label` column with:
   - `Yes` - genuinely belongs in this domain
   - `No` - false positive, doesn't belong
   - `Uncertain` - can't tell from the snippet alone (check the full
     judgment in the domain corpus CSV if needed)
3. Optionally add a short reason in the `notes` column - useful later
   when writing up your methodology/limitations section

## After labeling
Calculate a rough precision estimate:
```
precision = count(label == "Yes") / count(label in ["Yes","No"])
```
(Exclude "Uncertain" rows from the calculation, or treat them as "No"
for a conservative estimate.)

If precision is low for a specific domain/subcategory, that's a signal
to revisit that subcategory's ontology rules (Step 11) - e.g. tighten
keywords, add another exclusion condition - rather than accepting a
noisy corpus.
