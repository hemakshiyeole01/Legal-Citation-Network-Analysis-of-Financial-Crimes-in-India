"""Full-text search: query building, index building, and /search?scope=text.

Uses the same five synthetic cases as the other API tests, with a few lines of text each.
The last section builds a real index from the project's corpus CSVs and is skipped when
those files are not on this machine.
"""
import os
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.factory import create_app
from src.utils.fulltext import (FullTextError, FullTextIndex, IndexUnavailable, build_index, parse_snippet,
                                to_fts_query, MARK_CLOSE, MARK_OPEN)
from tests.conftest import A, B, C, D, E

TEXTS = {
    A: "The accused accepted a bribe from the contractor. Criminal breach of trust was not made out.",
    B: "The bank manager forged the documents and was charged with cheating under section 420.",
    C: "Cheating by personation in an online bank transfer. The bank lost money.",
    D: "Phishing of the OTP led to fraud on the bank account of the complainant.",
}


def write_corpus(folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    def frame(names):
        return pd.DataFrame({"file_name": names, "text": [TEXTS[n] for n in names]})
    frame([A, B]).to_csv(folder / "corruption_corpus.csv", index=False)
    frame([B, C]).to_csv(folder / "financial_fraud_corpus.csv", index=False)   # B sits in two corpora
    frame([D]).to_csv(folder / "digital_financial_fraud_corpus.csv", index=False)
    # no organized_crime / violent_crime files: a missing corpus file is tolerated; E has no text


@pytest.fixture()
def text_settings(settings, tmp_path):
    corpus = tmp_path / "corpus"
    write_corpus(corpus)
    db = tmp_path / "index" / "fulltext.db"
    build_index(corpus, db)
    return replace(settings, corpus_dir=corpus, fts_db_path=db)


@pytest.fixture()
def tclient(text_settings):
    return TestClient(create_app(text_settings))


def names(response):
    return [r["file_name"] for r in response.json()["results"]]


# ---------------------------------------------------------------- query building
@pytest.mark.parametrize("typed,expected", [
    ("bank", '"bank"'),
    ("bank fraud", '"bank" AND "fraud"'),
    ('"criminal breach of trust" bank', '"criminal breach of trust" AND "bank"'),
    ("section 420 of the IPC", '"section" AND "420" AND "IPC"'),   # filler words dropped
    ('"of the accused"', '"of the accused"'),                       # kept inside a phrase with a real word
])
def test_to_fts_query(typed, expected):
    assert to_fts_query(typed) == expected


@pytest.mark.parametrize("typed", ['bank OR NEAR(a b)', 'col:value', 'a* -b', '"unclosed', "it's", "bank; DROP TABLE x"])
def test_operators_become_plain_quoted_words(typed):
    query = to_fts_query(typed)
    assert "NEAR(" not in query.replace('"NEAR"', "") and "*" not in query and ";" not in query
    assert all(part.startswith('"') and part.endswith('"') for part in query.split(" AND "))


@pytest.mark.parametrize("typed", ["", "   ", '"', "!!!", "---"])
def test_nothing_to_search_for(typed):
    with pytest.raises(FullTextError, match="at least one word"):
        to_fts_query(typed)


@pytest.mark.parametrize("typed", ["the", "of the", '"of the"', "to be or not to be"])
def test_only_filler_words_is_rejected_with_explanation(typed):
    with pytest.raises(FullTextError, match="too common"):
        to_fts_query(typed)


def test_parse_snippet():
    raw = f"  the {MARK_OPEN}bank{MARK_CLOSE}\nmanager {MARK_OPEN}forged{MARK_CLOSE} it "
    assert parse_snippet(raw) == [
        {"text": "the ", "match": False}, {"text": "bank", "match": True},
        {"text": " manager ", "match": False}, {"text": "forged", "match": True}, {"text": " it", "match": False}]
    assert parse_snippet(None) == [] and parse_snippet("") == []
    assert parse_snippet("no matches here") == [{"text": "no matches here", "match": False}]


# ---------------------------------------------------------------- building the index
def test_build_index_counts_each_judgment_once(tmp_path):
    corpus = tmp_path / "c"; write_corpus(corpus)
    messages = []
    count = build_index(corpus, tmp_path / "i" / "f.db", progress=messages.append)
    assert count == 4                     # A, B, C, D: B appears in two corpus files
    assert len(messages) == 3             # three corpus files exist
    info = FullTextIndex(tmp_path / "i" / "f.db").info()
    assert info["available"] and info["documents"] == 4 and info["built_at"]


def test_build_index_without_corpus_files_fails_clearly_and_keeps_old_index(tmp_path):
    corpus = tmp_path / "c"; write_corpus(corpus)
    db = tmp_path / "f.db"
    build_index(corpus, db)
    before = db.stat().st_size
    with pytest.raises(FileNotFoundError, match="No \\*_corpus.csv"):
        build_index(tmp_path / "empty", db)
    assert db.stat().st_size == before and FullTextIndex(db).info()["documents"] == 4
    assert not (tmp_path / "f.db.tmp").exists()


def test_failed_build_leaves_no_temp_file_and_keeps_old_index(tmp_path):
    corpus = tmp_path / "c"; write_corpus(corpus)
    db = tmp_path / "f.db"
    build_index(corpus, db)
    pd.DataFrame({"file_name": ["x"], "wrong_column": ["y"]}).to_csv(corpus / "corruption_corpus.csv", index=False)
    with pytest.raises(ValueError):
        build_index(corpus, db)
    assert not (tmp_path / "f.db.tmp").exists() and FullTextIndex(db).info()["documents"] == 4


def test_rebuild_replaces_content(tmp_path):
    corpus = tmp_path / "c"; write_corpus(corpus)
    db = tmp_path / "f.db"; build_index(corpus, db)
    pd.DataFrame({"file_name": [E], "text": ["A new judgment about extortion."]}).to_csv(
        corpus / "violent_crime_homicide_corpus.csv", index=False)
    assert build_index(corpus, db) == 5
    assert FullTextIndex(db).match("extortion") == [E]


def test_index_unavailable_raises_helpful_error(tmp_path):
    index = FullTextIndex(tmp_path / "missing.db")
    assert index.info() == {"available": False, "documents": None, "built_at": None}
    with pytest.raises(IndexUnavailable, match="build_search_index.py"):
        index.match("bank")


# ---------------------------------------------------------------- the endpoint
def test_text_search_finds_words_inside_judgments(tclient):
    assert names(tclient.get("/search?scope=text&q=bribe")) == [A]
    assert set(names(tclient.get("/search?scope=text&q=bank"))) == {B, C, D}


def test_text_search_requires_all_words(tclient):
    assert set(names(tclient.get("/search?scope=text&q=bank cheating"))) == {B, C}
    assert tclient.get("/search?scope=text&q=bribe phishing").json()["total"] == 0


def test_exact_phrase_in_quotes(tclient):
    assert names(tclient.get('/search?scope=text&q="criminal breach of trust"')) == [A]
    assert tclient.get('/search?scope=text&q="trust criminal"').json()["total"] == 0
    # same words without quotes match on any order
    assert names(tclient.get("/search?scope=text&q=trust criminal")) == [A]


def test_stemming_matches_word_forms(tclient):
    assert names(tclient.get("/search?scope=text&q=forging")) == [B]      # text says "forged"
    assert set(names(tclient.get("/search?scope=text&q=documents"))) == {B}


def test_filler_words_do_not_exclude_results(tclient):
    assert set(names(tclient.get("/search?scope=text&q=the bank of the"))) == {B, C, D}


def test_snippets_highlight_the_matched_words(tclient):
    hit = tclient.get("/search?scope=text&q=bank cheating").json()["results"][0]
    parts = hit["snippet"]
    assert parts and all(set(p) == {"text", "match"} for p in parts)
    highlighted = {p["text"].lower() for p in parts if p["match"]}
    assert "bank" in highlighted and "cheating" in highlighted
    joined = "".join(p["text"] for p in parts)
    assert MARK_OPEN not in joined and MARK_CLOSE not in joined and "\n" not in joined


def test_results_carry_the_usual_case_fields(tclient):
    hit = tclient.get("/search?scope=text&q=bribe").json()["results"][0]
    assert hit["title"] == "Alpha Singh vs State Of Kerala" and hit["year"] == 1995
    assert hit["domains"] == ["Corruption"] and hit["cited_by_count"] == 1 and hit["pdf_available"] is False


def test_title_search_has_no_snippet(client):
    row = client.get("/search?q=alpha").json()["results"][0]
    assert row["snippet"] is None and client.get("/search?q=alpha").json()["scope"] == "title"


def test_text_search_domain_and_year_filters(tclient):
    assert names(tclient.get("/search?scope=text&q=bank&domain=digital_financial_fraud")) == [D]
    assert set(names(tclient.get("/search?scope=text&q=bank&domain=financial_fraud"))) == {B, C}
    assert set(names(tclient.get("/search?scope=text&q=bank&year_from=2000"))) == {C, D}
    assert names(tclient.get("/search?scope=text&q=bank&year_from=1990&year_to=1999")) == []


def test_text_search_sorting_and_paging(tclient):
    assert names(tclient.get("/search?scope=text&q=bank&sort=cited_by"))[0] == B
    assert names(tclient.get("/search?scope=text&q=bank&sort=year_asc")) == [B, C, D]
    page = tclient.get("/search?scope=text&q=bank&sort=year_asc&limit=2&offset=2").json()
    assert page["total"] == 3 and [r["file_name"] for r in page["results"]] == [D]
    assert tclient.get("/search?scope=text&q=bank").json()["sort"] == "relevance"


def test_text_search_is_limited_to_known_cases(tclient, tmp_path, text_settings):
    # a judgment in the index that is not in node_metrics is ignored, not an error
    corpus = tmp_path / "corpus"
    pd.DataFrame({"file_name": ["Stranger_vs_State_on_1_January_2000_1.PDF"], "text": ["bank robbery"]}).to_csv(
        corpus / "violent_crime_homicide_corpus.csv", index=False)
    build_index(corpus, text_settings.fts_db_path)
    assert set(names(tclient.get("/search?scope=text&q=bank"))) == {B, C, D}


@pytest.mark.parametrize("query,message", [
    ("scope=text", "at least one word"),
    ("scope=text&q=", "at least one word"),
    ("scope=text&q=%20%20", "at least one word"),
    ("scope=text&q=%22", "at least one word"),
    ("scope=text&q=the%20of", "too common"),
])
def test_text_search_bad_queries_are_422(tclient, query, message):
    r = tclient.get(f"/search?{query}")
    assert r.status_code == 422 and message in r.json()["detail"]


def test_operator_characters_never_cause_a_server_error(tclient):
    for q in ['bank OR', 'NEAR(bank fraud)', 'col:x', 'bank*', '-bank', "bank'", 'bank"', "(((", "a AND"]:
        assert tclient.get("/search", params={"scope": "text", "q": q}).status_code in (200, 422), q


def test_bad_scope_is_422(tclient):
    assert tclient.get("/search?scope=bogus&q=bank").status_code == 422


def test_text_search_without_index_is_503_with_instructions(client):
    r = client.get("/search?scope=text&q=bank")
    assert r.status_code == 503 and "build_search_index.py" in r.json()["detail"]
    assert client.get("/search?q=alpha").status_code == 200          # case-name search is unaffected


def test_health_reports_index_state(client, tclient):
    assert client.get("/health").json()["fulltext_index"]["available"] is False
    info = tclient.get("/health").json()["fulltext_index"]
    assert info["available"] is True and info["documents"] == 4 and info["built_at"]


# ---------------------------------------------------------------- real corpus (optional)
REAL_CORPUS = Path(os.environ.get("LCN_CORPUS_DIR", Path(__file__).resolve().parent.parent / "data" / "final"))
HAVE_REAL = (REAL_CORPUS / "corruption_corpus.csv").is_file()


@pytest.fixture(scope="module")
def real_client(tmp_path_factory):
    from config.settings import Settings
    settings = Settings.from_env()
    if not settings.node_metrics_path.is_file():
        pytest.skip("real node_metrics.csv not found")
    db = tmp_path_factory.mktemp("index") / "fulltext.db"
    build_index(REAL_CORPUS, db)
    return TestClient(create_app(replace(settings, corpus_dir=REAL_CORPUS, fts_db_path=db)))


@pytest.mark.skipif(not HAVE_REAL, reason="real corpus CSVs not found")
class TestRealCorpus:
    def test_every_case_is_indexed(self, real_client):
        health = real_client.get("/health").json()
        assert health["fulltext_index"]["documents"] == health["cases"] == 4172

    def test_phrase_search_returns_snippets_that_contain_the_phrase(self, real_client):
        body = real_client.get("/search", params={"scope": "text", "q": '"criminal breach of trust"', "limit": 10}).json()
        assert body["total"] > 100 and len(body["results"]) == 10
        for hit in body["results"]:
            text = "".join(p["text"] for p in hit["snippet"]).lower()
            assert any(p["match"] for p in hit["snippet"]) and "trust" in text

    def test_domain_filter_narrows_results(self, real_client):
        everything = real_client.get("/search", params={"scope": "text", "q": "cheating"}).json()["total"]
        digital = real_client.get("/search", params={"scope": "text", "q": "cheating",
                                                     "domain": "digital_financial_fraud"}).json()
        assert 0 < digital["total"] < everything
        assert all("Digital Financial Fraud" in r["domains"] for r in digital["results"])

    def test_common_legal_words_stay_fast(self, real_client):
        import time
        for word in ("court", "section", "accused"):
            started = time.time()
            assert real_client.get("/search", params={"scope": "text", "q": word, "limit": 20}).status_code == 200
            assert time.time() - started < 3
