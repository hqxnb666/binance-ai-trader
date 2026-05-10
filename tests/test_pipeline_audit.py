from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from journal.models import Base
from journal.pipeline_audit import (
    PipelineStage,
    PipelineStatus,
    pipeline_audits_by_run_id,
    record_pipeline_stage,
)


def test_pipeline_audit_records_stage() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(engine, class_=Session, expire_on_commit=False, future=True)()
    record_pipeline_stage(
        session,
        run_id="run-1",
        symbol="BTCUSDT",
        stage=PipelineStage.SNAPSHOT_CREATED,
        status=PipelineStatus.OK,
        raw_context_json={"x": 1},
    )
    rows = pipeline_audits_by_run_id(session, "run-1")
    assert len(rows) == 1
    assert rows[0].stage == "SNAPSHOT_CREATED"
    assert rows[0].raw_context_json == {"x": 1}

