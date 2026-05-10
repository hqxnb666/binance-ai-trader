from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pandas as pd
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, sessionmaker

from account.schemas import AccountPositionSnapshot, RuntimeAccountState, RuntimePositionState
from account.state_service import AccountPositionService
from ai.audit_schemas import AuditReportType
from ai.budget_guard import budget_status
from ai.context_builder import (
    build_audit_context,
    build_signal_review_context,
    build_strategy_context,
    summarize_strategy_plan,
)
from ai.schemas import (
    MarketRegime,
    RiskLevel,
    SignalDecision,
    SignalReview,
    SignalSide,
)
from ai.schemas import (
    TradeReview as TradeReviewSchema,
)
from ai.signal_reviewer import SignalReviewer, SignalReviewResult
from ai.strategy_planner import StrategyPlanner, fail_closed_strategy_output
from ai.strategy_schemas import StrategyPlanningMode
from ai.system_auditor import SystemAuditor
from ai.trade_reviewer import TradeReviewer
from binance_client.exchange_info import SymbolFilters, parse_all_symbol_filters
from binance_client.market_stream import KlineStream
from binance_client.user_stream import UserDataStreamClient
from broker.base import Broker, OrderRequest
from broker.binance_spot_testnet import BinanceSpotTestnetBroker
from config.settings import Settings
from data_quality.gate import DataQualityGate
from data_quality.schemas import DataQualitySeverity, DataQualitySnapshot
from features.kline_store import binance_klines_to_dataframe, persist_kline_event
from features.market_snapshot import build_market_snapshot
from journal.audit_store import (
    audit_record_to_dict,
    get_latest_trading_issue_report,
    save_trading_issue_report,
)
from journal.models import AIAnalysis, OrderRecord, RiskDecision, StrategySignal, TradeReview
from journal.openai_usage_store import summarize_openai_usage
from journal.pipeline_audit import PipelineStage, PipelineStatus, record_pipeline_stage
from journal.strategy_plan_store import (
    get_active_strategy_plan,
    list_recent_strategy_plans,
    save_strategy_plan,
)
from orders.order_manager import OrderManager, generate_client_order_id
from orders.reconciliation import reconcile_open_orders
from risk.circuit_breaker import CircuitBreaker
from risk.position_sizer import PositionSizer
from risk.risk_engine import AccountState, MarketHealth, PositionState, RiskEngine
from runtime.daemon_state import DaemonState, RuntimeLogBuffer
from runtime.health import RuntimeHealth
from shadow.evaluator import ShadowModeEvaluator
from shadow.recorder import ShadowModeRecorder
from shadow.schemas import ShadowDecisionType
from shadow.store import (
    build_shadow_report,
    list_open_shadow_decisions,
    list_recent_shadow_decisions,
)
from strategies.ema_trend import EmaTrendStrategy

logger = logging.getLogger(__name__)


def _strategy_plan_record_status(result: Any) -> str:
    if not result.schema_valid:
        return "FAILED"
    action = str(getattr(result.output, "plan_action", ""))
    if action in {"CREATE", "EXPIRE", "NO_TRADE"}:
        return "ACTIVE"
    return "SUPERSEDED"


class TestnetTradingDaemon:
    def __init__(
        self,
        *,
        settings: Settings,
        session_factory: sessionmaker[Session],
        broker: Broker | None = None,
        signal_reviewer: SignalReviewer | None = None,
        poll_interval_seconds: float = 60.0,
        reconciliation_interval_seconds: float = 30.0,
        dry_run: bool | None = None,
        order_execution_enabled: bool | None = None,
    ):
        self.settings = settings
        self.session_factory = session_factory
        self.broker = broker or BinanceSpotTestnetBroker(settings)
        self.signal_reviewer = signal_reviewer or SignalReviewer(settings)
        self.strategy_planner = StrategyPlanner(settings)
        self.system_auditor = SystemAuditor(settings)
        self.data_quality_gate = DataQualityGate(settings)
        self.shadow_recorder = ShadowModeRecorder(settings)
        self.shadow_evaluator = ShadowModeEvaluator(settings)
        self.strategy = EmaTrendStrategy(settings.strategy.ema_trend)
        self.poll_interval_seconds = poll_interval_seconds
        self.reconciliation_interval_seconds = reconciliation_interval_seconds
        self.dry_run = settings.trading_dry_run if dry_run is None else dry_run
        self.order_execution_enabled = (
            settings.order_execution_enabled
            if order_execution_enabled is None
            else order_execution_enabled
        )
        self.account_position_service = AccountPositionService(
            settings=settings,
            broker=self.broker,
            dry_run=self.dry_run,
            order_execution_enabled=self.order_execution_enabled,
        )
        self.risk_engine = RiskEngine(settings)
        self.state = DaemonState.STOPPED
        self.stop_event = asyncio.Event()
        self.tasks: list[asyncio.Task[None]] = []
        self.market_stream = KlineStream(
            settings.binance_spot_testnet_stream_base,
            settings.symbols.enabled_symbols,
            settings.symbols.timeframes.entry,
        )
        self.user_stream: UserDataStreamClient | None = self._build_user_stream()
        self.logs = RuntimeLogBuffer()
        self.last_error: str | None = None
        self.last_kline_time: datetime | None = None
        self.last_user_event_time: datetime | None = None
        self.last_rest_poll_ok_at: datetime | None = None
        self.frames: dict[tuple[str, str], pd.DataFrame] = {}
        self.exchange_filters: dict[str, SymbolFilters] = {}
        self.last_snapshots: dict[str, dict[str, Any]] = {}
        self.last_ai_reviews: list[dict[str, Any]] = []
        self.last_risk_decisions: list[dict[str, Any]] = []
        self.active_strategy_plan: dict[str, Any] | None = None
        self.last_strategy_plan_at: datetime | None = None
        self.latest_audit_report: dict[str, Any] | None = None
        self.latest_data_quality_snapshot: DataQualitySnapshot | None = None
        self.latest_account_state: RuntimeAccountState | None = None
        self.latest_position_states: dict[str, RuntimePositionState] = {}
        self.latest_account_position_snapshot: AccountPositionSnapshot | None = None
        self.last_shadow_evaluation_at: datetime | None = None

    async def start(self) -> dict[str, Any]:
        if self.state in {DaemonState.STARTING, DaemonState.RUNNING}:
            return {"started": False, "state": self.state.value, "reason": "already running"}
        if self.settings.trading_mode == "live":
            msg = "TestnetTradingDaemon refuses live trading mode"
            self.last_error = msg
            self.state = DaemonState.ERROR
            raise RuntimeError(msg)
        self.state = DaemonState.STARTING
        self.stop_event = asyncio.Event()
        self._log("daemon_starting", dry_run=self.dry_run)
        self.tasks = [
            asyncio.create_task(self._task_wrapper("rest_poll", self._rest_poll_worker())),
            asyncio.create_task(self._task_wrapper("market_stream", self._market_stream_worker())),
            asyncio.create_task(
                self._task_wrapper("reconciliation", self._reconciliation_worker())
            ),
        ]
        if self.settings.enable_strategy_planner:
            self.tasks.append(
                asyncio.create_task(
                    self._task_wrapper("strategy_planner", self._strategy_planner_worker())
                )
            )
        if self.settings.enable_system_auditor:
            self.tasks.append(
                asyncio.create_task(
                    self._task_wrapper("system_auditor", self._system_auditor_worker())
                )
            )
        if self.settings.enable_shadow_mode:
            self.tasks.append(
                asyncio.create_task(
                    self._task_wrapper("shadow_evaluator", self._shadow_evaluator_worker())
                )
            )
        if self.user_stream is not None:
            self.tasks.append(
                asyncio.create_task(self._task_wrapper("user_stream", self._user_stream_worker()))
            )
        else:
            self._log("user_stream_skipped", level="WARNING", reason="missing Testnet API key")
        self.state = DaemonState.RUNNING
        self._log("daemon_running", dry_run=self.dry_run)
        return {"started": True, "state": self.state.value, "dry_run": self.dry_run}

    async def stop(self) -> dict[str, Any]:
        if self.state == DaemonState.STOPPED:
            return {"stopped": False, "state": self.state.value, "reason": "already stopped"}
        self.state = DaemonState.STOPPING
        self._log("daemon_stopping")
        self.stop_event.set()
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        await self._close_broker()
        self.state = DaemonState.STOPPED
        self._log("daemon_stopped")
        return {"stopped": True, "state": self.state.value}

    def health(self) -> RuntimeHealth:
        market_health = self.market_stream.health
        user_health = self.user_stream.health if self.user_stream else None
        data_delay = self._data_delay_seconds()
        audit_status = self._audit_status()
        data_quality_status = self._data_quality_status()
        health_warning = bool(audit_status.get("health_warning")) or data_quality_status.get(
            "overall_status"
        ) in {"DEGRADED", "CRITICAL"}
        return RuntimeHealth(
            state=self.state,
            trading_mode="testnet",
            symbols=self.settings.symbols.enabled_symbols,
            market_stream_connected=self._market_connected_for_runtime(),
            user_stream_connected=bool(user_health and user_health.is_healthy()),
            last_kline_time=self.last_kline_time.isoformat() if self.last_kline_time else None,
            last_user_event_time=self.last_user_event_time.isoformat()
            if self.last_user_event_time
            else None,
            last_error=self.last_error,
            dry_run=self.dry_run,
            ai_enabled=self.settings.ai_analysis_enabled,
            order_execution_enabled=self.order_execution_enabled,
            reconnecting=market_health.reconnecting
            or bool(user_health and user_health.reconnecting),
            data_delay_seconds=data_delay,
            market_stream=market_health.as_dict(),
            user_stream=user_health.as_dict() if user_health else {"connected": False},
            budget_status=self._budget_status(),
            audit_status=audit_status,
            data_quality_status=data_quality_status,
            account_position_status=self._account_position_status(),
            risk_runtime_status=self._risk_runtime_status(),
            kill_switch_state=self._kill_switch_state(),
            shadow_status=self._shadow_status(),
            health_warning=health_warning,
        )

    async def _task_wrapper(self, name: str, coro: Any) -> None:
        try:
            await coro
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - keep daemon observable
            self.last_error = f"{name}: {exc}"
            self.state = DaemonState.ERROR
            self._log("daemon_task_error", level="ERROR", task=name, error=str(exc))
            self.stop_event.set()

    async def _rest_poll_worker(self) -> None:
        while not self.stop_event.is_set():
            try:
                await self._refresh_exchange_filters()
                for symbol in self.settings.symbols.enabled_symbols:
                    await self._refresh_symbol_frames(symbol)
                await self._refresh_account_positions()
                for symbol in self.settings.symbols.enabled_symbols:
                    await self._process_symbol(symbol)
                self.last_rest_poll_ok_at = datetime.now(UTC)
            except Exception as exc:  # noqa: BLE001 - daemon should keep polling
                self.last_error = str(exc)
                self._log("rest_poll_failed", level="ERROR", error=str(exc))
            await self._sleep_until_stop(self.poll_interval_seconds)

    async def _market_stream_worker(self) -> None:
        async for event in self.market_stream.messages(self.stop_event):
            try:
                if event.get("e") != "kline":
                    continue
                symbol = str(event.get("s", "")).upper()
                kline = event.get("k", {})
                self.last_kline_time = datetime.fromtimestamp(int(kline.get("T", 0)) / 1000, tz=UTC)
                if kline.get("x"):
                    with self.session_factory() as session:
                        persist_kline_event(
                            session,
                            symbol,
                            str(kline.get("i", self.settings.symbols.timeframes.entry)),
                            event,
                        )
                        self._audit(
                            session,
                            run_id=f"kline-{symbol}-{kline.get('T')}",
                            symbol=symbol,
                            stage=PipelineStage.KLINE_RECEIVED,
                            status=PipelineStatus.OK,
                            raw_context_json={"event_time": kline.get("T")},
                        )
                        session.commit()
                    self._log("kline_closed", symbol=symbol, timeframe=kline.get("i"))
            except Exception as exc:  # noqa: BLE001
                self.last_error = str(exc)
                self._log("market_stream_event_failed", level="ERROR", error=str(exc))

    async def _user_stream_worker(self) -> None:
        if self.user_stream is None:
            return
        async for event in self.user_stream.events(self.stop_event):
            self.last_user_event_time = datetime.now(UTC)
            with self.session_factory() as session:
                manager = OrderManager(broker=self.broker, session=session, trading_mode="testnet")
                record = manager.handle_user_stream_event(event)
                if record is not None and record.status in {
                    "FILLED",
                    "CANCELED",
                    "REJECTED",
                    "EXPIRED",
                }:
                    await self._maybe_trade_review(session, record)
                if record is not None:
                    self._audit(
                        session,
                        run_id=f"order-{record.client_order_id}",
                        symbol=record.symbol,
                        stage=PipelineStage.USER_STREAM_UPDATED,
                        status=PipelineStatus.OK,
                        order_record_id=record.id,
                        raw_context_json={"status": record.status, "event_type": event.get("e")},
                    )
                session.commit()

    async def _reconciliation_worker(self) -> None:
        while not self.stop_event.is_set():
            if self.order_execution_enabled and not self.dry_run:
                try:
                    with self.session_factory() as session:
                        updated = await reconcile_open_orders(broker=self.broker, session=session)
                        session.commit()
                    self._log("reconciliation_completed", updated=updated)
                except Exception as exc:  # noqa: BLE001
                    self.last_error = str(exc)
                    self._log("reconciliation_failed", level="ERROR", error=str(exc))
            await self._sleep_until_stop(self.reconciliation_interval_seconds)

    async def _strategy_planner_worker(self) -> None:
        while not self.stop_event.is_set():
            try:
                with self.session_factory() as session:
                    active = get_active_strategy_plan(session)
                    planning_mode = (
                        StrategyPlanningMode.FULL_REPLAN
                        if active is None
                        else StrategyPlanningMode.REFRESH
                    )
                    context = build_strategy_context(
                        self.settings,
                        self.settings.symbols.enabled_symbols,
                        self.last_snapshots,
                        active,
                        account_state=_account_context(self.latest_account_state),
                        positions=_position_contexts(
                            self.settings.symbols.enabled_symbols,
                            self.latest_position_states,
                        ),
                        budget_status=budget_status(self.settings, session),
                        data_quality_summary={
                            **self._data_quality_status(),
                            "source": "runtime_data_quality_gate",
                        },
                    )
                    dq_snapshot = self._evaluate_data_quality_runtime(
                        active_strategy_plan=summarize_strategy_plan(active)
                    )
                    if (
                        self.settings.enable_data_quality_gate
                        and self.settings.data_quality_block_strategy_planner_on_critical
                        and dq_snapshot.overall_status == DataQualitySeverity.CRITICAL
                    ):
                        output = fail_closed_strategy_output(
                            planning_mode=planning_mode,
                            previous_plan_id=str(active.id) if active else None,
                            reason_code="DATA_QUALITY_BLOCKED",
                            explanation="StrategyPlanner blocked by critical DataQualityGate.",
                        )
                        record = save_strategy_plan(
                            session,
                            plan=output,
                            raw_input_json={
                                "context": context,
                                "data_quality": dq_snapshot.model_dump(mode="json"),
                            },
                            model="data_quality_gate",
                            status="ACTIVE",
                        )
                        session.commit()
                        self.active_strategy_plan = summarize_strategy_plan(record)
                        self.last_strategy_plan_at = datetime.now(UTC)
                        self._log(
                            "data_quality_blocked_strategy_planner",
                            level="WARNING",
                            overall_status=dq_snapshot.overall_status.value,
                            reason_codes=dq_snapshot.reason_codes,
                        )
                    else:
                        result = await asyncio.to_thread(
                            self.strategy_planner.plan,
                            planning_mode=planning_mode,
                            context=context,
                            active_plan_id=str(active.id) if active else None,
                            usage_session=session,
                        )
                        record_status = _strategy_plan_record_status(result)
                        record = save_strategy_plan(
                            session,
                            plan=result.output,
                            raw_input_json=context,
                            model=result.model,
                            status=record_status,
                        )
                        session.commit()
                        self.active_strategy_plan = summarize_strategy_plan(
                            record if record_status == "ACTIVE" else active
                        )
                        self.last_strategy_plan_at = datetime.now(UTC)
                        self._log(
                            "strategy_plan_completed",
                            model=result.model,
                            planning_mode=planning_mode.value,
                            schema_valid=result.schema_valid,
                        )
            except Exception as exc:  # noqa: BLE001
                self.last_error = str(exc)
                self._log("strategy_plan_failed", level="ERROR", error=str(exc))
            await self._sleep_until_stop(self.settings.openai_strategy_interval_minutes * 60)

    async def _system_auditor_worker(self) -> None:
        while not self.stop_event.is_set():
            try:
                await self.run_system_audit_once()
            except Exception as exc:  # noqa: BLE001 - audit must not stop trading daemon
                self._log("system_audit_failed", level="WARNING", error=str(exc))
            await self._sleep_until_stop(self.settings.system_audit_interval_minutes * 60)

    async def _shadow_evaluator_worker(self) -> None:
        while not self.stop_event.is_set():
            try:
                await self.run_shadow_evaluation_once()
            except Exception as exc:  # noqa: BLE001 - shadow eval must not stop daemon
                self._log("shadow_evaluation_failed", level="WARNING", error=str(exc))
            await self._sleep_until_stop(
                max(self.settings.shadow_mode_evaluation_interval_minutes, 1) * 60
            )

    async def run_shadow_evaluation_once(self) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            current_prices = {
                symbol: Decimal(str(snapshot["price"]))
                for symbol, snapshot in self.last_snapshots.items()
                if snapshot.get("price") is not None
            }
            with self.session_factory() as session:
                evaluations = self.shadow_evaluator.evaluate_open_decisions(
                    session,
                    current_prices=current_prices,
                )
                session.commit()
            self.last_shadow_evaluation_at = datetime.now(UTC)
            self._log("shadow_evaluation_completed", evaluated=len(evaluations))
            return {"evaluated": len(evaluations), "evaluations": evaluations}

        return await asyncio.to_thread(_run)

    async def run_system_audit_once(
        self,
        *,
        report_type: AuditReportType = AuditReportType.PERIODIC_AUDIT,
        lookback_hours: int | None = None,
        deep: bool = False,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._run_system_audit_once_sync,
            report_type,
            lookback_hours or self.settings.system_audit_lookback_hours,
            deep,
        )

    def _run_system_audit_once_sync(
        self,
        report_type: AuditReportType,
        lookback_hours: int,
        deep: bool,
    ) -> dict[str, Any]:
        with self.session_factory() as session:
            context = self._build_audit_context(session)
            auditor = SystemAuditor(self.settings, deep=deep)
            result = auditor.audit(
                audit_context=context,
                report_type=report_type,
                lookback_hours=lookback_hours,
                usage_session=session,
            )
            record = save_trading_issue_report(
                session,
                report=result.report,
                raw_input_json=context,
            )
            session.commit()
            payload = audit_record_to_dict(record)
            self.latest_audit_report = payload
            self._log(
                "system_audit_completed",
                model=result.model,
                schema_valid=result.schema_valid,
                overall_status=result.report.overall_status,
                issue_count=len(result.report.issues),
            )
            return payload

    async def _refresh_exchange_filters(self) -> None:
        if self.exchange_filters:
            return
        exchange_info = await self.broker.get_exchange_info()
        self.exchange_filters = parse_all_symbol_filters(exchange_info)

    async def _refresh_symbol_frames(self, symbol: str) -> None:
        entry_tf = self.settings.symbols.timeframes.entry
        trend_tf = self.settings.symbols.timeframes.trend
        entry_klines = await self.broker.get_klines(symbol, entry_tf, 120)
        trend_klines = await self.broker.get_klines(symbol, trend_tf, 120)
        self.frames[(symbol, entry_tf)] = binance_klines_to_dataframe(entry_klines)
        self.frames[(symbol, trend_tf)] = binance_klines_to_dataframe(trend_klines)
        if entry_klines:
            self.last_kline_time = datetime.fromtimestamp(int(entry_klines[-1][6]) / 1000, tz=UTC)

    async def _refresh_account_positions(self) -> None:
        latest_prices: dict[str, Decimal] = {}
        entry_tf = self.settings.symbols.timeframes.entry
        for symbol in self.settings.symbols.enabled_symbols:
            frame = self.frames.get((symbol, entry_tf))
            if frame is not None and not frame.empty:
                latest_prices[symbol] = Decimal(str(frame["close"].iloc[-1]))
        snapshot = await self.account_position_service.refresh_all(
            self.settings.symbols.enabled_symbols,
            latest_prices,
        )
        self.latest_account_position_snapshot = snapshot
        self.latest_account_state = snapshot.account
        self.latest_position_states = {position.symbol: position for position in snapshot.positions}
        self._log(
            "account_position_refreshed",
            account_status=snapshot.account.status.value,
            safe_for_real_order=snapshot.safe_for_real_order,
        )

    async def _process_symbol(self, symbol: str) -> None:
        run_id = f"runtime-{uuid.uuid4().hex[:16]}"
        entry_tf = self.settings.symbols.timeframes.entry
        trend_tf = self.settings.symbols.timeframes.trend
        entry_df = self.frames.get((symbol, entry_tf), pd.DataFrame())
        trend_df = self.frames.get((symbol, trend_tf), pd.DataFrame())
        if entry_df.empty or trend_df.empty:
            return
        signal = self.strategy.generate_signal(
            symbol=symbol,
            entry_df=entry_df,
            trend_df=trend_df,
            current_position_pct=0,
            ws_health="ok" if self._market_connected_for_runtime() else "disconnected",
        )
        snapshot = build_market_snapshot(
            symbol=symbol,
            entry_df=entry_df,
            trend_df=trend_df,
            strategy_signal=signal,
            ws_health="ok" if self._market_connected_for_runtime() else "disconnected",
            data_delay_seconds=self._data_delay_seconds(),
        ).compact_dict()
        self.last_snapshots[symbol] = snapshot
        dq_snapshot = self._evaluate_data_quality_signal(
            snapshot=snapshot,
            entry_df=entry_df,
            trend_df=trend_df,
            active_strategy_plan=self.active_strategy_plan,
        )
        self._log("snapshot_created", symbol=symbol)
        if signal is None:
            with self.session_factory() as session:
                self._audit(
                    session,
                    run_id=run_id,
                    symbol=symbol,
                    stage=PipelineStage.SNAPSHOT_CREATED,
                    status=PipelineStatus.OK,
                    raw_context_json={"snapshot": snapshot, "signal": None},
                )
                self._record_shadow(
                    session,
                    decision_type=ShadowDecisionType.STRATEGY_NO_TRADE,
                    symbol=symbol,
                    side="HOLD",
                    reason="Strategy generated no trade candidate.",
                    reason_codes=["STRATEGY_NO_TRADE"],
                    context_summary={
                        "strategy_name": self.strategy.name,
                        "data_quality_status": dq_snapshot.overall_status.value,
                        "price_source": "market_snapshot",
                    },
                )
                session.commit()
            return
        with self.session_factory() as session:
            active_plan = get_active_strategy_plan(session)
            self.active_strategy_plan = summarize_strategy_plan(active_plan)
            self._audit(
                session,
                run_id=run_id,
                symbol=symbol,
                stage=PipelineStage.SNAPSHOT_CREATED,
                status=PipelineStatus.OK,
                raw_context_json={"snapshot": snapshot},
            )
            signal_record = StrategySignal(**signal.model_dump())
            session.add(signal_record)
            session.flush()
            self._audit(
                session,
                run_id=run_id,
                symbol=symbol,
                stage=PipelineStage.SIGNAL_GENERATED,
                status=PipelineStatus.OK,
                signal_id=signal_record.id,
                raw_context_json=signal.model_dump(mode="json"),
            )
            self._log("strategy_signal_generated", symbol=symbol, side=signal.side)
            if (
                self.settings.enable_data_quality_gate
                and self.settings.data_quality_block_signal_review_on_critical
                and not dq_snapshot.safe_for_signal_review
            ):
                ai_result = self._data_quality_blocked_signal_result(
                    snapshot=snapshot,
                    reason="SignalReview blocked by DataQualityGate",
                    data_quality=dq_snapshot,
                )
                ai_record = AIAnalysis(
                    **SignalReviewer.analysis_payload(
                        snapshot=ai_result.input_payload or snapshot,
                        review=ai_result.review,
                        schema_valid=ai_result.schema_valid,
                        model=ai_result.actual_model,
                    )
                )
                session.add(ai_record)
                session.flush()
                self._audit(
                    session,
                    run_id=run_id,
                    symbol=symbol,
                    stage=PipelineStage.AI_REVIEWED,
                    status=PipelineStatus.REJECTED,
                    signal_id=signal_record.id,
                    ai_analysis_id=ai_record.id,
                    raw_context_json=ai_result.review.model_dump(mode="json"),
                    error_message="DATA_QUALITY_BLOCKED",
                )
                self.last_ai_reviews.append(
                    {
                        "symbol": symbol,
                        "schema_valid": ai_result.schema_valid,
                        "actual_model": ai_result.actual_model,
                        "active_strategy_plan_id": ai_result.active_strategy_plan_id,
                        "review": ai_result.review.model_dump(mode="json"),
                    }
                )
                self.last_ai_reviews = self.last_ai_reviews[-20:]
                self._record_shadow(
                    session,
                    decision_type=ShadowDecisionType.DATA_QUALITY_BLOCKED,
                    symbol=symbol,
                    side=signal.side,
                    reason="SignalReview blocked by DataQualityGate.",
                    reason_codes=["DATA_QUALITY_BLOCKED", *dq_snapshot.reason_codes],
                    signal_review_id=ai_record.id,
                    data_quality_snapshot_id=run_id,
                    context_summary={
                        "strategy_name": signal.strategy_name,
                        "signal_type": signal.signal_type,
                        "data_quality_status": dq_snapshot.overall_status.value,
                        "notes": dq_snapshot.reason_codes[:5],
                    },
                )
                self._log(
                    "data_quality_blocked_signal_review",
                    level="WARNING",
                    symbol=symbol,
                    reason_codes=dq_snapshot.reason_codes,
                )
                session.commit()
                return
            self._log("ai_review_started", symbol=symbol)
            ai_result: SignalReviewResult = await asyncio.to_thread(
                self.signal_reviewer.review_with_schema,
                snapshot,
                active_strategy_plan=active_plan,
                signal_review_context=build_signal_review_context(
                    current_snapshot=snapshot,
                    candidate_signal=signal.model_dump(mode="json"),
                    active_strategy_plan=active_plan,
                    position_state=_position_context(
                        self.latest_position_states.get(symbol)
                    ),
                    risk_state={
                        "status": "pre_risk_check",
                        "kill_switch_state": self._kill_switch_state(),
                    },
                    account_state_summary=_account_context(self.latest_account_state),
                    settings=self.settings,
                    data_quality_flags=[]
                    if dq_snapshot.safe_for_signal_review
                    else dq_snapshot.reason_codes,
                    budget_status=budget_status(self.settings, session),
                ),
                usage_session=session,
            )
            self._log(
                "ai_review_completed",
                symbol=symbol,
                decision=ai_result.review.decision.value,
                schema_valid=ai_result.schema_valid,
            )
            ai_record = AIAnalysis(
                **SignalReviewer.analysis_payload(
                    snapshot=ai_result.input_payload or snapshot,
                    review=ai_result.review,
                    schema_valid=ai_result.schema_valid,
                    model=ai_result.actual_model,
                )
            )
            session.add(ai_record)
            session.flush()
            self._audit(
                session,
                run_id=run_id,
                symbol=symbol,
                stage=PipelineStage.AI_REVIEWED,
                status=PipelineStatus.OK if ai_result.schema_valid else PipelineStatus.ERROR,
                signal_id=signal_record.id,
                ai_analysis_id=ai_record.id,
                raw_context_json=ai_result.review.model_dump(mode="json"),
                error_message=None if ai_result.schema_valid else ai_result.reason,
            )
            self.last_ai_reviews.append(
                {
                    "symbol": symbol,
                    "schema_valid": ai_result.schema_valid,
                    "actual_model": ai_result.actual_model,
                    "active_strategy_plan_id": ai_result.active_strategy_plan_id,
                    "review": ai_result.review.model_dump(mode="json"),
                }
            )
            self.last_ai_reviews = self.last_ai_reviews[-20:]
            if not ai_result.approved_for_risk:
                decision_type = (
                    ShadowDecisionType.BUDGET_BLOCKED
                    if ai_result.reason == "BUDGET_GUARD_BLOCKED"
                    else ShadowDecisionType.AI_REJECTED
                )
                self._record_shadow(
                    session,
                    decision_type=decision_type,
                    symbol=symbol,
                    side=signal.side,
                    reason=ai_result.reason,
                    reason_codes=[ai_result.reason or "AI_REJECTED"],
                    signal_review_id=ai_record.id,
                    context_summary={
                        "strategy_name": signal.strategy_name,
                        "signal_type": signal.signal_type,
                        "ai_decision": ai_result.review.decision.value,
                        "data_quality_status": dq_snapshot.overall_status.value,
                    },
                )
            await self._risk_and_order(
                session=session,
                symbol=symbol,
                signal=signal,
                signal_record=signal_record,
                ai_result=ai_result,
                ai_record=ai_record,
                snapshot=snapshot,
                run_id=run_id,
            )
            session.commit()

    async def _risk_and_order(
        self,
        *,
        session: Session,
        symbol: str,
        signal: Any,
        signal_record: StrategySignal,
        ai_result: SignalReviewResult,
        ai_record: AIAnalysis,
        snapshot: dict[str, Any],
        run_id: str,
    ) -> None:
        filters = self.exchange_filters.get(symbol)
        if filters is None:
            self._record_shadow(
                session,
                decision_type=ShadowDecisionType.RISK_REJECTED,
                symbol=symbol,
                side=signal.side,
                reason="missing filters",
                reason_codes=["MISSING_EXCHANGE_FILTERS"],
                signal_review_id=ai_record.id,
                context_summary={
                    "strategy_name": signal.strategy_name,
                    "signal_type": signal.signal_type,
                    "risk_reason": "missing filters",
                },
            )
            self._log("risk_rejected", level="WARNING", symbol=symbol, reason="missing filters")
            return
        runtime_kill_switch_enabled = CircuitBreaker(session).is_enabled()
        account_runtime_state = self.latest_account_state
        position_runtime_state = self.latest_position_states.get(symbol)
        account_state = _account_to_risk_state(account_runtime_state)
        position_state = _position_to_risk_state(symbol, position_runtime_state)
        try:
            entry_price = Decimal(str(snapshot["price"]))
            atr_value = Decimal(str(snapshot.get("atr14_5m") or "0"))
            stop_loss = entry_price - max(atr_value, Decimal("1"))
            sized = PositionSizer().size_position(
                account_equity_usdt=account_state.equity_usdt,
                max_single_trade_risk_pct=Decimal(str(self.settings.risk_config.max_single_trade_risk_pct)),
                entry_price=entry_price,
                stop_loss_price=stop_loss,
                max_position_pct_per_symbol=Decimal(
                    str(self.settings.risk_config.max_position_pct_per_symbol)
                ),
                filters=filters,
            )
        except Exception as exc:  # noqa: BLE001
            risk_record = RiskDecision(
                symbol=symbol,
                signal_id=signal_record.id,
                ai_analysis_id=ai_record.id,
                approved=False,
                reason=f"position sizing failed: {exc}",
                risk_state_json={"snapshot": snapshot},
            )
            session.add(risk_record)
            session.flush()
            self._audit(
                session,
                run_id=run_id,
                symbol=symbol,
                stage=PipelineStage.RISK_CHECKED,
                status=PipelineStatus.ERROR,
                signal_id=signal_record.id,
                ai_analysis_id=ai_record.id,
                risk_decision_id=risk_record.id,
                error_message=risk_record.reason,
                raw_context_json={"snapshot": snapshot},
            )
            self._record_risk_decision(risk_record)
            self._record_shadow(
                session,
                decision_type=ShadowDecisionType.RISK_REJECTED,
                symbol=symbol,
                side=signal.side,
                reason=risk_record.reason,
                reason_codes=["POSITION_SIZING_FAILED"],
                signal_review_id=ai_record.id,
                risk_decision_id=risk_record.id,
                context_summary={
                    "strategy_name": signal.strategy_name,
                    "signal_type": signal.signal_type,
                    "risk_reason": risk_record.reason,
                },
            )
            self._log("risk_rejected", level="WARNING", symbol=symbol, reason=risk_record.reason)
            return
        market_health = self._risk_market_health()
        client_order_id = generate_client_order_id("testnet")
        self._log("risk_check_started", symbol=symbol)
        decision = self.risk_engine.evaluate(
            signal=signal,
            ai_review=ai_result.review,
            ai_schema_valid=ai_result.schema_valid,
            account=account_state,
            position=position_state,
            market_health=market_health,
            symbol_filters=filters,
            order_price=sized.adjusted_entry_price,
            order_quantity=sized.adjusted_quantity,
            trading_mode="testnet",
            client_order_id=client_order_id,
            runtime_kill_switch_enabled=runtime_kill_switch_enabled,
        )
        risk_record = RiskDecision(
            symbol=symbol,
            signal_id=signal_record.id,
            ai_analysis_id=ai_record.id,
            approved=decision.approved,
            reason=decision.reason,
            risk_state_json=decision.risk_state_json,
        )
        session.add(risk_record)
        session.flush()
        self._audit(
            session,
            run_id=run_id,
            symbol=symbol,
            stage=PipelineStage.RISK_CHECKED,
            status=PipelineStatus.OK if decision.approved else PipelineStatus.REJECTED,
            signal_id=signal_record.id,
            ai_analysis_id=ai_record.id,
            risk_decision_id=risk_record.id,
            raw_context_json=decision.risk_state_json,
            error_message=None if decision.approved else decision.reason,
        )
        self._record_risk_decision(risk_record)
        self._log(
            "risk_approved" if decision.approved else "risk_rejected",
            symbol=symbol,
            reason=decision.reason,
        )
        if not decision.approved:
            if ai_result.approved_for_risk:
                self._record_shadow(
                    session,
                    decision_type=ShadowDecisionType.RISK_REJECTED,
                    symbol=symbol,
                    side=signal.side,
                    reason=decision.reason,
                    reason_codes=[decision.reason or "RISK_REJECTED"],
                    signal_review_id=ai_record.id,
                    risk_decision_id=risk_record.id,
                    context_summary={
                        "strategy_name": signal.strategy_name,
                        "signal_type": signal.signal_type,
                        "risk_reason": decision.reason,
                    },
                )
            return
        order_quality = self.data_quality_gate.evaluate_order_preconditions(
            symbol=symbol,
            market_health={
                "market_stream_connected": market_health.market_stream_connected,
                "user_stream_connected": market_health.user_stream_connected,
                "data_delay_seconds": market_health.data_delay_seconds,
                "last_kline_time": self.last_kline_time.isoformat()
                if self.last_kline_time
                else None,
                "last_user_event_time": self.last_user_event_time.isoformat()
                if self.last_user_event_time
                else None,
            },
            exchange_filters_available=filters is not None,
            account_state_status=_data_quality_account_status(account_runtime_state),
            position_state_status=_data_quality_position_status(
                [position_runtime_state] if position_runtime_state else []
            ),
            active_strategy_plan=self.active_strategy_plan,
            for_real_order=self.order_execution_enabled and not self.dry_run,
        )
        self.latest_data_quality_snapshot = order_quality
        if (
            self.settings.enable_data_quality_gate
            and not order_quality.safe_for_order
            and (
                self.settings.data_quality_block_order_on_critical
                or order_quality.overall_status != DataQualitySeverity.CRITICAL
            )
        ):
            self._log(
                "data_quality_blocked_order",
                level="WARNING",
                symbol=symbol,
                reason_codes=order_quality.reason_codes,
            )
            self._record_shadow(
                session,
                decision_type=ShadowDecisionType.DATA_QUALITY_BLOCKED,
                symbol=symbol,
                side=signal.side,
                reason="Order path blocked by DataQualityGate.",
                reason_codes=["DATA_QUALITY_BLOCKED", *order_quality.reason_codes],
                signal_review_id=ai_record.id,
                risk_decision_id=risk_record.id,
                data_quality_snapshot_id=run_id,
                context_summary={
                    "strategy_name": signal.strategy_name,
                    "signal_type": signal.signal_type,
                    "data_quality_status": order_quality.overall_status.value,
                    "notes": order_quality.reason_codes[:5],
                },
            )
            return
        manager = OrderManager(broker=self.broker, session=session, trading_mode="testnet")
        order_record = await manager.submit_order(
            signal=signal,
            risk_decision=risk_record,
            order_request=OrderRequest(
                symbol=symbol,
                side=signal.side,
                order_type="LIMIT",
                price=sized.adjusted_entry_price,
                quantity=sized.adjusted_quantity,
                client_order_id=client_order_id,
            ),
            ai_analysis_id=ai_record.id,
            dry_run=self.dry_run,
            order_execution_enabled=self.order_execution_enabled,
            precheck_test_order=True,
        )
        self._audit(
            session,
            run_id=run_id,
            symbol=symbol,
            stage=PipelineStage.ORDER_CREATED,
            status=PipelineStatus.OK,
            signal_id=signal_record.id,
            ai_analysis_id=ai_record.id,
            risk_decision_id=risk_record.id,
            order_record_id=order_record.id,
            raw_context_json={"order_status": order_record.status, "dry_run": self.dry_run},
        )
        if self.dry_run or not self.order_execution_enabled:
            self._record_shadow(
                session,
                decision_type=ShadowDecisionType.WOULD_PLACE_ORDER,
                symbol=symbol,
                side=signal.side,
                reason="RiskEngine approved and OrderManager created a dry-run order record.",
                reason_codes=["WOULD_PLACE_ORDER", order_record.status],
                signal_review_id=ai_record.id,
                risk_decision_id=risk_record.id,
                order_type=order_record.order_type,
                simulated_entry_price=order_record.price,
                simulated_quantity=order_record.quantity,
                simulated_notional=(
                    (order_record.price or Decimal("0")) * order_record.quantity
                ),
                context_summary={
                    "strategy_name": signal.strategy_name,
                    "signal_type": signal.signal_type,
                    "ai_decision": ai_result.review.decision.value,
                    "risk_reason": risk_record.reason,
                    "price_source": "sized_order",
                },
            )

    def _build_user_stream(self) -> UserDataStreamClient | None:
        if (
            not self.settings.binance_testnet_api_key
            or not self.settings.binance_testnet_api_secret
        ):
            return None
        return UserDataStreamClient(
            ws_api_base=self.settings.binance_spot_testnet_ws_api_base,
            api_key=self.settings.binance_testnet_api_key,
            api_secret=self.settings.binance_testnet_api_secret,
        )

    async def _maybe_trade_review(self, session: Session, record: OrderRecord) -> None:
        existing = session.scalar(
            select(TradeReview).where(TradeReview.order_record_id == record.id)
        )
        if existing is not None:
            return
        payload = {
            "order": {
                "id": record.id,
                "symbol": record.symbol,
                "side": record.side,
                "status": record.status,
                "price": str(record.price) if record.price is not None else None,
                "quantity": str(record.quantity),
            },
            "executions": [
                {
                    "price": str(execution.price),
                    "quantity": str(execution.quantity),
                    "commission": str(execution.commission),
                    "commission_asset": execution.commission_asset,
                }
                for execution in record.executions
            ],
        }
        try:
            reviewer = TradeReviewer(self.settings)
            review = await asyncio.to_thread(reviewer.review, payload, session)
            model = reviewer.model
        except Exception as exc:  # noqa: BLE001 - fail closed but persist an auditable review
            self._log("trade_review_failed", level="WARNING", order_id=record.id, error=str(exc))
            review = TradeReviewSchema(
                grade="C",
                entry_quality="average",
                exit_quality="not_applicable",
                mistake_tag="none",
                main_reason=f"Trade review fallback: {exc}",
                improvement_candidate="Review manually before changing strategy.",
                requires_backtest=True,
            )
            model = TradeReviewer(self.settings).model
        session.add(
            TradeReview(
                order_record_id=record.id,
                model=model,
                input_json=payload,
                output_json=review.model_dump(mode="json"),
                grade=review.grade,
                mistake_tag=review.mistake_tag,
                improvement_candidate=review.improvement_candidate,
            )
        )
        session.flush()
        self._audit(
            session,
            run_id=f"order-{record.client_order_id}",
            symbol=record.symbol,
            stage=PipelineStage.TRADE_REVIEWED,
            status=PipelineStatus.OK,
            order_record_id=record.id,
            raw_context_json=review.model_dump(mode="json"),
        )
        self._log("trade_review_completed", order_id=record.id, grade=review.grade)

    def _audit(
        self,
        session: Session,
        *,
        run_id: str,
        symbol: str,
        stage: PipelineStage,
        status: PipelineStatus,
        raw_context_json: dict[str, Any] | None = None,
        signal_id: int | None = None,
        ai_analysis_id: int | None = None,
        risk_decision_id: int | None = None,
        order_record_id: int | None = None,
        error_message: str | None = None,
    ) -> None:
        record_pipeline_stage(
            session,
            run_id=run_id,
            symbol=symbol,
            stage=stage,
            status=status,
            raw_context_json=raw_context_json,
            signal_id=signal_id,
            ai_analysis_id=ai_analysis_id,
            risk_decision_id=risk_decision_id,
            order_record_id=order_record_id,
            error_message=error_message,
        )

    def _risk_market_health(self) -> MarketHealth:
        market_connected = self._market_connected_for_runtime()
        user_connected = (
            True if self.dry_run or not self.order_execution_enabled else self._user_connected()
        )
        return MarketHealth(
            ws_connected=market_connected and user_connected,
            market_stream_connected=market_connected,
            user_stream_connected=user_connected,
            account_stream_ok=user_connected,
            data_delay_seconds=self._data_delay_seconds(),
            reconnecting=self.market_stream.health.reconnecting
            or bool(self.user_stream and self.user_stream.health.reconnecting),
            last_error=self.last_error,
        )

    def _market_connected_for_runtime(self) -> bool:
        if self.market_stream.health.is_healthy():
            return True
        if self.last_rest_poll_ok_at is None:
            return False
        return (datetime.now(UTC) - self.last_rest_poll_ok_at).total_seconds() < 120

    def _user_connected(self) -> bool:
        return bool(self.user_stream and self.user_stream.health.is_healthy())

    def _data_delay_seconds(self) -> float:
        if self.last_kline_time is None:
            return 0.0 if self.last_rest_poll_ok_at else float("inf")
        return max((datetime.now(UTC) - self.last_kline_time).total_seconds(), 0.0)

    async def _sleep_until_stop(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self.stop_event.wait(), timeout=seconds)
        except TimeoutError:
            return

    async def _close_broker(self) -> None:
        client = getattr(self.broker, "client", None)
        close = getattr(client, "aclose", None)
        if close:
            await close()

    def _record_risk_decision(self, record: RiskDecision) -> None:
        self.last_risk_decisions.append(
            {
                "symbol": record.symbol,
                "approved": record.approved,
                "reason": record.reason,
                "created_at": record.created_at.isoformat() if record.created_at else None,
            }
        )
        self.last_risk_decisions = self.last_risk_decisions[-20:]

    def _record_shadow(
        self,
        session: Session,
        *,
        decision_type: ShadowDecisionType,
        symbol: str,
        side: str,
        reason: str,
        reason_codes: list[str] | None = None,
        context_summary: dict[str, Any] | None = None,
        signal_review_id: int | str | None = None,
        risk_decision_id: int | str | None = None,
        data_quality_snapshot_id: int | str | None = None,
        order_type: str | None = None,
        simulated_entry_price: Decimal | str | None = None,
        simulated_quantity: Decimal | str | None = None,
        simulated_notional: Decimal | str | None = None,
    ) -> None:
        try:
            record = self.shadow_recorder.record(
                session,
                decision_type=decision_type,
                symbol=symbol,
                side=side,
                reason=reason,
                reason_codes=reason_codes,
                context_summary=context_summary,
                signal_review_id=signal_review_id,
                risk_decision_id=risk_decision_id,
                data_quality_snapshot_id=data_quality_snapshot_id,
                order_type=order_type,
                simulated_entry_price=simulated_entry_price,
                simulated_quantity=simulated_quantity,
                simulated_notional=simulated_notional,
                dry_run=self.dry_run,
                order_execution_enabled=self.order_execution_enabled,
            )
            if record is not None:
                self._log(
                    "shadow_decision_recorded",
                    symbol=symbol,
                    decision_type=decision_type.value,
                    shadow_id=record.shadow_id,
                )
        except Exception as exc:  # noqa: BLE001 - shadow mode must not alter trading path
            self._log("shadow_record_failed", level="WARNING", symbol=symbol, error=str(exc))

    def _log(self, event: str, *, level: str = "INFO", **payload: Any) -> None:
        self.logs.append(event, level=level, **payload)
        log_fn: Callable[..., None] = logger.warning if level == "WARNING" else logger.info
        if level == "ERROR":
            log_fn = logger.error
        log_fn(event, extra={"runtime": payload})

    def _budget_status(self) -> dict[str, object]:
        try:
            with self.session_factory() as session:
                return budget_status(self.settings, session)
        except Exception as exc:  # noqa: BLE001 - health should stay available
            return budget_status(self.settings, None) | {"warning": type(exc).__name__}

    def _kill_switch_state(self) -> dict[str, object]:
        try:
            with self.session_factory() as session:
                runtime_enabled = CircuitBreaker(session).is_enabled()
        except Exception as exc:  # noqa: BLE001 - health should stay available
            runtime_enabled = False
            return {
                "config_enabled": self.settings.risk_config.kill_switch_enabled,
                "runtime_enabled": runtime_enabled,
                "effective_enabled": self.settings.risk_config.kill_switch_enabled,
                "warning": type(exc).__name__,
            }
        return {
            "config_enabled": self.settings.risk_config.kill_switch_enabled,
            "runtime_enabled": runtime_enabled,
            "effective_enabled": self.settings.risk_config.kill_switch_enabled
            or runtime_enabled,
        }

    def _risk_runtime_status(self) -> dict[str, object]:
        return self.risk_engine.runtime_state() | {
            "kill_switch_enabled_config": self.settings.risk_config.kill_switch_enabled,
            "kill_switch_enabled_runtime": self._kill_switch_state().get("runtime_enabled", False),
        }

    def _account_position_status(self) -> dict[str, Any]:
        snapshot = self.latest_account_position_snapshot
        if snapshot is None:
            snapshot = self.account_position_service.simulated_snapshot(
                self.settings.symbols.enabled_symbols
            )
            self.latest_account_position_snapshot = snapshot
            self.latest_account_state = snapshot.account
            self.latest_position_states = {
                position.symbol: position for position in snapshot.positions
            }
        return {
            "account_status": snapshot.account.status.value,
            "account_source": snapshot.account.source,
            "equity_usdt": str(snapshot.account.equity_usdt),
            "available_usdt": str(snapshot.account.available_usdt),
            "positions": [
                {
                    "symbol": position.symbol,
                    "status": position.status.value,
                    "source": position.source,
                    "side": position.side,
                    "quantity": str(position.quantity),
                    "position_pct": position.position_pct,
                    "is_safe_for_real_order": position.is_safe_for_real_order,
                }
                for position in snapshot.positions
            ],
            "safe_for_real_order": snapshot.safe_for_real_order,
            "latest_created_at": snapshot.created_at.isoformat(),
            "reason_codes": snapshot.reason_codes,
        }

    def _shadow_status(self) -> dict[str, Any]:
        try:
            with self.session_factory() as session:
                open_decisions = list_open_shadow_decisions(session, limit=100)
                recent_decisions = list_recent_shadow_decisions(session, limit=25)
                report = build_shadow_report(session, hours=24)
                return {
                    "enabled": self.settings.enable_shadow_mode,
                    "open_shadow_decisions": len(open_decisions),
                    "recent_shadow_decisions": len(recent_decisions),
                    "last_shadow_evaluation_at": self.last_shadow_evaluation_at.isoformat()
                    if self.last_shadow_evaluation_at
                    else None,
                    "simulated_total_pnl_usdt": report.simulated_total_pnl_usdt,
                    "simulated_win_rate": report.simulated_win_rate,
                    "latest_report_created_at": report.created_at.isoformat(),
                }
        except Exception as exc:  # noqa: BLE001 - health should stay available
            return {
                "enabled": self.settings.enable_shadow_mode,
                "open_shadow_decisions": 0,
                "recent_shadow_decisions": 0,
                "last_shadow_evaluation_at": self.last_shadow_evaluation_at.isoformat()
                if self.last_shadow_evaluation_at
                else None,
                "simulated_total_pnl_usdt": "0",
                "simulated_win_rate": None,
                "latest_report_created_at": None,
                "warning": type(exc).__name__,
            }

    def _shadow_summary_for_audit(self, session: Session) -> dict[str, Any]:
        report = build_shadow_report(session, hours=24)
        return {
            "total_decisions": report.total_decisions,
            "would_place_order_count": report.would_place_order_count,
            "risk_rejected_count": report.risk_rejected_count,
            "ai_rejected_count": report.ai_rejected_count,
            "data_quality_blocked_count": report.data_quality_blocked_count,
            "simulated_total_pnl_usdt": report.simulated_total_pnl_usdt,
            "simulated_win_rate": report.simulated_win_rate,
            "top_rejection_reasons": [
                item.model_dump(mode="json") for item in report.top_rejection_reasons
            ],
        }

    def _evaluate_data_quality_runtime(
        self, *, active_strategy_plan: dict[str, Any] | None = None
    ) -> DataQualitySnapshot:
        account_status = _data_quality_account_status(self.latest_account_state)
        position_status = _data_quality_position_status(
            list(self.latest_position_states.values())
        )
        snapshot = self.data_quality_gate.evaluate_runtime_health(
            runtime_health=self._runtime_health_snapshot(),
            exchange_filters_available=bool(self.exchange_filters) or None,
            account_state_status=account_status,
            position_state_status=position_status,
            active_strategy_plan=active_strategy_plan,
            for_real_order=self.order_execution_enabled and not self.dry_run,
        )
        self.latest_data_quality_snapshot = snapshot
        return snapshot

    def _evaluate_data_quality_signal(
        self,
        *,
        snapshot: dict[str, Any],
        entry_df: pd.DataFrame,
        trend_df: pd.DataFrame,
        active_strategy_plan: dict[str, Any] | None,
    ) -> DataQualitySnapshot:
        dq_snapshot = self.data_quality_gate.evaluate_signal_context(
            snapshot=snapshot,
            entry_df=entry_df,
            trend_df=trend_df,
            active_strategy_plan=active_strategy_plan,
        )
        self.latest_data_quality_snapshot = dq_snapshot
        return dq_snapshot

    async def run_data_quality_check_once(self) -> dict[str, Any]:
        snapshot = self._evaluate_data_quality_runtime(
            active_strategy_plan=self.active_strategy_plan
        )
        return snapshot.model_dump(mode="json")

    def _data_quality_status(self) -> dict[str, Any]:
        snapshot = self.latest_data_quality_snapshot
        if snapshot is None:
            try:
                snapshot = self._evaluate_data_quality_runtime(
                    active_strategy_plan=self.active_strategy_plan
                )
            except Exception as exc:  # noqa: BLE001 - health must remain available
                return {
                    "enabled": self.settings.enable_data_quality_gate,
                    "overall_status": "UNKNOWN",
                    "safe_for_strategy_planner": False,
                    "safe_for_signal_review": False,
                    "safe_for_order": False,
                    "safe_for_real_testnet_order": False,
                    "issue_count": 0,
                    "latest_created_at": None,
                    "warning": type(exc).__name__,
                }
        return {
            "enabled": self.settings.enable_data_quality_gate,
            "overall_status": snapshot.overall_status.value,
            "action": snapshot.action.value,
            "safe_for_strategy_planner": snapshot.safe_for_strategy_planner,
            "safe_for_signal_review": snapshot.safe_for_signal_review,
            "safe_for_order": snapshot.safe_for_order,
            "safe_for_real_testnet_order": snapshot.safe_for_real_testnet_order,
            "issue_count": len(snapshot.issues),
            "latest_created_at": snapshot.created_at.isoformat(),
            "reason_codes": snapshot.reason_codes,
        }

    def _audit_status(self) -> dict[str, object]:
        try:
            with self.session_factory() as session:
                latest = get_latest_trading_issue_report(session)
                if latest is None:
                    return {
                        "enabled": self.settings.enable_system_auditor,
                        "latest_overall_status": "UNKNOWN",
                        "latest_highest_severity": "UNKNOWN",
                        "latest_issue_count": 0,
                        "latest_report_created_at": None,
                        "latest_summary": None,
                        "health_warning": False,
                    }
                warning = _severity_at_least(
                    latest.highest_severity,
                    self.settings.system_audit_min_severity_to_health_warn,
                )
                return {
                    "enabled": self.settings.enable_system_auditor,
                    "latest_overall_status": latest.overall_status,
                    "latest_highest_severity": latest.highest_severity,
                    "latest_issue_count": latest.issue_count,
                    "latest_report_created_at": latest.created_at.isoformat(),
                    "latest_summary": latest.summary,
                    "health_warning": warning,
                }
        except Exception as exc:  # noqa: BLE001 - health should stay available
            return {
                "enabled": self.settings.enable_system_auditor,
                "latest_overall_status": "UNKNOWN",
                "latest_highest_severity": "UNKNOWN",
                "latest_issue_count": 0,
                "latest_report_created_at": None,
                "latest_summary": None,
                "health_warning": False,
                "warning": type(exc).__name__,
            }

    def _build_audit_context(self, session: Session) -> dict[str, Any]:
        active = get_active_strategy_plan(session)
        return build_audit_context(
            settings=self.settings,
            runtime_health=self._runtime_health_snapshot(),
            budget_status=budget_status(self.settings, session),
            active_strategy_plan=active,
            recent_strategy_plans=[
                {
                    "id": plan.id,
                    "status": plan.status,
                    "plan_action": plan.plan_action,
                    "risk_mode": plan.risk_mode,
                    "created_at": plan.created_at.isoformat(),
                }
                for plan in list_recent_strategy_plans(session, limit=10)
            ],
            recent_signal_reviews=[
                {
                    "id": row.id,
                    "symbol": row.symbol,
                    "decision": row.decision,
                    "schema_valid": row.schema_valid,
                    "created_at": row.created_at.isoformat(),
                }
                for row in session.scalars(
                    select(AIAnalysis)
                    .order_by(desc(AIAnalysis.created_at))
                    .limit(self.settings.ai_context_recent_signal_reviews_limit)
                ).all()
            ],
            recent_risk_decisions=[
                {
                    "id": row.id,
                    "symbol": row.symbol,
                    "approved": row.approved,
                    "reason": row.reason,
                    "created_at": row.created_at.isoformat(),
                }
                for row in session.scalars(
                    select(RiskDecision)
                    .order_by(desc(RiskDecision.created_at))
                    .limit(self.settings.ai_context_recent_risk_decisions_limit)
                ).all()
            ],
            recent_orders=[
                {
                    "id": row.id,
                    "symbol": row.symbol,
                    "status": row.status,
                    "side": row.side,
                    "created_at": row.created_at.isoformat(),
                }
                for row in session.scalars(
                    select(OrderRecord)
                    .order_by(desc(OrderRecord.created_at))
                    .limit(self.settings.ai_context_recent_orders_limit)
                ).all()
            ],
            recent_trade_reviews=[
                {
                    "id": row.id,
                    "grade": row.grade,
                    "mistake_tag": row.mistake_tag,
                    "created_at": row.created_at.isoformat(),
                }
                for row in session.scalars(
                    select(TradeReview)
                    .order_by(desc(TradeReview.created_at))
                    .limit(self.settings.ai_context_recent_trade_reviews_limit)
                ).all()
            ],
            openai_usage_summary=summarize_openai_usage(session, days=1),
            data_quality_summary={
                "market_stream_connected": self._market_connected_for_runtime(),
                "user_stream_connected": self._user_connected(),
                "data_delay_seconds": self._data_delay_seconds(),
                "last_error": self.last_error,
            },
            latest_data_quality_snapshot=self.latest_data_quality_snapshot.model_dump(mode="json")
            if self.latest_data_quality_snapshot
            else None,
            account_position_snapshot=self.latest_account_position_snapshot.model_dump(mode="json")
            if self.latest_account_position_snapshot
            else None,
            kill_switch_state=self._kill_switch_state(),
            risk_engine_runtime_state=self._risk_runtime_status(),
            shadow_summary=self._shadow_summary_for_audit(session),
            account_state=_account_context(self.latest_account_state),
            position_state={
                "positions": _position_contexts(
                    self.settings.symbols.enabled_symbols,
                    self.latest_position_states,
                )
            },
        )

    def _runtime_health_snapshot(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "market_stream_connected": self._market_connected_for_runtime(),
            "user_stream_connected": self._user_connected(),
            "data_delay_seconds": self._data_delay_seconds(),
            "last_error": self.last_error,
            "reconnecting": self.market_stream.health.reconnecting
            or bool(self.user_stream and self.user_stream.health.reconnecting),
        }

    def _data_quality_blocked_signal_result(
        self,
        *,
        snapshot: dict[str, Any],
        reason: str,
        data_quality: DataQualitySnapshot,
    ) -> SignalReviewResult:
        review = SignalReview(
            decision=SignalDecision.HUMAN_REVIEW_REQUIRED,
            symbol=str(snapshot.get("symbol", "UNKNOWN")),
            side=SignalSide.HOLD,
            confidence=0,
            risk_level=RiskLevel.HIGH,
            market_regime=MarketRegime.UNCLEAR,
            reason=f"{reason}: DATA_QUALITY_BLOCKED",
            warnings=data_quality.reason_codes[:5] or ["DATA_QUALITY_BLOCKED"],
            max_position_pct=0,
            requires_human_review=True,
        )
        payload = {
            **snapshot,
            "data_quality_snapshot": data_quality.model_dump(mode="json"),
            "reason_codes": ["DATA_QUALITY_BLOCKED", *data_quality.reason_codes],
        }
        return SignalReviewResult(
            review=review,
            approved_for_risk=False,
            reason="DATA_QUALITY_BLOCKED",
            schema_valid=True,
            actual_model="data_quality_gate",
            active_strategy_plan_id=(self.active_strategy_plan or {}).get("id"),
            input_payload=payload,
        )


def _simulated_account_context() -> dict[str, object]:
    return {
        "status": "simulated_or_unknown",
        "source": "simulated_default",
        "equity_usdt": 1000,
        "available_usdt": "unknown",
        "daily_realized_pnl": "unknown",
        "daily_unrealized_pnl": "unknown",
        "daily_loss_remaining": "unknown",
    }


def _unknown_position_context(symbol: str) -> dict[str, object]:
    return {
        "status": "unknown",
        "source": "not_synced",
        "symbol": symbol,
        "side": "unknown",
        "quantity": "unknown",
        "entry_price": "unknown",
        "unrealized_pnl": "unknown",
        "position_pct": "unknown",
    }


def _account_context(account: RuntimeAccountState | None) -> dict[str, object]:
    if account is None:
        return _simulated_account_context()
    return {
        "status": account.status.value.lower(),
        "source": account.source,
        "equity_usdt": str(account.equity_usdt),
        "available_usdt": str(account.available_usdt),
        "daily_realized_pnl": str(account.daily_realized_pnl),
        "daily_unrealized_pnl": str(account.daily_unrealized_pnl),
        "daily_loss_remaining": "unknown",
        "is_safe_for_real_order": account.is_safe_for_real_order,
    }


def _position_contexts(
    symbols: list[str], positions: dict[str, RuntimePositionState]
) -> list[dict[str, object]]:
    return [
        _position_context(positions.get(symbol.upper())) if positions.get(symbol.upper())
        else _unknown_position_context(symbol)
        for symbol in symbols
    ]


def _position_context(position: RuntimePositionState | None) -> dict[str, object]:
    if position is None:
        return _unknown_position_context("unknown")
    return {
        "status": position.status.value.lower(),
        "source": position.source,
        "symbol": position.symbol,
        "side": position.side,
        "quantity": str(position.quantity),
        "entry_price": str(position.entry_price),
        "unrealized_pnl": str(position.unrealized_pnl),
        "position_pct": position.position_pct,
        "is_safe_for_real_order": position.is_safe_for_real_order,
    }


def _data_quality_account_status(account: RuntimeAccountState | None) -> str:
    if account is None:
        return "unknown"
    if account.status.value == "OK":
        return "ok"
    if account.status.value == "SIMULATED_DEFAULT":
        return "simulated_default"
    if account.status.value == "ERROR":
        return "error"
    return "unknown"


def _data_quality_position_status(positions: list[RuntimePositionState]) -> str:
    if not positions:
        return "unknown"
    statuses = {position.status.value for position in positions}
    if statuses == {"OK"}:
        return "ok"
    if "ERROR" in statuses:
        return "error"
    if "SIMULATED_DEFAULT" in statuses:
        return "simulated_default"
    return "unknown"


def _account_to_risk_state(account: RuntimeAccountState | None) -> AccountState:
    if account is None:
        return AccountState(equity_usdt=Decimal("1000"))
    return AccountState(
        equity_usdt=_decimal_or_default(account.equity_usdt, Decimal("1000")),
        daily_loss_pct=account.daily_loss_pct,
        consecutive_losses=account.consecutive_losses,
        total_position_pct=account.total_position_pct,
    )


def _position_to_risk_state(symbol: str, position: RuntimePositionState | None) -> PositionState:
    if position is None:
        return PositionState(symbol=symbol)
    return PositionState(
        symbol=symbol,
        quantity=_decimal_or_default(position.quantity, Decimal("0")),
        position_pct=position.position_pct,
        side=position.side,
        last_loss_at=position.last_loss_at,
    )


def _decimal_or_default(value: object, default: Decimal) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001
        return default


def _severity_at_least(value: str, threshold: str) -> bool:
    rank = {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    return rank.get(str(value).upper(), 0) >= rank.get(str(threshold).upper(), 3)
