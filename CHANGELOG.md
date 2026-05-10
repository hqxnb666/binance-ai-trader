# Changelog

## v0.2.1 - Binance signed request diagnostics and -1022 fix

- Hardened Binance signed request construction so signed canonical query parameters match the
  transmitted query parameters.
- Added a safe signed request diagnostics script for Testnet account and `order/test` checks.
- Added signed request unit and REST mock tests.
- Improved smoke test reporting for Binance `-1022` signature failures.
- Added signed account and `order/test` preflight fields to Testnet readiness checks.

## v0.2.0 - Risk/account/position safety hardening

- Added AccountPositionService for Binance Spot Testnet account and position state snapshots.
- Reused RiskEngine at daemon scope so order frequency and client order ID state persist during runtime.
- Integrated database kill switch state into runtime RiskEngine evaluation.
- Added Testnet order readiness preflight script and readiness report directory.
- Tightened manual Testnet order lifecycle safety checks.
- Added DataQualityGate account/position context and runtime health summaries.
- Added GitHub Actions CI for ruff and pytest without external API requirements.
