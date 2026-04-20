"""Pydantic schemas for Ambulance Tasmania (AT) guideline extraction.

This module provides validated schemas for AT-specific structured data,
including guideline references, medicine references, and discovery results.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict


class ATGuidelineRef(BaseModel):
    """Reference to an AT Clinical Practice Guideline (CPG).

    Attributes:
        cpg_code: The CPG identifier (e.g. "A0201-1", "D003")
        title: The guideline title
        category: Clinical category (e.g. "Cardiac Arrest", "Medicines")
        route_slug: URL route slug (e.g. "cardiac-arrest")
        source_bundle: JS bundle filename containing content data
        has_flowchart: Whether the guideline includes a flowchart
        has_dose_table: Whether the guideline includes medication dose tables
    """

    model_config = ConfigDict(extra="forbid")

    cpg_code: str
    title: str
    category: str
    route_slug: str
    source_bundle: str
    has_flowchart: bool = False
    has_dose_table: bool = False


class ATMedicineRef(BaseModel):
    """Reference to an AT medication monograph.

    Attributes:
        cpg_code: The parent CPG code (D-code, e.g. "D003")
        name: The medication name (e.g. "Adrenaline")
        route_slug: URL slug for the medicine page
    """

    model_config = ConfigDict(extra="forbid")

    cpg_code: str
    name: str
    route_slug: str


class ATDiscoveryResult(BaseModel):
    """Result of site discovery phase.

    Attributes:
        guidelines: List of discovered guideline references
        medicines: List of discovered medication references
        categories: List of unique clinical categories found
        total_bundles_analysed: Number of JS bundles processed
        errors: List of any errors encountered during discovery
    """

    model_config = ConfigDict(extra="forbid")

    guidelines: List[ATGuidelineRef] = []
    medicines: List[ATMedicineRef] = []
    categories: List[str] = []
    total_bundles_analysed: int = 0
    errors: List[str] = []


class ATContentSection(BaseModel):
    """A section of clinical content within an AT guideline.

    Attributes:
        heading: The section title
        body: The section body text
        qualifications_required: List of qualifications required to apply this section
    """

    model_config = ConfigDict(extra="forbid")

    heading: str
    body: str
    qualifications_required: List[str] = []


class ATFlowchart(BaseModel):
    """A flowchart or algorithm diagram within an AT guideline.

    Attributes:
        cpg_code: The parent CPG code
        title: The flowchart title
        source_format: The original format ("data" | "svg" | "image" | "pdf")
        mermaid: Optional Mermaid.js syntax for the diagram
        asset_ref: Optional reference to a bundled asset file
        review_required: Whether the flowchart needs review (e.g. manual OCR)
    """

    model_config = ConfigDict(extra="forbid")

    cpg_code: str
    title: str
    source_format: Literal["data", "svg", "image", "pdf"]
    mermaid: Optional[str] = None
    asset_ref: Optional[str] = None
    review_required: bool = False
