"""Pydantic schemas for guideline documents and related structures.

This module provides validated schemas for structured guideline data,
including content sections, medication dosing, flowcharts, and references.
All models enforce strict validation (extra="forbid") to ensure data integrity
when reading and validating structured JSON files.
"""

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class ContentSection(BaseModel):
    """A section of clinical content within a guideline.

    Attributes:
        heading: The section title.
        body: The section body text.
        qualifications_required: List of qualifications required to apply this section.
    """

    model_config = ConfigDict(extra="forbid")

    heading: str
    body: str
    qualifications_required: list[str] = []


class MedicationDose(BaseModel):
    """A medication dose specification for a specific indication.

    Attributes:
        medication: The medication name.
        indication: The clinical indication for this dose.
        dose: The dose specification (e.g. "0.3-0.5 mg").
        route: The administration route (e.g. "IM", "IV").
        qualifications_required: List of qualifications required to administer.
    """

    model_config = ConfigDict(extra="forbid")

    medication: str
    indication: str
    dose: str
    route: str | None = None
    qualifications_required: list[str] = []


class Flowchart(BaseModel):
    """A flowchart or algorithm diagram within a guideline.

    Attributes:
        title: The flowchart title.
        mermaid: Mermaid.js syntax for the diagram.
        source_format: The original format of the flowchart ("data" | "svg" | "image" | "pdf").
        review_required: Whether the flowchart needs review (e.g. manual OCR conversion).
        asset_ref: Optional reference to a bundled asset file.
    """

    model_config = ConfigDict(extra="forbid")

    title: str
    mermaid: str
    source_format: Literal["data", "svg", "image", "pdf"]
    review_required: bool = False
    asset_ref: str | None = None


class Reference(BaseModel):
    """A reference or citation within a guideline.

    Attributes:
        label: The reference label (e.g. "ACTAS CMG 14").
        url: Optional URL to the referenced resource.
    """

    model_config = ConfigDict(extra="forbid")

    label: str
    url: str | None = None


class GuidelineDocument(BaseModel):
    """A complete structured guideline document.

    This is the schema for structured JSON files containing ACTAS CMG or
    related clinical guideline data. All fields with list types default to
    empty lists if omitted.

    Attributes:
        service: The service identifier (e.g. "actas").
        guideline_id: The guideline identifier (e.g. "CMG_14").
        title: The guideline title.
        categories: List of clinical categories (e.g. ["Clinical Guidelines"]).
        qualifications_required: List of qualifications required to use this guideline.
        content_sections: List of ContentSection objects.
        medications: List of MedicationDose objects.
        flowcharts: List of Flowchart objects.
        references: List of Reference objects.
        source_url: Optional URL to the original source.
        source_hash: Hash of the source data for change detection.
        last_modified: Optional date of last modification.
        extra: Optional dict for additional metadata not in the main schema.
    """

    model_config = ConfigDict(extra="forbid")

    service: str
    guideline_id: str
    title: str
    categories: list[str]
    qualifications_required: list[str]
    content_sections: list[ContentSection]
    medications: list[MedicationDose]
    flowcharts: list[Flowchart]
    references: list[Reference]
    source_url: str | None = None
    source_hash: str
    last_modified: date | None = None
    extra: dict[str, Any] = {}
