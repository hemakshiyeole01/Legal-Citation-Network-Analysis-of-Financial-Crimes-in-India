# network/citation_network (Phase 1 - Person A)

Resolves citation_normalized strings from Phase 0 against the full corpus
to build real citing_file_name -> cited_file_name edges.

## Run (after preprocessing/citation_extraction/extract_citations.py)
```
python network/citation_network/build_edges.py
```

## Edge classification
Every citation mention gets classified:
- **INTERNAL** - cited case is in the SAME domain corpus (these build your graphs)
- **CROSS_DOMAIN** - cited case is in a DIFFERENT one of your 3 domains
  (interesting on its own - e.g. does Financial Fraud cite Corruption cases?)
- **OUTSIDE_DOMAINS** - cited case exists in the full 26,688 corpus but
  isn't in any of your 3 domains (e.g. a landmark constitutional case)
- **UNRESOLVED** - not found anywhere in the full corpus (outside the
  Kaggle dataset, or a citation format we couldn't match)

## Bug found and fixed during testing
Some judgments genuinely match more than one domain (your full run: 1,127
+ 678 + 272 = 2,077 domain-file rows, but only 1,679 unique judgments
matched at all - meaning 398 judgments appear in 2+ domain corpora at
once). The original domain-membership lookup used a plain dict overwrite,
so any multi-domain judgment silently "forgot" all but the last domain
processed, causing wrong INTERNAL/CROSS_DOMAIN classification for those
398 judgments. Fixed by storing a set of domains per judgment instead of
a single value - verified against real data with an overlapping test
case.
**If you already have edge files from before this fix, re-run
build_edges.py to regenerate them with correct classifications.**

## Output (per domain)
- `*_edges_all.csv` - every citation mention with its classification, for
  cross-domain analysis later
- `*_edges_internal.csv` - deduplicated citing->cited pairs where both
  sides are in the same domain, ready to feed directly into
  `network/graph_construction/`

## On resolution rate
Expect a modest INTERNAL resolution rate (single digits to low tens of
percent) - most cited cases are landmark precedents from decades earlier
that may not have matched your domain's keyword/section retrieval rules,
so they won't be IN your domain corpus even though they're real, valid
citations. This is expected, not a bug - it's exactly why UNRESOLVED and
OUTSIDE_DOMAINS categories exist separately, so you can report the real
number honestly rather than pretending every citation resolves.

## Bug found and fixed during testing
Early testing showed judgments "citing themselves" (self-loops) in the
resolved edges. Root cause was in Phase 0 (see its README) - not
something to fix here, but flagging: if you rerun Phase 0 after pulling
a fresh copy of this project, make sure you have the version with the
800-character header-zone exclusion, or self-loops will reappear.
