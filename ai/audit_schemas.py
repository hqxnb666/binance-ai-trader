from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AuditReportType(StrEnum):
    PERIODIC_AUDIT = "PERIODIC_AUDIT"
    INCIDENT_AUDIT = "INCIDENT_AUDIT"
    DAILY_AUDIT = "DAILY_AUDIT"
    DEEP_AUDIT = "DEEP_AUDIT"


class AuditSeverity(StrEnum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AuditCategory(StrEnum):
    STRATEGY_PLAN = "STRATEGY_PLAN"
    SIGNAL_REVIEW = "SIGNAL_REVIEW"
    RISK_ENGINE = "RISK_ENGINE"
    ORDER_MANAGER = "ORDER_MANAGER"
    DATA_QUALITY = "DATA_QUALITY"
    OPENAI_BUDGET = "OPENAI_BUDGET"
    OPENAI_SCHEMA = "OPENAI_SCHEMA"
    RUNTIME = "RUNTIME"
    BINANCE_CONNECTIVITY = "BINANCE_CONNECTIVITY"
    ACCOUNT_POSITION = "ACCOUNT_POSITION"
    SECURITY_GUARDRAIL = "SECURITY_GUARDRAIL"
    UNKNOWN = "UNKNOWN"


class AuditIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: AuditSeverity
    category: AuditCategory
    title: str
    evidence: list[str]
    suspected_root_cause: str
    recommended_human_action: str
    requires_codex_change: bool
    auto_fix_allowed: Literal[False]
    can_modify_config: Literal[False]
    can_modify_strategy: Literal[False]
    can_place_order: Literal[False]
    related_ids: list[str]
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_issue(self) -> AuditIssue:
        if self.confidence < 0.6:
            action = self.recommended_human_action.lower()
            if not any(token in action for token in ("human", "manual", "review")):
                msg = "low confidence issue must recommend human/manual review"
                raise ValueError(msg)
        return self


class TradingIssueReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["trading_issue_report_v1"]
    report_type: AuditReportType
    created_at: datetime
    time_window_start: datetime
    time_window_end: datetime
    overall_status: Literal["OK", "WATCH", "DEGRADED", "CRITICAL"]
    summary: str
    issues: list[AuditIssue]
    recommended_next_human_steps: list[str]
    do_not_auto_modify: Literal[True]
    model: str
    input_hash: str | None = Field(...)
    output_hash: str | None = Field(...)

    @field_validator("issues")
    @classmethod
    def issues_required_list(cls, value: list[AuditIssue]) -> list[AuditIssue]:
        return value

    @model_validator(mode="after")
    def validate_report(self) -> TradingIssueReport:
        highest = highest_severity(self.issues)
        if highest == AuditSeverity.CRITICAL and self.overall_status == "OK":
            msg = "CRITICAL issue cannot have overall_status OK"
            raise ValueError(msg)
        if not self.issues and self.overall_status not in {"OK", "WATCH"}:
            msg = "empty issues require overall_status OK or WATCH"
            raise ValueError(msg)
        return self


def highest_severity(issues: list[AuditIssue]) -> AuditSeverity:
    if not issues:
        return AuditSeverity.INFO
    rank = {
        AuditSeverity.INFO: 0,
        AuditSeverity.LOW: 1,
        AuditSeverity.MEDIUM: 2,
        AuditSeverity.HIGH: 3,
        AuditSeverity.CRITICAL: 4,
    }
    return max(issues, key=lambda issue: rank[issue.severity]).severity
