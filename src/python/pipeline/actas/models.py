"""
Pydantic schemas for the ACTAS CMG Extraction Pipeline.
"""

from typing import List, Dict, Optional, Literal, Any
from pydantic import BaseModel, Field
from datetime import datetime


class WeightBand(BaseModel):
    id: str
    weight_kg: float
    label: str


class MedicineEntry(BaseModel):
    id: str
    name: str
    indications: List[str]
    routes: Optional[List[str]] = None


class DoseEntry(BaseModel):
    indication: str
    route: str
    dose: str
    volume: str
    notes: Optional[str] = None
    presentation: Optional[str] = None
    concentration: Optional[str] = None


class FlowchartEntry(BaseModel):
    cmg_number: str
    mermaid_code: Optional[str] = None
    source_type: Literal["svg", "image_flagged"]


class ExtractionMetadata(BaseModel):
    timestamp: str
    source_type: Literal["cmg", "med", "csm"] = "cmg"
    agent_version: str = "1.0"
    content_flag: Optional[str] = None


class CMGGuideline(BaseModel):
    id: str
    cmg_number: str
    title: str
    version_date: Optional[str] = None
    section: str  # Respiratory, Cardiac, Trauma, Medical, Pediatric, Obstetric, Other
    content_markdown: str
    is_icp_only: bool = False
    dose_lookup: Optional[Dict[str, Any]] = None  # Attached for medicine CMGs
    flowchart: Optional[FlowchartEntry] = None
    checksum: str
    extraction_metadata: ExtractionMetadata


class JSBundle(BaseModel):
    url: str
    size_bytes: int


class JSONPayload(BaseModel):
    url: str
    size_bytes: int


class DiscoveryResult(BaseModel):
    url: str
    captured_at: str
    js_bundles: List[JSBundle] = []
    json_payloads: List[JSONPayload] = []
    asset_paths_probed: List[str] = []
    recommendation: str


class ExtractionResult(BaseModel):
    extracted_count: int = 0
    structured_count: int = 0
    chunked_count: int = 0
    errors: List[str] = []
    warnings: List[str] = []
