from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from ai.audit_schemas import (
    AuditCategory,
    AuditIssue,
    AuditReportType,
    AuditSeverity,
    TradingIssueReport,
)
from ai.budget_guard import BudgetGuard
from ai.model_router import OpenAIModelRole, resolve_max_output_tokens, resolve_openai_model
from ai.openai_client import StructuredOpenAIClient
from ai.prompts import SYSTEM_AUDITOR_PROMPT_VERSION, load_system_auditor_prompt
from config.settings import Settings


@dataclass(frozen=True)
class SystemAuditResult:
    report: TradingIssueReport
    schema_valid: bool
    reason: str
    model: str
    role: OpenAIModelRole
    max_output_tokens: int | None
    prompt_version: str = SYSTEM_AUDITOR_PROMPT_VERSION


class SystemAuditor:
    def __init__(
        self,
        settings: Settings,
        client: StructuredOpenAIClient | None = None,
        *,
        deep: bool = False,
    ):
        self.settings = settings
        self.deep = deep
        self.role = OpenAIModelRole.DEEP_AUDITOR if deep else OpenAIModelRole.SYSTEM_AUDITOR
        self.model = resolve_openai_model(settings, self.role)
        self.max_output_tokens = resolve_max_output_tokens(settings, self.role)
        self.client = client or StructuredOpenAIClient(
            api_key=settings.openai_api_key,
            model=self.model,
            role=self.role,
            usage_ledger_enabled=settings.enable_openai_usage_ledger,
        )
        self.system_prompt = load_system_auditor_prompt()

    def audit(
        self,
        *,
        audit_context: dict[str, Any],
        report_type: AuditReportType = AuditReportType.PERIODIC_AUDIT,
        lookback_hours: int = 6,
        usage_session: Session | None = None,
    ) -> SystemAuditResult:
        now = datetime.now(UTC)
        window_start = now - timedelta(hours=lookback_hours)
        payload = {
            **audit_context,
            "report_type": report_type.value,
            "time_window_start": window_start.isoformat(),
            "time_window_end": now.isoformat(),
            "output_limits": {
                "max_issues": self.settings.system_auditor_max_issues,
                "max_evidence_per_issue": self.settings.system_auditor_max_evidence_per_issue,
                "max_text_chars": self.settings.system_auditor_max_text_chars,
            },
            "auditor_permissions": _forced_read_only_permissions(),
        }
        if self.deep and not self.settings.enable_deep_auditor:
            return self._fallback(
                report_type=report_type,
                window_start=window_start,
                window_end=now,
                category=AuditCategory.SECURITY_GUARDRAIL,
                severity=AuditSeverity.MEDIUM,
                title="Deep auditor disabled",
                reason="ENABLE_DEEP_AUDITOR=false",
                input_payload=payload,
            )
        if usage_session is not None:
            budget_guard = BudgetGuard(self.settings, usage_session)
            decision = budget_guard.check_before_openai_call(role=self.role, model=self.model)
            if not decision.allowed:
                reason = ",".join(decision.reason_codes) or "BUDGET_GUARD_BLOCKED"
                budget_guard.record_skipped_budget(
                    role=self.role,
                    model=self.model,
                    operation_name=f"system_audit.{report_type.value.lower()}",
                    reason=reason,
                    input_payload=payload,
                )
                return self._fallback(
                    report_type=report_type,
                    window_start=window_start,
                    window_end=now,
                    category=AuditCategory.OPENAI_BUDGET,
                    severity=AuditSeverity.MEDIUM,
                    title="System audit skipped by BudgetGuard",
                    reason=reason,
                    input_payload=payload,
                )
        try:
            report = self.client.parse(
                system_prompt=self.system_prompt,
                user_payload=payload,
                schema=TradingIssueReport,
                role=self.role,
                model_override=self.model,
                max_output_tokens=self.max_output_tokens,
                usage_session=usage_session,
                operation_name=f"system_audit.{report_type.value.lower()}",
            )
            if not isinstance(report, TradingIssueReport):
                msg = "SystemAuditor returned an object that did not match schema"
                raise ValueError(msg)
            report = normalize_trading_issue_report(
                report.model_copy(
                    update={
                        "model": self.model,
                        "input_hash": _hash_json(payload),
                    }
                ),
                self.settings,
            )
            report = _with_output_hash(report)
            return SystemAuditResult(
                report=report,
                schema_valid=True,
                reason="system audit completed",
                model=self.model,
                role=self.role,
                max_output_tokens=self.max_output_tokens,
            )
        except (ValidationError, ValueError, RuntimeError) as exc:
            category = (
                AuditCategory.OPENAI_SCHEMA
                if isinstance(exc, ValidationError | ValueError)
                else AuditCategory.RUNTIME
            )
            return self._fallback(
                report_type=report_type,
                window_start=window_start,
                window_end=now,
                category=category,
                severity=AuditSeverity.MEDIUM,
                title="System audit failed closed",
                reason=str(exc),
                input_payload=payload,
            )

    def _fallback(
        self,
        *,
        report_type: AuditReportType,
        window_start: datetime,
        window_end: datetime,
        category: AuditCategory,
        severity: AuditSeverity,
        title: str,
        reason: str,
        input_payload: dict[str, Any],
    ) -> SystemAuditResult:
        report = fallback_audit_report(
            report_type=report_type,
            model=self.model,
            window_start=window_start,
            window_end=window_end,
            category=category,
            severity=severity,
            title=title,
            reason=reason,
            input_hash=_hash_json(input_payload),
            max_text_chars=self.settings.system_auditor_max_text_chars,
        )
        return SystemAuditResult(
            report=report,
            schema_valid=False,
            reason=reason,
            model=self.model,
            role=self.role,
            max_output_tokens=self.max_output_tokens,
        )


def fallback_audit_report(
    *,
    report_type: AuditReportType,
    model: str,
    window_start: datetime,
    window_end: datetime,
    category: AuditCategory,
    severity: AuditSeverity,
    title: str,
    reason: str,
    input_hash: str | None,
    max_text_chars: int = 600,
) -> TradingIssueReport:
    max_chars = max(80, max_text_chars)
    safe_reason = _safe_reason(reason, max_chars=max_chars)
    safe_title = _clip_text(title, max_chars)
    issue = AuditIssue(
        severity=severity,
        category=category,
        title=safe_title,
        evidence=[safe_reason],
        suspected_root_cause=safe_reason,
        recommended_human_action="Manual human review is required before changing code or config.",
        requires_codex_change=False,
        auto_fix_allowed=False,
        can_modify_config=False,
        can_modify_strategy=False,
        can_place_order=False,
        related_ids=[],
        confidence=0.5,
    )
    overall_status = "WATCH" if severity in {AuditSeverity.INFO, AuditSeverity.LOW} else "DEGRADED"
    report = TradingIssueReport(
        schema_version="trading_issue_report_v1",
        report_type=report_type,
        created_at=datetime.now(UTC),
        time_window_start=window_start,
        time_window_end=window_end,
        overall_status=overall_status,
        summary=safe_title,
        issues=[issue],
        recommended_next_human_steps=[
            "Review the audit report manually.",
            "Do not change trading configuration without explicit human approval.",
        ],
        report_truncated=len(reason) > max_chars or len(title) > max_chars,
        do_not_auto_modify=True,
        model=model,
        input_hash=input_hash,
        output_hash=None,
    )
    return _with_output_hash(report)


def normalize_trading_issue_report(
    report: TradingIssueReport,
    settings: Settings,
) -> TradingIssueReport:
    max_issues = max(settings.system_auditor_max_issues, 1)
    max_evidence = max(settings.system_auditor_max_evidence_per_issue, 1)
    max_chars = max(settings.system_auditor_max_text_chars, 80)
    truncated = report.report_truncated
    issues: list[AuditIssue] = []
    if len(report.issues) > max_issues:
        truncated = True
    for issue in report.issues[:max_issues]:
        if len(issue.evidence) > max_evidence:
            truncated = True
        clipped_evidence = []
        for item in issue.evidence[:max_evidence]:
            clipped, did_clip = _clip_text_with_flag(item, max_chars)
            truncated = truncated or did_clip
            clipped_evidence.append(clipped)
        title, title_clipped = _clip_text_with_flag(issue.title, max_chars)
        root_cause, root_clipped = _clip_text_with_flag(issue.suspected_root_cause, max_chars)
        action, action_clipped = _clip_text_with_flag(issue.recommended_human_action, max_chars)
        truncated = truncated or title_clipped or root_clipped or action_clipped
        issues.append(
            issue.model_copy(
                update={
                    "title": title,
                    "evidence": clipped_evidence,
                    "suspected_root_cause": root_cause,
                    "recommended_human_action": action,
                    "auto_fix_allowed": False,
                    "can_modify_config": False,
                    "can_modify_strategy": False,
                    "can_place_order": False,
                }
            )
        )
    summary, summary_clipped = _clip_text_with_flag(report.summary, max_chars)
    truncated = truncated or summary_clipped
    steps: list[str] = []
    for step in report.recommended_next_human_steps[:max_issues]:
        clipped_step, step_clipped = _clip_text_with_flag(step, max_chars)
        truncated = truncated or step_clipped
        steps.append(clipped_step)
    if len(report.recommended_next_human_steps) > max_issues:
        truncated = True
    return report.model_copy(
        update={
            "summary": summary,
            "issues": issues,
            "recommended_next_human_steps": steps,
            "report_truncated": truncated,
            "do_not_auto_modify": True,
        }
    )


def _forced_read_only_permissions() -> dict[str, bool]:
    return {
        "auto_fix_allowed": False,
        "can_call_codex": False,
        "can_modify_config": False,
        "can_modify_strategy": False,
        "can_place_order": False,
    }


def _hash_json(payload: dict[str, Any]) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _with_output_hash(report: TradingIssueReport) -> TradingIssueReport:
    unhashed = report.model_copy(update={"output_hash": None})
    return unhashed.model_copy(update={"output_hash": _hash_json(unhashed.model_dump(mode="json"))})


def _safe_reason(value: str, *, max_chars: int) -> str:
    return _clip_text(value.replace("sk-", "[REDACTED]-"), max_chars)


def _clip_text(value: str, max_chars: int) -> str:
    return _clip_text_with_flag(value, max_chars)[0]


def _clip_text_with_flag(value: str, max_chars: int) -> tuple[str, bool]:
    text = str(value)
    if len(text) <= max_chars:
        return text, False
    suffix = " [truncated]"
    keep = max(max_chars - len(suffix), 1)
    return text[:keep].rstrip() + suffix, True
