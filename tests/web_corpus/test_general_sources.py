import json
import re
import sqlite3

import pytest

from paths import APP_ROOT
from web_corpus import build as corpus_build
from web_corpus import general_sources as gs
from web_corpus import questions as qb

MIGRATIONS = sorted((APP_ROOT / "web" / "migrations").glob("*.sql"))
FETCHED = "2026-11-02T00:00:00+00:00"

PAGE = """<html><head><title>Atrial Flutter • LITFL • ECG Library Diagnosis</title>
<meta name="author" content="Ed Burns"></head><body><nav>menu</nav>
<div class="entry-content"><h1>Atrial Flutter</h1>
<h2>Overview</h2><p>Atrial flutter is a macro-reentrant  atrial tachyarrhythmia with atrial rates around 300 bpm.</p>
<figure><img src="x.png"><figcaption>Image credit someone</figcaption></figure>
<h2>ECG features</h2><ul><li>Saw-tooth flutter waves, best seen in II, III and aVF</li>
<li>Ventricular rate is a fraction of the atrial rate<ul><li>2:1 block gives a rate near 150 bpm</li></ul></li></ul>
<p>Flutter waves are inverted in the inferior leads in typical counter-clockwise flutter, and the isoelectric baseline
is absent between flutter waves. Variable block produces an irregular ventricular rhythm.</p>
<h2>Management</h2><p>Give a medicine at a dose.</p><h3>Cardioversion</h3><p>Shock it.</p>
<h2>Clinical significance</h2><table><tr><th>Block</th><th>Rate</th></tr><tr><td>2:1</td><td>150</td></tr></table>
<h2>References</h2><p>Some reference.</p><h2>Empty heading</h2>
</div><div class="sharedaddy">share</div><footer>creativecommons.org/licenses/by-nc-sa/4.0</footer></body></html>"""


def test_pages_keep_recognition_text_and_drop_treatment_images_and_references():
    md = gs.clean(gs.html_to_markdown(gs.extract_main_html(PAGE)))
    assert "## ECG features" in md and "- Saw-tooth flutter waves" in md and "  - 2:1 block" in md
    assert "Block | Rate\n2:1 | 150" in md
    for gone in ("Management", "medicine", "Cardioversion", "References", "Image credit", "menu", "share", "Empty heading"):
        assert gone not in md
    assert gs.page_title(PAGE) == "Atrial Flutter"
    assert gs.page_authors(PAGE) == "Ed Burns"


def test_litfl_links_skip_indexes_quizzes_and_duplicates():
    html = """<div class="entry-content"><a href="https://litfl.com/atrial-flutter-ecg-library/">a</a>
    <a href="https://litfl.com/atrial-flutter-ecg-library/">again</a><a href="https://litfl.com/ecg-library/basics/">i</a>
    <a href="https://litfl.com/top-150-ecg-series/">t</a><a href="https://litfl.com/wellens-syndrome-ecg-library/">w</a>
    """ + "x" * 600 + "</div><footer></footer>"
    assert gs.litfl_links(html) == ["https://litfl.com/atrial-flutter-ecg-library/",
                                    "https://litfl.com/wellens-syndrome-ecg-library/"]


LITFL_INDEX = """<div class="entry-content"><h2>ECG Waves</h2><a href="https://litfl.com/p-wave-ecg-library/">P</a>
<a href="https://litfl.com/ecg-exam-template/">t</a><a href="https://litfl.com/paediatric-ecg-basics/">p</a>
<h2>Search the ECG Library (with Ninja hidden keywords)</h2><a href="https://litfl.com/john-hay/">eponym</a>
""" + "x" * 600 + """<aside class="litfl-cc"><a href="https://litfl.com/course/">course</a></aside></div>"""


def test_litfl_index_links_stop_at_the_hidden_keyword_block():
    assert gs.litfl_links(LITFL_INDEX) == ["https://litfl.com/p-wave-ecg-library/"]


def test_litfl_pages_end_before_course_and_author_boxes_and_bold_paragraphs_become_headings():
    html = """<div class="entry-content"><h5>ECG features</h5><p>Peaked T waves are an early sign of raised potassium,
    followed by PR prolongation, P wave flattening and QRS widening as the level rises further.</p>
    <p>Look at aVR. [PMID 18180024]</p><p>ECG 1</p>
    <p class="wp-block-paragraph"><strong>Related Topics</strong></p><ul><li>Hypokalaemia</li></ul>
    <p><strong>References</strong></p><ul><li>Smith. A paper. PMID 1</li></ul>
<h5>Clinical Cases</h5><ul><li>ECG Top 100 – Case 010</li></ul>
    <h5>Advanced Reading</h5><ul><li>A textbook</li></ul><h2>Critical Care</h2><p>Compendium</p><p>…more CCC</p>
    <p>Thanks to Dr Someone, FACEM, for providing this ECG.</p><p>Image Credit: a blog</p>""" + " " * 600 + """
    <aside class="litfl-cc"><span>Start learning for free</span></aside><div class="m-a-box">MBBS FACEM bio</div></div>
    <footer><a href="https://creativecommons.org/licenses/by-nc-sa/4.0/" rel="license">CC</a></footer>"""
    md = gs.clean(gs.html_to_markdown(gs.promote_bold_paragraphs(gs.extract_main_html(html))))
    assert "Peaked T waves" in md
    assert "Look at aVR.\n" in md
    for gone in ("Related", "Hypokalaemia", "PMID", "ECG 1", "Case 010", "textbook", "Compendium", "more CCC", "Thanks to", "Image Credit",
                 "Start learning", "MBBS"):
        assert gone not in md
    assert gs.litfl_licensed(html)
    assert not gs.litfl_licensed(html.replace("by-nc-sa", "by-nc-nd"))
    assert not gs.litfl_licensed(html.split("<footer>")[0] + '<a href="https://creativecommons.org/licenses/by-nc-sa/4.0/" rel="license">')


def test_page_authors_are_deduplicated_across_meta_tags():
    html = ('<meta name="author" content="Ed Burns"><meta name="author" content="Robert Buttner">'
            '<meta name="author" content="Ed Burns and Robert Buttner" />')
    assert gs.page_authors(html) == "Ed Burns and Robert Buttner"


def _bits_chapter(licence="http://creativecommons.org/licenses/by/4.0/"):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE book-part-wrapper PUBLIC "-//NLM//DTD BITS Book Interchange DTD v2.0 20151225//EN" "BITS-book2.dtd">
<book-part-wrapper xmlns:xlink="http://www.w3.org/1999/xlink" id="ch5cardio" content-type="chapter">
<book-meta><book-id book-id-type="pmcid">openrnha</book-id>
<permissions><license license-type="open-access" xlink:href="{licence}"><license-p>CC BY</license-p></license></permissions>
</book-meta>
<book-part book-part-type="chapter"><book-part-meta><book-part-id book-part-id-type="pmcid">ch5cardio</book-part-id>
<title-group><title>Chapter 5 Cardiovascular Alterations</title></title-group></book-part-meta>
<body>
<sec id="ch5cardio.sec5.1"><label>5.1</label><title>Cardiovascular Introduction</title>
<sec id="ch5cardio.o"><title>Learning Objectives</title><p>Apply the nursing process.</p></sec></sec>
<sec id="ch5cardio.sec5.4"><label>5.4</label><title>Common Cardiovascular Disorders</title><p>Each is discussed below.</p></sec>
<sec id="ch5cardio.sec5.8"><label>5.8</label><title>Heart Failure</title>
<sec id="ch5cardio.Overview_3"><title>Overview</title>
<p>Heart failure occurs when the heart loses its effectiveness in pumping blood, reducing cardiac output and causing
fatigue, dyspnoea and oedema as fluid backs up behind the failing ventricle.[<xref ref-type="bibr" rid="r1">1</xref>]
See <xref ref-type="fig" rid="f1">Figure 5.21</xref> for an illustration.</p>
<p>Malignant cells grow without control.[3] View a supplementary YouTube video on cardiac output: View an image of oedema.</p>
<boxed-text><p>View a supplementary YouTube video on heart failure.</p></boxed-text>
<fig id="f1"><label>Figure 5.21</label><caption><p>Image credit: someone</p></caption><graphic xlink:href="x"/></fig>
<table-wrap><table><thead><tr><th>Side</th><th>Signs</th><th colspan="1">Nursing Interventions</th><th>Treatment</th></tr></thead>
<tbody><tr><td>Left</td><td><list><list-item><p>Orthopnoea</p></list-item></list></td><td>Sit upright</td><td>Frusemide</td></tr>
<tr><td>Management</td><td>Diuretics</td><td>x</td><td>y</td></tr>
</tbody></table></table-wrap>
<p>Causes include the following,<xref ref-type="bibr" rid="r2">2</xref>,<xref ref-type="bibr" rid="r3">3</xref>: ischaemia and
hypertension.<xref ref-type="bibr" rid="r4">4</xref>,<xref ref-type="bibr" rid="r5">5</xref></p>
<p>Left-sided failure raises pulmonary venous pressure, so fluid moves into the alveoli and causes crackles and
pulmonary oedema, while right-sided failure causes peripheral oedema, hepatomegaly and jugular venous distension.</p>
</sec>
<sec id="ch5cardio.Medication_Therapy_2"><title>Medication Therapy</title><p>Give a diuretic at a dose.</p></sec>
<sec id="ch5cardio.Nursing_Interventions_3"><title>Nursing Interventions</title><p>Weigh daily.</p></sec>
<sec id="ch5cardio.References_6"><title>References</title><ref-list><ref><mixed-citation>A ref.</mixed-citation></ref></ref-list></sec>
</sec>
<sec id="ch5cardio.sec5.14"><label>5.14</label><title>Learning Activities</title><sec><title>Quiz</title><p>Q.</p></sec></sec>
<sec id="ch5cardio.Glossary"><label>V</label><title>Glossary</title><def-list><def-item><term>HF</term><def><p>x</p></def></def-item></def-list></sec>
</body></book-part></book-part-wrapper>""".encode("utf-8")


def test_openrn_chapters_keep_pathophysiology_and_drop_care_figures_and_references():
    book = gs.OPENRN_BOOKS[0]
    sections = gs.openrn_sections(_bits_chapter(), book)
    assert [(s["label"], s["title"]) for s in sections] == [("5.8", "Heart Failure")]
    assert sections[0]["url"] == "https://www.ncbi.nlm.nih.gov/books/n/openrnha/ch5cardio/#ch5cardio.sec5.8"
    doc = gs.make_document(gs.SOURCES["openrn"], doc_id="OPENRN_HA_5_8_Heart_Failure", number="HA 5.8",
                           title="Heart Failure", section=book.section, url=sections[0]["url"],
                           attribution=gs.openrn_attribution(book, "5.8 Heart Failure", sections[0]["url"]),
                           markdown=sections[0]["markdown"], fetched_at=FETCHED)
    md = doc["content_markdown"]
    assert "## Overview" in md and "cardiac output" in md and "Side | Signs" in md and "Orthopnoea" in md
    assert "jugular venous distension" in md
    assert "Malignant cells grow without control.\n" in md
    assert "Side | Signs\n" in md and "following: ischaemia and hypertension.\n" in md
    for gone in ("[1]", "[3]", "[]", "Figure", "YouTube", "image of", "Image credit", "diuretic", "Sit upright", "Frusemide", "Diuretics", ",,", "Weigh daily", "A ref.", "Quiz"):
        assert gone not in md
    assert "NCBI Bookshelf" in doc["attribution"] and "CC BY 4.0" in doc["attribution"]


def test_openrn_chapters_must_carry_the_cc_by_licence():
    with pytest.raises(ValueError, match="not CC BY 4.0"):
        gs.openrn_sections(_bits_chapter("http://creativecommons.org/licenses/by-nc/4.0/"), gs.OPENRN_BOOKS[0])


def test_openrn_book_ranges_and_titles():
    assert re.match(gs.OPENRN_BOOKS[0].chapter_pattern, "11.16") and not re.match(gs.OPENRN_BOOKS[0].chapter_pattern, "12.2")
    assert not re.match(gs.OPENRN_BOOKS[0].chapter_pattern, "2.3")
    assert re.match(gs.OPENRN_BOOKS[1].chapter_pattern, "7.4") and not re.match(gs.OPENRN_BOOKS[1].chapter_pattern, "7.5")
    assert gs.tidy_title("ECG PATTERNS AND DYSRHYTHMIAS") == "ECG Patterns and Dysrhythmias"
    assert gs.tidy_title("COPD") == "COPD"


def test_excluded_openrn_subchapters_are_skipped_by_number_or_title():
    book = gs.OPENRN_BOOKS[0]
    assert {n for n, _ in book.excluded} == {"4.3", "6.8", "8.10", "8.12", "8.13", "10.5", "10.7", "10.8", "11.12", "11.14"}
    by_number = gs.Book(**{**book.__dict__, "excluded": (("5.8", "Something else"),)})
    by_title = gs.Book(**{**book.__dict__, "excluded": (("9.9", "Heart Failure"),)})
    assert gs.openrn_sections(_bits_chapter(), by_number) == []
    assert gs.openrn_sections(_bits_chapter(), by_title) == []
    assert gs.openrn_sections(_bits_chapter(), book)


def test_litarch_path_comes_from_the_file_list():
    class Lister:
        def get(self, url):
            assert url.endswith("/file_list.csv")
            return ("File,Title,Publisher,Publication Year,Accession ID,Last Updated (YYYY-MM-DD HH:MM:SS)\n"
                    "b9/2a/openrnha_NBK613078.tar.gz,Health Alterations,Chippewa Valley Technical College,2024,"
                    "NBK613078,2026-11-01 04:35:22\n")
    assert gs.litarch_path(Lister(), "NBK613078") == "b9/2a/openrnha_NBK613078.tar.gz"
    with pytest.raises(ValueError):
        gs.litarch_path(Lister(), "NBK1")


def _general_doc(source="litfl", doc_id="LITFL_atrial_flutter", **overrides):
    md = gs.clean(gs.html_to_markdown(gs.extract_main_html(PAGE)))
    src = gs.SOURCES[source]
    doc = gs.make_document(src, doc_id=doc_id, number="LITFL" if source == "litfl" else "HA 5.4",
                           title="Atrial Flutter", section="ECGs", url="https://litfl.com/atrial-flutter-ecg-library/",
                           attribution=gs.litfl_attribution("Atrial Flutter", "Ed Burns", "https://litfl.com/x/"),
                           markdown=md, fetched_at=FETCHED)
    doc.update(overrides)
    return doc


def _write_general(root, doc):
    gs.write_document(root / doc["source"], doc)


def _cmg(tmp_path):
    from tests.web_corpus.test_build import _doc, _write

    _write(tmp_path / "cmg", _doc(content_markdown="# Arrhythmia\n\n## Recognition\n\nAtrial flutter shows saw-tooth "
                                  "flutter waves at about 300 per minute and is managed per the cardiac guideline.\n"))
    return tmp_path / "cmg"


@pytest.fixture()
def mixed(tmp_path):
    root = tmp_path / "general"
    _write_general(root, _general_doc())
    _write_general(root, _general_doc("openrn", "OPENRN_HA_heart_failure", licence="CC BY 4.0", title="Heart Failure",
                                      section="Pathophysiology"))
    return _cmg(tmp_path), root


def test_general_references_build_as_their_own_kind_with_their_own_licence(mixed):
    cmg, root = mixed
    corpus = corpus_build.build(cmg, built_at=FETCHED, general_dir=root)
    general = [d for d in corpus.documents if d.source_type == "general_reference"]
    assert {(d.kind, d.general_source, d.licence) for d in general} == {
        ("ref", "litfl", "CC BY-NC-SA 4.0"), ("ref", "openrn", "CC BY 4.0")}
    chunks = [c for c in corpus.chunks if c.document_id == "LITFL_atrial_flutter"]
    assert chunks and all(c.views == set(corpus_build.VIEWS) and c.licence == "CC BY-NC-SA 4.0" for c in chunks)
    assert all(c.embed_text.startswith("[LITFL ECG Library: Atrial Flutter]") for c in chunks)

    db = sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys = ON")
    for migration in MIGRATIONS:
        db.executescript(migration.read_text(encoding="utf-8"))
    db.executescript(corpus_build.to_sql(corpus))
    assert db.execute("SELECT kind, source_type, licence FROM corpus_documents WHERE id = 'LITFL_atrial_flutter'").fetchone() == (
        "ref", "general_reference", "CC BY-NC-SA 4.0")
    assert db.execute("SELECT DISTINCT licence FROM corpus_chunks WHERE document_id = 'LITFL_atrial_flutter'").fetchall() == [
        ("CC BY-NC-SA 4.0",)]

    without = corpus_build.build(cmg, built_at=FETCHED, general_dir=root, exclude_sources=frozenset({"litfl"}))
    db.executescript(corpus_build.to_sql(without))
    assert db.execute("SELECT COUNT(*) FROM corpus_documents WHERE id LIKE 'LITFL%'").fetchone() == (0,)
    assert db.execute("SELECT COUNT(*) FROM corpus_chunks WHERE document_id LIKE 'LITFL%' AND retired_at IS NULL").fetchone() == (0,)
    assert db.execute("SELECT COUNT(*) FROM corpus_documents WHERE id LIKE 'OPENRN%'").fetchone() == (1,)


def test_d1_rejects_a_guideline_kind_labelled_general():
    db = sqlite3.connect(":memory:")
    for migration in MIGRATIONS:
        db.executescript(migration.read_text(encoding="utf-8"))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO corpus_documents VALUES ('x','actas','cmg','1','t','s','all',NULL,'c','general_reference','l','a','u','v')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO corpus_documents VALUES ('x','actas','ref','1','t','s','all',NULL,'c','guideline','l','a','u','v')")


@pytest.mark.parametrize("bad", [{"licence": "CC BY-NC-ND 4.0"}, {"source_type": "guideline"}, {"source": "openstax"}])
def test_build_rejects_unapproved_or_mislabelled_general_documents(tmp_path, bad):
    root = tmp_path / "general"
    doc = {**_general_doc(), **bad}
    (root / "litfl").mkdir(parents=True)
    (root / "litfl" / "x.json").write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(corpus_build.CorpusBuildError):
        corpus_build.build(_cmg(tmp_path), general_dir=root)


def test_build_rejects_unknown_source_folders(tmp_path):
    (tmp_path / "general" / "openstax").mkdir(parents=True)
    with pytest.raises(corpus_build.CorpusBuildError):
        corpus_build.build(_cmg(tmp_path), general_dir=tmp_path / "general")


class FakeGemini:
    def __init__(self, conflict=False, out_of_scope=False, qtype="recall"):
        self.calls = []
        self.conflict, self.out_of_scope, self.qtype = conflict, out_of_scope, qtype

    def __call__(self, url, body, api_key):
        self.calls.append(body)
        system = body["systemInstruction"]["parts"][0]["text"]
        if system == qb.PROMPTS["conflictSystem"]:
            payload = {"conflict": self.conflict, "out_of_scope": self.out_of_scope, "reason": "checked",
                       "cmg_quote": "flutter waves at about 300" if self.conflict else ""}
        else:
            n = len(self.calls)
            payload = {"question_text": f"What ECG features define atrial flutter, case {n}?", "question_type": self.qtype,
                       "source_citation": "", "category": "Cardiac", "source_index": 1}
        return {"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}],
                "usageMetadata": {"promptTokenCount": 900, "candidatesTokenCount": 80, "thoughtsTokenCount": 0}}


def _run(tmp_path, mixed, fake):
    cmg, root = mixed
    corpus = corpus_build.build(cmg, built_at=FETCHED, general_dir=root)
    tasks = qb.plan(corpus, "general")
    assert tasks and all(t.general and t.gen_view == "ap" and "hard" not in t.difficulties for t in tasks)
    runner = qb.Runner(corpus, tmp_path, "key", fake, max_usd=100)
    runner.run(tasks, workers=1, progress=lambda _: None)
    return corpus, qb.load_raw(tmp_path / "raw.jsonl")


def test_general_questions_use_their_own_prompt_and_are_checked_against_the_cmgs(tmp_path, mixed):
    fake = FakeGemini()
    corpus, records = _run(tmp_path, mixed, fake)
    gen = [c for c in fake.calls if c["systemInstruction"]["parts"][0]["text"] == qb.PROMPTS["generalGenerationSystem"]]
    checks = [c for c in fake.calls if c["systemInstruction"]["parts"][0]["text"] == qb.PROMPTS["conflictSystem"]]
    assert len(gen) == len(checks) == len(records)
    assert "[Source 1: general_reference]" in gen[0]["contents"][0]["parts"][0]["text"]
    assert "Atrial flutter shows saw-tooth" in checks[0]["contents"][0]["parts"][0]["text"]
    assert all(r["prompt_version"] == qb.PROMPTS["generalPromptVersion"] and r["check"]["conflict"] is False for r in records)

    questions, stats = qb.select_questions(corpus, records)
    assert questions and stats["general_conflicts"] == 0
    flutter = next(q for q in questions if q["document_id"] == "LITFL_atrial_flutter")
    assert flutter["source_citation"] == "LITFL ECG Library: Atrial Flutter"
    assert flutter["licence"] == "CC BY-NC-SA 4.0" and "LITFL ECG Library" in flutter["attribution"]
    assert flutter["category"] == "ECGs" and all(flutter["vis"].values())
    openrn = next(q for q in questions if q["document_id"] == "OPENRN_HA_heart_failure")
    assert openrn["source_citation"] == "Open RN Health Alterations 5.4: Heart Failure"

    db = sqlite3.connect(":memory:")
    for migration in MIGRATIONS:
        db.executescript(migration.read_text(encoding="utf-8"))
    db.executescript(corpus_build.to_sql(corpus))
    db.executescript(qb.to_sql(questions))
    assert db.execute("SELECT DISTINCT source_type FROM question_bank").fetchall() == [("general_reference",)]
    assert {r[0] for r in db.execute("SELECT licence FROM question_bank")} == {"CC BY 4.0", "CC BY-NC-SA 4.0"}


@pytest.mark.parametrize("fake, reason", [
    (FakeGemini(conflict=True), "general_conflicts"),
    (FakeGemini(out_of_scope=True), "general_out_of_scope"),
    (FakeGemini(qtype="drug_dose"), "general_out_of_scope"),
])
def test_conflicting_or_out_of_scope_general_questions_are_dropped(tmp_path, mixed, fake, reason):
    corpus, records = _run(tmp_path, mixed, fake)
    questions, stats = qb.select_questions(corpus, records)
    assert questions == [] and stats[reason] == len(records)
    path = tmp_path / "dropped.csv"
    qb.write_dropped(path, stats["dropped"])
    assert reason in path.read_text(encoding="utf-8")


def test_unchecked_general_questions_are_dropped(tmp_path, mixed):
    corpus, records = _run(tmp_path, mixed, FakeGemini())
    for r in records:
        r.pop("check")
    questions, stats = qb.select_questions(corpus, records)
    assert questions == [] and stats["general_unchecked"] == len(records)


def test_estimate_counts_the_conflict_check(mixed):
    cmg, root = mixed
    corpus = corpus_build.build(cmg, built_at=FETCHED, general_dir=root)
    general = qb.plan(corpus, "general")
    calls = sum(len(t.difficulties) for t in general)
    assert qb.estimate_cost(general) > calls * (qb.EST_INPUT_TOKENS * 1.5 + qb.EST_OUTPUT_TOKENS * 7.5) / 1_000_000


def test_device_criteria_and_literature_reviews_are_dropped():
    md = "## ECG features\n\nPacing spikes precede the QRS.\n\n## Criteria for Pacemaker Insertion\n\nClass I indications.\n\n## Deep Dive into the literature of aVR\n\n95% specific in one study.\n"
    out = gs.clean(md)
    assert "Pacing spikes" in out and "Class I" not in out and "95% specific" not in out


def test_spend_cap_counts_only_this_run(tmp_path, mixed):
    cmg, root = mixed
    corpus = corpus_build.build(cmg, built_at=FETCHED, general_dir=root)
    (tmp_path / "raw.jsonl").write_text(json.dumps({"ok": False, "cost_usd": 50.0, "chunk_id": "x", "difficulty": "easy"}) + "\n")
    fake = FakeGemini()
    runner = qb.Runner(corpus, tmp_path, "key", fake, max_usd=1)
    runner.run(qb.plan(corpus, "general"), workers=1, progress=lambda _: None)
    assert fake.calls and runner.spent < 1 and runner.spent_before == 50.0


def test_per_chunk_limit_spreads_difficulties_across_general_chunks(mixed):
    cmg, root = mixed
    corpus = corpus_build.build(cmg, built_at=FETCHED, general_dir=root)
    full = qb.plan(corpus, "general")
    one = qb.plan(corpus, "general", per_chunk=1)
    assert len(one) == len(full) and all(len(t.difficulties) == 1 for t in one)
    assert all(t.difficulties[0] in f.difficulties for t, f in zip(one, full))
    assert qb.plan(corpus, "guidelines", per_chunk=1) == qb.plan(corpus, "guidelines")
