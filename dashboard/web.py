from __future__ import annotations

# ruff: noqa: E501


def dashboard_html() -> str:
    """Return the local operations dashboard HTML.

    The page is intentionally dependency-light: FastAPI serves this string directly, and the
    browser uses native JavaScript plus Tailwind CDN for a local-only operations console.
    """

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
      textarea { min-height: 12rem; }
    </style>
  </head>
  <body class="bg-slate-100 text-slate-950">
    <main class="mx-auto max-w-[1600px] px-4 py-5 sm:px-6 lg:px-8">
      <header class="mb-5 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p class="text-xs font-semibold uppercase tracking-wide text-emerald-700">Local Testnet / Dry-run console</p>
            <h1 class="mt-1 text-2xl font-semibold tracking-tight text-slate-950">
              Binance AI Trader Local Operations Dashboard
            </h1>
            <p class="mt-2 max-w-4xl text-sm text-slate-600">
              This page observes the local Testnet-first runtime, Shadow Mode, AI reviews, hard
              risk checks, and audit reports. It is not a Live trading console.
            </p>
            <p class="mt-2 text-xs font-medium text-red-700">
              Safety boundary: No real order button, No Live switch, No disable-dry-run button,
              No order execution enable button, No automatic Codex call.
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
            <button
              class="btn-danger"
              onclick="postAction('Kill Switch OFF','/control/kill-switch/off','关闭 runtime kill switch 会解除数据库层熔断，仅在确认 dry-run/testnet 安全状态下使用。确定继续？')"
            >
              Kill Switch OFF
            </button>
          </div>
        </div>
        <div class="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          Kill Switch OFF warning: 关闭 runtime kill switch 会解除数据库层熔断，仅在确认
          dry-run/testnet 安全状态下使用。
        </div>
        <div class="mt-4 flex flex-wrap items-center gap-3 text-xs text-slate-500">
          <span>Page last refreshed: <strong id="page-last-refresh">—</strong></span>
          <span id="action-result" class="rounded-md bg-slate-100 px-2 py-1 text-slate-700">No actions yet.</span>
        </div>
      </header>

      <section class="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8" id="safety-overview"></section>

      <div class="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>Runtime</h2>
              <p>Runtime 是系统主控，负责启动行情流、REST 轮询、策略生成、AI 审查、风控、Shadow 评估和审计任务。</p>
            </div>
            <span id="meta-health" class="module-meta">—</span>
          </div>
          <div id="runtime-body" class="kv-grid"></div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>Streams &amp; Network</h2>
              <p>该模块用于判断 Binance Testnet 行情流、用户流和网络状态是否正常。</p>
            </div>
            <span id="meta-status" class="module-meta">—</span>
          </div>
          <div id="streams-body" class="space-y-3"></div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>DataQualityGate</h2>
              <p>DataQualityGate 是交易前的数据质量闸门，用于判断当前数据是否可信，是否允许 StrategyPlanner、SignalReview 和订单路径继续执行。</p>
            </div>
            <span id="meta-dataQuality" class="module-meta">—</span>
          </div>
          <div id="data-quality-body" class="space-y-3"></div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>Strategy Snapshot</h2>
              <p>本地策略模块根据行情和技术指标生成候选信号。当前主要策略是 EMA Trend，它只生成 candidate signal，不直接下单。</p>
            </div>
            <span id="meta-snapshots" class="module-meta">—</span>
          </div>
          <div id="strategy-body" class="space-y-3"></div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>AI SignalReview</h2>
              <p>SignalReviewer 负责审查本地策略产生的候选信号，判断是否允许进入 RiskEngine。它只输出结构化 JSON，不能下单。</p>
            </div>
            <span id="meta-aiReviews" class="module-meta">—</span>
          </div>
          <div id="ai-body" class="space-y-3"></div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>RiskEngine</h2>
              <p>RiskEngine 是硬风控层。所有交易意图必须经过它，只有通过后才可能进入 OrderManager。</p>
            </div>
            <span id="meta-riskDecisions" class="module-meta">—</span>
          </div>
          <div id="risk-body" class="space-y-3"></div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>OrderManager / Recent Orders</h2>
              <p>OrderManager 是唯一订单入口。dry-run 或 order_execution_disabled 状态下只创建本地订单记录，不会提交 Binance 订单。</p>
            </div>
            <span id="meta-orders" class="module-meta">—</span>
          </div>
          <div id="orders-body" class="space-y-3"></div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>Shadow Mode</h2>
              <p>Shadow Mode 用来记录如果系统真的下单，本来会发生什么，并计算模拟 PnL、MFE、MAE。它不下单，不改交易状态。</p>
            </div>
            <span id="meta-shadowReport" class="module-meta">—</span>
          </div>
          <div class="mb-3 flex flex-wrap gap-2">
            <button class="btn-muted" onclick="postAction('Run Shadow Evaluation','/runtime/shadow/evaluate')">Run Shadow Evaluation</button>
            <button class="btn-muted" onclick="copyJson('Shadow Report', api.shadowReport.data)">Copy Shadow Report</button>
            <button class="btn-muted" onclick="copyShadowPrompt()">Copy GPT Shadow Review Prompt</button>
          </div>
          <div id="shadow-body" class="space-y-3"></div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>Account / Position</h2>
              <p>账户仓位模块用于查看 Testnet 账户状态、仓位状态和是否满足真实 Testnet 订单前置条件。</p>
            </div>
            <span id="meta-configSafe" class="module-meta">—</span>
          </div>
          <div id="account-body" class="space-y-3"></div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>OpenAI Budget</h2>
              <p>OpenAI Budget 用于控制 API 成本，防止 StrategyPlanner 和 SignalReviewer 产生不可控费用。</p>
            </div>
            <span id="meta-riskState" class="module-meta">—</span>
          </div>
          <div id="budget-body" class="space-y-3"></div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>SystemAuditor</h2>
              <p>SystemAuditor 是只读系统审计器，用于发现运行问题和安全边界异常。它不能改代码、不能改配置、不能调用 Codex、不能下单。</p>
            </div>
            <span id="meta-auditLatest" class="module-meta">—</span>
          </div>
          <div class="mb-3 flex flex-wrap gap-2">
            <button class="btn-muted" onclick="postAction('Run System Audit','/runtime/audits/run')">Run System Audit</button>
            <button class="btn-muted" onclick="copyJson('Audit JSON', api.auditLatest.data)">Copy Audit JSON</button>
            <button class="btn-muted" onclick="copyAuditPrompt()">Copy GPT Audit Review Prompt</button>
          </div>
          <div id="audit-body" class="space-y-3"></div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>Logs / Pipeline</h2>
              <p>日志和 Pipeline 用于定位系统链路卡在哪一步：snapshot、signal、AI、risk、order、user stream、reconciliation 或 trade review。</p>
            </div>
            <span id="meta-logs" class="module-meta">—</span>
          </div>
          <div id="logs-body" class="space-y-3"></div>
        </section>
      </div>

      <section class="panel mt-5">
        <div class="panel-head">
          <div>
            <h2>Review Workspace</h2>
            <p>把当前系统状态、Shadow Report、AI Reviews、Risk Decisions、Audit 和 DataQuality 摘要整理为可复制的 GPT 复盘包。</p>
          </div>
          <span class="module-meta">local only</span>
        </div>
        <div class="mb-3 flex flex-wrap gap-2">
          <button class="btn-primary" onclick="autoFillWorkspace()">Auto Fill From Current Dashboard</button>
          <button class="btn-muted" onclick="copyReviewPackage()">Copy GPT Review Package</button>
          <button class="btn-muted" onclick="clearWorkspace()">Clear Workspace</button>
        </div>
        <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <label class="workspace-label">
            <span>Shadow Report</span>
            <button class="btn-mini" onclick="copyTextArea('workspace-shadow')">Copy Individual Section</button>
            <textarea id="workspace-shadow" class="workspace-text"></textarea>
          </label>
          <label class="workspace-label">
            <span>AI Reviews</span>
            <button class="btn-mini" onclick="copyTextArea('workspace-ai')">Copy Individual Section</button>
            <textarea id="workspace-ai" class="workspace-text"></textarea>
          </label>
          <label class="workspace-label">
            <span>Risk Decisions</span>
            <button class="btn-mini" onclick="copyTextArea('workspace-risk')">Copy Individual Section</button>
            <textarea id="workspace-risk" class="workspace-text"></textarea>
          </label>
          <label class="workspace-label">
            <span>综合优化请求</span>
            <button class="btn-mini" onclick="copyTextArea('workspace-extra')">Copy Individual Section</button>
            <textarea id="workspace-extra" class="workspace-text" placeholder="写下你希望 GPT 重点分析的问题，例如：为什么 Shadow Mode 没有 WOULD_PLACE_ORDER？"></textarea>
          </label>
        </div>
      </section>
    </main>

    <script>
      const api = {
        health: { url: "/runtime/health", data: null, error: null, loading: false, last: null },
        logs: { url: "/runtime/logs/recent", data: null, error: null, loading: false, last: null },
        snapshots: { url: "/runtime/last-snapshots", data: null, error: null, loading: false, last: null },
        aiReviews: { url: "/runtime/last-ai-reviews", data: null, error: null, loading: false, last: null },
        riskDecisions: { url: "/runtime/last-risk-decisions", data: null, error: null, loading: false, last: null },
        dataQuality: { url: "/runtime/data-quality/latest", data: null, error: null, loading: false, last: null },
        shadowReport: { url: "/runtime/shadow/report", data: null, error: null, loading: false, last: null },
        shadowRecent: { url: "/runtime/shadow/recent", data: null, error: null, loading: false, last: null },
        shadowOpen: { url: "/runtime/shadow/open", data: null, error: null, loading: false, last: null },
        auditLatest: { url: "/runtime/audits/latest", data: null, error: null, loading: false, last: null },
        pipelineAudit: { url: "/runtime/audit/recent", data: null, error: null, loading: false, last: null },
        orders: { url: "/orders/recent", data: null, error: null, loading: false, last: null },
        signals: { url: "/signals/recent", data: null, error: null, loading: false, last: null },
        riskState: { url: "/risk/state", data: null, error: null, loading: false, last: null },
        configSafe: { url: "/config/safe", data: null, error: null, loading: false, last: null },
        status: { url: "/status", data: null, error: null, loading: false, last: null },
      };

      const style = document.createElement("style");
      style.innerHTML = `
        .panel { border: 1px solid rgb(226 232 240); border-radius: 0.5rem; background: white; padding: 1rem; box-shadow: 0 1px 2px rgb(15 23 42 / 0.06); }
        .panel-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; margin-bottom: 0.9rem; }
        .panel h2 { font-size: 1.05rem; font-weight: 700; color: rgb(15 23 42); }
        .panel p { margin-top: 0.25rem; font-size: 0.8rem; line-height: 1.35; color: rgb(71 85 105); }
        .module-meta { white-space: nowrap; border-radius: 999px; background: rgb(241 245 249); padding: 0.25rem 0.55rem; font-size: 0.72rem; color: rgb(71 85 105); }
        .btn-primary, .btn-safe, .btn-muted, .btn-warn, .btn-danger, .btn-mini { border-radius: 0.375rem; padding: 0.45rem 0.7rem; font-size: 0.78rem; font-weight: 700; transition: opacity .15s; }
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
        .kv .v { margin-top: 0.25rem; font-size: 0.9rem; font-weight: 700; color: rgb(15 23 42); overflow-wrap: anywhere; }
        .workspace-label { display: flex; flex-direction: column; gap: 0.5rem; font-size: 0.85rem; font-weight: 700; color: rgb(30 41 59); }
        .workspace-text { width: 100%; border: 1px solid rgb(203 213 225); border-radius: 0.375rem; padding: 0.65rem; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.78rem; font-weight: 400; color: rgb(15 23 42); }
      `;
      document.head.appendChild(style);

      function esc(value) {
        const raw = value === null || value === undefined || value === "" ? "—" : String(value);
        return raw.replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
      }

      function asText(value) {
        if (value === null || value === undefined || value === "") return "—";
        if (typeof value === "object") return JSON.stringify(value);
        return String(value);
      }

      function get(obj, path, fallback = "—") {
        const parts = path.split(".");
        let current = obj;
        for (const part of parts) {
          if (current === null || current === undefined || !(part in Object(current))) return fallback;
          current = current[part];
        }
        return current === null || current === undefined || current === "" ? fallback : current;
      }

      function normalizeStatus(value) {
        return asText(value).toUpperCase();
      }

      function badge(value, label = null) {
        const text = label || asText(value);
        const norm = normalizeStatus(value);
        let cls = "bg-slate-100 text-slate-700 border-slate-200";
        if (["OK", "SAFE", "RUNNING", "TRUE", "APPROVED", "ALLOW", "ACTIVE"].some((x) => norm.includes(x))) cls = "bg-emerald-50 text-emerald-700 border-emerald-200";
        if (["WARN", "WATCH", "DEGRADED", "UNKNOWN", "STOPPED", "HUMAN", "ON"].some((x) => norm.includes(x))) cls = "bg-amber-50 text-amber-800 border-amber-200";
        if (["CRITICAL", "ERROR", "FAILED", "FALSE", "BLOCK", "REJECT", "DISABLED"].some((x) => norm.includes(x))) cls = "bg-red-50 text-red-700 border-red-200";
        return `<span class="inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-bold ${cls}">${esc(text)}</span>`;
      }

      function kv(label, value) {
        return `<div class="kv"><div class="k">${esc(label)}</div><div class="v">${esc(asText(value))}</div></div>`;
      }

      function renderJson(title, data) {
        return `<details class="rounded-md border border-slate-200 bg-slate-50 p-2 text-xs">
          <summary class="cursor-pointer font-bold text-slate-700">${esc(title)}</summary>
          <pre class="mt-2 overflow-auto text-slate-700">${esc(JSON.stringify(data ?? {}, null, 2))}</pre>
        </details>`;
      }

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
          render();
        }
      }

      function refreshAll() {
        document.getElementById("page-last-refresh").textContent = new Date().toLocaleString();
        Object.keys(api).forEach((name) => fetchModule(name));
      }

      async function postAction(label, url, confirmText = null) {
        if (confirmText && !window.confirm(confirmText)) return;
        const target = document.getElementById("action-result");
        target.textContent = `${label}: running...`;
        target.className = "rounded-md bg-blue-50 px-2 py-1 text-blue-700";
        try {
          const response = await fetch(url, { method: "POST", cache: "no-store" });
          const text = await response.text();
          let payload = null;
          try { payload = text ? JSON.parse(text) : null; } catch { payload = { raw: text }; }
          if (!response.ok) throw new Error(`${response.status} ${response.statusText}: ${text.slice(0, 400)}`);
          target.textContent = `${label}: ${JSON.stringify(payload).slice(0, 260)}`;
          target.className = "rounded-md bg-emerald-50 px-2 py-1 text-emerald-700";
          refreshAll();
        } catch (error) {
          target.textContent = `${label} failed: ${error.message || error}`;
          target.className = "rounded-md bg-red-50 px-2 py-1 text-red-700";
        }
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
        const dq = api.dataQuality.data || get(h, "data_quality_status.latest_snapshot", {});
        const kill = get(h, "kill_switch_state.effective_enabled", get(status, "kill_switch_enabled", "UNKNOWN"));
        const liveDisabled = get(status, "live_trading_enabled", false) === false;
        const cards = [
          ["Runtime State", get(h, "state")],
          ["Trading Mode", get(h, "trading_mode", get(status, "trading_mode"))],
          ["Dry Run", get(h, "dry_run")],
          ["Order Execution", get(h, "order_execution_enabled")],
          ["Live Disabled", liveDisabled],
          ["Kill Switch", kill ? "ON" : "OFF"],
          ["Data Quality", get(dq, "overall_status", get(h, "data_quality_status.overall_status", "UNKNOWN"))],
          ["Health Warning", get(h, "health_warning", false)],
        ];
        document.getElementById("safety-overview").innerHTML = cards.map(([label, value]) => `
          <div class="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
            <div class="text-xs font-bold uppercase tracking-wide text-slate-500">${esc(label)}</div>
            <div class="mt-2 text-lg font-black">${badge(value)}</div>
          </div>
        `).join("");
      }

      function renderRuntime() {
        const h = api.health.data || {};
        document.getElementById("runtime-body").innerHTML = [
          kv("state", get(h, "state")),
          kv("trading_mode", get(h, "trading_mode")),
          kv("symbols", (get(h, "symbols", []) || []).join(", ")),
          kv("dry_run", get(h, "dry_run")),
          kv("ai_enabled", get(h, "ai_enabled")),
          kv("order_execution_enabled", get(h, "order_execution_enabled")),
          kv("reconnecting", get(h, "reconnecting")),
          kv("data_delay_seconds", get(h, "data_delay_seconds")),
          kv("last_kline_time", get(h, "last_kline_time")),
          kv("last_user_event_time", get(h, "last_user_event_time")),
          kv("last_error", get(h, "last_error")),
        ].join("");
      }

      function renderStreams() {
        const h = api.health.data || {};
        const network = get(h, "network_readiness", {});
        document.getElementById("streams-body").innerHTML = `
          <div class="kv-grid">
            ${kv("market_stream_connected", get(h, "market_stream_connected"))}
            ${kv("user_stream_connected", get(h, "user_stream_connected"))}
            ${kv("last_kline_time", get(h, "last_kline_time"))}
            ${kv("last_user_event_time", get(h, "last_user_event_time"))}
            ${kv("data_delay_seconds", get(h, "data_delay_seconds"))}
          </div>
          ${renderJson("market_stream", get(h, "market_stream", {}))}
          ${renderJson("user_stream", get(h, "user_stream", {}))}
          ${renderJson("network_readiness", network)}
        `;
      }

      function renderDataQuality() {
        const dq = api.dataQuality.data || {};
        if (dq.status === "NO_DATA_QUALITY_SNAPSHOT") {
          document.getElementById("data-quality-body").innerHTML = `<div class="rounded-md bg-amber-50 p-3 text-sm text-amber-800">暂无数据质量快照，请先启动 dry-run 或点击 Run Data Quality Check。</div>`;
          return;
        }
        const issues = get(dq, "issues", []);
        document.getElementById("data-quality-body").innerHTML = `
          <div class="kv-grid">
            ${kv("overall_status", get(dq, "overall_status"))}
            ${kv("action", get(dq, "action"))}
            ${kv("safe_for_strategy_planner", get(dq, "safe_for_strategy_planner"))}
            ${kv("safe_for_signal_review", get(dq, "safe_for_signal_review"))}
            ${kv("safe_for_order", get(dq, "safe_for_order"))}
            ${kv("safe_for_real_testnet_order", get(dq, "safe_for_real_testnet_order"))}
            ${kv("issue_count", Array.isArray(issues) ? issues.length : 0)}
            ${kv("reason_codes", (get(dq, "reason_codes", []) || []).join(", "))}
          </div>
          ${listItems(issues, (issue) => `<div class="rounded-md border border-slate-200 p-2 text-sm">${badge(get(issue, "severity"))} <strong>${esc(get(issue, "title"))}</strong><div class="mt-1 text-slate-600">${esc(get(issue, "recommended_action"))}</div>${renderJson("evidence", get(issue, "evidence", []))}</div>`, "No data quality issues.")}
          ${renderJson("DataQuality raw", dq)}
        `;
      }

      function renderStrategy() {
        const snapshots = api.snapshots.data || {};
        const signals = api.signals.data || [];
        const keys = snapshots && typeof snapshots === "object" ? Object.keys(snapshots) : [];
        const snapshotHtml = keys.length === 0
          ? `<div class="rounded-md bg-slate-50 p-3 text-sm text-slate-500">暂无行情快照，可能 runtime 未启动或 K线尚未加载。</div>`
          : keys.map((symbol) => {
              const snap = snapshots[symbol] || {};
              return `<div class="rounded-md border border-slate-200 p-2">
                <div class="mb-2 flex items-center justify-between"><strong>${esc(symbol)}</strong>${badge(get(snap, "ws_health", "UNKNOWN"))}</div>
                <div class="kv-grid">
                  ${kv("price", get(snap, "price"))}
                  ${kv("ema_fast", get(snap, "ema_fast_5m", get(snap, "ema_fast")))}
                  ${kv("ema_slow", get(snap, "ema_slow_5m", get(snap, "ema_slow")))}
                  ${kv("rsi", get(snap, "rsi14_5m", get(snap, "rsi")))}
                  ${kv("atr", get(snap, "atr14_5m", get(snap, "atr")))}
                  ${kv("volume_ratio", get(snap, "volume_ratio_5m", get(snap, "volume_ratio")))}
                  ${kv("data_delay_seconds", get(snap, "data_delay_seconds"))}
                </div>
              </div>`;
            }).join("");
        document.getElementById("strategy-body").innerHTML = `
          ${snapshotHtml}
          <h3 class="text-sm font-bold text-slate-700">Recent signals</h3>
          ${listItems(signals, (row) => `<div class="rounded-md border border-slate-200 p-2 text-sm"><strong>${esc(get(row, "symbol"))}</strong> ${badge(get(row, "side"))} confidence ${esc(get(row, "confidence"))}<div class="text-slate-600">${esc(get(row, "reason"))}</div></div>`, "No recent signals.")}
        `;
      }

      function reviewPayload(row) {
        return get(row, "review", get(row, "output_json", row));
      }

      function renderAI() {
        const rows = api.aiReviews.data || [];
        const summary = { total: rows.length, schema_valid: 0, schema_invalid: 0, decisions: {} };
        rows.forEach((row) => {
          if (get(row, "schema_valid", false) === true) summary.schema_valid += 1; else summary.schema_invalid += 1;
          const decision = get(reviewPayload(row), "decision", get(row, "decision", "UNKNOWN"));
          summary.decisions[decision] = (summary.decisions[decision] || 0) + 1;
        });
        document.getElementById("ai-body").innerHTML = `
          <div class="kv-grid">
            ${kv("total reviews", summary.total)}
            ${kv("schema_valid", summary.schema_valid)}
            ${kv("schema_invalid", summary.schema_invalid)}
            ${kv("decision distribution", JSON.stringify(summary.decisions))}
          </div>
          ${listItems(rows, (row, index) => {
            const review = reviewPayload(row);
            return `<div class="rounded-md border border-slate-200 p-3 text-sm">
              <div class="flex flex-wrap items-center justify-between gap-2">
                <strong>${esc(get(row, "symbol", get(review, "symbol")))}</strong>
                <div class="flex flex-wrap gap-2">
                  ${badge(get(row, "schema_valid", "UNKNOWN"), `schema_valid=${get(row, "schema_valid", "UNKNOWN")}`)}
                  ${badge(get(review, "decision", get(row, "decision", "UNKNOWN")))}
                </div>
              </div>
              <div class="mt-2 kv-grid">
                ${kv("actual_model", get(row, "actual_model", get(row, "model")))}
                ${kv("active_strategy_plan_id", get(row, "active_strategy_plan_id"))}
                ${kv("side", get(review, "side", get(row, "side")))}
                ${kv("confidence", get(review, "confidence", get(row, "confidence")))}
                ${kv("risk_level", get(review, "risk_level"))}
                ${kv("market_regime", get(review, "market_regime"))}
                ${kv("requires_human_review", get(review, "requires_human_review"))}
              </div>
              <p class="mt-2 text-sm text-slate-700">${esc(get(review, "reason", get(row, "reason")))}</p>
              ${renderJson("warnings", get(review, "warnings", []))}
              <div class="mt-2 flex flex-wrap gap-2">
                <button class="btn-mini" onclick='copyJson("AI Review", api.aiReviews.data[${index}])'>Copy JSON</button>
                <button class="btn-mini" onclick='copyAIReviewPrompt(${index})'>Copy GPT Review Prompt</button>
              </div>
            </div>`;
          }, "No AI reviews.")}
        `;
      }

      function renderRisk() {
        const rows = api.riskDecisions.data || [];
        const riskState = api.riskState.data || {};
        const h = api.health.data || {};
        const counts = {};
        rows.forEach((row) => {
          const reason = get(row, "reason", "UNKNOWN");
          counts[reason] = (counts[reason] || 0) + 1;
        });
        const top = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 8);
        document.getElementById("risk-body").innerHTML = `
          <div class="kv-grid">
            ${kv("orders_last_minute", get(h, "risk_runtime_status.orders_last_minute"))}
            ${kv("seen_client_order_id_count", get(h, "risk_runtime_status.seen_client_order_id_count"))}
            ${kv("risk_engine_reused", get(h, "risk_runtime_status.risk_engine_reused"))}
            ${kv("kill_switch_enabled_config", get(h, "risk_runtime_status.kill_switch_enabled_config", get(riskState, "configured.kill_switch_enabled")))}
            ${kv("kill_switch_enabled_runtime", get(h, "risk_runtime_status.kill_switch_enabled_runtime", get(riskState, "kill_switch_enabled")))}
          </div>
          <h3 class="text-sm font-bold text-slate-700">Top recent rejection reasons</h3>
          ${listItems(top, ([reason, count]) => `<div class="rounded-md bg-slate-50 p-2 text-sm"><strong>${esc(count)}</strong> ${esc(reason)}</div>`, "No rejections found.")}
          ${listItems(rows, (row) => `<div class="rounded-md border border-slate-200 p-2 text-sm">${badge(get(row, "approved") ? "APPROVED" : "REJECTED")} <strong>${esc(get(row, "symbol"))}</strong><div class="text-slate-600">${esc(get(row, "reason"))}</div>${renderJson("risk_state_json", get(row, "risk_state_json", row))}</div>`, "No risk decisions.")}
        `;
      }

      function renderOrders() {
        const orders = api.orders.data || [];
        const h = api.health.data || {};
        const dryRun = get(h, "dry_run", true);
        const execution = get(h, "order_execution_enabled", false);
        const possible = dryRun === false && execution === true;
        document.getElementById("orders-body").innerHTML = `
          <div class="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
            <div>当前 dry_run = <strong>${esc(dryRun)}</strong></div>
            <div>当前 order_execution_enabled = <strong>${esc(execution)}</strong></div>
            <div>当前真实 Binance new_order 是否可能触发 = <strong>${possible ? "可能，但本 Dashboard 不提供真实下单按钮" : "否，当前不会提交真实 Binance order"}</strong></div>
          </div>
          ${listItems(orders, (row) => `<div class="rounded-md border border-slate-200 p-2 text-sm"><div class="flex flex-wrap justify-between gap-2"><strong>${esc(get(row, "client_order_id"))}</strong>${badge(get(row, "status"))}</div><div class="kv-grid mt-2">${kv("symbol", get(row, "symbol"))}${kv("side", get(row, "side"))}${kv("order_type", get(row, "order_type"))}${kv("price", get(row, "price"))}${kv("quantity", get(row, "quantity"))}${kv("trading_mode", get(row, "trading_mode"))}${kv("created_at", get(row, "created_at"))}</div></div>`, "No recent orders.")}
        `;
      }

      function renderShadow() {
        const report = api.shadowReport.data || {};
        const open = api.shadowOpen.data || [];
        const recent = api.shadowRecent.data || [];
        document.getElementById("shadow-body").innerHTML = `
          <div class="kv-grid">
            ${kv("total_decisions", get(report, "total_decisions"))}
            ${kv("WOULD_PLACE_ORDER", get(report, "would_place_order_count"))}
            ${kv("AI_REJECTED", get(report, "ai_rejected_count"))}
            ${kv("RISK_REJECTED", get(report, "risk_rejected_count"))}
            ${kv("DATA_QUALITY_BLOCKED", get(report, "data_quality_blocked_count"))}
            ${kv("simulated_total_pnl_usdt", get(report, "simulated_total_pnl_usdt"))}
            ${kv("simulated_win_rate", get(report, "simulated_win_rate"))}
            ${kv("simulated_avg_pnl_pct", get(report, "simulated_avg_pnl_pct"))}
          </div>
          ${renderJson("best_shadow_trade", get(report, "best_shadow_trade", {}))}
          ${renderJson("worst_shadow_trade", get(report, "worst_shadow_trade", {}))}
          ${renderJson("top_rejection_reasons", get(report, "top_rejection_reasons", []))}
          <h3 class="text-sm font-bold text-slate-700">Open shadow decisions</h3>
          ${listItems(open, (row) => `<div class="rounded-md border border-slate-200 p-2 text-sm"><strong>${esc(get(row, "shadow_id"))}</strong> ${badge(get(row, "status"))} ${badge(get(row, "decision_type"))}<div>${esc(get(row, "symbol"))} ${esc(get(row, "side"))}</div></div>`, "No open shadow decisions.")}
          <h3 class="text-sm font-bold text-slate-700">Recent shadow decisions</h3>
          ${listItems(recent, (row) => `<div class="rounded-md border border-slate-200 p-2 text-sm"><strong>${esc(get(row, "shadow_id"))}</strong> ${badge(get(row, "decision_type"))}<div class="text-slate-600">${esc(get(row, "reason"))}</div></div>`, "No recent shadow decisions.")}
        `;
      }

      function renderAccount() {
        const status = get(api.health.data || {}, "account_position_status", {});
        const accountSource = get(status, "account_source");
        const positions = get(status, "positions", []);
        const simulated = accountSource === "simulated_default" || (Array.isArray(positions) && positions.some((p) => get(p, "source") === "simulated_default"));
        document.getElementById("account-body").innerHTML = `
          ${simulated ? `<div class="rounded-md bg-amber-50 p-3 text-sm font-bold text-amber-900">当前账户/仓位数据为 simulated_default，不可视为真实 Testnet 账户。</div>` : ""}
          <div class="kv-grid">
            ${kv("account_status", get(status, "account_status"))}
            ${kv("account_source", accountSource)}
            ${kv("equity_usdt", get(status, "equity_usdt"))}
            ${kv("available_usdt", get(status, "available_usdt"))}
            ${kv("safe_for_real_order", get(status, "safe_for_real_order"))}
            ${kv("latest_created_at", get(status, "latest_created_at"))}
            ${kv("reason_codes", (get(status, "reason_codes", []) || []).join(", "))}
          </div>
          ${renderJson("positions", positions)}
        `;
      }

      function renderBudget() {
        const budget = get(api.health.data || {}, "budget_status", {});
        document.getElementById("budget-body").innerHTML = `
          <div class="kv-grid">
            ${kv("daily budget", get(budget, "daily_budget_usd"))}
            ${kv("monthly budget", get(budget, "monthly_budget_usd"))}
            ${kv("today cost", get(budget, "openai_today_cost_usd", get(budget, "estimated_today_cost_usd")))}
            ${kv("month cost", get(budget, "openai_month_cost_usd", get(budget, "estimated_month_cost_usd")))}
            ${kv("strategy calls", get(budget, "strategy_calls_today"))}
            ${kv("signal calls", get(budget, "signal_calls_today"))}
            ${kv("budget_guard_enabled", get(budget, "budget_guard_enabled"))}
            ${kv("budget_blocked", get(budget, "budget_blocked"))}
          </div>
          ${renderJson("budget raw", budget)}
        `;
      }

      function renderAudit() {
        const report = api.auditLatest.data || {};
        if (report.status === "NO_AUDIT_REPORT") {
          document.getElementById("audit-body").innerHTML = `<div class="rounded-md bg-slate-50 p-3 text-sm text-slate-500">No SystemAuditor report yet. Click Run System Audit.</div>`;
          return;
        }
        document.getElementById("audit-body").innerHTML = `
          <div class="kv-grid">
            ${kv("latest_overall_status", get(report, "overall_status", get(report, "latest_overall_status")))}
            ${kv("latest_highest_severity", get(report, "highest_severity", get(report, "latest_highest_severity")))}
            ${kv("latest_issue_count", get(report, "issue_count", get(report, "latest_issue_count")))}
            ${kv("latest_report_created_at", get(report, "created_at", get(report, "latest_report_created_at")))}
          </div>
          <p class="rounded-md bg-slate-50 p-3 text-sm text-slate-700">${esc(get(report, "summary", get(report, "latest_summary")))}</p>
          ${renderJson("issues", get(report, "issues", get(report, "raw_output_json_sanitized.issues", [])))}
          ${renderJson("recommended_next_human_steps", get(report, "recommended_next_human_steps", []))}
        `;
      }

      function renderLogs() {
        const logs = api.logs.data || [];
        const audits = api.pipelineAudit.data || [];
        document.getElementById("logs-body").innerHTML = `
          <h3 class="text-sm font-bold text-slate-700">Recent runtime logs</h3>
          ${listItems(logs.slice(0, 100), (row) => `<div class="rounded-md border border-slate-200 p-2 text-xs">${esc(get(row, "event", get(row, "message", "runtime_log")))} ${badge(get(row, "level", get(row, "status", "INFO")))}${renderJson("raw", row)}</div>`, "No runtime logs.")}
          <h3 class="text-sm font-bold text-slate-700">Pipeline audit</h3>
          ${listItems(audits.slice(0, 100), (row) => `<div class="rounded-md border border-slate-200 p-2 text-xs"><strong>${esc(get(row, "stage"))}</strong> ${badge(get(row, "status"))}<div>${esc(get(row, "error_message"))}</div>${renderJson("raw", row)}</div>`, "No pipeline audit rows.")}
        `;
      }

      function render() {
        renderMeta();
        renderSafety();
        renderRuntime();
        renderStreams();
        renderDataQuality();
        renderStrategy();
        renderAI();
        renderRisk();
        renderOrders();
        renderShadow();
        renderAccount();
        renderBudget();
        renderAudit();
        renderLogs();
      }

      async function copyToClipboard(label, text) {
        const payload = String(text ?? "");
        try {
          if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(payload);
          } else {
            const area = document.createElement("textarea");
            area.value = payload;
            area.style.position = "fixed";
            area.style.left = "-9999px";
            document.body.appendChild(area);
            area.focus();
            area.select();
            document.execCommand("copy");
            document.body.removeChild(area);
          }
          document.getElementById("action-result").textContent = `${label}: copied`;
        } catch {
          const area = document.createElement("textarea");
          area.value = payload;
          document.body.appendChild(area);
          area.focus();
          area.select();
          document.getElementById("action-result").textContent = `${label}: clipboard unavailable, selected text for manual copy`;
        }
      }

      function copyJson(label, data) {
        return copyToClipboard(label, JSON.stringify(data ?? {}, null, 2));
      }

      function copyAIReviewPrompt(index) {
        const row = (api.aiReviews.data || [])[index] || {};
        return copyToClipboard("GPT AI Review Prompt", `请分析以下 SignalReviewer 记录，判断 AI 审查是否过于保守、是否 schema 稳定、是否上下文不足，并指出应该优化 prompt、context_builder 还是策略本身。以下是 JSON：\n\n${JSON.stringify(row, null, 2)}`);
      }

      function copyShadowPrompt() {
        return copyToClipboard("GPT Shadow Review Prompt", `请基于以下 Shadow Report，判断当前策略主要问题：是否样本不足、是否策略不产生信号、是否 AI 拒绝过多、是否 RiskEngine 拒绝过多、是否 DataQualityGate 阻断过多、WOULD_PLACE_ORDER 的模拟 PnL 是否支持继续观察或优化，并指出优先改哪个模块和文件。以下是 JSON：\n\n${JSON.stringify(api.shadowReport.data || {}, null, 2)}`);
      }

      function copyAuditPrompt() {
        return copyToClipboard("GPT Audit Review Prompt", `请基于以下 SystemAuditor 报告，判断系统主要风险、哪些问题需要人工处理、哪些文件可能需要小范围修改，并明确哪些安全边界绝对不能动。以下是 JSON：\n\n${JSON.stringify(api.auditLatest.data || {}, null, 2)}`);
      }

      function copyTextArea(id) {
        return copyToClipboard("Workspace section", document.getElementById(id).value);
      }

      function autoFillWorkspace() {
        document.getElementById("workspace-shadow").value = JSON.stringify(api.shadowReport.data || {}, null, 2);
        document.getElementById("workspace-ai").value = JSON.stringify(api.aiReviews.data || [], null, 2);
        document.getElementById("workspace-risk").value = JSON.stringify(api.riskDecisions.data || [], null, 2);
        document.getElementById("workspace-extra").value = JSON.stringify({
          data_quality: api.dataQuality.data || {},
          audit: api.auditLatest.data || {},
          runtime_health: api.health.data || {},
        }, null, 2);
      }

      function clearWorkspace() {
        ["workspace-shadow", "workspace-ai", "workspace-risk", "workspace-extra"].forEach((id) => {
          document.getElementById(id).value = "";
        });
      }

      function copyReviewPackage() {
        const payload = `项目：binance-ai-trader
当前目标：分析 Testnet dry-run / Shadow Mode 下的策略表现，并给出小步优化建议。

安全边界：
1. 不允许绕过 RiskEngine。
2. 不允许启用 Live。
3. 不允许 GPT 直接下单。
4. 不允许修改 OrderManager 唯一订单入口。
5. 不允许新增 Futures、Margin、Leverage。
6. 不允许为了提高交易数量而关闭 DataQualityGate。
7. 所有建议必须先经过 backtest / shadow 验证。

请基于以下材料判断：
1. 当前主要问题属于哪一层：
   - 数据质量
   - 本地策略
   - AI 审查
   - 风控
   - Shadow 评价
   - 样本不足
   - 执行链路
2. 应该优先修改哪些文件。
3. 哪些地方绝对不能改。
4. 给出一个小步 Codex 修改提示词。
5. 给出修改后的验证命令。

【Shadow Report】
${document.getElementById("workspace-shadow").value}

【AI Reviews】
${document.getElementById("workspace-ai").value}

【Risk Decisions】
${document.getElementById("workspace-risk").value}

【DataQuality】
${JSON.stringify(api.dataQuality.data || {}, null, 2)}

【Audit】
${JSON.stringify(api.auditLatest.data || {}, null, 2)}

【用户补充问题】
${document.getElementById("workspace-extra").value}
`;
        return copyToClipboard("GPT Review Package", payload);
      }

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
