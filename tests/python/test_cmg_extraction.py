"""
Tests for CMG extraction pipeline — navigation, template parsing, content, and dose tables.
"""

import json
import os
import tempfile
import pytest

from pipeline.actas.extractor import (
    extract_navigation,
    extract_route_mappings,
    _classify_section,
)
from pipeline.actas.template_parser import (
    parse_template_instructions,
    html_to_markdown,
    _decode_unicode_escapes,
)
from pipeline.actas.dose_tables import _is_dose_related, _group_dose_texts


SAMPLE_MAIN_BUNDLE = """
var x=1;
{"title":"Settings","sectionId":"settings","icon":"folder","atp":["p","icp"],"pages":[{"title":"General Care","section":"CMG 1","spotlightId":"1iA3FOWukpEi","icon":"angle-double-right","color":"default","atp":["p","icp"],"tags":["patient"]},{"title":"Pain Management","section":"CMG 2","spotlightId":"Tanp4PgrNR2yWw0I","icon":"angle-double-right","color":"default","atp":["p","icp"],"tags":["pain","analgesia"]}]}
var y=2;
{"title":"Another Section","sectionId":"other","pages":[{"title":"Glasgow Coma Score","section":"","spotlightId":"g9W5SSHS","icon":"angle-double-right","color":"default","atp":["p","icp"]}]}
"""

SAMPLE_ROUTES = """
const routes=[{path:"",redirectTo:"tabs/guidelines",pathMatch:"full"},{path:"cmg-1-general-care/:spotlightId",loadChildren:()=>Promise.all([t.e(30839),t.e(77083),t.e(72076),t.e(98834)]).then(t.bind(t,98834)).then(r=>r.GeneralCarePageModule)},{path:"pain-management/:spotlightId",loadChildren:()=>Promise.all([t.e(30839),t.e(77083),t.e(72076),t.e(79624)]).then(t.bind(t,79624)).then(r=>r.PainManagementPageModule)}];
"""

SAMPLE_TEMPLATE = """
template:function(h,v){1&v&&(h.j41(0,"ion-content",0)(1,"div",1)(2,"section")(3,"h4"),h.EFF(4,"General Care"),h.k0s(),h.j41(5,"ul")(6,"fa-li"),h.EFF(7,"Oxygen administration "),h.j41(8,"ul")(9,"fa-li"),h.EFF(10,"High\\u2010flow, high\\u2010concentration."),h.k0s()()(),h.j41(11,"fa-li"),h.EFF(12,"Early, rapid transport to appropriate hospital"),h.k0s()())}
"""

SAMPLE_TEMPLATE_WITH_NRM = """
template:function(h,v){1&v&&(h.j41(0,"section")(1,"p"),h.EFF(2,"Some text"),h.k0s(),h.nrm(3,"br"),h.j41(4,"p"),h.EFF(5,"More text"),h.k0s()())}
"""


class TestNavigationExtraction:
    def test_extract_navigation_finds_cmg_entries(self, tmp_path):
        bundle_path = tmp_path / "2_main.test123.js"
        bundle_path.write_text(SAMPLE_MAIN_BUNDLE)

        output_path = tmp_path / "nav.json"
        result = extract_navigation(
            js_bundle_path=str(bundle_path),
            output_path=str(output_path),
        )

        with open(result) as f:
            data = json.load(f)

        cmg_entries = [
            e for e in data["all_pages"] if e.get("section", "").startswith("CMG")
        ]
        assert len(cmg_entries) >= 2
        titles = {e["title"] for e in cmg_entries}
        assert "General Care" in titles
        assert "Pain Management" in titles

    def test_extract_navigation_preserves_metadata(self, tmp_path):
        bundle_path = tmp_path / "2_main.test123.js"
        bundle_path.write_text(SAMPLE_MAIN_BUNDLE)

        output_path = tmp_path / "nav.json"
        extract_navigation(
            js_bundle_path=str(bundle_path), output_path=str(output_path)
        )

        with open(output_path) as f:
            data = json.load(f)

        cmg_1 = next(e for e in data["all_pages"] if e.get("section") == "CMG 1")
        assert cmg_1["spotlightId"] == "1iA3FOWukpEi"
        assert "patient" in cmg_1["tags"]
        assert "p" in cmg_1["atp"]

    def test_extract_navigation_handles_missing_file(self, tmp_path):
        result = extract_navigation(
            js_bundle_path=str(tmp_path / "nonexistent.js"),
            output_path=str(tmp_path / "nav.json"),
        )

        with open(result) as f:
            data = json.load(f)
        assert data["all_pages"] == []
        assert data["sections"] == []

    def test_extract_navigation_extracts_sections(self, tmp_path):
        bundle_path = tmp_path / "2_main.test123.js"
        bundle_path.write_text(SAMPLE_MAIN_BUNDLE)

        output_path = tmp_path / "nav.json"
        extract_navigation(
            js_bundle_path=str(bundle_path), output_path=str(output_path)
        )

        with open(output_path) as f:
            data = json.load(f)

        assert len(data["sections"]) >= 1
        sections_with_pages = [s for s in data["sections"] if s.get("pages")]
        assert len(sections_with_pages) >= 1


class TestRouteMapping:
    def test_extract_route_mapping(self, tmp_path):
        inv_dir = tmp_path / "investigation"
        inv_dir.mkdir()
        common_path = inv_dir / "7_common.test123.js"
        common_path.write_text(SAMPLE_ROUTES)

        (inv_dir / "22_30839.hash.js").write_text("// chunk")
        (inv_dir / "25_77083.hash.js").write_text("// chunk")
        (inv_dir / "59_98834.hash.js").write_text("// chunk")
        (inv_dir / "70_79624.hash.js").write_text("// chunk")

        output_path = tmp_path / "routes.json"
        result = extract_route_mappings(
            investigation_dir=str(inv_dir),
            output_path=str(output_path),
        )

        with open(result) as f:
            routes = json.load(f)

        assert len(routes) >= 1
        assert "cmg-1-general-care/:spotlightId" in routes
        route = routes["cmg-1-general-care/:spotlightId"]
        assert route["module_name"] == "GeneralCarePageModule"

    def test_extract_route_mapping_empty_bundle(self, tmp_path):
        inv_dir = tmp_path / "investigation"
        inv_dir.mkdir()
        common_path = inv_dir / "7_common.test123.js"
        common_path.write_text("var x=1;")

        output_path = tmp_path / "routes.json"
        result = extract_route_mappings(
            investigation_dir=str(inv_dir),
            output_path=str(output_path),
        )

        with open(result) as f:
            routes = json.load(f)
        assert routes == {}


class TestTemplateParser:
    def test_parse_template_extracts_text(self):
        results = parse_template_instructions(SAMPLE_TEMPLATE)
        assert len(results) >= 1
        html = results[0]["html"]
        assert "General Care" in html
        assert "Oxygen administration" in html
        assert "High\U00002010flow" in html

    def test_parse_template_builds_html_structure(self):
        results = parse_template_instructions(SAMPLE_TEMPLATE)
        html = results[0]["html"]
        assert "<section>" in html
        assert "<h4>" in html
        assert "</h4>" in html
        assert "<ul>" in html
        assert "<fa-li>" in html

    def test_parse_template_handles_nrm_self_closing(self):
        results = parse_template_instructions(SAMPLE_TEMPLATE_WITH_NRM)
        html = results[0]["html"]
        assert "<br />" in html

    def test_parse_template_empty_content(self):
        results = parse_template_instructions(
            'template:function(h,v){1&v&&(h.j41(0,"div"),h.k0s())}'
        )
        assert len(results) == 0

    def test_unicode_decode(self):
        text = _decode_unicode_escapes("\\u2265 18 years")
        assert "\u2265" in text
        assert "18 years" in text

    def test_html_to_markdown_conversion(self):
        html = "<h4>General Care</h4><section><ul><fa-li>Oxygen administration</fa-li></ul></section>"
        md = html_to_markdown(html)
        assert "#### General Care" in md
        assert "- Oxygen administration" in md

    def test_html_to_markdown_separates_list_items(self):
        html = "<ul><li>Item one</li><li>Item two</li><li>Item three</li></ul>"
        md = html_to_markdown(html)
        lines = [l.strip() for l in md.strip().split("\n") if l.strip()]
        assert len(lines) == 3
        assert lines[0] == "- Item one"
        assert lines[1] == "- Item two"
        assert lines[2] == "- Item three"


class TestSectionClassification:
    def test_classify_known_sections(self):
        assert _classify_section("CMG 1") == "General Care"
        assert _classify_section("CMG 2") == "Pain Management"
        assert _classify_section("CMG 4") == "Cardiac"
        assert _classify_section("CMG 17") == "Trauma"
        assert _classify_section("CMG 45") == "Palliative Care"

    def test_classify_unknown_section(self):
        assert _classify_section("CMG 99") == "Other"

    def test_classify_non_cmg(self):
        assert _classify_section("Skills") == "Other"

    def test_classify_lowercase_letter_suffix(self):
        assert _classify_section("CMG 22a") == "Neurology"
        assert _classify_section("CMG 22A") == "Neurology"


class TestTitleToPathMatching:
    def test_title_to_path_strips_special_chars(self):
        from pipeline.actas.content_extractor import _title_to_path

        assert _title_to_path("General Care") == "general-care"
        assert (
            _title_to_path("RSI (Rapid Sequence Intubation)")
            == "rsi-rapid-sequence-intubation"
        )

    def test_find_route_for_title_fuzzy_match(self, tmp_path):
        from pipeline.actas.content_extractor import _find_route_for_title

        routes = {
            "cardiac-arrest-paediatric": {"path": "cardiac-arrest-paediatric"},
            "febrile-paediatric": {"path": "febrile-paediatric"},
            "general-care": {"path": "general-care"},
        }

        assert (
            _find_route_for_title("Cardiac Arrest: Paediatric (<12 years old)", routes)
            == "cardiac-arrest-paediatric"
        )
        assert (
            _find_route_for_title("Febrile Paediatric (<12yo)", routes)
            == "febrile-paediatric"
        )
        assert _find_route_for_title("General Care", routes) == "general-care"


class TestBoilerplateStripping:
    def test_strip_more_information(self):
        from pipeline.actas.template_parser import strip_boilerplate

        html = "<span>More information<fa-icon /></span><section><p>Real content</p></section>"
        result = strip_boilerplate(html)
        assert "More information" not in result
        assert "Real content" in result

    def test_strip_my_notes(self):
        from pipeline.actas.template_parser import strip_boilerplate

        html = "<section><h4>My Notes</h4><div></div></section><p>Clinical text</p>"
        result = strip_boilerplate(html)
        assert "My Notes" not in result
        assert "Clinical text" in result

    def test_strip_tap_to_zoom(self):
        from pipeline.actas.template_parser import strip_boilerplate

        html = "<div><span>Tap to zoom</span></div><p>Important</p>"
        result = strip_boilerplate(html)
        assert "Tap to zoom" not in result
        assert "Important" in result

    def test_strip_open_print_version(self):
        from pipeline.actas.template_parser import strip_boilerplate

        html = "<ion-button>Open print version</ion-button><p>Content</p>"
        result = strip_boilerplate(html)
        assert "Open print version" not in result
        assert "Content" in result

    def test_strip_ui_components(self):
        from pipeline.actas.template_parser import strip_boilerplate

        html = "<content-header /><ion-content><section-menu></section-menu><div><p>Real clinical text</p></div></ion-content>"
        result = strip_boilerplate(html)
        assert "content-header" not in result
        assert "section-menu" not in result
        assert "ion-content" not in result
        assert "Real clinical text" in result

    def test_strip_all_boilerplate_preserves_clinical(self):
        from pipeline.actas.template_parser import strip_boilerplate

        html = (
            "<content-header />"
            "<ion-content><section-menu></section-menu>"
            "<div><section><h4>Indications</h4><ul><fa-li>Chest pain</fa-li></ul></section></div>"
            "</ion-content>"
            "<span>More information<fa-icon /></span>"
            "<section><h4>My Notes</h4><div></div></section>"
        )
        result = strip_boilerplate(html)
        assert "Indications" in result
        assert "Chest pain" in result
        assert "More information" not in result
        assert "My Notes" not in result

    def test_strip_boilerplate_markdown(self):
        from pipeline.actas.template_parser import strip_boilerplate_md

        md = "More information\n\n#### My Notes\n\nTap to zoom\n\nOpen print version\n\n## Indications\n- Chest pain"
        result = strip_boilerplate_md(md)
        assert "More information" not in result
        assert "My Notes" not in result
        assert "Tap to zoom" not in result
        assert "Open print version" not in result
        assert "## Indications" in result
        assert "Chest pain" in result


class TestSelectorExtractor:
    def test_extract_selectors_from_bundle(self, tmp_path):
        from pipeline.actas.selector_extractor import extract_selector_templates

        bundle = tmp_path / "7_common.test123.js"
        bundle.write_text(
            'selectors:[["app-general-care"]],features:[e.Vt3],decls:147,'
            'vars:15,consts:[[3,"data",4,"ngIf"]],template:function(c,i){1&c&&('
            'e.j41(0,"ion-content")(1,"div")(2,"section")(3,"h4"),'
            'e.EFF(4,"Patient Centred Care"),h.k0s(),'
            'e.j41(5,"p"),e.EFF(6,"Treat all patients with dignity."),'
            "h.k0s()()())}"
        )

        results = extract_selector_templates(str(bundle))
        assert len(results) == 1
        assert results[0]["selector"] == "app-general-care"
        assert "Patient Centred Care" in results[0]["html"]
        assert "Treat all patients with dignity." in results[0]["html"]

    def test_extract_multiple_selectors(self, tmp_path):
        from pipeline.actas.selector_extractor import extract_selector_templates

        bundle = tmp_path / "7_common.test123.js"
        bundle.write_text(
            'selectors:[["app-pain-management"]],template:function(c,i){'
            '1&c&&(e.EFF(0,"Pain Scale"))}'
            '\nselectors:[["app-shock"]],template:function(c,i){'
            '1&c&&(e.EFF(0,"Shock Management"))}'
        )

        results = extract_selector_templates(str(bundle))
        assert len(results) == 2
        selectors = {r["selector"] for r in results}
        assert "app-pain-management" in selectors
        assert "app-shock" in selectors

    def test_selector_to_route_path(self):
        from pipeline.actas.selector_extractor import selector_to_route

        assert selector_to_route("app-general-care") == "general-care"
        assert selector_to_route("app-cardiac-arrest-adult") == "cardiac-arrest-adult"
        assert selector_to_route("app-cresst-screening-tool") == "cresst-screening-tool"

    def test_extract_selectors_missing_file(self, tmp_path):
        from pipeline.actas.selector_extractor import extract_selector_templates

        results = extract_selector_templates(str(tmp_path / "nonexistent.js"))
        assert results == []

    def test_integration_selector_extraction_from_real_bundle(self, tmp_path):
        inv_dir = "data/cmgs/investigation/"
        if not os.path.exists(inv_dir):
            pytest.skip("No investigation data")

        from pipeline.actas.selector_extractor import extract_selector_templates
        import glob

        common_files = glob.glob(os.path.join(inv_dir, "7_common.*.js"))
        if not common_files:
            pytest.skip("No 7_common bundle")

        results = extract_selector_templates(common_files[0])
        assert len(results) >= 200

        selectors = {r["selector"] for r in results}
        assert "app-general-care" in selectors
        assert "app-bradyarrhythmias" in selectors

        general_care = next(r for r in results if r["selector"] == "app-general-care")
        assert "Patient Centred Care" in general_care["html"]
        assert len(general_care["html"]) > 500


class TestContentExtractorIntegration:
    def test_extract_content_uses_selector_fallback(self, tmp_path):
        from pipeline.actas.content_extractor import extract_content

        inv_dir = "data/cmgs/investigation/"
        if not os.path.exists(inv_dir):
            pytest.skip("No investigation data")

        output = str(tmp_path / "content.json")
        extract_content(investigation_dir=inv_dir, output_path=output)

        with open(output) as f:
            data = json.load(f)

        general_care_entries = [
            v for v in data.values() if v.get("title") == "General Care"
        ]
        assert len(general_care_entries) >= 1
        entry = general_care_entries[0]
        md = entry.get("markdown", "")

        assert "More information" not in md
        assert "My Notes" not in md
        assert "Patient Centred Care" in md

    def test_merge_includes_previously_unmatched_cmgs(self, tmp_path):
        from pipeline.actas.content_extractor import merge_navigation_and_content
        from pipeline.actas.extractor import extract_navigation
        from pipeline.actas.content_extractor import extract_content

        inv_dir = "data/cmgs/investigation/"
        if not os.path.exists(inv_dir):
            pytest.skip("No investigation data")

        nav_path = str(tmp_path / "nav.json")
        content_path = str(tmp_path / "content.json")
        output_path = str(tmp_path / "guidelines.json")

        extract_navigation(investigation_dir=inv_dir, output_path=nav_path)
        extract_content(investigation_dir=inv_dir, output_path=content_path)
        merge_navigation_and_content(
            nav_path=nav_path,
            content_path=content_path,
            output_path=output_path,
        )

        with open(output_path) as f:
            guidelines = json.load(f)

        cmg5 = next(g for g in guidelines if g["cmg_number"] == "5")
        assert cmg5["content_markdown"]
        assert len(cmg5["content_markdown"]) > 100

        cmg44 = next(g for g in guidelines if g["cmg_number"] == "44")
        assert cmg44["content_markdown"]
        assert len(cmg44["content_markdown"]) > 100

    def test_merge_includes_med_and_csm_entries(self, tmp_path):
        inv_dir = "data/cmgs/investigation/"
        if not os.path.exists(inv_dir):
            pytest.skip("No investigation data")

        from pipeline.actas.content_extractor import (
            merge_navigation_and_content,
            extract_content,
        )
        from pipeline.actas.extractor import extract_navigation

        nav_path = str(tmp_path / "nav.json")
        content_path = str(tmp_path / "content.json")
        output_path = str(tmp_path / "guidelines.json")

        extract_navigation(investigation_dir=inv_dir, output_path=nav_path)
        extract_content(investigation_dir=inv_dir, output_path=content_path)
        merge_navigation_and_content(
            nav_path=nav_path,
            content_path=content_path,
            output_path=output_path,
        )

        with open(output_path) as f:
            guidelines = json.load(f)

        med_entries = [g for g in guidelines if g.get("entry_type") == "med"]
        csm_entries = [g for g in guidelines if g.get("entry_type") == "csm"]
        assert len(med_entries) > 0
        assert len(csm_entries) > 0


class TestDoseDetection:
    def test_dose_related_text_detected(self):
        assert _is_dose_related("Dose: 0.25 mg")
        assert _is_dose_related("Volume: 0.3ml")
        assert _is_dose_related("Adrenaline 0.5mg IM")

    def test_non_dose_text_rejected(self):
        assert not _is_dose_related("Assess the patient")
        assert not _is_dose_related("Transport to hospital")

    def test_group_dose_texts(self):
        texts = [
            "Assess the patient",
            "Adrenaline 0.5mg IM injection",
            "Dose: 0.25 mg",
            "Volume: 0.25 ml",
            "Monitor vital signs",
        ]
        groups = _group_dose_texts(texts)
        assert len(groups) == 1
        assert groups[0]["medicines"] == ["Adrenaline"]
        assert len(groups[0]["dose_values"]) >= 1


class TestMEDCSMExtraction:
    def test_med_section_regex(self):
        from pipeline.actas.extractor import _MED_SECTION_RE

        assert _MED_SECTION_RE.match("MED01")
        assert _MED_SECTION_RE.match("MED35")
        assert not _MED_SECTION_RE.match("CMG 1")

    def test_csm_section_regex(self):
        from pipeline.actas.extractor import _CSM_SECTION_RE

        assert _CSM_SECTION_RE.match("CSM.A01")
        assert _CSM_SECTION_RE.match("CSM.B99")
        assert _CSM_SECTION_RE.match("CSM.PA01")
        assert not _CSM_SECTION_RE.match("MED01")


class TestDoseSegmentation:
    def test_dose_groups_include_source_file(self, tmp_path):
        from pipeline.actas.dose_tables import extract_dose_tables_segmented

        inv_dir = tmp_path / "inv"
        inv_dir.mkdir()
        chunk = inv_dir / "99_12345.test.js"
        chunk.write_text(
            '.EFF(1,"Adrenaline 0.5mg IM injection").EFF(2,"Dose: 0.25 mg")'
        )

        output = str(tmp_path / "dose.json")
        result = extract_dose_tables_segmented(
            investigation_dir=str(inv_dir), output_path=output
        )

        with open(output) as f:
            data = json.load(f)

        assert "per_file" in data
        assert len(data["per_file"]) >= 1
        for file_entry in data["per_file"]:
            assert "source_file" in file_entry
            assert "dose_groups" in file_entry

    def test_integration_segmented_dose_tables(self, tmp_path):
        inv_dir = "data/cmgs/investigation/"
        if not os.path.exists(inv_dir):
            pytest.skip("No investigation data")

        from pipeline.actas.dose_tables import extract_dose_tables_segmented

        output = str(tmp_path / "dose.json")
        extract_dose_tables_segmented(investigation_dir=inv_dir, output_path=output)

        with open(output) as f:
            data = json.load(f)

        assert "per_file" in data
        assert len(data["per_file"]) >= 5
        total_groups = sum(len(f["dose_groups"]) for f in data["per_file"])
        assert total_groups > 0


class TestIntegrationFromBundles:
    """Integration tests that run against the real JS bundles if available."""

    INVESTIGATION_DIR = "data/cmgs/investigation/"

    @pytest.fixture(autouse=True)
    def skip_if_no_data(self):
        if not os.path.exists(self.INVESTIGATION_DIR):
            pytest.skip("No investigation data available")

    def test_navigation_extracts_cmg_count(self, tmp_path):
        output = str(tmp_path / "nav.json")
        extract_navigation(
            investigation_dir=self.INVESTIGATION_DIR,
            output_path=output,
        )
        with open(output) as f:
            data = json.load(f)
        assert data["cmg_count"] >= 40
        assert data["total_pages"] > data["cmg_count"]

    def test_route_mappings_count(self, tmp_path):
        output = str(tmp_path / "routes.json")
        extract_route_mappings(
            investigation_dir=self.INVESTIGATION_DIR,
            output_path=output,
        )
        with open(output) as f:
            routes = json.load(f)
        assert len(routes) >= 100

    def test_content_extraction_produces_output(self, tmp_path):
        from pipeline.actas.content_extractor import extract_content

        output = str(tmp_path / "content.json")
        extract_content(
            investigation_dir=self.INVESTIGATION_DIR,
            output_path=output,
        )
        assert os.path.exists(output)
        with open(output) as f:
            data = json.load(f)
        assert len(data) > 0

    def test_dose_tables_find_medicines(self, tmp_path):
        from pipeline.actas.dose_tables import extract_dose_tables

        output = str(tmp_path / "dose.json")
        extract_dose_tables(
            investigation_dir=self.INVESTIGATION_DIR,
            output_path=output,
        )
        with open(output) as f:
            data = json.load(f)
        assert data["medicine_count"] > 0
        assert "Adrenaline" in data["unique_medicines"]
