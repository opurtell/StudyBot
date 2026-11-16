import json

from web_corpus import answers

TEXT = (
    "#### Hypoglycaemia\n\n"
    "- Hypoglycaemia is a BGL below 4 mmol/L.\n"
    "- Give oral glucose 15 g if able to swallow.\n"
    " Volume in mL  1600  500  240 \n"
    "---\n"
)


def test_segments_are_verbatim_lines_without_blank_or_symbol_only_lines():
    spans = answers.segments(TEXT)
    assert [TEXT[a:b] for a, b in spans] == [
        "#### Hypoglycaemia",
        "- Hypoglycaemia is a BGL below 4 mmol/L.",
        "- Give oral glucose 15 g if able to swallow.",
        "Volume in mL  1600  500  240",
    ]


def test_long_lines_split_into_sentences():
    para = "First sentence about airway management in adults. " * 4 + "Then (in children) use a smaller mask. Finally recheck."
    spans = answers.segments(para)
    parts = [para[a:b] for a, b in spans]
    assert len(parts) == 6
    assert parts[4] == "Then (in children) use a smaller mask."
    assert all(p in para for p in parts)


def test_parse_lines_keeps_valid_numbers_only():
    assert answers.parse_lines('{"lines": [3, 1, 3, 9, true, "2"]}', 4) == [1, 3]
    assert answers.parse_lines('```json\n{"lines": []}\n```', 4) == []
    assert answers.parse_lines("no json here", 4) is None


def test_quotes_merge_adjacent_lines_and_refuse_broad_selections():
    spans = answers.segments(TEXT)
    assert answers.quotes_for(TEXT, spans, [2, 3]) == [
        "- Hypoglycaemia is a BGL below 4 mmol/L.\n- Give oral glucose 15 g if able to swallow."
    ]
    assert answers.quotes_for(TEXT, spans, [2, 4]) == ["- Hypoglycaemia is a BGL below 4 mmol/L.", "Volume in mL  1600  500  240"]
    assert answers.quotes_for(TEXT, spans, [1, 2, 3, 4]) == []


def test_locate_one_reports_status():
    q = {"id": "q1", "question_text": "What BGL defines hypoglycaemia?", "source_text": TEXT}
    prompts = []

    def fake(system, user):
        prompts.append(user)
        return '{"lines": [2]}'

    record = answers.locate_one(fake, q)
    assert record == {"id": "q1", "lines": [2], "quotes": ["- Hypoglycaemia is a BGL below 4 mmol/L."], "status": "ok"}
    assert "[2] - Hypoglycaemia is a BGL below 4 mmol/L." in prompts[0]
    assert answers.locate_one(lambda s, u: "garbage", q)["status"] == "unreadable"
    assert answers.locate_one(lambda s, u: '{"lines": []}', q)["status"] == "no_answer"
    assert answers.locate_one(lambda s, u: '{"lines": [1, 2]}', q)["lines"] == [2]
    assert answers.locate_one(lambda s, u: '{"lines": [2, 3, 4]}', q)["status"] == "too_broad"


def test_run_locate_resumes_and_export_writes_guarded_sql(tmp_path):
    (tmp_path / "questions.json").write_text(json.dumps([{"results": [
        {"id": "q1", "question_text": "What BGL?", "source_text": TEXT},
        {"id": "q2", "question_text": "What's the dose?", "source_text": TEXT},
    ], "success": True}]))
    questions = answers.load_questions(tmp_path / "questions.json")
    calls = []

    def fake(system, user):
        calls.append(user)
        return '{"lines": [3]}' if len(calls) == 1 else "oops"

    answers.run_locate(questions, tmp_path, fake)
    answers.run_locate(questions, tmp_path, lambda s, u: '{"lines": [3]}')
    records = answers.load_records(tmp_path / "answers.jsonl")
    assert {k: v["status"] for k, v in records.items()} == {"q1": "ok", "q2": "ok"}
    assert len(calls) == 2

    assert answers.main(["export", "--out", str(tmp_path)]) == 0
    sql = (tmp_path / "answers.sql").read_text()
    assert sql.count("UPDATE question_bank SET answer_quotes = ") == 2
    assert "WHERE id = 'q1' AND instr(source_text, '- Give oral glucose 15 g if able to swallow.') > 0;" in sql
    assert (tmp_path / "review-sample.csv").exists()
