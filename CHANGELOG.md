# Changelog

## v0.2.0 - Risk/account/position safety hardening

- Added AccountPositionService for Binance Spot Testnet account and position state snapshots.
- Reused RiskEngine at daemon scope so order frequency and client order ID state persist during runtime.
- Integrated database kill switch state into runtime RiskEngine evaluation.
- Added Testnet order readiness preflight script and readiness report directory.
- Tightened manual Testnet order lifecycle safety checks.
- Added DataQualityGate account/position context and runtime health summaries.
- Added GitHub Actions CI for ruff and pytest without external API requirements.
