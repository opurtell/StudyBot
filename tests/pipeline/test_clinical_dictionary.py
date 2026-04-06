from pipeline.clinical_dictionary import (
    SUBJECT_TO_CATEGORY,
    CLINICAL_TERMS,
    CANONICAL_CATEGORIES,
    get_category,
    get_terms_for_category,
)

def test_canonical_categories_has_all_required():
    required = {
        "Clinical Guidelines", "Medication Guidelines", "Operational Guidelines",
        "Clinical Skills", "Pathophysiology", "Pharmacology", "ECGs", "General Paramedicine",
    }
    assert required == set(CANONICAL_CATEGORIES)

def test_known_folder_maps_to_category():
    assert get_category("CSA236 Pharmacology") == "Pharmacology"

def test_unknown_folder_defaults_to_general():
    assert get_category("Some Unknown Folder") == "General Paramedicine"

def test_variant_folders_map_same_category():
    cat1 = get_category("CNA308 Ethics and Law")
    cat2 = get_category("CNA308 Legal and Ethical")
    assert cat1 == cat2 == "Operational Guidelines"

def test_all_mapped_categories_are_canonical():
    for folder, cat in SUBJECT_TO_CATEGORY.items():
        assert cat in CANONICAL_CATEGORIES, f"{folder} maps to non-canonical '{cat}'"

def test_clinical_terms_keys_are_canonical():
    for cat in CLINICAL_TERMS:
        assert cat in CANONICAL_CATEGORIES, f"Term list key '{cat}' not canonical"

def test_get_terms_for_category_returns_list():
    terms = get_terms_for_category("Pharmacology")
    assert isinstance(terms, list)
    assert len(terms) > 0
    assert "adrenaline" in terms

def test_get_terms_for_unknown_category_returns_empty():
    assert get_terms_for_category("Nonexistent") == []
