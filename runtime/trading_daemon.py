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

from ai.audit_schemas import AuditReportType
from ai.budget_guard import budget_status
from ai.context_builder import (
    build_audit_context,
    build_signal_review_context,
    build_strategy_context,
    summarize_strategy_plan,
)
from ai.schemas import TradeReview as TradeReviewSchema
from ai.signal_reviewer import SignalReviewer, SignalReviewResult
from ai.strategy_planner import StrategyPlanner
from ai.strategy_schemas import StrategyPlanningMode
from ai.system_auditor import SystemAuditor
from ai.trade_reviewer import TradeReviewer
from binance_client.exchange_info import SymbolFilters, parse_all_symbol_filters
from binance_client.market_stream import KlineStream
from binance_client.user_stream import UserDataStreamClient
from broker.base import Broker, OrderRequest
from broker.binance_spot_testnet import BinanceSpotTestnetBroker
from config.settings import Settings
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
from risk.position_sizer import PositionSizer
from risk.risk_engine import AccountState, MarketHealth, PositionState, RiskEngine
from runtime.daemon_state import DaemonState, RuntimeLogBuffer
from runtime.health import RuntimeHealth
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
        self.strategy = EmaTrendStrategy(settings.strategy.ema_trend)
        self.poll_interval_seconds = poll_interval_seconds
        self.reconciliation_interval_seconds = reconciliation_interval_seconds
        self.dry_run = settings.trading_dry_run if dry_run is None else dry_run
        self.order_execution_enabled = (
            settings.order_execution_enabled
            if order_execution_enabled is None
            else order_execution_enabled
        )
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
            health_warning=bool(audit_status.get("health_warning")),
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
                        account_state=_simulated_account_context(),
                        positions=[
                            _unknown_position_context(item)
                            for item in self.settings.symbols.enabled_symbols
                        ],
                        budget_status=budget_status(self.settings, session),
                        data_quality_summary={
                            "market_stream_connected": self._market_connected_for_runtime(),
                            "data_delay_seconds": self._data_delay_seconds(),
                            "source": "runtime_health",
                        },
                    )
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
            self._log("ai_review_started", symbol=symbol)
            ai_result: SignalReviewResult = await asyncio.to_thread(
                self.signal_reviewer.review_with_schema,
                snapshot,
                active_strategy_plan=active_plan,
                signal_review_context=build_signal_review_context(
                    current_snapshot=snapshot,
                    candidate_signal=signal.model_dump(mode="json"),
                    active_strategy_plan=active_plan,
                    position_state={"symbol": symbol, "status": "unknown", "source": "not_synced"},
                    risk_state={"status": "pre_risk_check"},
                    settings=self.settings,
                    data_quality_flags=[]
                    if self._market_connected_for_runtime()
                    else ["market_stream_unhealthy"],
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
            self._log("risk_rejected", level="WARNING", symbol=symbol, reason="missing filters")
            return
        try:
            entry_price = Decimal(str(snapshot["price"]))
            atr_value = Decimal(str(snapshot.get("atr14_5m") or "0"))
            stop_loss = entry_price - max(atr_value, Decimal("1"))
            sized = PositionSizer().size_position(
                account_equity_usdt=Decimal("1000"),
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
            self._log("risk_rejected", level="WARNING", symbol=symbol, reason=risk_record.reason)
            return
        market_health = self._risk_market_health()
        client_order_id = generate_client_order_id("testnet")
        self._log("risk_check_started", symbol=symbol)
        decision = RiskEngine(self.settings).evaluate(
            signal=signal,
            ai_review=ai_result.review,
            ai_schema_valid=ai_result.schema_valid,
            account=AccountState(equity_usdt=Decimal("1000")),
            position=PositionState(symbol=symbol),
            market_health=market_health,
            symbol_filters=filters,
            order_price=sized.adjusted_entry_price,
            order_quantity=sized.adjusted_quantity,
            trading_mode="testnet",
            client_order_id=client_order_id,
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
            account_state=_simulated_account_context(),
            position_state={"status": "unknown", "source": "not_synced"},
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


def _severity_at_least(value: str, threshold: str) -> bool:
    rank = {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    return rank.get(str(value).upper(), 0) >= rank.get(str(threshold).upper(), 3)
