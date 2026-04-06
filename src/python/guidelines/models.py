from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class GuidelineSummary(BaseModel):
    id: str
    cmg_number: str
    title: str
    section: str
    source_type: str
    is_icp_only: bool = False


class GuidelineDetail(BaseModel):
    id: str
    cmg_number: str
    title: str
    section: str
    source_type: str
    content_markdown: str
    is_icp_only: bool = False
    dose_lookup: Optional[dict] = None
    flowchart: Optional[dict] = None
