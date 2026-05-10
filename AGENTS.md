# Instructions For Future AI Coding Agents

This repository is a trading system. Treat safety controls as production-critical.

1. Do not commit `.env` or any secret-bearing file.
2. Do not hardcode API keys, secrets, account IDs, or private credentials.
3. Do not default-enable Live Trading.
4. Do not bypass `RiskEngine`.
5. Do not let any AI module call `place_order`, `new_order`, or broker order methods.
6. Do not implement martingale, infinite averaging down, or loss-doubling position sizing.
7. Do not delete tests to make a change pass.
8. Any risk-control change must add or update tests.
9. Any Binance signing change must add or update tests.
10. Any AI schema change must add or update tests.
11. Every PR must explicitly state whether it affects Live Trading.
12. Every strategy change must state whether it requires backtesting before Testnet or Live use.
13. Runtime daemon changes must add or update tests.
14. Dry-run mode must not be removed.
15. `ORDER_EXECUTION_ENABLED` must default to `false`.
16. Any real Testnet order path must be protected by explicit configuration.
17. Any Live path modification must prove default configuration cannot place orders.
18. WebSocket reconnect logic changes must add or update health tests.
19. User Data Stream event mapping changes must add or update tests.
20. Strategy changes must not automatically modify Live configuration.
21. Any real Testnet `new_order` must be protected by an explicit CLI flag.
22. Order lifecycle scripts must force `TRADING_MODE=testnet`.
23. Backtests must not call OpenAI.
24. Backtests must not call broker order methods.
25. Backtests must not use future data.
26. Generated report files should not be committed by default.
27. Any Live broker change must update `test_live_guard`.
28. Any reconciliation change must add or update tests.
29. Do not describe backtest results as a profit promise.
30. Do not read or modify Clash, VPN, or system proxy configuration files.
31. Do not implement automatic proxy switching.
32. Do not suggest bypassing Binance regional restrictions.
33. Diagnostics may report proxy env presence, but must not print proxy URLs.
34. Diagnostics must fail closed when Binance reports region restrictions.
35. OpenAI model routing changes must add or update tests.
36. `OPENAI_MODEL` is legacy fallback only; do not restore `gpt-5.1-mini` as a default.
37. Do not default to `gpt-5.5-pro`, `gpt-5.4-pro`, or any high-cost pro model.
38. GPT-5.5 is reserved for low-frequency Strategy Planner work unless a human approves otherwise.
39. SignalReview must use the signal-review model role, not the Strategy Planner model role.
40. StrategyPlan records may constrain review context but must never create order requests.
41. Strategy Planner prompts and schemas must keep `place_order`, quantity, price, and client order
    IDs out of model output.
42. StrategyPlan persistence must sanitize raw input/output and must not store API keys or `.env`
    contents.
43. Changing `.env` model settings requires runtime restart; do not add hot reload that reads
    secrets into logs.
44. Do not submit real diagnostics, smoke test, order lifecycle, or model-list reports.
45. BudgetGuard must fail closed when configured budget or role call limits are exceeded.
46. Do not disable `ENABLE_BUDGET_GUARD` or `ENABLE_OPENAI_USAGE_LEDGER` by default.
47. Do not auto-fallback to a more expensive OpenAI model when budget is exceeded.
48. OpenAIUsageLedger must not store API keys, request headers, raw prompts, raw responses, or
    Binance secrets.
49. AI contexts must mark unknown account or position data as `unknown`; never invent balances or
    positions.
50. Simulated account defaults must be explicitly labeled `source=simulated_default`.
51. AI context changes must keep JSON size bounded and add or update tests.
52. SystemAuditor and TradingIssueAuditor must remain read-only report generators.
53. Do not turn any auditor into an automatic fixer or allow it to call Codex.
54. Auditor code must not call `OrderManager`, broker order methods, or Binance `new_order`.
55. Auditor code must not bypass `RiskEngine` or influence order approval.
56. Auditor code must not modify `.env`, risk config, strategy config, or Live Trading settings.
57. Audit reports in `reports/audits/*.json` must not be committed.
58. Auditor schema, context, runtime, or API changes must add or update tests.
59. DataQualityGate must remain a read-only blocking/degrading gate; it must not call broker order
    methods, OpenAI order paths, Codex, or config writers.
60. DataQualityGate failures may only reduce permissions or require human review; they must never
    relax RiskEngine, exchange filters, account checks, or order execution flags.
61. Critical DataQualityGate results must block StrategyPlanner, SignalReview, and OrderManager
    entry points unless a human explicitly changes the documented safety policy and tests.
62. Real Testnet order paths must require user stream, account state, position state, and exchange
    filters to be available.
63. Dry-run may tolerate unknown data only when it is explicitly marked degraded or unknown.
64. Data quality reports in `reports/data_quality/*.json` must not be committed.
65. DataQualityGate schema, runtime, smoke-test, diagnostics, or API changes must add or update
    tests.
66. Do not add `HumanApprovalGate`, pending approval intents, or manual approval APIs unless a
    human explicitly reverses the current scope.
67. AccountPositionService must remain read-only and must never call broker order methods.
68. Runtime real Testnet order paths must require account state `OK`, position state `OK`, user
    stream availability, exchange filters, DataQualityGate safe state, and kill switch off.
69. The database kill switch and config kill switch must both be honored by runtime RiskEngine.
70. RiskEngine runtime state should be reused by the daemon so rate limiting and duplicate
    `client_order_id` checks remain effective during the daemon lifetime.
71. Readiness reports in `reports/readiness/*.json` must not be committed.

Default assumption: this project is Testnet-only unless a human deliberately enables Live mode
through both environment variables and checked configuration.
