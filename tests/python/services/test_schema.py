import pytest
from pydantic import ValidationError

from src.python.services.schema import GuidelineDocument


def test_minimal_valid_document():
    """Test that a minimal valid GuidelineDocument can be created."""
    doc = GuidelineDocument(
        service="actas",
        guideline_id="CMG_14",
        title="Anaphylaxis",
        categories=["Clinical Guidelines"],
        qualifications_required=["AP"],
        content_sections=[],
        medications=[],
        flowcharts=[],
        references=[],
        source_hash="abc",
        extra={},
    )
    assert doc.service == "actas"
    assert doc.guideline_id == "CMG_14"
    assert doc.title == "Anaphylaxis"


def test_rejects_unknown_top_level_field():
    """Test that extra fields at top level are rejected."""
    with pytest.raises(ValidationError):
        GuidelineDocument(
            service="actas",
            guideline_id="X",
            title="T",
            categories=[],
            qualifications_required=[],
            content_sections=[],
            medications=[],
            flowcharts=[],
            references=[],
            source_hash="x",
            extra={},
            bogus_field=1,
        )


def test_content_section_with_qualifications():
    """Test that ContentSection accepts qualifications_required."""
    from src.python.services.schema import ContentSection

    section = ContentSection(
        heading="Initial Assessment",
        body="Check for anaphylaxis signs",
        qualifications_required=["AP", "SP"],
    )
    assert section.heading == "Initial Assessment"
    assert len(section.qualifications_required) == 2


def test_medication_dose_minimal():
    """Test that MedicationDose accepts minimal fields."""
    from src.python.services.schema import MedicationDose

    med = MedicationDose(
        medication="Adrenaline",
        indication="Anaphylaxis",
        dose="0.3-0.5 mg",
    )
    assert med.medication == "Adrenaline"
    assert med.route is None


def test_medication_dose_with_route():
    """Test that MedicationDose accepts route."""
    from src.python.services.schema import MedicationDose

    med = MedicationDose(
        medication="Adrenaline",
        indication="Anaphylaxis",
        dose="0.3-0.5 mg",
        route="IM",
        qualifications_required=["AP"],
    )
    assert med.route == "IM"


def test_flowchart_with_mermaid():
    """Test that Flowchart accepts mermaid syntax."""
    from src.python.services.schema import Flowchart

    chart = Flowchart(
        title="Anaphylaxis Algorithm",
        mermaid="graph TD; A-->B",
        source_format="data",
    )
    assert chart.title == "Anaphylaxis Algorithm"
    assert chart.source_format == "data"
    assert chart.review_required is False


def test_flowchart_with_review_flag():
    """Test that Flowchart can be flagged for review."""
    from src.python.services.schema import Flowchart

    chart = Flowchart(
        title="Test",
        mermaid="graph TD; A-->B",
        source_format="image",
        review_required=True,
        asset_ref="image_001.svg",
    )
    assert chart.review_required is True
    assert chart.asset_ref == "image_001.svg"


def test_reference_with_url():
    """Test that Reference accepts a URL."""
    from src.python.services.schema import Reference

    ref = Reference(
        label="ACTAS CMG 14",
        url="https://cmg.ambulance.act.gov.au/cmg/14",
    )
    assert ref.label == "ACTAS CMG 14"
    assert ref.url == "https://cmg.ambulance.act.gov.au/cmg/14"


def test_reference_without_url():
    """Test that Reference URL is optional."""
    from src.python.services.schema import Reference

    ref = Reference(label="Internal Reference")
    assert ref.url is None


def test_full_guideline_document():
    """Test a comprehensive GuidelineDocument with all fields."""
    from src.python.services.schema import (
        ContentSection,
        MedicationDose,
        Flowchart,
        Reference,
    )

    doc = GuidelineDocument(
        service="actas",
        guideline_id="CMG_14",
        title="Anaphylaxis",
        categories=["Clinical Guidelines", "Allergic Reactions"],
        qualifications_required=["AP", "SP"],
        content_sections=[
            ContentSection(
                heading="Initial Assessment",
                body="Check for signs of anaphylaxis",
                qualifications_required=["AP"],
            ),
        ],
        medications=[
            MedicationDose(
                medication="Adrenaline",
                indication="Anaphylaxis",
                dose="0.3-0.5 mg",
                route="IM",
                qualifications_required=["AP"],
            ),
        ],
        flowcharts=[
            Flowchart(
                title="Anaphylaxis Response Algorithm",
                mermaid="graph TD; A-->B",
                source_format="data",
            ),
        ],
        references=[
            Reference(
                label="ACTAS CMG 14",
                url="https://cmg.ambulance.act.gov.au/cmg/14",
            ),
        ],
        source_url="https://cmg.ambulance.act.gov.au/cmg/14",
        source_hash="abc123def456",
        extra={"original_structure": "some_metadata"},
    )

    assert doc.service == "actas"
    assert len(doc.content_sections) == 1
    assert len(doc.medications) == 1
    assert len(doc.flowcharts) == 1
    assert len(doc.references) == 1


def test_nested_extra_forbid():
    """Test that extra fields are forbidden in nested models."""
    from src.python.services.schema import ContentSection

    with pytest.raises(ValidationError):
        ContentSection(
            heading="Test",
            body="Body",
            bogus_field="should_fail",
        )


def test_medication_dose_extra_forbid():
    """Test that MedicationDose forbids extra fields."""
    from src.python.services.schema import MedicationDose

    with pytest.raises(ValidationError):
        MedicationDose(
            medication="Test",
            indication="Test",
            dose="1mg",
            unknown_field="fail",
        )


def test_flowchart_extra_forbid():
    """Test that Flowchart forbids extra fields."""
    from src.python.services.schema import Flowchart

    with pytest.raises(ValidationError):
        Flowchart(
            title="Test",
            mermaid="graph TD",
            source_format="data",
            bad_field="fail",
        )


def test_reference_extra_forbid():
    """Test that Reference forbids extra fields."""
    from src.python.services.schema import Reference

    with pytest.raises(ValidationError):
        Reference(
            label="Test",
            extra_field="fail",
        )
