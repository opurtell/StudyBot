import csv
import json

import pytest

from web_corpus import build as corpus_build
from web_corpus import scenarios as sc


@pytest.fixture(scope="module")
def corpus():
    return corpus_build.build(built_at="2026-11-24T00:00:00+00:00")


def _bp(corpus, cmg="16", view="ap", difficulty="medium"):
    return next(b for b in sc.plan(corpus) if b.document_id.startswith(f"CMG_{cmg}_") and b.view == view
                and b.difficulty == difficulty)


def _content_lines(pack, prefix="G"):
    return [l for l in pack.lines.values() if l.id.startswith(prefix) and not l.heading]


def _line_with(pack, needle, prefix="G"):
    return next(l.id for l in _content_lines(pack, prefix) if needle.lower() in l.text.lower())


def _scenario(stages):
    return {"title": "Chest pain at home", "dispatch": "58-year-old man, chest pain, Belconnen.", "stages": stages}


def _stage(cites, point="Treat as suspected ACS", critical=True, question="What is your working diagnosis?"):
    return {"findings": "Pale and sweaty, HR 96.", "question": question, "focus": "assessment",
            "rubric": [{"point": point, "critical": critical, "cites": cites},
                       {"point": "Perform a 12 lead ECG", "critical": False, "cites": cites}]}


def test_quotas_cover_every_cmg_once(corpus):
    quotas = sc.load_quotas()
    numbers = [q.cmg.upper() for q in quotas]
    cmgs = {d.number.upper() for d in corpus.documents if d.kind == "cmg"}
    assert len(numbers) == len(set(numbers))
    assert set(numbers) == cmgs


def test_plan_counts_follow_weights(corpus):
    bps = sc.plan(corpus)
    acs = [b for b in bps if b.document_id.startswith("CMG_16_") and b.view == "ap"]
    assert len(acs) == 9
    assert {b.difficulty for b in acs} == {"easy", "medium", "hard"}
    assert not [b for b in bps if b.document_id.startswith("CMG_3B_")]
    assert len({b.id for b in bps}) == len(bps)


def test_pilot_is_thirty_ap_plus_three_icp(corpus):
    pilot = sc.plan(corpus, pilot=True)
    assert len(pilot) == 33
    assert sum(b.icp for b in pilot) == 3


def test_stage_counts_and_links_follow_difficulty(corpus):
    for b in sc.plan(corpus):
        if b.difficulty == "easy":
            assert b.stages == 2 and not b.links and b.band_chunk_id is None
        elif b.difficulty == "medium":
            assert b.stages == 3 and len(b.links) + (b.band_chunk_id is not None) <= 1
        else:
            assert b.stages in (3, 4) and len(b.links) + (b.band_chunk_id is not None) <= 2


def test_icp_blueprints_prefer_icp_only_medicines(corpus):
    bp = next(b for b in sc.plan(corpus) if b.document_id.startswith("CMG_8_") and b.icp)
    assert bp.links and "Amiodarone" in bp.links[0]


def test_paediatric_blueprints_get_a_weight_band(corpus):
    bp = next(b for b in sc.plan(corpus) if b.document_id.startswith("CMG_44_") and b.difficulty == "medium")
    pack = sc.build_pack(corpus, bp)
    assert bp.band_chunk_id and any(l.startswith("R") for l in pack.lines)
    assert "Weight band" in pack.text


def test_pack_lines_are_verbatim_chunk_text(corpus):
    bp = _bp(corpus, difficulty="hard")
    pack = sc.build_pack(corpus, bp)
    chunks = {c.id: c for c in corpus.chunks}
    assert pack.documents["G"] == bp.document_id
    for line in pack.lines.values():
        assert line.text in chunks[line.chunk_id].text
        assert f"[{line.id}] {line.text}" in pack.text


def test_valid_scenario_resolves_to_verbatim_quotes(corpus):
    bp = _bp(corpus, difficulty="easy")
    pack = sc.build_pack(corpus, bp)
    ecg = _line_with(pack, "12 lead ECG")
    scenario, reasons = sc.resolve(bp, corpus, pack, _scenario([_stage([ecg]), _stage([ecg])]))
    assert reasons == []
    quote = scenario["stages"][0]["rubric"][0]["cites"][0]
    assert quote["quote"] == pack.lines[ecg].text and quote["chunk_id"] == pack.lines[ecg].chunk_id
    assert scenario["vis"]["ap"] and scenario["vis"]["ap_pacer"]
    assert scenario["sources"] == [{"chunk_id": pack.lines[ecg].chunk_id, "document_id": bp.document_id}]


def test_ap_scenario_is_visible_to_icps_when_its_lines_are_in_the_icp_view(corpus):
    bp = _bp(corpus, difficulty="easy")
    pack = sc.build_pack(corpus, bp)
    ecg = _line_with(pack, "12 lead ECG")
    scenario, _ = sc.resolve(bp, corpus, pack, _scenario([_stage([ecg]), _stage([ecg])]))
    assert scenario["vis"]["icp"] and scenario["vis"]["icp_pacer"]


@pytest.mark.parametrize("mutate, reason", [
    (lambda s, ids: s["stages"].pop(), "stage_count"),
    (lambda s, ids: s["stages"][0]["rubric"][0]["cites"].__setitem__(0, "G999"), "unknown_line"),
    (lambda s, ids: s["stages"][0]["rubric"][0]["cites"].__setitem__(0, ids["heading"]), "cites_heading"),
    (lambda s, ids: s["stages"][0]["rubric"][0].__setitem__("point", "Give 900 mg of something"), "number_not_in_source"),
    (lambda s, ids: [p.__setitem__("critical", False) for p in s["stages"][1]["rubric"]], "no_critical_point"),
    (lambda s, ids: s["stages"][0].__setitem__("question", "According to the guideline, what next?"), "according_to"),
    (lambda s, ids: s.__setitem__("dispatch", "Call for EMTs, give epinephrine"), "us_term"),
    (lambda s, ids: s["stages"][0]["rubric"][0].__setitem__("point", "Prepare amiodarone"), "out_of_scope"),
    (lambda s, ids: s["stages"][0].__setitem__("rubric", s["stages"][0]["rubric"][:1]), "point_count"),
])
def test_deterministic_checks_reject_bad_scenarios(corpus, mutate, reason):
    bp = _bp(corpus, difficulty="easy")
    pack = sc.build_pack(corpus, bp)
    ecg = _line_with(pack, "12 lead ECG")
    heading = next(l.id for l in pack.lines.values() if l.heading)
    raw = _scenario([_stage([ecg]), _stage([ecg])])
    mutate(raw, {"heading": heading})
    _, reasons = sc.resolve(bp, corpus, pack, raw)
    assert any(reason in r for r in reasons), reasons


def test_primary_must_be_cited_and_links_limited(corpus):
    bp = _bp(corpus, difficulty="medium")
    pack = sc.build_pack(corpus, bp)
    a_line = _content_lines(pack, "A")[0].id
    raw = _scenario([_stage([a_line]) for _ in range(3)])
    _, reasons = sc.resolve(bp, corpus, pack, raw)
    assert "primary_not_cited" in reasons


def test_numbers_must_appear_in_cited_lines(corpus):
    bp = _bp(corpus, difficulty="medium")
    pack = sc.build_pack(corpus, bp)
    dose = next(l for l in _content_lines(pack, "A") if any(ch.isdigit() for ch in l.text))
    ecg = _line_with(pack, "12 lead ECG")
    number = sc._numbers(dose.text).pop()
    good = _scenario([_stage([ecg]), _stage([ecg]), _stage([ecg, dose.id], point=f"Give {number}")])
    _, reasons = sc.resolve(bp, corpus, pack, good)
    assert not [r for r in reasons if "number_not_in_source" in r]
    assert sc._numbers("Perform a 12 lead ECG") == set()


def test_icp_scenario_must_cite_icp_only_lines(corpus):
    bp = next(b for b in sc.plan(corpus) if b.document_id.startswith("CMG_8_") and b.icp)
    pack = sc.build_pack(corpus, bp)
    ap_body = next(d for d in corpus.documents if d.id == bp.document_id).bodies["ap"]
    shared = next(l.id for l in _content_lines(pack) if l.text in ap_body)
    stages = [_stage([shared]) for _ in range(bp.stages)]
    _, reasons = sc.resolve(bp, corpus, pack, _scenario(stages))
    assert "no_icp_only_content" in reasons
    icp_line = next((l.id for l in _content_lines(pack) if l.text not in ap_body), None)
    assert icp_line
    stages[0]["rubric"][0]["cites"] = [icp_line]
    stages[0]["rubric"][0]["point"] = "Consider the ICP option"
    scenario, reasons = sc.resolve(bp, corpus, pack, _scenario(stages))
    assert "no_icp_only_content" not in reasons
    assert not scenario["vis"]["ap"] and scenario["vis"]["icp"]


def test_unreadable_and_schema_errors(corpus):
    bp = _bp(corpus, difficulty="easy")
    pack = sc.build_pack(corpus, bp)
    assert sc.resolve(bp, corpus, pack, None) == (None, ["unreadable"])
    assert sc.resolve(bp, corpus, pack, {"title": "x"})[1] == ["schema"]


def test_parse_check():
    good = '{"stages": [{"supported": true, "consistent": true, "complete": true, "in_scope": true, "reason": ""}]}'
    assert sc.parse_check(good, 1)["pass"] is True
    bad = good.replace('"complete": true', '"complete": false')
    assert sc.parse_check(bad, 1)["pass"] is False
    assert sc.parse_check(good, 2) is None
    assert sc.parse_check("nope", 1) is None


def _fake_writer(corpus):
    def complete(system, user, schema):
        bp_line = next(l for l in user.splitlines() if l.startswith("Stages: exactly"))
        stages = int(bp_line.split()[-1])
        ecg = next(l.split("]")[0][1:] for l in user.splitlines() if l.startswith("[G") and "12 lead ECG" in l
                   and not l.split("] ", 1)[1].startswith("#"))
        return json.dumps(_scenario([_stage([ecg]) for _ in range(stages)])), {}
    return complete


def _fake_checker(passing=True):
    def complete(system, user, schema):
        n = user.split("Source pack:")[0].count("\nStage ")
        st = {"supported": True, "consistent": True, "complete": passing, "in_scope": True,
              "reason": "" if passing else "misses aspirin"}
        return json.dumps({"stages": [st] * n}), {}
    return complete


def test_write_check_export_end_to_end(corpus, tmp_path):
    bps = [b for b in sc.plan(corpus, pilot=True) if b.document_id.startswith("CMG_16_")]
    out = tmp_path / "runs" / "t"
    counts = sc.run_write(corpus, bps, out, _fake_writer(corpus), "lmstudio:fake")
    assert counts == {"ok": 1, "dropped": 2} or sum(counts.values()) == 3
    again = sc.run_write(corpus, bps, out, _fake_writer(corpus), "lmstudio:fake")
    assert again == {}
    records = sc.load_raw(out / "raw.jsonl")
    assert records[bps[0].id]["model_id"] == "lmstudio:fake"
    sc.run_check(corpus, out, _fake_checker(), "lmstudio:checker")
    records = list(sc.load_raw(out / "raw.jsonl").values())
    ok = [r for r in records if r["status"] == "ok"]
    assert ok and all(r["check"]["pass"] and r["check_model_id"] == "lmstudio:checker" for r in ok)
    kept, dropped = sc.select(corpus, records)
    assert len(kept) == 1 or len(kept) == len({sc.content_hash(sc._scenario_text(r["scenario"])) for r in ok})
    sql = sc.to_sql(kept)
    assert "INSERT OR IGNORE INTO scenario_bank" in sql and "scenario_sources" in sql
    assert "retired_at IS NULL" in sql
    assert kept[0]["category"] == "Cardiac"


def test_failed_check_and_review_rejection_drop(corpus, tmp_path):
    bps = [b for b in sc.plan(corpus, pilot=True) if b.document_id.startswith("CMG_16_") and b.difficulty == "easy"]
    out = tmp_path / "runs" / "t"
    sc.run_write(corpus, bps, out, _fake_writer(corpus), "lmstudio:fake")
    sc.run_check(corpus, out, _fake_checker(passing=False), "lmstudio:checker")
    kept, dropped = sc.select(corpus, list(sc.load_raw(out / "raw.jsonl").values()))
    assert not kept and dropped[0]["drop_reason"].startswith("check_failed") and "aspirin" in dropped[0]["drop_reason"]

    out2 = tmp_path / "runs" / "u"
    sc.run_write(corpus, bps, out2, _fake_writer(corpus), "lmstudio:fake")
    sc.run_check(corpus, out2, _fake_checker(), "lmstudio:checker")
    records = list(sc.load_raw(out2 / "raw.jsonl").values())
    kept, _ = sc.select(corpus, records, {bps[0].id: "N"})
    assert not kept
    kept, _ = sc.select(corpus, records, {bps[0].id: "Y"})
    assert kept[0]["reviewed"] and "'oscar'" in sc.to_sql(kept)


def test_export_writes_review_files(corpus, tmp_path):
    bps = [b for b in sc.plan(corpus, pilot=True) if b.document_id.startswith("CMG_16_") and b.difficulty == "easy"]
    sc.run_write(corpus, bps, tmp_path / "runs" / "pilot", _fake_writer(corpus), "lmstudio:fake")
    sc.run_check(corpus, tmp_path / "runs" / "pilot", _fake_checker(), "lmstudio:checker")
    assert sc.main(["export", "--out", str(tmp_path), "--run", "pilot"]) == 0
    run = tmp_path / "runs" / "pilot"
    for name in ("scenarios.sql", "review.csv", "review.html", "dropped.csv", "report.json"):
        assert (run / name).exists()
    rows = list(csv.DictReader((run / "review.csv").read_text(encoding="utf-8").splitlines()))
    assert rows and rows[0]["approve (Y/N)"] == ""
    assert json.loads((run / "report.json").read_text())["kept"] == 1


def test_rating_sheet_is_blinded(corpus, tmp_path):
    bps = [b for b in sc.plan(corpus, pilot=True) if b.document_id.startswith("CMG_16_") and b.difficulty == "easy"]
    runs = {}
    for name in ("bench-a", "bench-b"):
        sc.run_write(corpus, bps, tmp_path / "runs" / name, _fake_writer(corpus), f"lmstudio:{name}")
        runs[name] = list(sc.load_raw(tmp_path / "runs" / name / "raw.jsonl").values())
    assert sc.write_sheet(tmp_path / "bench", runs) == 2
    sheet = (tmp_path / "bench" / "rating-sheet.csv").read_text(encoding="utf-8")
    assert "bench-a" not in sheet and "bench-b" not in sheet
    key = json.loads((tmp_path / "bench" / "rating-key.json").read_text())
    assert sorted(key.values()) == ["bench-a", "bench-b"]


def test_run_names_are_safe(tmp_path):
    with pytest.raises(ValueError):
        sc.run_dir(tmp_path, "../escape")


def test_bench_subset_spreads_across_guidelines(corpus):
    picked = sc.bench_subset(sc.plan(corpus, pilot=True), 10)
    assert len(picked) == 10
    assert sum(b.icp for b in picked) == 1
    assert len({b.document_id for b in picked}) == 10
    assert {b.difficulty for b in picked} == {"easy", "medium", "hard"}
