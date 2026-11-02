import csv
import json
import sqlite3
from unittest.mock import patch

import pytest

from paths import APP_ROOT
from quiz.agent import DIFFICULTY_INSTRUCTIONS, EVALUATION_SCHEMA, EVALUATION_SYSTEM_PROMPT, build_generation_prompt
from services.registry import get_service
from web_corpus import build as corpus_build
from web_corpus import questions as qb

MIGRATIONS = sorted((APP_ROOT / "web" / "migrations").glob("*.sql"))


@pytest.fixture(scope="module")
def corpus():
    return corpus_build.build(built_at="2026-11-01T00:00:00+00:00")


def test_web_prompts_match_the_python_reference():
    with patch("services.active.active_service", return_value=get_service("actas")):
        assert qb.PROMPTS["generationSystem"]["ap"] == build_generation_prompt(frozenset({"AP"}))
        assert qb.PROMPTS["generationSystem"]["icp"] == build_generation_prompt(frozenset({"AP", "ICP"}))
    assert qb.PROMPTS["evaluationSystem"] == EVALUATION_SYSTEM_PROMPT
    assert qb.PROMPTS["evaluationSchema"] == EVALUATION_SCHEMA
    diffs = qb.PROMPTS["difficultyInstructions"]
    assert diffs["easy"] == DIFFICULTY_INSTRUCTIONS["easy"]
    assert diffs["medium"] == DIFFICULTY_INSTRUCTIONS["medium"]
    assert diffs["hard"].startswith(DIFFICULTY_INSTRUCTIONS["hard"])
    assert "e.g. ACTAS CMG 14.1" in qb.PROMPTS["generationSystem"]["ap"]


def test_hash_matches_the_worker():
    assert qb.content_hash("What BGL defines hypoglycaemia in CMG 10?") == (
        "f81b5caa1831db5580ecbf002a7e26a629b5da27b8f0e6b4953775a487c92a1e"
    )


def test_plan_uses_the_narrowest_scope_and_skips_tiny_chunks(corpus):
    tasks = qb.plan(corpus)
    for task in tasks:
        assert task.gen_view == next(v for v in qb.VIEW_ORDER if v in task.chunk.views)
        assert len(task.chunk.text) >= qb.MIN_CHARS
    icp_only = [t for t in tasks if "ap" not in t.chunk.views and "ap_pacer" not in t.chunk.views]
    assert icp_only and all(t.gen_view.startswith("icp") for t in icp_only)
    assert all("Intensive Care Paramedic (ICP)" not in qb.system_prompt(t.gen_view) for t in icp_only)


@pytest.mark.parametrize(
    "question, expected",
    [
        ("What is the adult dose of IM adrenaline in anaphylaxis?", {"ap", "ap_pacer", "icp", "icp_pacer"}),
        ("When is amiodarone given in VF arrest?", {"icp", "icp_pacer"}),
        ("When should topical lignocaine be applied?", {"ap", "ap_pacer", "icp", "icp_pacer"}),
        ("What rate is used for transcutaneous pacing?", {"icp", "icp_pacer"}),
        ("Which drugs are used for RSI?", {"icp", "icp_pacer"}),
    ],
)
def test_ap_users_never_see_questions_that_name_icp_care(question, expected):
    vis = qb.visibility("ap", set(qb.VIEW_ORDER), question)
    assert {v for v, shown in vis.items() if shown} == expected


def test_icp_questions_stay_icp_even_from_shared_chunks():
    vis = qb.visibility("icp", set(qb.VIEW_ORDER), "What is the dose of oxygen?")
    assert {v for v, shown in vis.items() if shown} == {"icp", "icp_pacer"}


def _reply(question, qtype="recall"):
    return {
        "candidates": [{"content": {"parts": [{"text": json.dumps({
            "question_text": question, "question_type": qtype, "source_citation": "ACTAS CMG 10",
            "category": "Medical", "source_index": 1,
        })}]}}],
        "usageMetadata": {"promptTokenCount": 800, "candidatesTokenCount": 100, "thoughtsTokenCount": 200},
    }


class FakeGemini:
    def __init__(self, replies=None):
        self.calls = []
        self.replies = replies

    def __call__(self, url, body, api_key):
        self.calls.append(body)
        user = body["contents"][0]["parts"][0]["text"]
        if self.replies:
            return self.replies.pop(0)
        difficulty = user.split("Difficulty: ")[1].split("\n")[0]
        return _reply(f"Question {len(self.calls)} at {difficulty} about {user[40:80]!r}?")


def test_generate_is_resumable_and_passes_earlier_questions(tmp_path, corpus):
    tasks = qb.plan(corpus)[:3]
    fake = FakeGemini()
    runner = qb.Runner(corpus, tmp_path, "key", fake, max_usd=100)
    runner.run(tasks, workers=2, progress=lambda _: None)
    expected_calls = sum(len(t.difficulties) for t in tasks)
    assert len(fake.calls) == expected_calls
    assert fake.calls[0]["generationConfig"]["responseJsonSchema"] == qb.PROMPTS["generationSchema"]
    full = next(t for t in tasks if len(t.difficulties) == 3)
    users = [c["contents"][0]["parts"][0]["text"] for c in fake.calls if full.chunk.embed_text in c["contents"][0]["parts"][0]["text"]]
    assert "Previously asked questions" not in users[0]
    assert "Previously asked questions" in users[-1]

    again = FakeGemini()
    qb.Runner(corpus, tmp_path, "key", again, max_usd=100).run(tasks, workers=2, progress=lambda _: None)
    assert again.calls == []
    records = qb.load_raw(tmp_path / "raw.jsonl")
    assert len(records) == expected_calls and all(r["ok"] for r in records)
    assert records[0]["cost_usd"] == pytest.approx((800 * 1.5 + 300 * 7.5) / 1e6)


def test_unparseable_replies_are_retried_then_recorded_as_failures(tmp_path, corpus):
    task = qb.Task(qb.plan(corpus)[0].chunk, "ap", ("easy",))
    bad = {"candidates": [{"content": {"parts": [{"text": "Sure! Here's a question."}]}}], "usageMetadata": {}}
    fake = FakeGemini([bad, dict(bad)])
    qb.Runner(corpus, tmp_path, "key", fake, max_usd=100).run([task], workers=1, progress=lambda _: None)
    assert len(fake.calls) == 2
    [record] = qb.load_raw(tmp_path / "raw.jsonl")
    assert record["ok"] is False and record["error"].startswith("unparseable")


def test_spend_cap_stops_generation(tmp_path, corpus):
    tasks = qb.plan(corpus)[:5]
    fake = FakeGemini()
    qb.Runner(corpus, tmp_path, "key", fake, max_usd=0.0000001).run(tasks, workers=1, progress=lambda _: None)
    assert len(fake.calls) == 1


def _db():
    db = sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys = ON")
    for migration in MIGRATIONS:
        db.executescript(migration.read_text(encoding="utf-8"))
    return db


def test_export_dedupes_drops_stale_rows_and_loads_into_d1_schema(tmp_path, corpus):
    tasks = [t for t in qb.plan(corpus) if len(t.difficulties) == 3][:2]
    first, second = tasks[0].chunk, tasks[1].chunk
    base = {"model_id": qb.MODEL_ID, "prompt_version": "web-1", "corpus_version": corpus.version, "ok": True,
            "question_type": "recall", "source_citation": "", "category": "", "cost_usd": 0.001}
    records = [
        {**base, "chunk_id": first.id, "document_id": first.document_id, "source_text": first.embed_text,
         "difficulty": "easy", "gen_view": tasks[0].gen_view, "question_text": "What is the patient's first priority?"},
        {**base, "chunk_id": first.id, "document_id": first.document_id, "source_text": first.embed_text,
         "difficulty": "medium", "gen_view": tasks[0].gen_view, "question_text": "What is the patient's first priority??"},
        {**base, "chunk_id": first.id, "document_id": first.document_id, "source_text": first.embed_text,
         "difficulty": "hard", "gen_view": tasks[0].gen_view, "question_text": "What is the patient's very first priority?"},
        {**base, "chunk_id": second.id, "document_id": second.document_id, "source_text": "old text",
         "difficulty": "easy", "gen_view": tasks[1].gen_view, "question_text": "A stale question about something?"},
        {**base, "chunk_id": second.id, "document_id": second.document_id, "source_text": second.embed_text,
         "difficulty": "easy", "gen_view": tasks[1].gen_view, "question_text": "Which adenosine dose is used?"},
        {**base, "ok": False, "chunk_id": second.id, "difficulty": "hard", "error": "unparseable"},
    ]
    questions, stats = qb.select_questions(corpus, records)
    assert [q["question_text"] for q in questions] == ["What is the patient's first priority?", "Which adenosine dose is used?"]
    assert stats == {"stale": 1, "unplanned": 0, "exact_duplicates": 1, "near_duplicates": 1, "ap_restricted": int("ap" in second.views)}
    assert questions[0]["source_citation"].startswith("ACTAS ")
    assert questions[0]["id"] == questions[0]["content_hash"][:16]

    db = _db()
    db.executescript(corpus_build.to_sql(corpus))
    db.executescript(qb.to_sql(questions))
    db.executescript(qb.to_sql(questions))
    rows = db.execute("SELECT id, status, origin, vis_ap, chunk_id FROM question_bank ORDER BY question_text").fetchall()
    assert [(r[1], r[2]) for r in rows] == [("active", "bank"), ("active", "bank")]
    assert rows[1][3] == 0

    db.execute("UPDATE corpus_chunks SET embed_text = 'changed' WHERE id = ?", (first.id,))
    db.execute("DELETE FROM question_bank")
    db.executescript(qb.to_sql(questions))
    assert db.execute("SELECT COUNT(*) FROM question_bank").fetchone() == (1,)

    path = tmp_path / "sample.csv"
    qb.write_sample(path, qb.review_sample(questions, 10))
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    assert len(rows) == 2 and rows[0]["accurate (Y/N)"] == ""


def test_generate_needs_explicit_confirmation(tmp_path, capsys):
    assert qb.main(["generate", "--out", str(tmp_path), "--limit", "2"], transport=FakeGemini()) == 1
    assert "--yes" in capsys.readouterr().out


def _chunk(chunk_id, text, views, heading="#### Management", doc="CMG_99_Test"):
    return corpus_build.Chunk(chunk_id, doc, 0, heading, text, f"[ACTAS CMG 99]\n{heading}\n{text}", set(views))


def test_icp_twins_of_ap_sections_get_one_question_on_the_icp_only_lines():
    shared = "\n".join(f"- Shared management step number {i} for both levels." for i in range(12))
    ap = _chunk("ap1", shared, {"ap", "ap_pacer", "icp", "icp_pacer"})
    icp = _chunk("icp1", shared + "\n- **ICP:** Consider adrenaline infusion if refractory.", {"icp", "icp_pacer"})
    lone = _chunk("icp2", "- **ICP:** RSI drug sequence step. " * 15, {"icp", "icp_pacer"}, heading="#### RSI")
    corpus = corpus_build.Corpus("v", "t", None, [], [ap, icp, lone])
    tasks = {t.chunk.id: t for t in qb.plan(corpus)}
    assert tasks["ap1"].difficulties == ("easy", "medium", "hard") and tasks["ap1"].focus == ()
    assert tasks["icp1"].difficulties == ("medium",)
    assert tasks["icp1"].focus == ("- **ICP:** Consider adrenaline infusion if refractory.",)
    assert tasks["icp2"].focus == ()
    prompt = qb.user_prompt(icp.embed_text, "medium", [], tasks["icp1"].focus)
    assert qb.PROMPTS["icpFocusInstruction"] in prompt and prompt.endswith("refractory.")


def test_icp_twins_with_trivial_differences_are_skipped():
    shared = "\n".join(f"- Shared management step number {i} for both levels." for i in range(12))
    ap = _chunk("ap1", shared, {"ap", "ap_pacer"})
    icp = _chunk("icp1", shared + "\n- ICP.", {"icp", "icp_pacer"})
    tasks = qb.plan(corpus_build.Corpus("v", "t", None, [], [ap, icp]))
    assert [t.chunk.id for t in tasks] == ["ap1"]


def test_icp_chunks_holding_every_ap_line_are_twins_even_when_much_longer():
    shared = "- LMA size: 2\n- Shock: 70 joules\n- Adrenaline (1:10,000): Dose: 0.13mg"
    extra = "\n".join(f"- **ICP:** Drug {i}: Dose: {i}mg; Volume: {i}ml with a long preparation note" for i in range(8))
    ap = _chunk("ap1", shared, {"ap", "ap_pacer"}, heading="2 Years - 13kg")
    icp = _chunk("icp1", shared + "\n" + extra, {"icp", "icp_pacer"}, heading="2 Years - 13kg")
    tasks = {t.chunk.id: t for t in qb.plan(corpus_build.Corpus("v", "t", None, [], [ap, icp]))}
    assert tasks["icp1"].difficulties == ("medium",)
    assert len(tasks["icp1"].focus) == 8 and all("ICP" in line for line in tasks["icp1"].focus)


def test_name_guidelines_adds_titles_to_bare_codes():
    titles = {("CMG", "35A"): "Poisoning and Overdose", ("MED", "3"): "Adrenaline",
              ("CSM", "A13"): "Laryngoscope and Bougie Railroad Technique (Endotracheal Intubation)",
              ("CMG", "22"): "Seizures"}
    assert qb.name_guidelines("According to ACTAS CMG 35A, what is first?", titles) == (
        "According to ACTAS CMG 35A (Poisoning and Overdose), what is first?")
    assert qb.name_guidelines("Per ACTAS MED 03, the dose", titles) == "Per ACTAS MED 03 (Adrenaline), the dose"
    assert qb.name_guidelines("Using CSM.A13, how deep?", titles) == (
        "Using CSM.A13 (Laryngoscope and Bougie Railroad Technique, Endotracheal Intubation), how deep?")
    assert qb.name_guidelines("ACTAS CMG 22 (Seizures) says", titles) == "ACTAS CMG 22 (Seizures) says"
    assert qb.name_guidelines("the Seizures guideline (CMG 22) says", titles) == "the Seizures guideline (CMG 22) says"
    assert qb.name_guidelines("Per CMG 14.1 the dose", titles) == "Per CMG 14.1 the dose"
    assert qb.name_guidelines("Per CMG 99, the dose", titles) == "Per CMG 99, the dose"
