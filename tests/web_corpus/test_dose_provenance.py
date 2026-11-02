from web_corpus import dose_provenance as dp


def test_chunk_id_reads_numbered_and_common_bundles():
    assert dp.chunk_id("120_21365.471026e5120d7468.js") == "21365"
    assert dp.chunk_id("7_common.ecd3ea9c6ba03a70.js") == "7"


def test_line_hash_ignores_whitespace_and_case():
    assert dp.line_hash(" Pre-oxygenate:  nasal prongs ") == dp.line_hash("pre-oxygenate: nasal prongs")


def test_resolve_prefers_title_then_url_and_flags_reference_cards():
    by_url = {"airtraq": ["CSM_A10"]}
    by_title = {"seizures": ["CMG_22"], "ketamine-hydrochloride": ["MED_18"]}
    assert dp.resolve("guidelines/seizures", by_url, by_title) == (["CMG_22"], "title")
    assert dp.resolve("reference/airtraq", by_url, by_title) == (["CSM_A10"], "url")
    assert dp.resolve("medicines/ketamine-hydrochloride-ketalar", by_url, by_title) == (["MED_18"], "title_prefix")
    assert dp.resolve("calculators/critical-care-reference-cards", by_url, by_title) == ([dp.REFERENCE_CARD], "reference_card")
    assert dp.resolve("reference/radio-test", by_url, by_title) == (["page:reference/radio-test"], "no_document")


BAND = (
    'function C(s,a){1&s&&(F.j41(0,"div")(1,"section")(2,"h4",12),F.EFF(3,"2 Years - 13kg"),F.k0s(),'
    'F.j41(4,"h4",13),F.EFF(5,"Cardiac Arrest"),F.k0s(),F.j41(6,"h5"),F.EFF(7,"Airway"),F.k0s(),'
    'F.j41(8,"p")(9,"strong"),F.EFF(10,"ETT size:"),F.k0s(),F.EFF(11," 4.5mm"),F.k0s(),'
    'F.j41(12,"h5"),F.EFF(13,"Medications"),F.k0s(),F.j41(14,"p")(15,"strong"),'
    'F.EFF(16,"Adrenaline (1:10,000) IV/IO:"),F.k0s()(),F.j41(17,"ul")(18,"fa-li"),'
    'F.EFF(19,"Formula: 0.01mg/kg"),F.k0s(),F.j41(20,"fa-li"),F.EFF(21,"Preparation: 1mg in 10mls"),'
    'F.k0s(),F.j41(22,"fa-li"),F.EFF(23,"Dose: 0.13mg"),F.k0s(),F.j41(24,"fa-li"),'
    'F.EFF(25,"Volume: 1.3ml"),F.k0s()(),F.j41(26,"p")(27,"strong"),F.EFF(28,"Volume: 6ml"),F.k0s()(),'
    'F.j41(29,"ul")(30,"fa-li"),F.EFF(31,"Formula: 50mg/kg"),F.k0s(),F.j41(32,"fa-li"),'
    'F.EFF(33,"Dose: 650mg"),F.k0s()())}'
)


def test_parse_band_reads_band_fields_and_dose_rows():
    band = dp.parse_band(BAND)
    assert (band["band"], band["age"], band["weight_kg"]) == ("2 Years - 13kg", "2 Years", 13)
    airway, meds = band["sections"][0]["groups"]
    assert airway["fields"] == {"ETT size": "4.5mm"}
    adrenaline, quirk = meds["drugs"]
    assert adrenaline["drug"] == "Adrenaline (1:10,000) IV/IO"
    assert adrenaline["route"] == "IV/IO"
    assert (adrenaline["formula"], adrenaline["preparation"], adrenaline["dose"], adrenaline["volume"]) == (
        "0.01mg/kg", "1mg in 10mls", "0.13mg", "1.3ml")
    assert quirk["drug"] is None and quirk["label_quirk"] and quirk["dose"] == "650mg"
