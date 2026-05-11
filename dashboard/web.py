from __future__ import annotations

# ruff: noqa: E501


def dashboard_html() -> str:
    """Return the simplified local operations dashboard HTML."""

    return r"""
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Binance AI Trader Dashboard</title>
    <style>
      :root {
        --bg: #f4f6f8;
        --card: #ffffff;
        --border: #e5e7eb;
        --text: #111827;
        --muted: #6b7280;
        --green: #0f766e;
        --green-bg: #ecfdf5;
        --yellow: #a16207;
        --yellow-bg: #fffbeb;
        --red: #b91c1c;
        --red-bg: #fef2f2;
        --blue: #2563eb;
        --blue-bg: #eff6ff;
        --shadow: 0 8px 26px rgba(15, 23, 42, 0.06);
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        background: var(--bg);
        color: var(--text);
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }
      main { max-width: 1440px; margin: 0 auto; padding: 24px; }
      .hero, .card, details.advanced {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 16px;
        box-shadow: var(--shadow);
      }
      .hero { padding: 22px; margin-bottom: 18px; }
      .card { padding: 18px; }
      .grid { display: grid; gap: 16px; }
      .grid-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }
      .grid-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .grid-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      @media (max-width: 1100px) { .grid-4, .grid-3 { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
      @media (max-width: 740px) { main { padding: 14px; } .grid-4, .grid-3, .grid-2 { grid-template-columns: 1fr; } }
      h1 { margin: 0; font-size: 28px; letter-spacing: -0.02em; }
      h2 { margin: 0 0 8px; font-size: 18px; }
      h3 { margin: 14px 0 8px; font-size: 14px; color: var(--muted); }
      p { margin: 0; line-height: 1.6; color: var(--muted); }
      .top-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
      .tag-row, .actions, .mini-actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
      .tag-row { margin-top: 12px; }
      .actions { margin: 18px 0; }
      .badge {
        display: inline-flex; align-items: center; gap: 6px;
        border-radius: 999px; padding: 5px 10px; font-size: 12px; font-weight: 800;
        background: #f3f4f6; color: #374151; border: 1px solid #e5e7eb;
      }
      .ok { background: var(--green-bg); color: var(--green); border-color: #a7f3d0; }
      .warn { background: var(--yellow-bg); color: var(--yellow); border-color: #fde68a; }
      .bad { background: var(--red-bg); color: var(--red); border-color: #fecaca; }
      .info { background: var(--blue-bg); color: var(--blue); border-color: #bfdbfe; }
      button {
        border: 0; border-radius: 12px; padding: 10px 14px; font-weight: 800; cursor: pointer;
        background: #e5e7eb; color: #111827;
      }
      button:hover { filter: brightness(0.98); }
      .btn-primary { background: var(--blue); color: white; }
      .btn-safe { background: var(--green); color: white; }
      .btn-danger { background: var(--red); color: white; }
      .btn-muted { background: #f3f4f6; color: #1f2937; border: 1px solid var(--border); }
      .primary-actions button { min-height: 42px; }
      .metric { border: 1px solid var(--border); border-radius: 14px; padding: 14px; background: #fbfdff; }
      .metric .label { color: var(--muted); font-size: 12px; font-weight: 800; text-transform: uppercase; letter-spacing: .04em; }
      .metric .value { margin-top: 6px; font-size: 20px; font-weight: 900; overflow-wrap: anywhere; }
      .list { display: grid; gap: 8px; margin-top: 10px; }
      .row { display: flex; justify-content: space-between; gap: 12px; padding: 10px 0; border-top: 1px solid #f1f5f9; }
      .row:first-child { border-top: 0; }
      .small { font-size: 12px; color: var(--muted); }
      .section-stack { margin-top: 16px; }
      .notice { padding: 12px; border-radius: 14px; background: var(--blue-bg); border: 1px solid #bfdbfe; color: #1e40af; }
      .warning { background: var(--yellow-bg); border-color: #fde68a; color: #92400e; }
      details.advanced { padding: 16px; margin-top: 18px; }
      details.advanced > summary { cursor: pointer; font-weight: 900; }
      .advanced-grid { margin-top: 14px; display: grid; gap: 16px; grid-template-columns: repeat(2, minmax(0, 1fr)); }
      @media (max-width: 900px) { .advanced-grid { grid-template-columns: 1fr; } }
      textarea, input, select {
        width: 100%; border: 1px solid var(--border); border-radius: 12px; padding: 10px;
        font: inherit; color: var(--text); background: white;
      }
      textarea { min-height: 120px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
      .form-grid { display: grid; gap: 10px; grid-template-columns: repeat(3, minmax(0, 1fr)); }
      @media (max-width: 900px) { .form-grid { grid-template-columns: 1fr; } }
      .compact-json { max-height: 360px; overflow: auto; background: #0f172a; color: #e5e7eb; padding: 12px; border-radius: 12px; font-size: 12px; }
      .hidden { display: none; }
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <div class="top-row">
          <div>
            <h1>Binance AI Trader Dashboard</h1>
            <p>Testnet / Dry-run 安全控制台。本页只展示系统摘要和关键阻断原因；完整原始数据不默认渲染，可一键复制诊断包给 GPT 复盘。</p>
            <p class="small">安全边界：没有真实下单按钮，没有 Live 开关，没有关闭 dry-run 按钮，没有开启 order execution 按钮。</p>
            <div class="tag-row" id="env-tags"></div>
          </div>
          <div class="small">最后刷新：<strong id="last-refresh">-</strong></div>
        </div>
      </section>

      <section class="card">
        <h2>一键诊断中心</h2>
        <p>推荐流程：启动 Dry Run → 一键运行检查 → 加载完整诊断包 → 复制 GPT 完整复盘包。</p>
        <div class="actions primary-actions" id="primary-actions">
          <button class="btn-primary primary-action" onclick="refreshAll()">一键刷新状态</button>
          <button class="btn-primary primary-action" onclick="runAllChecks()">一键运行检查</button>
          <button class="btn-primary primary-action" onclick="loadDiagnosticSnapshot()">加载完整诊断包</button>
          <button class="btn-safe primary-action" onclick="copyFullDiagnosticReviewPackage()">复制 GPT 完整复盘包</button>
          <button class="btn-muted primary-action" id="runtime-toggle" onclick="toggleRuntime()">Start Dry Run</button>
        </div>
        <div class="mini-actions">
          <button class="btn-muted" onclick="copyDiagnosticSnapshot()">复制原始 Diagnostic JSON</button>
          <button class="btn-muted" onclick="copyMissingDataChecklist()">复制缺失数据清单</button>
        </div>
        <p class="small" id="action-result">暂无操作。</p>
      </section>

      <section class="section-stack grid grid-4" id="safety-overview"></section>

      <section class="section-stack grid grid-2">
        <div class="card">
          <h2>Current Diagnosis</h2>
          <div id="current-diagnosis" class="list"></div>
        </div>
        <div class="card">
          <h2>Safety Overview</h2>
          <div id="safety-details" class="list"></div>
        </div>
      </section>

      <section class="section-stack grid grid-3">
        <div class="card">
          <h2>Shadow 摘要</h2>
          <div id="shadow-summary"></div>
        </div>
        <div class="card">
          <h2>StrategyPlan 摘要</h2>
          <div id="strategy-plan-summary"></div>
        </div>
        <div class="card">
          <h2>配置摘要</h2>
          <div id="config-summary"></div>
        </div>
      </section>

      <section class="section-stack grid grid-3">
        <div class="card">
          <h2>Recent Signals</h2>
          <div id="signals-summary"></div>
        </div>
        <div class="card">
          <h2>AI Reviews</h2>
          <div id="ai-summary"></div>
        </div>
        <div class="card">
          <h2>Risk Decisions</h2>
          <div id="risk-summary"></div>
        </div>
      </section>

      <section class="section-stack card">
        <h2>Audit Summary</h2>
        <div id="audit-summary"></div>
      </section>

      <details class="advanced">
        <summary>Advanced：低频操作 / 配置中心 / 复制工具</summary>
        <div class="advanced-grid">
          <div>
            <h3>Runtime 与安全操作</h3>
            <div class="actions">
              <button class="btn-safe" onclick="postAction('启动 Dry Run','/runtime/testnet/start-dry-run')">Start Dry Run</button>
              <button class="btn-muted" onclick="postAction('停止 Dry Run','/runtime/testnet/stop-dry-run')">Stop Dry Run</button>
              <button class="btn-danger" onclick="postAction('打开熔断','/control/kill-switch/on')">Kill Switch ON</button>
              <button class="btn-danger" onclick="postAction('关闭熔断','/control/kill-switch/off','关闭 runtime kill switch 会解除数据库层熔断。仅在确认 dry-run/testnet 安全状态后使用。确认关闭？')">Kill Switch OFF</button>
            </div>
            <h3>检查与报告</h3>
            <div class="actions">
              <button class="btn-muted" onclick="runDataQuality()">Run DataQuality</button>
              <button class="btn-muted" onclick="runReadiness()">Run Readiness</button>
              <button class="btn-muted" onclick="runShadowEvaluation()">Run Shadow Evaluation</button>
              <button class="btn-muted" onclick="runSystemAudit()">Run System Audit</button>
              <button class="btn-muted" onclick="loadOpenAIUsage(1)">Load 1 Day OpenAI Usage</button>
              <button class="btn-muted" onclick="loadOpenAIUsage(7)">Load 7 Day OpenAI Usage</button>
            </div>
            <h3>复制工具</h3>
            <div class="actions">
              <button class="btn-muted" onclick="copyFrontendSnapshot()">Copy Frontend State Snapshot</button>
              <button class="btn-muted" onclick="copyReadinessPackage()">Copy Readiness Review Package</button>
              <button class="btn-muted" onclick="copyStrategyOptimizationPackage()">Copy Strategy Optimization Package</button>
            </div>
          </div>
          <div>
            <h3>策略参数设置中心</h3>
            <p>保存只写入 config/strategy.yaml，不热加载，不重启 runtime，不下单，不改 risk/live/order execution。保存后必须 backtest 和 Shadow Mode 验证。</p>
            <div class="actions">
              <button class="btn-muted" onclick="loadStrategyConfig()">Load Strategy Config</button>
              <button class="btn-muted" onclick="validateStrategyDraft()">Validate Strategy Draft</button>
              <button class="btn-primary" onclick="saveStrategyDraft()">Save Strategy Config</button>
              <button class="btn-muted" onclick="resetStrategyDraft()">Reset Draft</button>
            </div>
            <div id="strategy-form" class="form-grid"></div>
            <div id="strategy-validation" class="small">尚未运行校验。</div>
          </div>
        </div>
        <details>
          <summary>调试用折叠 JSON 预览（默认关闭，高度限制）</summary>
          <pre class="compact-json" id="debug-json">尚未加载完整诊断包。</pre>
        </details>
      </details>
    </main>

    <script>
      const api = {
        summary: mod("/runtime/dashboard-summary"),
        health: mod("/runtime/health"),
        diagnostic: mod("/runtime/diagnostic-snapshot"),
        strategyConfig: mod("/config/strategy"),
        riskConfig: mod("/config/risk"),
        readinessLatest: mod("/runtime/readiness/latest"),
      };
      let diagnosticSnapshot = null;
      let readinessData = null;
      let openaiUsageData = null;
      let strategyDraft = null;
      let strategyCurrent = null;

      function mod(url) { return { url, data: null, error: null, loading: false, last: null }; }
      function get(obj, path, fallback = "—") {
        try {
          const value = String(path).split(".").reduce((acc, key) => acc == null ? undefined : acc[key], obj);
          return value == null || value === "" ? fallback : value;
        } catch { return fallback; }
      }
      function esc(value) {
        return String(value ?? "—").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
      }
      function badge(value, label) {
        const text = String(label ?? value ?? "UNKNOWN");
        const upper = String(value ?? "").toUpperCase();
        let cls = "badge";
        if (["TRUE", "OK", "SAFE", "RUNNING", "TESTNET", "SUCCESS", "APPROVED"].includes(upper)) cls += " ok";
        else if (["FALSE"].includes(upper) && /live|order/i.test(text)) cls += " ok";
        else if (["WATCH", "WARNING", "WARN", "DEGRADED", "UNKNOWN", "STOPPED"].includes(upper)) cls += " warn";
        else if (["ERROR", "CRITICAL", "FAILED", "BLOCKED", "LIVE"].includes(upper)) cls += " bad";
        else cls += " info";
        return `<span class="${cls}">${esc(text)}</span>`;
      }
      function metric(label, value, state) {
        return `<div class="metric"><div class="label">${esc(label)}</div><div class="value">${badge(state ?? value, value)}</div></div>`;
      }
      function row(label, value) { return `<div class="row"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`; }
      function list(items, renderer, empty = "暂无数据。") {
        if (!Array.isArray(items) || items.length === 0) return `<p class="small">${esc(empty)}</p>`;
        return `<div class="list">${items.map(renderer).join("")}</div>`;
      }
      async function fetchJson(url, options = {}) {
        const res = await fetch(url, { cache: "no-store", ...options });
        if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
        return res.json();
      }
      async function fetchModule(name) {
        const item = api[name];
        item.loading = true;
        try {
          item.data = await fetchJson(item.url);
          item.error = null;
          item.last = new Date().toLocaleTimeString();
          if (name === "strategyConfig") applyStrategyConfig(item.data);
        } catch (error) {
          item.error = error.message || String(error);
        } finally {
          item.loading = false;
        }
      }
      async function refreshAll() {
        await Promise.all(["summary", "health", "strategyConfig", "riskConfig", "readinessLatest"].map(fetchModule));
        if (api.readinessLatest.data && api.readinessLatest.data.status !== "NO_READINESS_CHECK_RUN") readinessData = api.readinessLatest.data;
        document.getElementById("last-refresh").textContent = new Date().toLocaleTimeString();
        setAction("状态已刷新。");
        render();
      }
      async function postAction(label, url, confirmText) {
        if (confirmText && !window.confirm(confirmText)) return;
        try {
          const data = await fetchJson(url, { method: "POST" });
          setAction(`${label} 完成：${JSON.stringify(data).slice(0, 180)}`);
          await refreshAll();
        } catch (error) { setAction(`${label} 失败：${error.message || error}`, true); }
      }
      async function runDataQuality() { return postAction("DataQuality 检查", "/runtime/data-quality/check"); }
      async function runShadowEvaluation() { return postAction("Shadow 评估", "/runtime/shadow/evaluate"); }
      async function runSystemAudit() { return postAction("系统审计", "/runtime/audits/run"); }
      async function runReadiness() {
        try {
          readinessData = await fetchJson("/runtime/readiness/check", { method: "POST" });
          api.readinessLatest.data = readinessData;
          setAction("Readiness 检查完成。");
          await refreshAll();
        } catch (error) { setAction(`Readiness 检查失败：${error.message || error}`, true); }
      }
      async function runAllChecks() {
        const steps = [
          ["DataQuality", () => fetchJson("/runtime/data-quality/check", { method: "POST" })],
          ["Readiness", async () => { readinessData = await fetchJson("/runtime/readiness/check", { method: "POST" }); return readinessData; }],
          ["Shadow", () => fetchJson("/runtime/shadow/evaluate", { method: "POST" })],
          ["Audit", () => fetchJson("/runtime/audits/run", { method: "POST" })],
        ];
        const results = [];
        for (const [name, fn] of steps) {
          try { await fn(); results.push(`${name}: OK`); }
          catch (error) { results.push(`${name}: 失败 ${String(error.message || error).slice(0, 120)}`); }
        }
        setAction(`一键运行检查完成：${results.join("；")}`);
        await refreshAll();
      }
      async function loadDiagnosticSnapshot() {
        try {
          diagnosticSnapshot = await fetchJson("/runtime/diagnostic-snapshot?shadow_limit=100&signal_limit=50&plan_limit=10");
          api.diagnostic.data = diagnosticSnapshot;
          document.getElementById("debug-json").textContent = JSON.stringify(diagnosticSnapshot, null, 2);
          setAction("完整诊断包已加载。页面只显示摘要，完整数据已保存在内存中用于复制。");
          await fetchModule("summary");
          render();
        } catch (error) { setAction(`加载完整诊断包失败：${error.message || error}`, true); }
      }
      async function toggleRuntime() {
        const running = get(api.summary.data, "safety.runtime_state") === "RUNNING";
        await postAction(running ? "停止 Dry Run" : "启动 Dry Run", running ? "/runtime/testnet/stop-dry-run" : "/runtime/testnet/start-dry-run");
      }
      function setAction(text, isError = false) {
        const el = document.getElementById("action-result");
        el.textContent = text;
        el.style.color = isError ? "var(--red)" : "var(--muted)";
      }
      function render() {
        const s = api.summary.data || {};
        renderHeader(s); renderSafety(s); renderDiagnosis(s); renderShadow(s); renderStrategyPlan(s);
        renderSignalAiRisk(s); renderConfig(s); renderAudit(s); renderStrategyForm();
      }
      function renderHeader(s) {
        const safety = s.safety || {};
        document.getElementById("env-tags").innerHTML = [
          badge(safety.trading_mode || "testnet"),
          badge(safety.dry_run === true ? "OK" : "CRITICAL", `dry-run ${safety.dry_run}`),
          badge(safety.order_execution_enabled === false ? "OK" : "CRITICAL", `order execution ${safety.order_execution_enabled}`),
          badge(safety.live_trading_enabled === false ? "OK" : "CRITICAL", `live ${safety.live_trading_enabled}`),
        ].join("");
        document.getElementById("runtime-toggle").textContent = safety.runtime_state === "RUNNING" ? "Stop Dry Run" : "Start Dry Run";
      }
      function renderSafety(s) {
        const safety = s.safety || {};
        document.getElementById("safety-overview").innerHTML = [
          metric("Runtime", safety.runtime_state, safety.runtime_state),
          metric("Trading Mode", safety.trading_mode, safety.trading_mode),
          metric("Dry Run", safety.dry_run, safety.dry_run === true ? "OK" : "CRITICAL"),
          metric("Order Execution", safety.order_execution_enabled, safety.order_execution_enabled === false ? "OK" : "CRITICAL"),
          metric("Live Trading", safety.live_trading_enabled, safety.live_trading_enabled === false ? "OK" : "CRITICAL"),
          metric("Kill Switch", safety.kill_switch_enabled, safety.kill_switch_enabled ? "WATCH" : "OK"),
          metric("Market Stream", safety.market_stream_connected, safety.market_stream_connected ? "OK" : "UNKNOWN"),
          metric("DataQuality", safety.data_quality || "UNKNOWN", safety.data_quality || "UNKNOWN"),
        ].join("");
        document.getElementById("safety-details").innerHTML = [
          row("User Stream", safety.user_stream_connected),
          row("Safe for Order", safety.safe_for_order),
          row("Primary Status", get(s, "diagnosis.primary_status")),
          row("缺失数据", (get(s, "diagnosis.missing_sections", []) || []).join(", ") || "无"),
        ].join("");
      }
      function renderDiagnosis(s) {
        const items = get(s, "diagnosis.human_summary", []);
        document.getElementById("current-diagnosis").innerHTML = list(items, (item) => `<div class="notice warning">${esc(item)}</div>`, "暂无诊断结论。请先加载完整诊断包或刷新状态。");
      }
      function renderShadow(s) {
        const sh = s.shadow || {};
        document.getElementById("shadow-summary").innerHTML = `<div class="grid grid-2">${[
          row("total_decisions", sh.total_decisions),
          row("WOULD_PLACE_ORDER", sh.would_place_order_count),
          row("Risk rejected", sh.risk_rejected_count),
          row("AI rejected", sh.ai_rejected_count),
          row("DataQuality blocked", sh.data_quality_blocked_count),
          row("模拟 PnL", sh.simulated_total_pnl_usdt),
        ].join("")}</div><h3>Top 5 rejection reasons</h3>${list(sh.top_rejection_reasons, (x) => `<div class="row"><span>${esc(x.reason)}</span><strong>${esc(x.count)}</strong></div>`)}`;
      }
      function renderStrategyPlan(s) {
        const p = s.strategy_plan || {};
        document.getElementById("strategy-plan-summary").innerHTML = [
          row("Active status", p.active_status),
          row("risk_mode", p.risk_mode),
          row("trade_bias", p.trade_bias),
          row("requires_human_review", p.requires_human_review),
          row("FAILED", p.failed_count),
          row("ACTIVE", p.active_count),
          row("SUPERSEDED", p.superseded_count),
          row("SCHEMA_INVALID", p.schema_invalid_count),
          `<h3>最近 5 条 plan</h3>`,
          list(p.recent_compact, (x) => `<div class="row"><span>#${esc(x.id)} ${esc(x.status)} ${esc(x.risk_mode || "—")} / ${esc(x.trade_bias || "—")}<br><span class="small">${esc((x.reason_codes || []).join(", "))}</span></span><strong>${esc(x.expires_at)}</strong></div>`),
        ].join("");
      }
      function renderSignalAiRisk(s) {
        const sig = s.signals || {}, ai = s.ai_reviews || {}, risk = s.risk || {};
        document.getElementById("signals-summary").innerHTML = [row("总数", sig.total), row("BTCUSDT BUY", get(sig, "by_symbol_side.BTCUSDT_BUY", 0)), row("ETHUSDT BUY", get(sig, "by_symbol_side.ETHUSDT_BUY", 0)), row("最新 signal", sig.latest_signal_at)].join("");
        document.getElementById("ai-summary").innerHTML = [row("APPROVE", ai.approve_count), row("HUMAN_REVIEW", ai.human_review_count), row("REJECT", ai.reject_count)].join("");
        document.getElementById("risk-summary").innerHTML = [row("approved", risk.approved_count), row("rejected", risk.rejected_count), `<h3>Top 5 reasons</h3>`, list(risk.top_reasons, (x) => `<div class="row"><span>${esc(x.reason)}</span><strong>${esc(x.count)}</strong></div>`)].join("");
      }
      function renderConfig(s) {
        const strategy = get(s, "config.strategy", {});
        const risk = get(s, "config.risk", {});
        document.getElementById("config-summary").innerHTML = [
          row("ema_fast / ema_slow", `${get(strategy, "ema_fast")} / ${get(strategy, "ema_slow")}`),
          row("rsi_min / rsi_max", `${get(strategy, "rsi_min")} / ${get(strategy, "rsi_max")}`),
          row("volume_ratio_min", get(strategy, "volume_ratio_min")),
          row("max_position_pct_per_symbol", get(risk, "max_position_pct_per_symbol")),
          row("max_total_position_pct", get(risk, "max_total_position_pct")),
          row("allow_limit_orders", get(risk, "allow_limit_orders")),
          row("allow_market_orders", get(risk, "allow_market_orders")),
          row("kill_switch_enabled", get(risk, "kill_switch_enabled")),
        ].join("");
      }
      function renderAudit(s) {
        const audit = s.audit || {};
        document.getElementById("audit-summary").innerHTML = [row("overall_status", audit.overall_status), row("highest_severity", audit.highest_severity), row("issue_count", audit.issue_count), `<p>${esc(audit.summary || "暂无审计摘要。")}</p><h3>Top issues</h3>`, list(audit.top_issues, (x) => `<div class="row"><span>${badge(x.severity)} ${esc(x.category)}：${esc(x.title)}</span></div>`, "暂无 issues。")].join("");
      }
      function applyStrategyConfig(payload) {
        if (!payload || !payload.config) return;
        strategyCurrent = JSON.parse(JSON.stringify(payload.config));
        if (!strategyDraft) strategyDraft = JSON.parse(JSON.stringify(payload.config));
      }
      async function loadStrategyConfig() { await fetchModule("strategyConfig"); renderStrategyForm(); setAction("策略配置已加载。"); }
      function renderStrategyForm() {
        const host = document.getElementById("strategy-form");
        if (!strategyDraft || !strategyDraft.ema_trend) { host.innerHTML = `<p class="small">点击 Load Strategy Config 后可编辑 EMA Trend 参数。</p>`; return; }
        const fields = ["enabled","entry_timeframe","trend_timeframe","ema_fast","ema_slow","rsi_period","rsi_min","rsi_max","atr_period","volume_ratio_min","take_profit_r_multiple","stop_loss_atr_multiple"];
        host.innerHTML = fields.map((field) => `<label class="small"><strong>${field}</strong><input id="sp-${field}" value="${esc(strategyDraft.ema_trend[field])}" /></label>`).join("");
      }
      function collectStrategyDraft() {
        const fields = ["enabled","entry_timeframe","trend_timeframe","ema_fast","ema_slow","rsi_period","rsi_min","rsi_max","atr_period","volume_ratio_min","take_profit_r_multiple","stop_loss_atr_multiple"];
        const ints = new Set(["ema_fast","ema_slow","rsi_period","atr_period"]);
        const floats = new Set(["rsi_min","rsi_max","volume_ratio_min","take_profit_r_multiple","stop_loss_atr_multiple"]);
        const ema = {};
        fields.forEach((field) => {
          const raw = document.getElementById(`sp-${field}`)?.value;
          if (field === "enabled") ema[field] = String(raw).toLowerCase() === "true";
          else if (ints.has(field)) ema[field] = parseInt(raw, 10);
          else if (floats.has(field)) ema[field] = parseFloat(raw);
          else ema[field] = raw;
        });
        return { ema_trend: ema };
      }
      async function validateStrategyDraft() {
        try {
          const result = await fetchJson("/config/strategy/validate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(collectStrategyDraft()) });
          document.getElementById("strategy-validation").textContent = result.valid ? "校验通过。" : `校验失败：${(result.errors || []).join("; ")}`;
        } catch (error) { document.getElementById("strategy-validation").textContent = `校验失败：${error.message || error}`; }
      }
      async function saveStrategyDraft() {
        if (!window.confirm("保存策略参数只会写入 config/strategy.yaml，不会热加载、不会重启 runtime、不会下单。保存后请运行 backtest 和 Shadow Mode 验证。确认保存？")) return;
        try {
          const result = await fetchJson("/config/strategy/save", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(collectStrategyDraft()) });
          document.getElementById("strategy-validation").textContent = result.saved ? "已保存。pending_restart=true，请重启后生效。" : `未保存：${(result.errors || []).join("; ")}`;
        } catch (error) { document.getElementById("strategy-validation").textContent = `保存失败：${error.message || error}`; }
      }
      function resetStrategyDraft() { strategyDraft = JSON.parse(JSON.stringify(strategyCurrent || {})); renderStrategyForm(); }
      async function loadOpenAIUsage(days) {
        try { openaiUsageData = await fetchJson(`/runtime/openai-usage?days=${days}`); setAction(`OpenAI ${days} 天用量已加载，可复制前端快照或 GPT 包。`); }
        catch (error) { setAction(`OpenAI 用量加载失败：${error.message || error}`, true); }
      }
      function unavailableSections(snapshot) {
        const missing = [];
        Object.entries(snapshot || {}).forEach(([key, value]) => {
          if (value && typeof value === "object" && String(value.status || "").startsWith("NO_")) missing.push(`${key}: ${value.status}`);
          if (value && typeof value === "object" && value.status === "NOT_AVAILABLE") missing.push(`${key}: ${value.reason || "NOT_AVAILABLE"}`);
        });
        return [...new Set(missing)];
      }
      async function copyToClipboard(label, payload) {
        const text = String(payload ?? "");
        try {
          if (navigator.clipboard) await navigator.clipboard.writeText(text);
          else throw new Error("clipboard unavailable");
          setAction(`${label} 已复制。`);
        } catch {
          const area = document.createElement("textarea"); area.value = text; document.body.appendChild(area); area.focus(); area.select(); setAction(`${label}：剪贴板不可用，已选中文本，请手动复制。`);
        }
      }
      function frontendSnapshot() { return { summary: api.summary.data || {}, health: api.health.data || {}, readiness: readinessData || api.readinessLatest.data || {}, openai_usage: openaiUsageData || {}, diagnostic_snapshot_loaded: Boolean(diagnosticSnapshot) }; }
      function copyFrontendSnapshot() { return copyToClipboard("前端状态快照", JSON.stringify(frontendSnapshot(), null, 2)); }
      function copyDiagnosticSnapshot() { return copyToClipboard("Diagnostic JSON", JSON.stringify(diagnosticSnapshot || api.diagnostic.data || {}, null, 2)); }
      function copyMissingDataChecklist() {
        const missing = unavailableSections(diagnosticSnapshot || api.diagnostic.data || {});
        return copyToClipboard("缺失数据清单", missing.length ? missing.map((x) => `- ${x}`).join("\n") : "- 当前没有检测到缺失项。");
      }
      function diagnosticReviewPackage() {
        const snap = diagnosticSnapshot || api.diagnostic.data || {};
        return `项目：binance-ai-trader
当前目标：基于完整诊断快照，判断 Testnet dry-run / Shadow Mode 下系统为什么没有产生 WOULD_PLACE_ORDER，并给出小步、安全、可验证的优化建议。

安全边界：
1. 不允许绕过 RiskEngine。
2. 不允许启用 Live。
3. 不允许 GPT 直接下单。
4. 不允许修改 OrderManager 唯一订单入口。
5. 不允许新增 Futures、Margin、Leverage。
6. 不允许为了增加交易数量而关闭 DataQualityGate。
7. 不允许直接放宽风控上限来换取交易。
8. 所有策略参数修改必须先 backtest，再 Shadow Mode 验证。

请判断：
1. 当前主要问题属于数据质量、本地 EMA 策略、StrategyPlan no-trade / human review、AI SignalReview、RiskEngine 仓位限制、Testnet 账户状态污染、Shadow 评价口径、样本不足还是执行链路。
2. 当前 0 WOULD_PLACE_ORDER 的第一主因和第二主因分别是什么。
3. 是否需要先清理 dry-run / shadow 账户基线，而不是直接调 EMA 参数。
4. EMA 参数是否有调整必要；如果有，一次最多建议 1-2 个参数。
5. 哪些地方绝对不能改。
6. 给出一个有边界的 Codex 修改提示词。
7. 给出修改后的验证命令。

【Diagnostic Snapshot】
${JSON.stringify(snap, null, 2)}
`;
      }
      function copyFullDiagnosticReviewPackage() { return copyToClipboard("GPT 完整复盘包", diagnosticReviewPackage()); }
      function copyReadinessPackage() { return copyToClipboard("Readiness 复盘包", JSON.stringify(readinessData || api.readinessLatest.data || {}, null, 2)); }
      function copyStrategyOptimizationPackage() { return copyToClipboard("策略优化包", diagnosticReviewPackage()); }

      refreshAll();
      setInterval(() => refreshAll(), 15000);
    </script>
  </body>
</html>
"""
