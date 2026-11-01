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
