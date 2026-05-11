from __future__ import annotations

# ruff: noqa: E501


def dashboard_html() -> str:
    """Return the local Dashboard V2 HTML."""

    return r"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Binance AI Trader Local Operations Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
      body { font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
      pre { white-space: pre-wrap; word-break: break-word; }
      textarea { min-height: 11rem; }
      html { scroll-behavior: smooth; }
    </style>
  </head>
  <body class="bg-slate-100 text-slate-950">
    <main class="mx-auto max-w-[1800px] px-4 py-5 sm:px-6 lg:px-8">
      <header id="overview" class="mb-5 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <p class="text-xs font-semibold uppercase tracking-wide text-emerald-700">Local Testnet / dry-run / Shadow Mode console</p>
            <h1 class="mt-1 text-2xl font-semibold tracking-tight">Binance AI Trader Local Operations Dashboard</h1>
            <p class="mt-2 max-w-5xl text-sm text-slate-600">
              Dashboard V2 is a local control and review surface for Testnet-first operations. It observes runtime health, data quality, StrategyPlanner/SignalReviewer outputs, RiskEngine decisions, orders, Shadow Mode, audits, readiness, and OpenAI usage.
            </p>
            <p class="mt-2 text-xs font-bold text-red-700">
              Safety boundary: No real order button, No Live switch, No disable-dry-run button, No order execution enable button, No automatic Codex call.
            </p>
          </div>
          <div class="flex flex-wrap gap-2">
            <button class="btn-primary" onclick="refreshAll()">Refresh All</button>
            <button class="btn-safe" onclick="postAction('Start Dry Run','/runtime/testnet/start-dry-run')">Start Dry Run</button>
            <button class="btn-muted" onclick="postAction('Stop Dry Run','/runtime/testnet/stop-dry-run')">Stop Dry Run</button>
            <button class="btn-muted" onclick="postAction('Run Data Quality Check','/runtime/data-quality/check')">Run Data Quality Check</button>
            <button class="btn-muted" onclick="postAction('Run Shadow Evaluation','/runtime/shadow/evaluate')">Run Shadow Evaluation</button>
            <button class="btn-muted" onclick="postAction('Run System Audit','/runtime/audits/run')">Run System Audit</button>
            <button class="btn-warn" onclick="postAction('Kill Switch ON','/control/kill-switch/on')">Kill Switch ON</button>
            <button class="btn-danger" onclick="postAction('Kill Switch OFF','/control/kill-switch/off','Turning OFF the runtime kill switch removes the database circuit breaker. Use only after confirming dry-run/testnet safety. Continue?')">Kill Switch OFF</button>
          </div>
        </div>
        <div class="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          Kill Switch OFF warning: closing the runtime kill switch only removes the database-layer circuit breaker. Confirm dry-run/testnet safety first.
        </div>
        <div class="mt-4 flex flex-wrap items-center gap-3 text-xs text-slate-500">
          <span>Page last refreshed: <strong id="page-last-refresh">-</strong></span>
          <span id="action-result" class="rounded-md bg-slate-100 px-2 py-1 text-slate-700">No actions yet.</span>
        </div>
      </header>

      <nav class="sticky top-0 z-20 mb-5 rounded-lg border border-slate-200 bg-white/95 p-3 shadow-sm backdrop-blur">
        <div class="flex flex-wrap gap-2 text-xs font-bold">
          <a class="nav-chip" href="#overview">Overview</a>
          <a class="nav-chip" href="#runtime">Runtime</a>
          <a class="nav-chip" href="#data-quality">Data Quality</a>
          <a class="nav-chip" href="#strategy">Strategy</a>
          <a class="nav-chip" href="#ai-review">AI Review</a>
          <a class="nav-chip" href="#risk">Risk</a>
          <a class="nav-chip" href="#orders">Orders</a>
          <a class="nav-chip" href="#shadow">Shadow</a>
          <a class="nav-chip" href="#account">Account</a>
          <a class="nav-chip" href="#budget">Budget</a>
          <a class="nav-chip" href="#audit">Audit</a>
          <a class="nav-chip" href="#logs">Logs</a>
          <a class="nav-chip" href="#strategy-params">Strategy Params</a>
          <a class="nav-chip" href="#risk-config">Risk Config</a>
          <a class="nav-chip" href="#readiness">Readiness</a>
          <a class="nav-chip" href="#review-workspace">Review Workspace</a>
        </div>
      </nav>

      <section class="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8" id="safety-overview"></section>

      <div class="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <section id="runtime" class="panel">
          <div class="panel-head"><div><h2>Runtime</h2><p>Runtime starts streams, REST polling, strategy, AI review, risk checks, Shadow evaluation, and audit tasks.</p></div><span id="meta-health" class="module-meta">-</span></div>
          <div id="runtime-body" class="kv-grid"></div>
        </section>

        <section id="streams" class="panel">
          <div class="panel-head"><div><h2>Streams &amp; Network</h2><p>Use this module to inspect Binance Testnet market stream, user stream, and cached network readiness.</p></div><span id="meta-status" class="module-meta">-</span></div>
          <div id="streams-body" class="space-y-3"></div>
        </section>

        <section id="data-quality" class="panel">
          <div class="panel-head"><div><h2>DataQualityGate</h2><p>DataQualityGate is the pre-trade data quality gate. Critical status blocks StrategyPlanner, SignalReview, and order paths.</p></div><span id="meta-dataQuality" class="module-meta">-</span></div>
          <div id="data-quality-body" class="space-y-3"></div>
        </section>

        <section id="strategy" class="panel">
          <div class="panel-head"><div><h2>Strategy Snapshot</h2><p>The EMA Trend strategy creates candidate signals only. It cannot place orders directly.</p></div><span id="meta-snapshots" class="module-meta">-</span></div>
          <div id="strategy-body" class="space-y-3"></div>
        </section>

        <section id="ai-review" class="panel">
          <div class="panel-head"><div><h2>AI SignalReview</h2><p>SignalReviewer returns structured JSON and cannot place orders. Approved intent still must pass RiskEngine.</p></div><span id="meta-aiReviews" class="module-meta">-</span></div>
          <div id="ai-body" class="space-y-3"></div>
        </section>

        <section id="risk" class="panel">
          <div class="panel-head"><div><h2>RiskEngine</h2><p>RiskEngine is the hard risk layer. All trade intent must pass it before OrderManager is reachable.</p></div><span id="meta-riskDecisions" class="module-meta">-</span></div>
          <div id="risk-body" class="space-y-3"></div>
        </section>

        <section id="orders" class="panel">
          <div class="panel-head"><div><h2>OrderManager / Recent Orders</h2><p>OrderManager is the only order entry point. In dry-run or disabled execution mode, no Binance new_order is submitted.</p></div><span id="meta-orders" class="module-meta">-</span></div>
          <div id="orders-body" class="space-y-3"></div>
        </section>

        <section id="shadow" class="panel">
          <div class="panel-head"><div><h2>Shadow Mode</h2><p>Shadow Mode records what would have happened and calculates simulated PnL, MFE, and MAE. It does not trade.</p></div><span id="meta-shadowReport" class="module-meta">-</span></div>
          <div class="mb-3 flex flex-wrap gap-2">
            <button class="btn-muted" onclick="postAction('Run Shadow Evaluation','/runtime/shadow/evaluate')">Run Shadow Evaluation</button>
            <button class="btn-muted" onclick="copyJson('Shadow Report', api.shadowReport.data)">Copy Shadow Report</button>
            <button class="btn-muted" onclick="copyShadowPrompt()">Copy GPT Shadow Review Prompt</button>
          </div>
          <div id="shadow-body" class="space-y-3"></div>
        </section>

        <section id="account" class="panel">
          <div class="panel-head"><div><h2>Account / Position</h2><p>Shows Testnet account/position readiness and whether simulated defaults are being used.</p></div><span id="meta-configSafe" class="module-meta">-</span></div>
          <div id="account-body" class="space-y-3"></div>
        </section>

        <section id="budget" class="panel">
          <div class="panel-head"><div><h2>OpenAI Budget</h2><p>OpenAI Budget controls StrategyPlanner, SignalReviewer, SystemAuditor, and report costs.</p></div><span id="meta-riskState" class="module-meta">-</span></div>
          <div id="budget-body" class="space-y-3"></div>
        </section>

        <section id="audit" class="panel">
          <div class="panel-head"><div><h2>SystemAuditor</h2><p>SystemAuditor is read-only. It cannot modify code/config, call Codex, or place orders.</p></div><span id="meta-auditLatest" class="module-meta">-</span></div>
          <div class="mb-3 flex flex-wrap gap-2">
            <button class="btn-muted" onclick="postAction('Run System Audit','/runtime/audits/run')">Run System Audit</button>
            <button class="btn-muted" onclick="copyJson('Audit JSON', api.auditLatest.data)">Copy Audit JSON</button>
            <button class="btn-muted" onclick="copyAuditPrompt()">Copy GPT Audit Review Prompt</button>
          </div>
          <div id="audit-body" class="space-y-3"></div>
        </section>

        <section id="logs" class="panel">
          <div class="panel-head"><div><h2>Logs / Pipeline</h2><p>Logs and pipeline audit help locate the step where snapshot, signal, AI, risk, order, stream, reconciliation, or review stalled.</p></div><span id="meta-logs" class="module-meta">-</span></div>
          <div id="logs-body" class="space-y-3"></div>
        </section>

        <section id="strategy-params" class="panel xl:col-span-2">
          <div class="panel-head">
            <div>
              <h2>Strategy Parameter Center</h2>
              <p>This module views and edits local EMA Trend strategy parameters. Save only writes config/strategy.yaml; it does not hot reload, restart runtime, or trigger orders. Changes require backtest and Shadow Mode validation.</p>
            </div>
            <span id="meta-strategyConfig" class="module-meta">-</span>
          </div>
          <div class="mb-3 flex flex-wrap gap-2">
            <button class="btn-muted" onclick="loadStrategyConfig()">Load Strategy Config</button>
            <button class="btn-muted" onclick="validateStrategyDraft()">Validate Draft</button>
            <button class="btn-primary" onclick="saveStrategyDraft()">Save Strategy Config</button>
            <button class="btn-muted" onclick="resetStrategyDraft()">Reset Draft</button>
            <button class="btn-muted" onclick="copyStrategyOptimizationPackage()">Copy Strategy Optimization Prompt</button>
          </div>
          <div class="rounded-md border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900">
            Save confirmation: strategy save only writes config/strategy.yaml. It does not hot reload, restart runtime, or place orders. After saving, run backtest and Shadow Mode validation.
          </div>
          <div class="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div class="space-y-3 lg:col-span-2" id="strategy-form"></div>
            <div class="space-y-3">
              <h3 class="text-sm font-bold text-slate-700">Parameter guide</h3>
              <ul id="strategy-guide" class="space-y-2 text-sm text-slate-600"></ul>
              <div id="strategy-validation" class="rounded-md bg-slate-50 p-3 text-sm text-slate-700">No validation run yet.</div>
            </div>
          </div>
          <div id="strategy-diff" class="mt-4"></div>
        </section>

        <section id="risk-config" class="panel">
          <div class="panel-head"><div><h2>Risk Config Viewer</h2><p>Read-only RiskEngine config. Dashboard V2 does not allow editing risk.yaml to avoid accidental safety boundary relaxation.</p></div><span id="meta-riskConfig" class="module-meta">-</span></div>
          <div id="risk-config-body" class="space-y-3"></div>
        </section>

        <section id="readiness" class="panel">
          <div class="panel-head"><div><h2>Testnet Readiness Check</h2><p>Checks dry-run, order/test, and real small Testnet order preconditions. It only checks; it does not place orders. Real lifecycle remains CLI-only.</p></div><span id="meta-readinessLatest" class="module-meta">-</span></div>
          <div class="mb-3 flex flex-wrap gap-2">
            <button class="btn-primary" onclick="runReadinessCheck()">Run Readiness Check</button>
            <button class="btn-muted" onclick="copyReadinessPackage()">Copy Readiness Review Package</button>
          </div>
          <div class="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            Dashboard does not provide a real order button. Even when ready_for_real_testnet_order=true, use CLI and explicit confirmation for testnet_order_lifecycle.
          </div>
          <div id="readiness-body" class="mt-3 space-y-3"></div>
        </section>

        <section id="openai-usage" class="panel xl:col-span-2">
          <div class="panel-head"><div><h2>OpenAI Usage Report</h2><p>Displays OpenAI API usage and local cost estimates for StrategyPlanner, SignalReviewer, SystemAuditor, and related roles. Raw prompts and raw responses are not returned.</p></div><span id="meta-openaiUsage" class="module-meta">manual</span></div>
          <div class="mb-3 flex flex-wrap gap-2">
            <button class="btn-muted" onclick="loadOpenAIUsage(1)">Load 1 Day Usage</button>
            <button class="btn-muted" onclick="loadOpenAIUsage(7)">Load 7 Day Usage</button>
            <button class="btn-muted" onclick="copyJson('OpenAI Usage JSON', openaiUsageData)">Copy Usage JSON</button>
            <button class="btn-muted" onclick="copyCostReviewPrompt()">Copy Cost Review Prompt</button>
          </div>
          <div id="openai-usage-body" class="space-y-3"></div>
        </section>

        <section id="frontend-snapshot" class="panel xl:col-span-2">
          <div class="panel-head"><div><h2>Frontend System Snapshot / Export</h2><p>Exports the current in-memory dashboard state for review. Nothing is written to localStorage.</p></div><span class="module-meta">local only</span></div>
          <button class="btn-muted" onclick="copyFrontendSnapshot()">Copy Frontend State Snapshot</button>
        </section>
      </div>

      <section id="review-workspace" class="panel mt-5">
        <div class="panel-head">
          <div>
            <h2>Review Workspace</h2>
            <p>Build a copyable GPT review package from current safety overview, runtime health, data quality, Shadow, AI, risk, readiness, strategy config, OpenAI usage, and audit data.</p>
          </div>
          <span class="module-meta">local only</span>
        </div>
        <div class="mb-3 flex flex-wrap gap-2">
          <button class="btn-primary" onclick="autoFillWorkspace()">Auto Fill From Current Dashboard</button>
          <button class="btn-muted" onclick="copyReviewPackage()">Copy Full GPT Review Package</button>
          <button class="btn-muted" onclick="copyStrategyOptimizationPackage()">Copy Strategy Optimization Package</button>
          <button class="btn-muted" onclick="copyFrontendSnapshot()">Copy Frontend State Snapshot</button>
          <button class="btn-muted" onclick="copyReadinessPackage()">Copy Readiness Review Package</button>
          <button class="btn-muted" onclick="clearWorkspace()">Clear Workspace</button>
        </div>
        <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <label class="workspace-label"><span>Shadow Report</span><button class="btn-mini" onclick="copyTextArea('workspace-shadow')">Copy Individual Section</button><textarea id="workspace-shadow" class="workspace-text"></textarea></label>
          <label class="workspace-label"><span>AI Reviews</span><button class="btn-mini" onclick="copyTextArea('workspace-ai')">Copy Individual Section</button><textarea id="workspace-ai" class="workspace-text"></textarea></label>
          <label class="workspace-label"><span>Risk Decisions</span><button class="btn-mini" onclick="copyTextArea('workspace-risk')">Copy Individual Section</button><textarea id="workspace-risk" class="workspace-text"></textarea></label>
          <label class="workspace-label"><span>Comprehensive Optimization Request</span><button class="btn-mini" onclick="copyTextArea('workspace-extra')">Copy Individual Section</button><textarea id="workspace-extra" class="workspace-text" placeholder="Add your question, e.g. why Shadow Mode has no WOULD_PLACE_ORDER decisions."></textarea></label>
        </div>
      </section>
    </main>

    <script>
      const api = {
        health: mod("/runtime/health"),
        logs: mod("/runtime/logs/recent"),
        snapshots: mod("/runtime/last-snapshots"),
        aiReviews: mod("/runtime/last-ai-reviews"),
        riskDecisions: mod("/runtime/last-risk-decisions"),
        dataQuality: mod("/runtime/data-quality/latest"),
        shadowReport: mod("/runtime/shadow/report"),
        shadowRecent: mod("/runtime/shadow/recent"),
        shadowOpen: mod("/runtime/shadow/open"),
        auditLatest: mod("/runtime/audits/latest"),
        pipelineAudit: mod("/runtime/audit/recent"),
        orders: mod("/orders/recent"),
        signals: mod("/signals/recent"),
        riskState: mod("/risk/state"),
        configSafe: mod("/config/safe"),
        status: mod("/status"),
        strategyConfig: mod("/config/strategy"),
        riskConfig: mod("/config/risk"),
        readinessLatest: mod("/runtime/readiness/latest"),
      };

      let strategyDraft = null;
      let strategyCurrent = null;
      let strategyValidation = null;
      let readinessData = null;
      let openaiUsageData = null;

      const style = document.createElement("style");
      style.innerHTML = `
        .panel { border: 1px solid rgb(226 232 240); border-radius: 0.5rem; background: white; padding: 1rem; box-shadow: 0 1px 2px rgb(15 23 42 / 0.06); }
        .panel-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; margin-bottom: 0.9rem; }
        .panel h2 { font-size: 1.05rem; font-weight: 800; color: rgb(15 23 42); }
        .panel p { margin-top: 0.25rem; font-size: 0.8rem; line-height: 1.35; color: rgb(71 85 105); }
        .module-meta { white-space: nowrap; border-radius: 999px; background: rgb(241 245 249); padding: 0.25rem 0.55rem; font-size: 0.72rem; color: rgb(71 85 105); }
        .nav-chip { border-radius: 999px; background: rgb(241 245 249); padding: 0.35rem 0.65rem; color: rgb(51 65 85); }
        .nav-chip:hover { background: rgb(219 234 254); color: rgb(30 64 175); }
        .btn-primary, .btn-safe, .btn-muted, .btn-warn, .btn-danger, .btn-mini { border-radius: 0.375rem; padding: 0.45rem 0.7rem; font-size: 0.78rem; font-weight: 800; transition: opacity .15s; }
        .btn-primary { background: rgb(37 99 235); color: white; }
        .btn-safe { background: rgb(5 150 105); color: white; }
        .btn-muted { background: rgb(226 232 240); color: rgb(15 23 42); }
        .btn-warn { background: rgb(245 158 11); color: rgb(69 26 3); }
        .btn-danger { background: rgb(220 38 38); color: white; }
        .btn-mini { background: rgb(241 245 249); color: rgb(51 65 85); padding: 0.25rem 0.45rem; font-size: 0.7rem; }
        button:hover { opacity: 0.88; }
        .kv-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.6rem; }
        .kv { border: 1px solid rgb(226 232 240); border-radius: 0.375rem; padding: 0.55rem; background: rgb(248 250 252); }
        .kv .k { font-size: 0.68rem; color: rgb(100 116 139); text-transform: uppercase; letter-spacing: .04em; }
        .kv .v { margin-top: 0.25rem; font-size: 0.9rem; font-weight: 800; color: rgb(15 23 42); overflow-wrap: anywhere; }
        .workspace-label { display: flex; flex-direction: column; gap: 0.5rem; font-size: 0.85rem; font-weight: 800; color: rgb(30 41 59); }
        .workspace-text, .input { width: 100%; border: 1px solid rgb(203 213 225); border-radius: 0.375rem; padding: 0.55rem; font-size: 0.8rem; color: rgb(15 23 42); }
        .workspace-text { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-weight: 400; }
      `;
      document.head.appendChild(style);

      function mod(url) { return { url, data: null, error: null, loading: false, last: null }; }
      function esc(value) {
        const raw = value === null || value === undefined || value === "" ? "-" : String(value);
        return raw.replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
      }
      function asText(value) { if (value === null || value === undefined || value === "") return "-"; return typeof value === "object" ? JSON.stringify(value) : String(value); }
      function get(obj, path, fallback = "-") {
        const parts = path.split(".");
        let current = obj;
        for (const part of parts) {
          if (current === null || current === undefined || !(part in Object(current))) return fallback;
          current = current[part];
        }
        return current === null || current === undefined || current === "" ? fallback : current;
      }
      function clone(value) { return JSON.parse(JSON.stringify(value ?? {})); }
      function badge(value, label = null) {
        const text = label || asText(value);
        const norm = asText(value).toUpperCase();
        let cls = "bg-slate-100 text-slate-700 border-slate-200";
        if (["OK", "SAFE", "RUNNING", "TRUE", "APPROVED", "ALLOW", "ACTIVE", "SUCCESS"].some((x) => norm.includes(x))) cls = "bg-emerald-50 text-emerald-700 border-emerald-200";
        if (["WARN", "WATCH", "DEGRADED", "UNKNOWN", "STOPPED", "HUMAN", "ON", "PENDING"].some((x) => norm.includes(x))) cls = "bg-amber-50 text-amber-800 border-amber-200";
        if (["CRITICAL", "ERROR", "FAILED", "FALSE", "BLOCK", "REJECT", "DISABLED"].some((x) => norm.includes(x))) cls = "bg-red-50 text-red-700 border-red-200";
        return `<span class="inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-bold ${cls}">${esc(text)}</span>`;
      }
      function kv(label, value) { return `<div class="kv"><div class="k">${esc(label)}</div><div class="v">${esc(asText(value))}</div></div>`; }
      function jsonBlock(title, data) { return `<details class="rounded-md border border-slate-200 bg-slate-50 p-2 text-xs"><summary class="cursor-pointer font-bold text-slate-700">${esc(title)}</summary><pre class="mt-2 overflow-auto text-slate-700">${esc(JSON.stringify(data ?? {}, null, 2))}</pre></details>`; }
      function listItems(items, renderer, emptyText = "No records.") {
        if (!Array.isArray(items) || items.length === 0) return `<div class="rounded-md bg-slate-50 p-3 text-sm text-slate-500">${esc(emptyText)}</div>`;
        return `<div class="space-y-2">${items.map(renderer).join("")}</div>`;
      }

      async function fetchModule(name) {
        const item = api[name];
        if (!item) return;
        item.loading = true;
        item.error = null;
        renderMeta();
        try {
          const response = await fetch(item.url, { cache: "no-store" });
          const text = await response.text();
          let payload = null;
          try { payload = text ? JSON.parse(text) : null; } catch { payload = { raw: text }; }
          if (!response.ok) throw new Error(`${response.status} ${response.statusText}: ${text.slice(0, 400)}`);
          item.data = payload;
          item.last = new Date().toLocaleTimeString();
        } catch (error) {
          item.error = error.message || String(error);
        } finally {
          item.loading = false;
          if (name === "strategyConfig" && item.data) applyLoadedStrategyConfig(item.data);
          if (name === "readinessLatest" && item.data && item.data.status !== "NO_READINESS_CHECK_RUN") readinessData = item.data;
          render();
        }
      }

      async function fetchJson(url, options = {}) {
        const response = await fetch(url, { cache: "no-store", ...options });
        const text = await response.text();
        let payload = null;
        try { payload = text ? JSON.parse(text) : null; } catch { payload = { raw: text }; }
        if (!response.ok) throw new Error(`${response.status} ${response.statusText}: ${text.slice(0, 400)}`);
        return payload;
      }

      function refreshAll() {
        document.getElementById("page-last-refresh").textContent = new Date().toLocaleString();
        Object.keys(api).forEach((name) => fetchModule(name));
      }

      async function postAction(label, url, confirmText = null) {
        if (confirmText && !window.confirm(confirmText)) return;
        setAction(`${label}: running...`, "blue");
        try {
          const payload = await fetchJson(url, { method: "POST" });
          setAction(`${label}: ${JSON.stringify(payload).slice(0, 280)}`, "green");
          refreshAll();
        } catch (error) {
          setAction(`${label} failed: ${error.message || error}`, "red");
        }
      }

      function setAction(message, tone = "slate") {
        const el = document.getElementById("action-result");
        const cls = tone === "green" ? "bg-emerald-50 text-emerald-700" : tone === "red" ? "bg-red-50 text-red-700" : tone === "blue" ? "bg-blue-50 text-blue-700" : "bg-slate-100 text-slate-700";
        el.className = `rounded-md px-2 py-1 ${cls}`;
        el.textContent = message;
      }

      function renderMeta() {
        Object.entries(api).forEach(([name, item]) => {
          const el = document.getElementById(`meta-${name}`);
          if (!el) return;
          if (item.loading) el.textContent = "loading...";
          else if (item.error) el.textContent = `error: ${item.error.slice(0, 80)}`;
          else el.textContent = item.last ? `updated ${item.last}` : "not loaded";
        });
      }

      function renderSafety() {
        const h = api.health.data || {};
        const status = api.status.data || {};
        const dq = api.dataQuality.data || get(h, "data_quality_status", {});
        const kill = get(h, "kill_switch_state.effective_enabled", get(status, "kill_switch_enabled", "UNKNOWN"));
        const liveDisabled = get(status, "live_trading_enabled", false) === false;
        const cards = [
          ["Runtime State", get(h, "state")],
          ["Trading Mode", get(h, "trading_mode", get(status, "trading_mode"))],
          ["Dry Run", get(h, "dry_run")],
          ["Order Execution", get(h, "order_execution_enabled")],
          ["Live Disabled", liveDisabled],
          ["Kill Switch", kill ? "ON" : "OFF"],
          ["Data Quality", get(dq, "overall_status", "UNKNOWN")],
          ["Health Warning", get(h, "health_warning", false)],
        ];
        document.getElementById("safety-overview").innerHTML = cards.map(([label, value]) => `<div class="rounded-lg border border-slate-200 bg-white p-3 shadow-sm"><div class="text-xs font-bold uppercase tracking-wide text-slate-500">${esc(label)}</div><div class="mt-2 text-lg font-black">${badge(value)}</div></div>`).join("");
      }

      function renderRuntime() {
        const h = api.health.data || {};
        document.getElementById("runtime-body").innerHTML = [
          kv("state", get(h, "state")), kv("trading_mode", get(h, "trading_mode")), kv("symbols", (get(h, "symbols", []) || []).join(", ")), kv("dry_run", get(h, "dry_run")), kv("ai_enabled", get(h, "ai_enabled")), kv("order_execution_enabled", get(h, "order_execution_enabled")), kv("reconnecting", get(h, "reconnecting")), kv("data_delay_seconds", get(h, "data_delay_seconds")), kv("last_kline_time", get(h, "last_kline_time")), kv("last_user_event_time", get(h, "last_user_event_time")), kv("last_error", get(h, "last_error")),
        ].join("");
      }
      function renderStreams() {
        const h = api.health.data || {};
        document.getElementById("streams-body").innerHTML = `<div class="kv-grid">${kv("market_stream_connected", get(h, "market_stream_connected"))}${kv("user_stream_connected", get(h, "user_stream_connected"))}${kv("last_kline_time", get(h, "last_kline_time"))}${kv("last_user_event_time", get(h, "last_user_event_time"))}${kv("data_delay_seconds", get(h, "data_delay_seconds"))}</div>${jsonBlock("market_stream", get(h, "market_stream", {}))}${jsonBlock("user_stream", get(h, "user_stream", {}))}${jsonBlock("network_readiness", get(h, "network_readiness", {}))}`;
      }
      function renderDataQuality() {
        const dq = api.dataQuality.data || {};
        if (dq.status === "NO_DATA_QUALITY_SNAPSHOT") {
          document.getElementById("data-quality-body").innerHTML = `<div class="rounded-md bg-amber-50 p-3 text-sm text-amber-800">No data quality snapshot yet. Start dry-run or click Run Data Quality Check.</div>`;
          return;
        }
        const issues = get(dq, "issues", []);
        document.getElementById("data-quality-body").innerHTML = `<div class="kv-grid">${kv("overall_status", get(dq, "overall_status"))}${kv("action", get(dq, "action"))}${kv("safe_for_strategy_planner", get(dq, "safe_for_strategy_planner"))}${kv("safe_for_signal_review", get(dq, "safe_for_signal_review"))}${kv("safe_for_order", get(dq, "safe_for_order"))}${kv("safe_for_real_testnet_order", get(dq, "safe_for_real_testnet_order"))}${kv("issue_count", Array.isArray(issues) ? issues.length : 0)}${kv("reason_codes", (get(dq, "reason_codes", []) || []).join(", "))}</div>${listItems(issues, (issue) => `<div class="rounded-md border border-slate-200 p-2 text-sm">${badge(get(issue, "severity"))} <strong>${esc(get(issue, "title"))}</strong><div class="mt-1 text-slate-600">${esc(get(issue, "recommended_action"))}</div>${jsonBlock("evidence", get(issue, "evidence", []))}</div>`, "No data quality issues.")}${jsonBlock("DataQuality raw", dq)}`;
      }
      function renderStrategy() {
        const snapshots = api.snapshots.data || {};
        const signals = api.signals.data || [];
        const keys = snapshots && typeof snapshots === "object" ? Object.keys(snapshots) : [];
        const snapshotHtml = keys.length === 0 ? `<div class="rounded-md bg-slate-50 p-3 text-sm text-slate-500">No market snapshots yet. Runtime may be stopped or klines are not loaded.</div>` : keys.map((symbol) => {
          const snap = snapshots[symbol] || {};
          return `<div class="rounded-md border border-slate-200 p-2"><div class="mb-2 flex items-center justify-between"><strong>${esc(symbol)}</strong>${badge(get(snap, "ws_health", "UNKNOWN"))}</div><div class="kv-grid">${kv("price", get(snap, "price"))}${kv("ema_fast", get(snap, "ema_fast_5m", get(snap, "ema_fast")))}${kv("ema_slow", get(snap, "ema_slow_5m", get(snap, "ema_slow")))}${kv("rsi", get(snap, "rsi14_5m", get(snap, "rsi")))}${kv("atr", get(snap, "atr14_5m", get(snap, "atr")))}${kv("volume_ratio", get(snap, "volume_ratio_5m", get(snap, "volume_ratio")))}${kv("data_delay_seconds", get(snap, "data_delay_seconds"))}</div></div>`;
        }).join("");
        document.getElementById("strategy-body").innerHTML = `${snapshotHtml}<h3 class="text-sm font-bold text-slate-700">Recent signals</h3>${listItems(signals, (row) => `<div class="rounded-md border border-slate-200 p-2 text-sm"><strong>${esc(get(row, "symbol"))}</strong> ${badge(get(row, "side"))} confidence ${esc(get(row, "confidence"))}<div class="text-slate-600">${esc(get(row, "reason"))}</div></div>`, "No recent signals.")}`;
      }
      function reviewPayload(row) { return get(row, "review", get(row, "output_json", row)); }
      function renderAI() {
        const rows = api.aiReviews.data || [];
        const summary = { total: rows.length, schema_valid: 0, schema_invalid: 0, decisions: {} };
        rows.forEach((row) => { if (get(row, "schema_valid", false) === true) summary.schema_valid += 1; else summary.schema_invalid += 1; const decision = get(reviewPayload(row), "decision", get(row, "decision", "UNKNOWN")); summary.decisions[decision] = (summary.decisions[decision] || 0) + 1; });
        document.getElementById("ai-body").innerHTML = `<div class="kv-grid">${kv("total reviews", summary.total)}${kv("schema_valid", summary.schema_valid)}${kv("schema_invalid", summary.schema_invalid)}${kv("decision distribution", JSON.stringify(summary.decisions))}</div>${listItems(rows, (row, index) => { const review = reviewPayload(row); return `<div class="rounded-md border border-slate-200 p-3 text-sm"><div class="flex flex-wrap items-center justify-between gap-2"><strong>${esc(get(row, "symbol", get(review, "symbol")))}</strong><div class="flex flex-wrap gap-2">${badge(get(row, "schema_valid", "UNKNOWN"), `schema_valid=${get(row, "schema_valid", "UNKNOWN")}`)}${badge(get(review, "decision", get(row, "decision", "UNKNOWN")))}</div></div><div class="mt-2 kv-grid">${kv("actual_model", get(row, "actual_model", get(row, "model")))}${kv("active_strategy_plan_id", get(row, "active_strategy_plan_id"))}${kv("side", get(review, "side", get(row, "side")))}${kv("confidence", get(review, "confidence", get(row, "confidence")))}${kv("risk_level", get(review, "risk_level"))}${kv("market_regime", get(review, "market_regime"))}${kv("requires_human_review", get(review, "requires_human_review"))}</div><p class="mt-2 text-sm text-slate-700">${esc(get(review, "reason", get(row, "reason")))}</p>${jsonBlock("warnings", get(review, "warnings", []))}<div class="mt-2 flex flex-wrap gap-2"><button class="btn-mini" onclick='copyJson("AI Review", api.aiReviews.data[${index}])'>Copy JSON</button><button class="btn-mini" onclick='copyAIReviewPrompt(${index})'>Copy GPT Review Prompt</button></div></div>`; }, "No AI reviews.")}`;
      }
      function renderRisk() {
        const rows = api.riskDecisions.data || [];
        const riskState = api.riskState.data || {};
        const h = api.health.data || {};
        const counts = {};
        rows.forEach((row) => { const reason = get(row, "reason", "UNKNOWN"); counts[reason] = (counts[reason] || 0) + 1; });
        const top = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 8);
        document.getElementById("risk-body").innerHTML = `<div class="kv-grid">${kv("orders_last_minute", get(h, "risk_runtime_status.orders_last_minute"))}${kv("seen_client_order_id_count", get(h, "risk_runtime_status.seen_client_order_id_count"))}${kv("risk_engine_reused", get(h, "risk_runtime_status.risk_engine_reused"))}${kv("kill_switch_enabled_config", get(h, "risk_runtime_status.kill_switch_enabled_config", get(riskState, "configured.kill_switch_enabled")))}${kv("kill_switch_enabled_runtime", get(h, "risk_runtime_status.kill_switch_enabled_runtime", get(riskState, "kill_switch_enabled")))}</div><h3 class="text-sm font-bold text-slate-700">Top recent rejection reasons</h3>${listItems(top, ([reason, count]) => `<div class="rounded-md bg-slate-50 p-2 text-sm"><strong>${esc(count)}</strong> ${esc(reason)}</div>`, "No rejections found.")}${listItems(rows, (row) => `<div class="rounded-md border border-slate-200 p-2 text-sm">${badge(get(row, "approved") ? "APPROVED" : "REJECTED")} <strong>${esc(get(row, "symbol"))}</strong><div class="text-slate-600">${esc(get(row, "reason"))}</div>${jsonBlock("risk_state_json", get(row, "risk_state_json", row))}</div>`, "No risk decisions.")}`;
      }
      function renderOrders() {
        const orders = api.orders.data || [];
        const h = api.health.data || {};
        const dryRun = get(h, "dry_run", true);
        const execution = get(h, "order_execution_enabled", false);
        const possible = dryRun === false && execution === true;
        document.getElementById("orders-body").innerHTML = `<div class="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm"><div>Current dry_run = <strong>${esc(dryRun)}</strong></div><div>Current order_execution_enabled = <strong>${esc(execution)}</strong></div><div>Can real Binance new_order be triggered now = <strong>${possible ? "Potentially, but this Dashboard provides no real order button" : "No, current state will not submit a real Binance order"}</strong></div></div>${listItems(orders, (row) => `<div class="rounded-md border border-slate-200 p-2 text-sm"><div class="flex flex-wrap justify-between gap-2"><strong>${esc(get(row, "client_order_id"))}</strong>${badge(get(row, "status"))}</div><div class="kv-grid mt-2">${kv("symbol", get(row, "symbol"))}${kv("side", get(row, "side"))}${kv("order_type", get(row, "order_type"))}${kv("price", get(row, "price"))}${kv("quantity", get(row, "quantity"))}${kv("trading_mode", get(row, "trading_mode"))}${kv("created_at", get(row, "created_at"))}</div></div>`, "No recent orders.")}`;
      }
      function renderShadow() {
        const report = api.shadowReport.data || {};
        const open = api.shadowOpen.data || [];
        const recent = api.shadowRecent.data || [];
        document.getElementById("shadow-body").innerHTML = `<div class="kv-grid">${kv("total_decisions", get(report, "total_decisions"))}${kv("WOULD_PLACE_ORDER", get(report, "would_place_order_count"))}${kv("AI_REJECTED", get(report, "ai_rejected_count"))}${kv("RISK_REJECTED", get(report, "risk_rejected_count"))}${kv("DATA_QUALITY_BLOCKED", get(report, "data_quality_blocked_count"))}${kv("simulated_total_pnl_usdt", get(report, "simulated_total_pnl_usdt"))}${kv("simulated_win_rate", get(report, "simulated_win_rate"))}${kv("simulated_avg_pnl_pct", get(report, "simulated_avg_pnl_pct"))}</div>${jsonBlock("best_shadow_trade", get(report, "best_shadow_trade", {}))}${jsonBlock("worst_shadow_trade", get(report, "worst_shadow_trade", {}))}${jsonBlock("top_rejection_reasons", get(report, "top_rejection_reasons", []))}<h3 class="text-sm font-bold text-slate-700">Open shadow decisions</h3>${listItems(open, (row) => `<div class="rounded-md border border-slate-200 p-2 text-sm"><strong>${esc(get(row, "shadow_id"))}</strong> ${badge(get(row, "status"))} ${badge(get(row, "decision_type"))}<div>${esc(get(row, "symbol"))} ${esc(get(row, "side"))}</div></div>`, "No open shadow decisions.")}<h3 class="text-sm font-bold text-slate-700">Recent shadow decisions</h3>${listItems(recent, (row) => `<div class="rounded-md border border-slate-200 p-2 text-sm"><strong>${esc(get(row, "shadow_id"))}</strong> ${badge(get(row, "decision_type"))}<div class="text-slate-600">${esc(get(row, "reason"))}</div></div>`, "No recent shadow decisions.")}`;
      }
      function renderAccount() {
        const status = get(api.health.data || {}, "account_position_status", {});
        const accountSource = get(status, "account_source");
        const positions = get(status, "positions", []);
        const simulated = accountSource === "simulated_default" || (Array.isArray(positions) && positions.some((p) => get(p, "source") === "simulated_default"));
        document.getElementById("account-body").innerHTML = `${simulated ? `<div class="rounded-md bg-amber-50 p-3 text-sm font-bold text-amber-900">Current account/position data is simulated_default and must not be treated as real Testnet account state.</div>` : ""}<div class="kv-grid">${kv("account_status", get(status, "account_status"))}${kv("account_source", accountSource)}${kv("equity_usdt", get(status, "equity_usdt"))}${kv("available_usdt", get(status, "available_usdt"))}${kv("safe_for_real_order", get(status, "safe_for_real_order"))}${kv("latest_created_at", get(status, "latest_created_at"))}${kv("reason_codes", (get(status, "reason_codes", []) || []).join(", "))}</div>${jsonBlock("positions", positions)}`;
      }
      function renderBudget() {
        const budget = get(api.health.data || {}, "budget_status", {});
        document.getElementById("budget-body").innerHTML = `<div class="kv-grid">${kv("daily budget", get(budget, "daily_budget_usd"))}${kv("monthly budget", get(budget, "monthly_budget_usd"))}${kv("today cost", get(budget, "openai_today_cost_usd", get(budget, "estimated_today_cost_usd")))}${kv("month cost", get(budget, "openai_month_cost_usd", get(budget, "estimated_month_cost_usd")))}${kv("strategy calls", get(budget, "strategy_calls_today"))}${kv("signal calls", get(budget, "signal_calls_today"))}${kv("budget_guard_enabled", get(budget, "budget_guard_enabled"))}${kv("budget_blocked", get(budget, "budget_blocked"))}</div>${jsonBlock("budget raw", budget)}`;
      }
      function renderAudit() {
        const report = api.auditLatest.data || {};
        if (report.status === "NO_AUDIT_REPORT") { document.getElementById("audit-body").innerHTML = `<div class="rounded-md bg-slate-50 p-3 text-sm text-slate-500">No SystemAuditor report yet. Click Run System Audit.</div>`; return; }
        document.getElementById("audit-body").innerHTML = `<div class="kv-grid">${kv("latest_overall_status", get(report, "overall_status", get(report, "latest_overall_status")))}${kv("latest_highest_severity", get(report, "highest_severity", get(report, "latest_highest_severity")))}${kv("latest_issue_count", get(report, "issue_count", get(report, "latest_issue_count")))}${kv("latest_report_created_at", get(report, "created_at", get(report, "latest_report_created_at")))}</div><p class="rounded-md bg-slate-50 p-3 text-sm text-slate-700">${esc(get(report, "summary", get(report, "latest_summary")))}</p>${jsonBlock("issues", get(report, "issues", get(report, "raw_output_json_sanitized.issues", [])))}${jsonBlock("recommended_next_human_steps", get(report, "recommended_next_human_steps", []))}`;
      }
      function renderLogs() {
        const logs = api.logs.data || [];
        const audits = api.pipelineAudit.data || [];
        document.getElementById("logs-body").innerHTML = `<h3 class="text-sm font-bold text-slate-700">Recent runtime logs</h3>${listItems(logs.slice(0, 100), (row) => `<div class="rounded-md border border-slate-200 p-2 text-xs">${esc(get(row, "event", get(row, "message", "runtime_log")))} ${badge(get(row, "level", get(row, "status", "INFO")))}${jsonBlock("raw", row)}</div>`, "No runtime logs.")}<h3 class="text-sm font-bold text-slate-700">Pipeline audit</h3>${listItems(audits.slice(0, 100), (row) => `<div class="rounded-md border border-slate-200 p-2 text-xs"><strong>${esc(get(row, "stage"))}</strong> ${badge(get(row, "status"))}<div>${esc(get(row, "error_message"))}</div>${jsonBlock("raw", row)}</div>`, "No pipeline audit rows.")}`;
      }

      function applyLoadedStrategyConfig(payload) {
        if (!payload || !payload.config) return;
        strategyCurrent = clone(payload.config);
        if (!strategyDraft) strategyDraft = clone(payload.config);
      }
      function loadStrategyConfig() { fetchModule("strategyConfig"); }
      function field(name, label, type = "number", step = "1") {
        const value = get(strategyDraft, `ema_trend.${name}`, "");
        if (type === "checkbox") return `<label class="flex items-center gap-2 rounded-md border border-slate-200 p-2 text-sm"><input id="sp-${name}" type="checkbox" ${value === true ? "checked" : ""} /> <span class="font-bold">${esc(label)}</span></label>`;
        return `<label class="block text-sm"><span class="font-bold text-slate-700">${esc(label)}</span><input id="sp-${name}" class="input mt-1" type="${type}" step="${step}" value="${esc(value)}" /></label>`;
      }
      function selectField(name, label) {
        const intervals = get(api.strategyConfig.data || {}, "allowed_intervals", ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"]);
        const value = get(strategyDraft, `ema_trend.${name}`, "");
        return `<label class="block text-sm"><span class="font-bold text-slate-700">${esc(label)}</span><select id="sp-${name}" class="input mt-1">${intervals.map((item) => `<option value="${esc(item)}" ${item === value ? "selected" : ""}>${esc(item)}</option>`).join("")}</select></label>`;
      }
      function renderStrategyCenter() {
        if (!strategyDraft) {
          document.getElementById("strategy-form").innerHTML = `<div class="rounded-md bg-slate-50 p-3 text-sm text-slate-500">Click Load Strategy Config to edit EMA Trend settings.</div>`;
          document.getElementById("strategy-guide").innerHTML = "";
          document.getElementById("strategy-diff").innerHTML = "";
          return;
        }
        document.getElementById("strategy-form").innerHTML = `<div class="grid grid-cols-1 gap-3 md:grid-cols-2">${field("enabled", "enabled", "checkbox")}${selectField("entry_timeframe", "entry_timeframe")}${selectField("trend_timeframe", "trend_timeframe")}${field("ema_fast", "ema_fast")}${field("ema_slow", "ema_slow")}${field("rsi_period", "rsi_period")}${field("rsi_min", "rsi_min", "number", "0.1")}${field("rsi_max", "rsi_max", "number", "0.1")}${field("atr_period", "atr_period")}${field("volume_ratio_min", "volume_ratio_min", "number", "0.01")}${field("take_profit_r_multiple", "take_profit_r_multiple", "number", "0.1")}${field("stop_loss_atr_multiple", "stop_loss_atr_multiple", "number", "0.1")}</div>${jsonBlock("Current config", api.strategyConfig.data || {})}`;
        const descriptions = get(api.strategyConfig.data || {}, "parameter_descriptions", {});
        document.getElementById("strategy-guide").innerHTML = Object.entries(descriptions).map(([key, value]) => `<li class="rounded-md bg-slate-50 p-2"><strong>${esc(key)}:</strong> ${esc(value)}</li>`).join("");
        const diff = strategyValidation ? strategyValidation.diff : [];
        document.getElementById("strategy-diff").innerHTML = `${jsonBlock("Validation / diff preview", strategyValidation || { message: "No validation run yet." })}${listItems(diff, (row) => `<div class="rounded-md border border-slate-200 p-2 text-sm"><strong>${esc(row.field)}</strong>: ${esc(row.old)} -> ${esc(row.new)}</div>`, "No diff preview.")}`;
      }
      function collectStrategyDraft() {
        const numberFields = ["ema_fast", "ema_slow", "rsi_period", "rsi_min", "rsi_max", "atr_period", "volume_ratio_min", "take_profit_r_multiple", "stop_loss_atr_multiple"];
        const draft = { ema_trend: {} };
        draft.ema_trend.enabled = document.getElementById("sp-enabled")?.checked === true;
        draft.ema_trend.entry_timeframe = document.getElementById("sp-entry_timeframe")?.value;
        draft.ema_trend.trend_timeframe = document.getElementById("sp-trend_timeframe")?.value;
        numberFields.forEach((name) => {
          const raw = document.getElementById(`sp-${name}`)?.value;
          draft.ema_trend[name] = ["ema_fast", "ema_slow", "rsi_period", "atr_period"].includes(name) ? Number.parseInt(raw, 10) : Number.parseFloat(raw);
        });
        strategyDraft = draft;
        return draft;
      }
      async function validateStrategyDraft() {
        try {
          const payload = await fetchJson("/config/strategy/validate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(collectStrategyDraft()) });
          strategyValidation = payload;
          document.getElementById("strategy-validation").innerHTML = payload.valid ? `${badge("VALID")} Draft is valid.` : `${badge("INVALID")} ${esc((payload.errors || []).join("; "))}`;
          renderStrategyCenter();
        } catch (error) { document.getElementById("strategy-validation").innerHTML = `${badge("ERROR")} ${esc(error.message || error)}`; }
      }
      async function saveStrategyDraft() {
        if (!window.confirm("Saving strategy parameters only writes config/strategy.yaml. It does not hot reload, restart runtime, or place orders. After saving, run backtest and Shadow Mode validation. Continue?")) return;
        try {
          const payload = await fetchJson("/config/strategy/save", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(collectStrategyDraft()) });
          strategyValidation = payload;
          document.getElementById("strategy-validation").innerHTML = payload.saved ? `${badge("SAVED")} Saved config/strategy.yaml. Pending restart is true. Stop dry-run and restart FastAPI/runtime before expecting changes to take effect.` : `${badge("INVALID")} ${esc((payload.errors || []).join("; "))}`;
          await fetchModule("strategyConfig");
        } catch (error) { document.getElementById("strategy-validation").innerHTML = `${badge("ERROR")} ${esc(error.message || error)}`; }
      }
      function resetStrategyDraft() { strategyDraft = clone(strategyCurrent); strategyValidation = null; renderStrategyCenter(); }

      function renderRiskConfig() {
        const payload = api.riskConfig.data || {};
        const config = get(payload, "config", {});
        const risk = get(config, "risk", {});
        const live = get(config, "live_trading", {});
        document.getElementById("risk-config-body").innerHTML = `<div class="rounded-md border border-red-200 bg-red-50 p-3 text-sm font-bold text-red-800">Read only. Dashboard V2 cannot edit risk.yaml.</div><div class="kv-grid">${["max_single_trade_risk_pct","max_daily_loss_pct","max_position_pct_per_symbol","max_total_position_pct","max_consecutive_losses","cooldown_minutes_per_symbol","block_on_ws_disconnect","block_on_ai_schema_error","block_on_data_delay_seconds","allow_market_orders","allow_limit_orders","kill_switch_enabled","max_orders_per_minute"].map((key) => kv(`risk.${key}`, get(risk, key))).join("")}${kv("live_trading.enabled", get(live, "enabled"))}${kv("live_trading.require_manual_enable", get(live, "require_manual_enable"))}${kv("live_trading.require_env_live_enabled", get(live, "require_env_live_enabled"))}</div>${jsonBlock("risk raw", payload)}`;
      }
      async function runReadinessCheck() {
        document.getElementById("readiness-body").innerHTML = `<div class="rounded-md bg-blue-50 p-3 text-sm text-blue-700">Running readiness check. This checks only and does not place orders.</div>`;
        try {
          readinessData = await fetchJson("/runtime/readiness/check", { method: "POST" });
          api.readinessLatest.data = readinessData;
          api.readinessLatest.last = new Date().toLocaleTimeString();
          renderReadiness();
        } catch (error) { document.getElementById("readiness-body").innerHTML = `<div class="rounded-md bg-red-50 p-3 text-sm text-red-700">${esc(error.message || error)}</div>`; }
      }
      function renderReadiness() {
        const r = readinessData || (api.readinessLatest.data && api.readinessLatest.data.status !== "NO_READINESS_CHECK_RUN" ? api.readinessLatest.data : null);
        if (!r) { document.getElementById("readiness-body").innerHTML = `<div class="rounded-md bg-slate-50 p-3 text-sm text-slate-500">No readiness check run yet. Click Run Readiness Check.</div>`; return; }
        document.getElementById("readiness-body").innerHTML = `<div class="kv-grid">${["trading_mode","live_disabled","dry_run","order_execution_enabled","testnet_keys_present","testnet_rest_ok","testnet_user_stream_possible","signed_account_ok","signed_test_order_ok","exchange_filters_ok","account_state_status","position_state_status","data_quality_status","kill_switch_enabled","strategy_plan_status","ready_for_dry_run","ready_for_test_order_only","ready_for_real_testnet_order","ready_for_live"].map((key) => kv(key, get(r, key))).join("")}</div>${jsonBlock("blockers", get(r, "blockers", []))}${jsonBlock("warnings", get(r, "warnings", []))}${jsonBlock("readiness raw", r)}`;
      }
      async function loadOpenAIUsage(days) {
        document.getElementById("openai-usage-body").innerHTML = `<div class="rounded-md bg-blue-50 p-3 text-sm text-blue-700">Loading ${days} day usage...</div>`;
        try { openaiUsageData = await fetchJson(`/runtime/openai-usage?days=${days}`); renderOpenAIUsage(); }
        catch (error) { document.getElementById("openai-usage-body").innerHTML = `<div class="rounded-md bg-red-50 p-3 text-sm text-red-700">${esc(error.message || error)}</div>`; }
      }
      function renderOpenAIUsage() {
        const usage = openaiUsageData || {};
        const summary = get(usage, "summary", {});
        document.getElementById("openai-usage-body").innerHTML = `<div class="kv-grid">${kv("days", get(usage, "days"))}${kv("total estimated cost", get(summary, "estimated_cost_usd"))}${kv("total calls", get(summary, "total_calls"))}${kv("daily budget", get(usage, "daily_budget_usd"))}${kv("monthly budget", get(usage, "monthly_budget_usd"))}${kv("status breakdown", JSON.stringify(get(usage, "status_breakdown", {})))}</div>${jsonBlock("role breakdown", get(summary, "by_role", {}))}${jsonBlock("model breakdown", get(summary, "by_model", {}))}${jsonBlock("warnings", get(usage, "warnings", []))}${jsonBlock("usage raw", usage)}`;
      }

      function render() {
        renderMeta(); renderSafety(); renderRuntime(); renderStreams(); renderDataQuality(); renderStrategy(); renderAI(); renderRisk(); renderOrders(); renderShadow(); renderAccount(); renderBudget(); renderAudit(); renderLogs(); renderStrategyCenter(); renderRiskConfig(); renderReadiness(); renderOpenAIUsage();
      }

      async function copyToClipboard(label, text) {
        const payload = String(text ?? "");
        try {
          if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(payload);
          else { const area = document.createElement("textarea"); area.value = payload; area.style.position = "fixed"; area.style.left = "-9999px"; document.body.appendChild(area); area.focus(); area.select(); document.execCommand("copy"); document.body.removeChild(area); }
          setAction(`${label}: copied`, "green");
        } catch {
          const area = document.createElement("textarea"); area.value = payload; document.body.appendChild(area); area.focus(); area.select(); setAction(`${label}: clipboard unavailable, selected text for manual copy`, "blue");
        }
      }
      function copyJson(label, data) { return copyToClipboard(label, JSON.stringify(data ?? {}, null, 2)); }
      function copyAIReviewPrompt(index) { const row = (api.aiReviews.data || [])[index] || {}; return copyToClipboard("GPT AI Review Prompt", `Analyze this SignalReviewer record. Is the AI review too conservative, schema-stable, or missing context? Say whether to improve prompt, context_builder, or strategy logic.\n\nJSON:\n${JSON.stringify(row, null, 2)}`); }
      function copyShadowPrompt() { return copyToClipboard("GPT Shadow Review Prompt", `Analyze this Shadow Report. Is the sample too small, strategy not producing signals, AI rejecting too much, RiskEngine rejecting too much, DataQualityGate blocking too much, or WOULD_PLACE_ORDER simulated PnL insufficient? Suggest the highest-priority module/file to inspect.\n\nJSON:\n${JSON.stringify(api.shadowReport.data || {}, null, 2)}`); }
      function copyAuditPrompt() { return copyToClipboard("GPT Audit Review Prompt", `Analyze this SystemAuditor report. Identify major runtime/safety risks and bounded follow-up work. Do not suggest bypassing safety gates.\n\nJSON:\n${JSON.stringify(api.auditLatest.data || {}, null, 2)}`); }
      function copyCostReviewPrompt() { return copyToClipboard("GPT Cost Review Prompt", `Analyze this OpenAI usage report. Identify costly roles/models, budget risk, and safe cost-control improvements without switching to more expensive models.\n\nJSON:\n${JSON.stringify(openaiUsageData || {}, null, 2)}`); }
      function copyTextArea(id) { return copyToClipboard("Workspace section", document.getElementById(id).value); }
      function frontendSnapshot() { return { safety: api.health.data || {}, status: api.status.data || {}, data_quality: api.dataQuality.data || {}, shadow_report: api.shadowReport.data || {}, ai_reviews: api.aiReviews.data || [], risk_decisions: api.riskDecisions.data || [], readiness: readinessData || api.readinessLatest.data || {}, strategy_config: api.strategyConfig.data || {}, openai_usage: openaiUsageData || {}, audit: api.auditLatest.data || {} }; }
      function copyFrontendSnapshot() { return copyJson("Frontend State Snapshot", frontendSnapshot()); }
      function autoFillWorkspace() { document.getElementById("workspace-shadow").value = JSON.stringify(api.shadowReport.data || {}, null, 2); document.getElementById("workspace-ai").value = JSON.stringify(api.aiReviews.data || [], null, 2); document.getElementById("workspace-risk").value = JSON.stringify(api.riskDecisions.data || [], null, 2); document.getElementById("workspace-extra").value = JSON.stringify({ safety_overview: api.health.data || {}, readiness: readinessData || api.readinessLatest.data || {}, strategy_config: api.strategyConfig.data || {}, openai_usage: openaiUsageData || {}, data_quality: api.dataQuality.data || {}, audit: api.auditLatest.data || {} }, null, 2); }
      function clearWorkspace() { ["workspace-shadow", "workspace-ai", "workspace-risk", "workspace-extra"].forEach((id) => { document.getElementById(id).value = ""; }); }
      function reviewPackageTemplate(kind) {
        const extra = document.getElementById("workspace-extra").value;
        return `Project: binance-ai-trader
Current goal: analyze Testnet dry-run / Shadow Mode performance and propose small safe optimizations.

Safety boundaries:
1. Do not bypass RiskEngine.
2. Do not enable Live.
3. GPT cannot place orders.
4. Do not modify OrderManager as the only order entry point.
5. Do not add Futures, Margin, or Leverage.
6. Do not disable DataQualityGate to increase trade count.
7. Any strategy parameter change must be validated by backtest, then Shadow Mode.

Review type: ${kind}

Please judge:
1. Whether the main issue is data quality, local strategy, AI review, risk, sample size, Shadow evaluation, or execution chain.
2. Whether EMA parameters are too conservative or too aggressive.
3. Which 1-2 parameters or files should be inspected first.
4. Which areas must not be changed.
5. A bounded Codex prompt for the next change.
6. Validation commands after the change.

[Strategy Config]
${JSON.stringify(api.strategyConfig.data || {}, null, 2)}

[Shadow Report]
${document.getElementById("workspace-shadow").value || JSON.stringify(api.shadowReport.data || {}, null, 2)}

[AI Reviews]
${document.getElementById("workspace-ai").value || JSON.stringify(api.aiReviews.data || [], null, 2)}

[Risk Decisions]
${document.getElementById("workspace-risk").value || JSON.stringify(api.riskDecisions.data || [], null, 2)}

[DataQuality]
${JSON.stringify(api.dataQuality.data || {}, null, 2)}

[Readiness]
${JSON.stringify(readinessData || api.readinessLatest.data || {}, null, 2)}

[OpenAI Usage]
${JSON.stringify(openaiUsageData || {}, null, 2)}

[Audit]
${JSON.stringify(api.auditLatest.data || {}, null, 2)}

[User Notes]
${extra}
`;
      }
      function copyReviewPackage() { return copyToClipboard("Full GPT Review Package", reviewPackageTemplate("full dashboard review")); }
      function copyStrategyOptimizationPackage() { return copyToClipboard("Strategy Optimization Package", reviewPackageTemplate("strategy parameter optimization")); }
      function copyReadinessPackage() { return copyToClipboard("Readiness Review Package", `Review this Testnet readiness report. Do not suggest adding Dashboard order buttons. Real lifecycle must remain CLI-only.\n\n${JSON.stringify(readinessData || api.readinessLatest.data || {}, null, 2)}`); }

      refreshAll();
      setInterval(() => fetchModule("health"), 5000);
      setInterval(() => { fetchModule("logs"); fetchModule("snapshots"); fetchModule("pipelineAudit"); }, 10000);
      setInterval(() => { fetchModule("aiReviews"); fetchModule("riskDecisions"); fetchModule("orders"); fetchModule("signals"); fetchModule("riskState"); fetchModule("dataQuality"); }, 15000);
      setInterval(() => { fetchModule("shadowReport"); fetchModule("shadowRecent"); fetchModule("shadowOpen"); }, 30000);
      setInterval(() => fetchModule("auditLatest"), 60000);
    </script>
  </body>
</html>
"""
