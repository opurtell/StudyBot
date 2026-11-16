import csv
import json

from web_corpus import quality

SOURCE = "- Hypoglycaemia is a BGL below 4 mmol/L.\n- Give oral glucose 15 g if able to swallow.\n"

GOOD = {"relevance": 5, "asks": 1, "scenario": False, "scenario_needed": True, "list_recital": False,
        "stands_alone": True, "answerable": True, "trivia": "none", "reason": "No issues"}


def q(qid, text, doc="CMG_10_Diabetic_Emergencies", h=None):
    return {"id": qid, "document_id": doc, "document": "Doc", "chunk_id": "c1", "question_type": "recall",
            "difficulty": "easy", "question_text": text, "content_hash": h or qid, "source_text": SOURCE}


def rec(qid, **overrides):
    return {"id": qid, "status": "ok", "version": "v", **GOOD, **overrides}


def test_source_and_cap_mapping():
    assert quality.source_of("CMG_CSM.C07_Mechanical") == "csm"
    assert quality.source_of("ACTAS_Critical_Care_Reference_Cards") == "csm"
    assert quality.source_of("CMG_45_Palliative_Care_and_VAD") == "cmg"
    assert quality.source_of("MED_03_Adrenaline") == "med"
    assert quality.source_of("STATPEARLS_abc") == "StatPearls"
    assert quality.source_of("OPENRN_HA_5_x") == "Open RN"
    assert quality.cap_of("CMG_CSM.P06_Supine") == ("Stretcher positioning skills", 6)
    assert quality.cap_of("CMG_45_Palliative_Care_and_VAD") == ("Palliative Care and VAD", 20)
    assert quality.cap_of("ACTAS_Critical_Care_Reference_Cards") is None


def test_australianise_swaps_drug_names_and_spellings_only():
    text, changes = quality.australianise(
        "How does acetaminophen and Epinephrine affect hemodynamic ischemic edema, oedema and labored breathing "
        "in a categorized pediatric patient with systemic anemia and seizures of normal size?")
    assert text == ("How does paracetamol and Adrenaline affect haemodynamic ischaemic oedema, oedema and laboured "
                    "breathing in a categorised paediatric patient with systemic anaemia and seizures of normal size?")
    assert len(changes) == 9
    assert quality.australianise("Hemiplegic migraine and pandemic systemic disease") == (
        "Hemiplegic migraine and pandemic systemic disease", [])


def test_parse_scores_validates_and_coerces():
    assert quality.parse_scores(json.dumps(GOOD)) == GOOD
    loose = quality.parse_scores('```json\n{"relevance": "2", "asks": 3, "stands_alone": "false", "trivia": "Device"}\n```')
    assert loose["relevance"] == 2 and loose["asks"] == 3 and loose["stands_alone"] is False
    assert loose["trivia"] == "device" and loose["answerable"] is True
    assert quality.parse_scores('{"relevance": 9, "asks": 1}') is None
    assert quality.parse_scores("nonsense") is None


def test_rubric_reasons_follow_thresholds():
    assert quality.rubric_reasons(rec("a")) == []
    assert quality.rubric_reasons(rec("a", relevance=2)) == ["low relevance (2/5)"]
    assert quality.rubric_reasons(rec("a", asks=3)) == []
    assert quality.rubric_reasons(rec("a", asks=4)) == ["4 separate asks"]
    assert quality.rubric_reasons(rec("a", scenario=True, scenario_needed=False, list_recital=True)) == []
    assert quality.rubric_reasons(rec("a", scenario=True, scenario_needed=False)) == []
    assert quality.rubric_reasons(rec("a", trivia="device", relevance=3)) == ["trivia: device"]
    assert quality.rubric_reasons(rec("a", trivia="device", relevance=4)) == []
    assert quality.rubric_reasons(rec("a", stands_alone=False, answerable=False)) == [
        "does not stand alone", "source does not state the answer"]


CORPULS = ["Where is the strap stored?", "Which stamp size fits adults?", "When is the device paused?",
           "What compression depth applies?", "How is the battery charged?", "Who checks the backplate daily?",
           "Why might alarms sound?", "What rate suits infants?", "Which colour light shows faults?"]


def test_decide_retires_examples_duplicates_and_caps():
    questions = [
        q("ex", "In Example 3, which leads show inverted U waves?", doc="LITFL_u_wave"),
        q("d1", "According to the ACTAS Diabetic Emergencies guideline (CMG 10), what BGL defines hypoglycaemia?"),
        q("d2", "What BGL defines hypoglycaemia under the guideline?"),
    ] + [q(f"c{i}", w, doc="CMG_CSM.C07_Corpuls") for i, w in enumerate(CORPULS)]
    records = {x["id"]: rec(x["id"]) for x in questions}
    records["d1"]["relevance"] = 4
    records["c8"]["relevance"] = 1
    decisions = quality.decide(questions, records)
    assert decisions["ex"]["reasons"] == ["refers to an unseen example"]
    assert decisions["d1"]["retire"] and decisions["d1"]["reasons"][0].startswith("near duplicate of d2")
    assert not decisions["d2"]["retire"]
    assert decisions["c8"]["reasons"] == ["low relevance (1/5)"]
    capped = [f"c{i}" for i in range(8) if decisions[f"c{i}"]["retire"]]
    assert capped == ["c6", "c7"]
    assert decisions["c6"]["reasons"] == ["over the cap of 6 for Corpuls cpr"]


def test_plan_fixes_skips_retired_and_hash_collisions():
    questions = [q("a", "What is myxedema coma?"), q("b", "Acetaminophen dose?"),
                 q("c", "Paracetamol dose?", h=quality.content_hash("Paracetamol dose?")), q("d", "Hemoptysis?")]
    decisions = {x["id"]: {"retire": x["id"] == "d", "reasons": [], "score": 0} for x in questions}
    fixes = quality.plan_fixes(questions, decisions)
    assert set(fixes) == {"a"}
    assert fixes["a"]["text"] == "What is myxoedema coma?"
    assert fixes["a"]["hash"] == quality.content_hash("What is myxoedema coma?")


def test_calibration_reports_rates_on_a_split():
    labels = {f"w{i}": {"label": "weak"} for i in range(30)} | {f"s{i}": {"label": "strong"} for i in range(30)}
    records = {k: rec(k, relevance=2 if k.startswith("w") and k != "w1" else 5) for k in labels}
    records["s2"]["asks"] = 4
    result = quality.calibration(labels, records, {}, "all")
    assert result["scored"] == 60
    assert result["weak_caught"] == round(29 / 30, 3)
    assert result["strong_flagged"] == round(1 / 30, 3)
    assert [r["id"] for r in result["missed_weak"]] == ["w1"]
    tune = quality.calibration(labels, records, {}, "tune")
    hold = quality.calibration(labels, records, {}, "holdout")
    assert tune["scored"] + hold["scored"] == 60 and hold["scored"] > 0


def test_score_resumes_and_export_writes_sql_review_and_floor(tmp_path):
    questions = [q(f"q{i}", f"Distinct question {i} about subject {i * 13} and item {i * 31}?") for i in range(10)]
    questions.append(q("us", "Which receptor does norepinephrine bind on a myocyte?"))
    (tmp_path / "questions.json").write_text(json.dumps([{"results": questions, "success": True}]))
    version = quality.prompt_version(quality.DEFAULT_MODEL)
    calls = []

    def fake(system, user):
        calls.append(user)
        if len(calls) == 3:
            return "garbage"
        relevance = 1 if "Distinct question 0 " in user else 5
        return json.dumps({**GOOD, "relevance": relevance})

    loaded = quality.load_questions(tmp_path / "questions.json")
    quality.run_score(loaded, tmp_path, fake, version)
    quality.run_score(loaded, tmp_path, fake, version)
    records = quality.load_records(tmp_path / "scores.jsonl", version)
    assert len(records) == 11 and all(r["status"] == "ok" for r in records.values())
    assert len(calls) == 12

    assert quality.main(["export", "--out", str(tmp_path), "--now-ms", "123"]) == 0
    sql = (tmp_path / "quality.sql").read_text()
    assert ("UPDATE question_bank SET status = 'retired', status_reason = 'quality_review', updated_at = 123 "
            "WHERE id = 'q0' AND status = 'active';") in sql
    assert "question_text = 'Which receptor does noradrenaline bind on a myocyte?'" in sql
    assert "WHERE id = 'us' AND question_text = 'Which receptor does norepinephrine bind on a myocyte?';" in sql
    with (tmp_path / "review.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    assert [r["action"] for r in rows][:2] == ["retire", "fix wording"]

    for r in rows:
        r["rescue"] = "Y" if r["id"] in {"q0", "us"} else ""
    with (tmp_path / "reviewed.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=quality.REVIEW_HEADER)
        writer.writeheader()
        writer.writerows(rows)
    assert quality.main(["export", "--out", str(tmp_path), "--rescue", str(tmp_path / "reviewed.csv")]) == 0
    assert (tmp_path / "quality.sql").read_text() == ""

    with (tmp_path / "scores.jsonl").open("a") as fh:
        for i in range(1, 5):
            fh.write(json.dumps(rec(f"q{i}", relevance=1, version=version)) + "\n")
    assert quality.main(["export", "--out", str(tmp_path)]) == 2
    assert not (tmp_path / "quality.sql").exists()
    assert "blocked" in json.loads((tmp_path / "summary.json").read_text())
