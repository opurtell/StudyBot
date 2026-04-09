from guidelines.markdown import has_icp_content, strip_icp_content


def test_has_icp_content_detects_icp_marker():
    text = "- **ICP:** 1mMol/kg IV"
    assert has_icp_content(text) is True


def test_has_icp_content_detects_icp_with_drug_name():
    text = "- **ICP: Adrenaline:** double dose"
    assert has_icp_content(text) is True


def test_has_icp_content_false_for_normal_text():
    text = "- **Adrenaline 1mg IV** every 3-5 minutes\n- Normal item"
    assert has_icp_content(text) is False


def test_has_icp_content_false_for_empty():
    assert has_icp_content("") is False


def test_strip_icp_removes_single_icp_line():
    text = "- **Adrenaline 1mg IV** every 3-5 minutes\n- **ICP:** 1mMol/kg IV\n- Normal item here"
    result = strip_icp_content(text)
    assert "**ICP:**" not in result
    assert "Adrenaline 1mg IV" in result
    assert "Normal item here" in result


def test_strip_icp_removes_icp_with_sub_bullets():
    text = (
        "- **ICP:** Additional intervention\n"
        "  - Sub-bullet one\n"
        "  - Sub-bullet two\n"
        "- **Normal item** here"
    )
    result = strip_icp_content(text)
    assert "**ICP:**" not in result
    assert "Sub-bullet" not in result
    assert "Normal item" in result


def test_strip_icp_removes_multiple_icp_blocks():
    text = (
        "- **Normal** item\n"
        "- **ICP:** first block\n"
        "  - sub-item\n"
        "- **Normal** item 2\n"
        "- **ICP: DrugName:** second block\n"
        "  - Paediatric: 0.1mg/kg\n"
        "- Final item"
    )
    result = strip_icp_content(text)
    assert "**ICP" not in result
    assert "sub-item" not in result
    assert "Paediatric" not in result
    assert "Normal" in result
    assert "Final item" in result


def test_strip_icp_no_change_when_no_icp():
    text = "- **Adrenaline 1mg IV** every 3-5 minutes\n- Normal item"
    assert strip_icp_content(text) == text


def test_strip_icp_cleans_double_blanks():
    text = "- Item A\n- **ICP:** removed\n\n\n- Item B"
    result = strip_icp_content(text)
    assert "\n\n\n" not in result


def test_has_icp_detects_inline_glued():
    text = "- Upper hard infusion limit: 50mg/hr- **ICP:** Default bolus: 2mg (2mL)"
    assert has_icp_content(text) is True


def test_has_icp_detects_bold_prefix_glued():
    text = "**and/ or **- **ICP:** Consider adrenaline infusion."
    assert has_icp_content(text) is True


def test_strip_icp_inline_glued_via_dash():
    text = "- Limit: 50mg/hr- **ICP:** Default bolus: 2mg\n- Next item"
    result = strip_icp_content(text)
    assert "**ICP:**" not in result
    assert "- Limit: 50mg/hr" in result
    assert "- Next item" in result


def test_strip_icp_bold_prefix_glued():
    text = "**and/ or **- **ICP:** Consider adrenaline infusion."
    result = strip_icp_content(text)
    assert "**ICP:" not in result
    assert "**and/ or **" in result


def test_strip_icp_multiple_icp_same_line():
    text = "- **ICP:** Early bicarb - **ICP:** Calcium chloride"
    result = strip_icp_content(text)
    assert "**ICP" not in result


def test_strip_icp_line_start_no_trailing_newline():
    text = "text\n- **ICP:** Adrenaline infusion if sBP drops"
    result = strip_icp_content(text)
    assert "**ICP:" not in result
    assert "text" in result


def test_strip_icp_dose_lookup_pattern():
    text = "- **AP:** max dose 20mg- **ICP:** no max dose\n#### Next section"
    result = strip_icp_content(text)
    assert "**ICP:" not in result
    assert "- **AP:** max dose 20mg" in result
    assert "#### Next section" in result


def test_strip_icp_midhr_infusion():
    text = "- Upper hard infusion limit: 50mg/hr- **ICP:** Default bolus: 2mg (2mL) \n- Lower hard bolus limit: 0.5mg"
    result = strip_icp_content(text)
    assert "**ICP:" not in result
    assert "- Upper hard infusion limit: 50mg/hr" in result
    assert "- Lower hard bolus limit: 0.5mg" in result
