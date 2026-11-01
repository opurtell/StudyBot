import json
import sqlite3
from pathlib import Path

import pytest

from guidelines import actas_scope as scope
from guidelines.markdown import normalise_markdown_syntax
from paths import APP_ROOT, service_structured_dir
from web_corpus import build as corpus_build

MIGRATIONS = sorted((APP_ROOT / "web" / "migrations").glob("*.sql"))


@pytest.fixture(scope="module")
def corpus():
    return corpus_build.build(built_at="2026-11-01T00:00:00+00:00")


def _doc(document_id="CMG_99_Test", source_type="cmg", **overrides):
    data = {
        "id": document_id,
        "cmg_number": "99",
        "title": "Patient's Test Guideline",
        "section": "Medical",
        "version_date": None,
        "is_icp_only": False,
        "content_markdown": "# Test\n\n#### Management\n\n- Give oxygen.\n- Adenosine IV.\n",
        "dose_lookup": {},
        "flowchart": None,
        "checksum": "abc",
        "extraction_metadata": {"timestamp": "2026-11-01T00:00:00+00:00", "source_type": source_type},
        "qualifications_required": ["AP"],
    }
    data.update(overrides)
    return data


def _write(directory: Path, data: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{data['id']}.json").write_text(json.dumps(data), encoding="utf-8")


def test_only_guideline_content_enters_the_corpus(corpus):
    assert {d.source_type for d in corpus.documents} == {"guideline"}
    assert corpus_build.manifest(corpus)["documents_by_kind"] == {"cmg": 56, "csm": 103, "med": 35}
    structured = service_structured_dir("actas").resolve()
    for path in corpus_build.input_files(structured):
        assert structured in path.resolve().parents or path.resolve().parent == structured


@pytest.mark.parametrize("source_type", ["cpd_doc", "ref_doc", "notability_note", "upload", None])
def test_build_fails_on_any_other_source_type(tmp_path, source_type):
    _write(tmp_path, _doc())
    _write(tmp_path, _doc("CMG_98_Personal", source_type=source_type))
    with pytest.raises(corpus_build.CorpusBuildError, match="not ACTAS guideline content"):
        corpus_build.build(tmp_path)


def test_allowlist_check_rejects_a_tampered_document(corpus):
    corpus.documents[0].source_type = "cpd_doc"
    try:
        with pytest.raises(corpus_build.CorpusBuildError, match="not allowed"):
            corpus_build.check_allowlist(corpus)
    finally:
        corpus.documents[0].source_type = "guideline"


def test_cli_exits_non_zero_without_writing_output(tmp_path):
    _write(tmp_path / "in", _doc(source_type="notability_note"))
    assert corpus_build.main(["--structured-dir", str(tmp_path / "in"), "--out", str(tmp_path / "out")]) == 1
    assert not (tmp_path / "out").exists()


def test_bodies_match_the_desktop_scope_rules(corpus):
    files = {p.stem: p for p in corpus_build.input_files(service_structured_dir("actas"))}
    for doc in corpus.documents:
        data = json.loads(files[doc.id].read_text(encoding="utf-8"))
        content = normalise_markdown_syntax(corpus_build.decode_literal_escapes(data["content_markdown"]))
        if doc.scope in ("all", "mixed"):
            assert doc.bodies["ap"] == scope.ap_text(data, content)
        assert doc.bodies["icp"] == ("" if doc.scope == "pacer" else scope.icp_text(data, content))
        assert doc.bodies["icp_pacer"] == scope.render(scope.classify(data, content), {"AP", "ICP", "PACER"})


def test_icp_only_guidelines_are_hidden_from_ap(corpus):
    icp_only = [d for d in corpus.documents if d.scope == "icp"]
    assert any(d.kind == "cmg" and d.number.upper() == "3A" for d in icp_only)
    icp_ids = {d.id for d in icp_only}
    for doc in icp_only:
        assert doc.bodies["ap"] == ""
    for chunk in corpus.chunks:
        if chunk.document_id in icp_ids:
            assert "ap" not in chunk.views


def test_olanzapine_is_pacer_only(corpus):
    olanzapine = next(d for d in corpus.documents if d.kind == "med" and "olanzapine" in d.title.lower())
    assert olanzapine.scope == "pacer"
    views = {v for c in corpus.chunks if c.document_id == olanzapine.id for v in c.views}
    assert views == {"ap_pacer", "icp_pacer"}


def test_chunks_are_bounded_unique_and_labelled(corpus):
    ids = [c.id for c in corpus.chunks]
    assert len(ids) == len(set(ids))
    titles = {d.id: d.context for d in corpus.documents}
    for chunk in corpus.chunks:
        assert 0 < len(chunk.text) <= corpus_build.MAX_CHUNK_CHARS
        assert chunk.embed_text.startswith(titles[chunk.document_id])
        assert chunk.views


def test_version_is_stable_across_builds(corpus):
    assert corpus_build.build(built_at="2030-01-01T00:00:00+00:00").version == corpus.version


def _db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys = ON")
    for migration in MIGRATIONS:
        db.executescript(migration.read_text(encoding="utf-8"))
    return db


def test_sql_loads_into_the_d1_schema_and_reloads_idempotently(tmp_path):
    _write(tmp_path, _doc())
    first = corpus_build.build(tmp_path)
    db = _db()
    db.executescript(corpus_build.to_sql(first))
    db.execute("UPDATE corpus_chunks SET embedded_at = 1")
    db.executescript(corpus_build.to_sql(first))
    assert db.execute("SELECT title FROM corpus_documents").fetchall() == [("Patient's Test Guideline",)]
    assert db.execute("SELECT COUNT(*) FROM corpus_chunks WHERE embedded_at IS NULL OR retired_at IS NOT NULL").fetchone() == (0,)
    assert db.execute("SELECT version, is_current FROM corpus_versions").fetchall() == [(first.version, 1)]


def test_reload_with_changed_content_retires_old_chunks(tmp_path):
    _write(tmp_path, _doc())
    _write(tmp_path, _doc("CMG_97_Removed"))
    first = corpus_build.build(tmp_path)
    db = _db()
    db.executescript(corpus_build.to_sql(first))
    (tmp_path / "CMG_97_Removed.json").unlink()
    _write(tmp_path, _doc(content_markdown="# Test\n\n- New wording.\n", checksum="def"))
    second = corpus_build.build(tmp_path)
    db.executescript(corpus_build.to_sql(second))
    assert db.execute("SELECT id FROM corpus_documents").fetchall() == [("CMG_99_Test",)]
    assert db.execute("SELECT COUNT(*) FROM corpus_document_bodies WHERE document_id = 'CMG_97_Removed'").fetchone() == (0,)
    live = db.execute("SELECT text FROM corpus_chunks WHERE retired_at IS NULL").fetchall()
    assert live == [("- New wording.",)]
    assert db.execute("SELECT COUNT(*) FROM corpus_chunks WHERE retired_at IS NOT NULL").fetchone()[0] >= 2
    assert db.execute("SELECT version FROM corpus_versions WHERE is_current = 1").fetchall() == [(second.version,)]


def test_real_corpus_loads_into_the_d1_schema(corpus):
    db = _db()
    db.executescript(corpus_build.to_sql(corpus))
    assert db.execute("SELECT COUNT(*) FROM corpus_documents").fetchone() == (194,)
    assert db.execute("SELECT COUNT(*) FROM corpus_chunks").fetchone() == (len(corpus.chunks),)
    assert db.execute("SELECT DISTINCT source_type FROM corpus_chunks").fetchall() == [("guideline",)]


def test_literal_escapes_from_the_scrape_are_decoded(corpus):
    assert corpus_build.decode_literal_escapes(r"\u03b2 effects, 30\xb0C, \xbd tablet,\xa0x") == "\u03b2 effects, 30\xb0C, \xbd tablet, x"
    for doc in corpus.documents:
        assert not corpus_build._LITERAL_ESCAPE.search(doc.bodies["icp_pacer"]), doc.id
