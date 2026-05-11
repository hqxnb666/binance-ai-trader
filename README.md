# Binance AI Trader MVP

AI-assisted Binance Global Spot trading bot MVP for Testnet-first development.

This project is not investment advice, does not guarantee profit, and is not a high-frequency
trading system. Version 1 only supports Binance Spot Testnet as the normal execution path. Live
Spot code exists behind explicit guards and is disabled by default.

## Architecture

Market data -> indicators -> EMA strategy -> MarketSnapshot -> OpenAI structured review ->
RiskEngine -> OrderManager -> Broker -> Binance Spot Testnet. User Data Stream and reconciliation
sync execution state back into the journal database.

AI modules only return JSON analysis and trade intent. They cannot place orders and cannot bypass
risk checks.

## Install

```powershell
cd C:\Users\anlan\OneDrive\Desktop\Bn\binance-ai-trader
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

Copy `.env.example` to `.env`, then fill only the keys you need. `.env` is ignored by git.

## Binance Spot Testnet Key

Create a Spot Testnet API key at https://testnet.binance.vision/. Put it in:

```text
BINANCE_TESTNET_API_KEY=...
BINANCE_TESTNET_API_SECRET=...
```

The default REST endpoint is `https://testnet.binance.vision/api`.

## OpenAI Key

Set:

```text
OPENAI_API_KEY=...
OPENAI_DEFAULT_MODEL=gpt-5.4-nano
OPENAI_DIAGNOSTIC_MODEL=gpt-5.4-nano
OPENAI_STRATEGY_MODEL=gpt-5.5
OPENAI_SIGNAL_MODEL=gpt-5.4-mini
```

The OpenAI API used by this runtime is separate from ChatGPT Plus, the Codex app, and browser
plugins. The bot reads `OPENAI_API_KEY` from `.env`; do not paste API keys into prompts or logs.

If `AI_ANALYSIS_ENABLED=false` or no key is present, unit tests still run and external AI calls are
not required. Runtime AI checks fail closed as human-review/no-trade decisions.

## OpenAI Model Roles

Models are routed by task:

- Diagnostics: `OPENAI_DIAGNOSTIC_MODEL`, default `gpt-5.4-nano`.
- Strategy Planner: `OPENAI_STRATEGY_MODEL`, default `gpt-5.5`.
- SignalReview: `OPENAI_SIGNAL_MODEL`, default `gpt-5.4-mini`.
- TradeReview: `OPENAI_TRADE_REVIEW_MODEL`, default `gpt-5.4-mini`.
- DailyReport: `OPENAI_DAILY_REPORT_MODEL`, default `gpt-5.4-nano`.

`OPENAI_MODEL` is kept only as a legacy fallback. The fallback order is role-specific model,
`OPENAI_DEFAULT_MODEL`, legacy `OPENAI_MODEL`, then `gpt-5.4-nano`. Automatic model fallback is off
by default with `OPENAI_ENABLE_MODEL_FALLBACK=false`, and the project does not default to pro-tier
models.

List models visible to your OpenAI API key:

```powershell
python scripts/list_openai_models.py
python scripts/list_openai_models.py --all
python scripts/list_openai_models.py --save-report
```

After changing `.env` model settings, restart FastAPI or the daemon because settings are cached.

## Initialize Database

```powershell
python scripts/init_db.py
```

Default database: `sqlite:///./trading_bot.db`.

## Run API

```powershell
uvicorn app.main:app --reload
```

Useful endpoints:

- `GET /health`
- `GET /status`
- `GET /config/safe`
- `GET /symbols`
- `GET /orders/recent`
- `GET /runtime/health`
- `POST /runtime/testnet/start-dry-run`
- `POST /runtime/testnet/stop-dry-run`
- `POST /control/kill-switch/on`
- `POST /control/kill-switch/off`

## Local Operations Dashboard V2

Run FastAPI locally, then open the dashboard:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/dashboard.

The dashboard is a local HTML/JavaScript page served by FastAPI. It uses native browser APIs and
Tailwind CDN only; there is no React, Vite, npm build step, or public-facing product surface. It
shows runtime health, Binance stream status, DataQualityGate state, Strategy snapshots, AI
SignalReview records, RiskEngine decisions, recent orders, Shadow Mode reports, account/position
readiness, OpenAI budget, SystemAuditor output, logs, readiness checks, OpenAI usage, and a review
workspace for copying GPT analysis packages.

Allowed dashboard actions are intentionally limited:

- Start/stop Testnet dry-run runtime.
- Refresh local status panels.
- Run DataQualityGate check.
- Run Shadow evaluation.
- Run SystemAuditor.
- Turn runtime kill switch on.
- Turn runtime kill switch off after a browser confirmation warning.
- Load, validate, and save EMA Trend strategy parameters to `config/strategy.yaml`.
- Run a Testnet readiness check that only checks preconditions and does not place orders.
- Load 1-day or 7-day OpenAI usage summaries.

The dashboard deliberately does not provide real order buttons, a Live switch, a disable-dry-run
button, an order execution enable button, risk/live/order configuration editing, Codex automation,
or a Testnet order lifecycle launcher. It does not call `broker.place_order` and does not change
RiskEngine, OrderManager, broker, Live guard, or default trading safety settings.

Dashboard V2 includes a Strategy Parameter Center for the local EMA Trend strategy. It may save only
the whitelisted `ema_trend` fields in `config/strategy.yaml`, creates a YAML backup under
`reports/config_backups/`, and returns `pending_restart=true`. Saving does not hot reload settings,
does not restart FastAPI/runtime, and never triggers orders. After changing strategy parameters,
restart FastAPI/runtime and validate with:

```powershell
python scripts/backtest.py --symbol BTCUSDT --days 90
python scripts/backtest.py --symbol ETHUSDT --days 90
python scripts/shadow_report.py --hours 24 --json
```

Risk parameters are shown in the Risk Config Viewer as read-only. Dashboard V2 does not save
`risk.yaml`, `.env`, trading mode, dry-run, order execution, broker, or Live settings.

Real Testnet lifecycle remains CLI-only. Even if the dashboard readiness panel says
`ready_for_real_testnet_order=true`, this project does not expose a dashboard order button; use the
CLI readiness and lifecycle scripts with explicit confirmations.

## Phase 2 Runtime Daemon

The second-stage MVP includes a controlled Testnet runtime daemon. It starts:

- Binance Spot Testnet kline WebSocket.
- Optional User Data Stream when Testnet keys are present.
- REST kline polling for recovery and bootstrap.
- Strategy -> AI review -> RiskEngine -> OrderManager chain.
- Reconciliation loop when real Testnet execution is enabled.

The daemon is managed by FastAPI and is stopped gracefully on application shutdown.

## Strategy Planner

The runtime can run a low-frequency GPT-5.5 Strategy Planner when
`ENABLE_STRATEGY_PLANNER=true`. It runs on daemon start and then every
`OPENAI_STRATEGY_INTERVAL_MINUTES` minutes. If no active plan exists it performs a `FULL_REPLAN`;
otherwise it performs a `REFRESH`.

StrategyPlan output is persisted to `StrategyPlanRecord` with input/output hashes and sanitized raw
JSON. It can constrain later strategy review context, but it cannot place orders, set quantities,
set prices, change `.env`, raise risk limits, or enable Live trading. RiskEngine and OrderManager
remain the hard gates.

SignalReview still uses `OPENAI_SIGNAL_MODEL`, not GPT-5.5, and receives only a summarized active
StrategyPlan. If a plan says `no_trade`, `observe_only`, or `blocked`, SignalReview fails closed
toward `HOLD`, `REJECT_SIGNAL`, or human review.

## OpenAI BudgetGuard And UsageLedger

OpenAI usage is tracked locally when `ENABLE_OPENAI_USAGE_LEDGER=true`. The ledger stores role,
model, operation name, status, token counts when the SDK reports them, estimated cost, latency,
request id, sanitized error summary, and input/output hashes. It does not store API keys, request
headers, raw prompts, raw responses, Binance secrets, or `.env` contents.

BudgetGuard is enabled by default:

```text
ENABLE_BUDGET_GUARD=true
OPENAI_DAILY_BUDGET_USD=1
OPENAI_MONTHLY_BUDGET_USD=20
OPENAI_STRATEGY_DAILY_CALL_LIMIT=24
OPENAI_SIGNAL_DAILY_CALL_LIMIT=1000
OPENAI_FAIL_CLOSED_ON_BUDGET_EXCEEDED=true
```

If a budget or call limit is exceeded, the system fails closed. Strategy Planner returns `NO_TRADE`
when there is no active plan, or `KEEP` without extending expiration when an existing plan is still
active. SignalReview returns `HOLD` / human review and cannot approve a trade. TradeReview and
DailyReport may be skipped. BudgetGuard never selects a more expensive fallback model and never
changes trading configuration.

Usage report:

```powershell
python scripts/openai_usage_report.py
python scripts/openai_usage_report.py --days 7 --json
python scripts/openai_usage_report.py --days 7 --save-report
```

Cost is a local estimate only and may differ from the final OpenAI bill.

## AI Context Builder

AI context is built from runtime/database facts, not from chat memory. Contexts include run mode,
account/position state, market snapshots, active StrategyPlan, recent signal/risk/order/trade
summaries, data quality, budget status, kill switch state, and cooldowns. Unknown values are marked
as `unknown`; simulated defaults are marked with `source=simulated_default`.

Long lists are truncated by `AI_CONTEXT_RECENT_*` limits. If the JSON payload exceeds
`AI_CONTEXT_MAX_JSON_CHARS`, it is compressed and marked `truncated=true`. Context builders redact
secret-like fields and keep payloads JSON-serializable.

## SystemAuditor

SystemAuditor is a read-only issue reporter for the runtime. It can inspect summarized daemon
health, StrategyPlan history, SignalReview behavior, RiskEngine decisions, order lifecycle
summaries, Binance connectivity, OpenAI usage, and safety guardrails. It cannot place orders,
change code, modify configuration, call Codex, tune strategies, bypass RiskEngine, or enable Live
trading. Its schema hard-codes `auto_fix_allowed=false` and `do_not_auto_modify=true`.

Run a manual audit:

```powershell
python scripts/run_system_audit.py --lookback-hours 6 --json
python scripts/run_system_audit.py --lookback-hours 6 --save-report
python scripts/run_system_audit.py --lookback-hours 24 --save-report
```

Reports are written to `reports/audits/` when `--save-report` is used. Generated audit JSON files
are ignored by git because they can contain local runtime status, order IDs, and account summaries.
They must not contain API keys or Binance secrets.

Runtime endpoints:

- `GET /runtime/audits/latest`
- `GET /runtime/audits/recent`
- `POST /runtime/audits/run`

Manual remediation flow:

1. SystemAuditor generates a report.
2. You send the report to ChatGPT for interpretation.
3. ChatGPT helps identify the issue and possible fix scope.
4. You explicitly assign Codex a bounded change.
5. Codex implements only that requested change.
6. You rerun tests and runtime checks.

If an audit reports `CRITICAL`, that is a warning for human review. It does not automatically stop
the daemon unless a future explicit KillSwitch rule is added.

## DataQualityGate

DataQualityGate is a read-only pre-trade data gate. It checks market stream health, user stream
health, kline freshness, indicator NaN values, exchange filters, account/position state,
StrategyPlan safety, runtime mode, and security guardrails before expensive AI review or any order
path.

It can only warn, degrade, or block. It cannot place orders, modify config, call Codex, change
strategy parameters, or bypass RiskEngine. Critical data quality blocks StrategyPlanner,
SignalReview, and OrderManager entry points. Dry-run can tolerate some unknown user/account state,
but real Testnet orders require user stream, account state, position state, and exchange filters.

Manual check:

```powershell
python scripts/data_quality_check.py --json
python scripts/data_quality_check.py --save-report
```

Reports are written to `reports/data_quality/` and generated JSON is ignored by git.

Runtime endpoints:

```powershell
curl http://127.0.0.1:8000/runtime/data-quality/latest
curl -X POST http://127.0.0.1:8000/runtime/data-quality/check
curl http://127.0.0.1:8000/runtime/health
```

`/runtime/health` includes `data_quality_status` with the latest overall status, safe-for-AI flags,
safe-for-order flags, issue count, and reason codes.

## Dry-run Mode

Dry-run is the default:

```text
TRADING_DRY_RUN=true
ORDER_EXECUTION_ENABLED=false
```

Dry-run can read market data, calculate indicators, generate strategy signals, call GPT if an
OpenAI key is configured, run RiskEngine, and create virtual `OrderRecord` rows. It does not call
Binance `new_order`. Dry-run order statuses are `DRY_RUN_APPROVED` and `DRY_RUN_REJECTED`.

Start and stop dry-run daemon:

```powershell
curl -X POST http://127.0.0.1:8000/runtime/testnet/start-dry-run
curl http://127.0.0.1:8000/runtime/health
curl -X POST http://127.0.0.1:8000/runtime/testnet/stop-dry-run
```

`ORDER_EXECUTION_ENABLED=false` means no real Testnet order is submitted even if RiskEngine
approves. Set it to `true` only when you deliberately want real Binance Spot Testnet orders.

## Account, Position, And Runtime Risk State

The runtime uses `AccountPositionService` to read Binance Spot Testnet account balances through
`broker.get_account()`, parse BTC/ETH/USDT balances, estimate position value from latest prices, and
produce explicit `RuntimeAccountState` / `RuntimePositionState` snapshots. Unknown or simulated
values are labeled with `source=unknown` or `source=simulated_default`; dry-run balances are not
presented as real account data.

Dry-run may continue with simulated defaults, but real Testnet order paths require Testnet mode,
Live disabled, DataQualityGate safe state, account and position state `OK`, user stream available,
exchange filters available, runtime/config kill switches off, RiskEngine approval,
`ORDER_EXECUTION_ENABLED=true`, and `TRADING_DRY_RUN=false`.

The daemon reuses one RiskEngine instance for its lifetime so order frequency and duplicate
`client_order_id` state persist across evaluations. The database-backed kill switch from
`/control/kill-switch/on` is passed into RiskEngine and blocks runtime order paths.

Readiness-only check:

```powershell
python scripts/verify_testnet_order_readiness.py --json
python scripts/verify_testnet_order_readiness.py --save-report
```

Reports are written to `reports/readiness/` and generated JSON is ignored by git.

This project intentionally does not implement `HumanApprovalGate`, pending order intents, or manual
approval APIs.

## Start Testnet Daemon From CLI

```powershell
python scripts/run_testnet.py
```

This starts the same Testnet daemon outside FastAPI and stops on Ctrl+C.

## Testnet Smoke Test

Third-stage smoke test is a staged Testnet integration tool. It is safe by default and will not
place a Testnet order unless `ORDER_EXECUTION_ENABLED=true` and
`--allow-real-testnet-order` are both set.

```powershell
python scripts/smoke_test_testnet.py --check-config-only
python scripts/smoke_test_testnet.py --no-ai
python scripts/smoke_test_testnet.py --with-ai
python scripts/smoke_test_testnet.py --with-ai --test-order-only
python scripts/smoke_test_testnet.py --with-ai --allow-real-testnet-order
```

Smoke test behavior:

- Stage 0 checks `.env`, Testnet keys, OpenAI key when requested, Testnet mode, Live disabled,
  dry-run, and order execution flags.
- Stage 1 checks REST ping, server time, exchangeInfo, and BTCUSDT/ETHUSDT filters.
- Stage 2 loads 5m/1h market data, stores klines, calculates indicators, and creates snapshots.
- Stage 2.5 runs DataQualityGate. Critical data quality stops AI review and all order stages with
  `DATA_QUALITY_BLOCKED`.
- Stage 3 calls OpenAI only with `--with-ai`; otherwise it uses a local schema-valid no-ai review.
- Stage 4 runs RiskEngine.
- Stage 4.5 runs Testnet order readiness when `--test-order-only` or
  `--allow-real-testnet-order` is requested.
- Stage 5 calls Binance `test_order` only after RiskEngine approval.
- Stage 6 can submit a small LIMIT Testnet order only with `--allow-real-testnet-order`.
- With Testnet connectivity it checks exchangeInfo, BTCUSDT/ETHUSDT filters, price, 5m/1h klines,
  indicators, MarketSnapshot, AI review, and RiskEngine.
- With `ORDER_EXECUTION_ENABLED=false`, it stops before `new_order`.
- With `ORDER_EXECUTION_ENABLED=true`, it calls `test_order` first, then submits a very small
  Testnet limit order constrained by `minNotional`, queries it, and cancels if still open.

Reports are written to `reports/smoke_tests/`.

## Testnet Order Lifecycle

The lifecycle script validates a manually requested small LIMIT order path. It is not the full AI
runtime trading path. It never uses the Live broker and refuses to run unless Testnet mode, Live
disabled, `ORDER_EXECUTION_ENABLED=true`, `TRADING_DRY_RUN=false`, kill switch off, account/position
`OK`, DataQualityGate real-order readiness, and an explicit confirmation flag are all present.

```powershell
python scripts/testnet_order_lifecycle.py --symbol BTCUSDT --side BUY --i-understand-this-is-testnet
```

It prints an order summary before sending anything, calls `test_order`, submits a LIMIT Testnet
order, listens for User Data Stream events, cancels if needed, reconciles with REST, and writes a
report to `reports/order_lifecycle/`.

Use `verify_testnet_order_readiness.py` before attempting any manual small Testnet order.

## Backtesting

Backtest MVP uses historical klines and the EMA trend strategy without OpenAI, brokers, or Binance
order endpoints.

```powershell
python scripts/backtest.py --symbol BTCUSDT --start 2024-01-01 --end 2024-03-01
python scripts/backtest.py --symbol ETHUSDT --start 2024-01-01 --end 2024-03-01
python scripts/backtest.py --symbol BTCUSDT --days 90
```

Reports are written to `reports/backtests/` as JSON and CSV. Backtests do not represent future
returns, and Testnet fills do not represent Live market execution.

## Runtime Audit

Pipeline stages are persisted to `PipelineAudit` and can be queried:

```powershell
curl http://127.0.0.1:8000/runtime/audit/recent
curl http://127.0.0.1:8000/runtime/audit/{run_id}
```

This helps identify where a chain stopped: snapshot, signal, AI review, risk, order, user stream,
reconciliation, or trade review.

## Network Diagnostics

If you use Clash, a system proxy, or rule-based routing, run diagnostics before any Testnet smoke
test. This project does not read Clash configuration, change proxies, switch nodes, or bypass
regional restrictions. Network routing remains your local system responsibility.

```powershell
python scripts/diagnose_environment.py
python scripts/diagnose_environment.py --json
python scripts/diagnose_environment.py --save-report
```

Diagnostics check Python, OS, time, `.env`, required env presence without printing values, proxy
environment variable presence without printing proxy addresses, Binance Global/Testnet REST,
Binance Global/Testnet WebSocket, and OpenAI structured output connectivity.

`REGION_RESTRICTED` means the exchange endpoint is not usable from the current network path. The
bot fails closed in that state. It will not suggest or implement ways to bypass regional
restrictions. Binance Global and Binance.US are different platforms and keys are not interchangeable.

OpenAI connectivity and Binance connectivity are independent:

- If OpenAI works but Binance fails, AI review may be available but trading workflows are blocked.
- If Binance works but OpenAI fails, use `--no-ai` smoke tests.
- If Binance Testnet is unavailable, continue development with database/CSV backtests instead of
  forcing orders.

Runtime diagnostics endpoints:

```powershell
curl -X POST http://127.0.0.1:8000/runtime/diagnostics/run
curl http://127.0.0.1:8000/runtime/diagnostics/latest
curl http://127.0.0.1:8000/runtime/health
```

`/runtime/health` includes a cached `network_readiness` summary and does not call the network on
every request.

## Binance Signature Diagnostics

Binance error `-1022` means the signed request did not validate. Common causes are using the wrong
Testnet secret, hidden whitespace in environment variables, timestamp/recvWindow issues, or a
client bug where the signed query string differs from the transmitted query string.

Use the signed diagnostics script before any real Testnet lifecycle test:

```powershell
python scripts/diagnose_binance_signed_requests.py --testnet --json
python scripts/diagnose_binance_signed_requests.py --testnet --include-test-order --json
python scripts/diagnose_binance_signed_requests.py --testnet --save-report
```

This script may call `GET /api/v3/account` and, with `--include-test-order`, Binance
`POST /api/v3/order/test`. The `order/test` endpoint validates parameters and signatures but does
not enter the matching engine and does not create a real order. The script never calls
`POST /api/v3/order`.

Do not paste API keys, API secrets, full signed query strings, or generated JSON reports into issue
trackers or prompts. Real diagnostics reports under `reports/diagnostics/*.json` are ignored by git.

## Shadow Mode

Shadow Mode is a dry-run observation layer. It records what would have happened after
StrategySignal, SignalReview, DataQualityGate, and RiskEngine finish, but it never submits,
cancels, or modifies real Binance orders.

It records `WOULD_PLACE_ORDER` only when the runtime reached the order path in dry-run or with
`ORDER_EXECUTION_ENABLED=false`. It records `AI_REJECTED`, `RISK_REJECTED`,
`DATA_QUALITY_BLOCKED`, `STRATEGY_NO_TRADE`, and `BUDGET_BLOCKED` for blocked paths when configured.
These records are for diagnosis only and do not bypass RiskEngine, DataQualityGate, or OrderManager.

Run one-time evaluation and reports:

```powershell
python scripts/evaluate_shadow_mode.py --once --json
python scripts/shadow_report.py --hours 24 --json
python scripts/shadow_report.py --hours 24 --save-report
```

Shadow PnL is simulated from later market prices:
`BUY PnL = (current_price - simulated_entry_price) * simulated_quantity`.
MFE and MAE are tracked for observed favorable/adverse movement. Spot `SELL` without known owned
inventory is invalidated rather than treated as a short. Shadow PnL is not account PnL and is not a
profit promise.

Runtime endpoints:

```text
GET  /runtime/shadow/recent
GET  /runtime/shadow/open
GET  /runtime/shadow/report
POST /runtime/shadow/evaluate
```

Generated reports live under `reports/shadow/` and are ignored by git. The recommended next step
before a small Testnet lifecycle test is to run Shadow Mode for 24-72 hours and inspect the report.

## Tests

```powershell
python -m pytest
python -m ruff check .
```

Tests use fake clients/brokers and run without Binance or OpenAI keys.

## Live Mode Is Disabled By Default

Live trading requires all of the following:

- `TRADING_MODE=live`
- `LIVE_TRADING_ENABLED=true`
- `config/risk.yaml` has `live_trading.enabled: true`
- `run_live_guarded.py` passes its guard checks

If any guard is false, `BinanceSpotLiveBroker.place_order()` raises `LiveTradingDisabledError`.
Never enable Live mode with money you cannot afford to lose.

The Testnet runtime daemon always constructs the Testnet broker. `/runtime/testnet/start` and
`/runtime/testnet/start-dry-run` do not use the Live broker.

## API Key Safety

- Never commit `.env`.
- Use read-only or Testnet keys when possible.
- Restrict Binance API keys by IP if you can.
- Rotate keys after accidental exposure.
- Do not paste keys into prompts or issue trackers.

## FAQ

**Does GPT place trades?** No. GPT returns structured review JSON only.

**Does this support futures?** No. Futures has a placeholder interface only.

**Can it short BTC or ETH?** No. Spot MVP can buy and can sell owned inventory only.

**Is this high-frequency trading?** No. It uses 5m entry and 1h trend context.

**Can the bot auto-optimize live parameters?** No. Strategy changes require human review and
backtesting/Testnet validation.

**API Key missing.** Dry-run still starts with public REST/WebSocket paths. User Data Stream and
real Testnet orders require Testnet keys.

**Binance Testnet connection failed.** Check network access and the Testnet base URLs in `.env`.

**OpenAI API Key missing.** AI review fails closed as human-review-required; no order can bypass
RiskEngine.

**AI schema validation failed.** The AI result is persisted as invalid and the trade is rejected.

**exchangeInfo filters failed.** Price, quantity, or notional did not satisfy tickSize, stepSize,
minQty, or minNotional.

**WebSocket disconnected.** Runtime health marks the stream unhealthy, and RiskEngine rejects new
openings.

**User Data Stream event not received.** Reconciliation can query REST order state when real
Testnet execution is enabled.

**Where are reports?** Local reports are under `reports/`. JSON and CSV files are ignored by git
because they may include order IDs, account summaries, or trade records.

## V1 Limits

- Spot only.
- BTCUSDT and ETHUSDT only.
- No futures order placement.
- No leverage.
- No high-frequency trading.
- No martingale or loss-doubling.
- No automatic live strategy parameter optimization.
