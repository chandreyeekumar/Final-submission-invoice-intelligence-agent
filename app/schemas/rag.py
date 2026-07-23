from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class VendorCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor_id: str
    legal_name: str
    distance: float
    metadata: dict = Field(default_factory=dict)


class RAGDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["verified", "unknown", "ambiguous", "mismatch", "not_applicable"]
    matched_vendor_id: str | None = None
    matched_legal_name: str | None = None
    candidates: list[VendorCandidate] = Field(default_factory=list)
    exact_checks: dict[str, bool | None] = Field(default_factory=dict)
    template_evidence: list[dict] = Field(default_factory=list)
    history_evidence: list[dict] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    recommended_action: Literal["continue", "correct_name", "human_review"] = "continue"
