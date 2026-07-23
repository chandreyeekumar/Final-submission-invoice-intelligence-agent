from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SafetyAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: Literal["benign", "malicious", "suspicious"]
    attack_type: str | None = Field(default=None, max_length=100)
    risk_score: float = Field(ge=0, le=1)
    reasons: list[str] = Field(default_factory=list, max_length=50)
    expected_action: Literal["allow", "block", "review"]
    deterministic_matches: list[str] = Field(default_factory=list)
    classifier_used: bool = False
