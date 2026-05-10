from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import load_settings
from journal.models import Base
from shadow.recorder import ShadowModeRecorder
from shadow.schemas import ShadowDecisionType
from shadow.store import list_recent_shadow_decisions


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, class_=Session, expire_on_commit=False, future=True)()


def test_shadow_recorder_records_decision_types_without_broker() -> None:
    settings = load_settings()
    session = _session()
    recorder = ShadowModeRecorder(settings)
    recorder.record_would_place_order(
        session,
        symbol="BTCUSDT",
        side="BUY",
        reason="dry run approved",
        reason_codes=["WOULD_PLACE_ORDER"],
        simulated_entry_price=Decimal("100"),
        simulated_quantity=Decimal("0.1"),
        simulated_notional=Decimal("10"),
        dry_run=True,
        order_execution_enabled=False,
    )
    recorder.record_ai_rejected(
        session,
        symbol="BTCUSDT",
        side="BUY",
        reason="AI rejected",
        reason_codes=["AI_REJECTED"],
        dry_run=True,
        order_execution_enabled=False,
    )
    recorder.record_risk_rejected(
        session,
        symbol="BTCUSDT",
        side="BUY",
        reason="Risk rejected",
        reason_codes=["RISK_REJECTED"],
        dry_run=True,
        order_execution_enabled=False,
    )
    recorder.record_data_quality_blocked(
        session,
        symbol="BTCUSDT",
        side="BUY",
        reason="DQ block",
        reason_codes=["DATA_QUALITY_BLOCKED"],
        dry_run=True,
        order_execution_enabled=False,
    )
    types = {record.decision_type for record in list_recent_shadow_decisions(session, limit=10)}
    assert ShadowDecisionType.WOULD_PLACE_ORDER.value in types
    assert ShadowDecisionType.AI_REJECTED.value in types
    assert ShadowDecisionType.RISK_REJECTED.value in types
    assert ShadowDecisionType.DATA_QUALITY_BLOCKED.value in types


def test_shadow_recorder_can_be_disabled_for_real_order_path() -> None:
    settings = load_settings()
    session = _session()
    recorder = ShadowModeRecorder(settings)
    record = recorder.record_would_place_order(
        session,
        symbol="BTCUSDT",
        side="BUY",
        reason="real path",
        dry_run=False,
        order_execution_enabled=True,
    )
    assert record is None
