from __future__ import annotations

# ruff: noqa: E501


def dashboard_html() -> str:
    """Return the local Dashboard V2 HTML."""

    return r"""
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Binance AI Trader 本地运维控制台</title>
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
            <p class="text-xs font-semibold uppercase tracking-wide text-emerald-700">本地 Testnet / Dry-run / Shadow Mode 控制台</p>
            <h1 class="mt-1 text-2xl font-semibold tracking-tight">Binance AI Trader 本地运维控制台</h1>
            <p class="mt-2 max-w-5xl text-sm text-slate-600">
              Dashboard V2 是本地控制与复盘页面，用于观察 Testnet-first 运行状态、数据质量、StrategyPlanner/SignalReviewer 输出、RiskEngine 决策、订单记录、Shadow Mode、系统审计、readiness 和 OpenAI 用量。
            </p>
            <p class="mt-2 text-xs font-bold text-red-700">
              安全边界：没有真实下单按钮，没有 Live 开关，没有关闭 dry-run 按钮，没有开启 order execution 按钮，没有自动调用 Codex。
            </p>
          </div>
          <div class="flex flex-wrap gap-2">
            <button class="btn-primary" onclick="refreshAll()">刷新全部</button>
            <button class="btn-safe" onclick="postAction('启动 Dry Run','/runtime/testnet/start-dry-run')">启动 Dry Run</button>
            <button class="btn-muted" onclick="postAction('停止 Dry Run','/runtime/testnet/stop-dry-run')">停止 Dry Run</button>
            <button class="btn-muted" onclick="postAction('运行数据质量检查','/runtime/data-quality/check')">运行数据质量检查</button>
            <button class="btn-muted" onclick="postAction('运行 Shadow 评估','/runtime/shadow/evaluate')">运行 Shadow 评估</button>
            <button class="btn-muted" onclick="postAction('运行系统审计','/runtime/audits/run')">运行系统审计</button>
            <button class="btn-warn" onclick="postAction('打开熔断开关','/control/kill-switch/on')">熔断 ON</button>
            <button class="btn-danger" onclick="postAction('关闭熔断开关','/control/kill-switch/off','关闭 runtime kill switch 会解除数据库层熔断。请仅在确认 dry-run/testnet 安全状态后继续。确定关闭？')">熔断 OFF</button>
          </div>
        </div>
        <div class="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          熔断 OFF 警告：关闭 runtime kill switch 只会解除数据库层熔断。请先确认 dry-run/testnet 安全状态。
        </div>
        <div class="mt-4 flex flex-wrap items-center gap-3 text-xs text-slate-500">
          <span>页面最后刷新：<strong id="page-last-refresh">-</strong></span>
          <span id="action-result" class="rounded-md bg-slate-100 px-2 py-1 text-slate-700">暂无操作。</span>
        </div>
      </header>

      <nav class="sticky top-0 z-20 mb-5 rounded-lg border border-slate-200 bg-white/95 p-3 shadow-sm backdrop-blur">
        <div class="flex flex-wrap gap-2 text-xs font-bold">
          <a class="nav-chip" href="#overview">总览</a>
          <a class="nav-chip" href="#runtime">运行时</a>
          <a class="nav-chip" href="#data-quality">数据质量</a>
          <a class="nav-chip" href="#strategy">策略</a>
          <a class="nav-chip" href="#ai-review">AI 审查</a>
          <a class="nav-chip" href="#risk">风控</a>
          <a class="nav-chip" href="#orders">订单</a>
          <a class="nav-chip" href="#shadow">Shadow</a>
          <a class="nav-chip" href="#account">账户</a>
          <a class="nav-chip" href="#budget">预算</a>
          <a class="nav-chip" href="#audit">审计</a>
          <a class="nav-chip" href="#logs">日志</a>
          <a class="nav-chip" href="#strategy-params">策略参数</a>
          <a class="nav-chip" href="#risk-config">风控配置</a>
          <a class="nav-chip" href="#readiness">Readiness</a>
          <a class="nav-chip" href="#review-workspace">复盘工作台</a>
        </div>
      </nav>

      <section class="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8" id="safety-overview"></section>

      <div class="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <section id="runtime" class="panel">
          <div class="panel-head"><div><h2>运行时 Runtime</h2><p>Runtime 负责启动行情流、REST 轮询、策略生成、AI 审查、风控、Shadow 评估和审计任务。</p></div><span id="meta-health" class="module-meta">-</span></div>
          <div id="runtime-body" class="kv-grid"></div>
        </section>

        <section id="streams" class="panel">
          <div class="panel-head"><div><h2>行情流与网络 Streams &amp; Network</h2><p>用于查看 Binance Testnet 行情流、用户流和缓存的网络 readiness 状态。</p></div><span id="meta-status" class="module-meta">-</span></div>
          <div id="streams-body" class="space-y-3"></div>
        </section>

        <section id="data-quality" class="panel">
          <div class="panel-head"><div><h2>数据质量闸门 DataQualityGate</h2><p>DataQualityGate 是交易前的数据质量闸门。CRITICAL 状态会阻断 StrategyPlanner、SignalReview 和订单路径。</p></div><span id="meta-dataQuality" class="module-meta">-</span></div>
          <div id="data-quality-body" class="space-y-3"></div>
        </section>

        <section id="strategy" class="panel">
          <div class="panel-head"><div><h2>策略快照 Strategy Snapshot</h2><p>EMA Trend 策略只生成候选信号，不能直接下单。</p></div><span id="meta-snapshots" class="module-meta">-</span></div>
          <div id="strategy-body" class="space-y-3"></div>
        </section>

        <section id="ai-review" class="panel">
          <div class="panel-head"><div><h2>AI 信号审查 SignalReview</h2><p>SignalReviewer 只返回结构化 JSON，不能下单。即使 AI 通过，交易意图仍必须经过 RiskEngine。</p></div><span id="meta-aiReviews" class="module-meta">-</span></div>
          <div id="ai-body" class="space-y-3"></div>
        </section>

        <section id="risk" class="panel">
          <div class="panel-head"><div><h2>硬风控 RiskEngine</h2><p>RiskEngine 是硬风控层。所有交易意图必须先通过它，才可能进入 OrderManager。</p></div><span id="meta-riskDecisions" class="module-meta">-</span></div>
          <div id="risk-body" class="space-y-3"></div>
        </section>

        <section id="orders" class="panel">
          <div class="panel-head"><div><h2>订单管理 / 最近订单</h2><p>OrderManager 是唯一订单入口。dry-run 或 order execution 关闭时，不会提交 Binance new_order。</p></div><span id="meta-orders" class="module-meta">-</span></div>
          <div id="orders-body" class="space-y-3"></div>
        </section>

        <section id="shadow" class="panel">
          <div class="panel-head"><div><h2>影子模式 Shadow Mode</h2><p>Shadow Mode 记录“如果真实下单会怎样”，并计算模拟 PnL、MFE、MAE。它不真实交易。</p></div><span id="meta-shadowReport" class="module-meta">-</span></div>
          <div class="mb-3 flex flex-wrap gap-2">
            <button class="btn-muted" onclick="postAction('运行 Shadow 评估','/runtime/shadow/evaluate')">运行 Shadow 评估</button>
            <button class="btn-muted" onclick="copyJson('Shadow 报告', api.shadowReport.data)">复制 Shadow 报告</button>
            <button class="btn-muted" onclick="copyShadowPrompt()">复制 GPT Shadow 复盘提示词</button>
          </div>
          <div id="shadow-body" class="space-y-3"></div>
        </section>

        <section id="account" class="panel">
          <div class="panel-head"><div><h2>账户 / 仓位</h2><p>展示 Testnet 账户和仓位 readiness，以及当前是否使用 simulated_default 模拟数据。</p></div><span id="meta-configSafe" class="module-meta">-</span></div>
          <div id="account-body" class="space-y-3"></div>
        </section>

        <section id="budget" class="panel">
          <div class="panel-head"><div><h2>OpenAI 预算</h2><p>OpenAI Budget 用于控制 StrategyPlanner、SignalReviewer、SystemAuditor 和报告生成成本。</p></div><span id="meta-riskState" class="module-meta">-</span></div>
          <div id="budget-body" class="space-y-3"></div>
        </section>

        <section id="audit" class="panel">
          <div class="panel-head"><div><h2>系统审计 SystemAuditor</h2><p>SystemAuditor 只读。它不能改代码/配置，不能调用 Codex，不能下单。</p></div><span id="meta-auditLatest" class="module-meta">-</span></div>
          <div class="mb-3 flex flex-wrap gap-2">
            <button class="btn-muted" onclick="postAction('运行系统审计','/runtime/audits/run')">运行系统审计</button>
            <button class="btn-muted" onclick="copyJson('审计 JSON', api.auditLatest.data)">复制审计 JSON</button>
            <button class="btn-muted" onclick="copyAuditPrompt()">复制 GPT 审计复盘提示词</button>
          </div>
          <div id="audit-body" class="space-y-3"></div>
        </section>

        <section id="logs" class="panel">
          <div class="panel-head"><div><h2>日志 / Pipeline</h2><p>日志和 pipeline audit 用于定位链路卡在哪一步：snapshot、signal、AI、risk、order、stream、reconciliation 或 review。</p></div><span id="meta-logs" class="module-meta">-</span></div>
          <div id="logs-body" class="space-y-3"></div>
        </section>

        <section id="strategy-params" class="panel xl:col-span-2">
          <div class="panel-head">
            <div>
              <h2>策略参数设置中心</h2>
              <p>用于查看和编辑本地 EMA Trend 策略参数。保存只会写入 config/strategy.yaml，不会热加载、不会重启 runtime、不会触发订单。参数修改必须先经过 backtest 和 Shadow Mode 验证。</p>
            </div>
            <span id="meta-strategyConfig" class="module-meta">-</span>
          </div>
          <div class="mb-3 flex flex-wrap gap-2">
            <button class="btn-muted" onclick="loadStrategyConfig()">加载策略配置</button>
            <button class="btn-muted" onclick="validateStrategyDraft()">校验草稿</button>
            <button class="btn-primary" onclick="saveStrategyDraft()">保存策略配置</button>
            <button class="btn-muted" onclick="resetStrategyDraft()">恢复当前配置</button>
            <button class="btn-muted" onclick="copyStrategyOptimizationPackage()">复制策略优化提示词</button>
          </div>
          <div class="rounded-md border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900">
            保存确认：策略保存只会写入 config/strategy.yaml；不会热加载，不会重启 runtime，不会下单。保存后请运行回测和 Shadow Mode 验证。
          </div>
          <div class="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div class="space-y-3 lg:col-span-2" id="strategy-form"></div>
            <div class="space-y-3">
              <h3 class="text-sm font-bold text-slate-700">参数说明</h3>
              <ul id="strategy-guide" class="space-y-2 text-sm text-slate-600"></ul>
              <div id="strategy-validation" class="rounded-md bg-slate-50 p-3 text-sm text-slate-700">尚未运行校验。</div>
            </div>
          </div>
          <div id="strategy-diff" class="mt-4"></div>
        </section>

        <section id="risk-config" class="panel">
          <div class="panel-head"><div><h2>风控配置只读查看器</h2><p>这里只读展示 RiskEngine 配置。Dashboard V2 不允许编辑 risk.yaml，避免误放宽安全边界。</p></div><span id="meta-riskConfig" class="module-meta">-</span></div>
          <div id="risk-config-body" class="space-y-3"></div>
        </section>

        <section id="readiness" class="panel">
          <div class="panel-head"><div><h2>Testnet Readiness 检查</h2><p>检查 dry-run、order/test 和真实小额 Testnet order 的前置条件。它只检查，不下单。真实 lifecycle 仍必须通过 CLI 执行。</p></div><span id="meta-readinessLatest" class="module-meta">-</span></div>
          <div class="mb-3 flex flex-wrap gap-2">
            <button class="btn-primary" onclick="runReadinessCheck()">运行 Readiness 检查</button>
            <button class="btn-muted" onclick="copyReadinessPackage()">复制 Readiness 复盘包</button>
          </div>
          <div class="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            Dashboard 不提供真实下单按钮。即使 ready_for_real_testnet_order=true，也必须通过 CLI 和明确确认流程执行 testnet_order_lifecycle。
          </div>
          <div id="readiness-body" class="mt-3 space-y-3"></div>
        </section>

        <section id="openai-usage" class="panel xl:col-span-2">
          <div class="panel-head"><div><h2>OpenAI 用量报告</h2><p>展示 StrategyPlanner、SignalReviewer、SystemAuditor 等角色的 OpenAI API 用量和本地成本估算。不会返回 raw prompt 或 raw response。</p></div><span id="meta-openaiUsage" class="module-meta">手动</span></div>
          <div class="mb-3 flex flex-wrap gap-2">
            <button class="btn-muted" onclick="loadOpenAIUsage(1)">加载 1 天用量</button>
            <button class="btn-muted" onclick="loadOpenAIUsage(7)">加载 7 天用量</button>
            <button class="btn-muted" onclick="copyJson('OpenAI 用量 JSON', openaiUsageData)">复制用量 JSON</button>
            <button class="btn-muted" onclick="copyCostReviewPrompt()">复制成本复盘提示词</button>
          </div>
          <div id="openai-usage-body" class="space-y-3"></div>
        </section>

        <section id="frontend-snapshot" class="panel xl:col-span-2">
          <div class="panel-head"><div><h2>前端系统快照 / 导出</h2><p>导出当前页面内存中的状态用于复盘。不会写入 localStorage。</p></div><span class="module-meta">仅本地</span></div>
          <button class="btn-muted" onclick="copyFrontendSnapshot()">复制前端状态快照</button>
        </section>
      </div>

      <section id="review-workspace" class="panel mt-5">
        <div class="panel-head">
          <div>
            <h2>复盘工作台</h2>
            <p>把当前安全总览、runtime health、数据质量、Shadow、AI、风控、readiness、策略配置、OpenAI 用量和审计数据整理成可复制的 GPT 复盘包。</p>
          </div>
          <span class="module-meta">仅本地</span>
        </div>
        <div class="mb-3 flex flex-wrap gap-2">
          <button class="btn-primary" onclick="autoFillWorkspace()">从当前 Dashboard 自动填充</button>
          <button class="btn-muted" onclick="copyReviewPackage()">复制完整 GPT 复盘包</button>
          <button class="btn-muted" onclick="copyStrategyOptimizationPackage()">复制策略优化包</button>
          <button class="btn-muted" onclick="copyFrontendSnapshot()">复制前端状态快照</button>
          <button class="btn-muted" onclick="copyReadinessPackage()">复制 Readiness 复盘包</button>
          <button class="btn-muted" onclick="clearWorkspace()">清空工作台</button>
        </div>
        <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <label class="workspace-label"><span>Shadow 报告</span><button class="btn-mini" onclick="copyTextArea('workspace-shadow')">复制本段</button><textarea id="workspace-shadow" class="workspace-text"></textarea></label>
          <label class="workspace-label"><span>AI 审查记录</span><button class="btn-mini" onclick="copyTextArea('workspace-ai')">复制本段</button><textarea id="workspace-ai" class="workspace-text"></textarea></label>
          <label class="workspace-label"><span>风控决策</span><button class="btn-mini" onclick="copyTextArea('workspace-risk')">复制本段</button><textarea id="workspace-risk" class="workspace-text"></textarea></label>
          <label class="workspace-label"><span>综合优化请求</span><button class="btn-mini" onclick="copyTextArea('workspace-extra')">复制本段</button><textarea id="workspace-extra" class="workspace-text" placeholder="补充你的问题，例如：为什么 Shadow Mode 没有 WOULD_PLACE_ORDER？"></textarea></label>
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
      function listItems(items, renderer, emptyText = "暂无记录。") {
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
          ["运行状态", get(h, "state")],
          ["交易模式", get(h, "trading_mode", get(status, "trading_mode"))],
          ["Dry Run", get(h, "dry_run")],
          ["订单执行", get(h, "order_execution_enabled")],
          ["Live 已禁用", liveDisabled],
          ["熔断开关", kill ? "ON" : "OFF"],
          ["数据质量", get(dq, "overall_status", "UNKNOWN")],
          ["健康告警", get(h, "health_warning", false)],
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
          document.getElementById("data-quality-body").innerHTML = `<div class="rounded-md bg-amber-50 p-3 text-sm text-amber-800">暂无数据质量快照。请先启动 dry-run，或点击“运行数据质量检查”。</div>`;
          return;
        }
        const issues = get(dq, "issues", []);
        document.getElementById("data-quality-body").innerHTML = `<div class="kv-grid">${kv("overall_status", get(dq, "overall_status"))}${kv("action", get(dq, "action"))}${kv("safe_for_strategy_planner", get(dq, "safe_for_strategy_planner"))}${kv("safe_for_signal_review", get(dq, "safe_for_signal_review"))}${kv("safe_for_order", get(dq, "safe_for_order"))}${kv("safe_for_real_testnet_order", get(dq, "safe_for_real_testnet_order"))}${kv("issue_count", Array.isArray(issues) ? issues.length : 0)}${kv("reason_codes", (get(dq, "reason_codes", []) || []).join(", "))}</div>${listItems(issues, (issue) => `<div class="rounded-md border border-slate-200 p-2 text-sm">${badge(get(issue, "severity"))} <strong>${esc(get(issue, "title"))}</strong><div class="mt-1 text-slate-600">${esc(get(issue, "recommended_action"))}</div>${jsonBlock("证据", get(issue, "evidence", []))}</div>`, "暂无数据质量问题。")}${jsonBlock("DataQuality 原始 JSON", dq)}`;
      }
      function renderStrategy() {
        const snapshots = api.snapshots.data || {};
        const signals = api.signals.data || [];
        const keys = snapshots && typeof snapshots === "object" ? Object.keys(snapshots) : [];
        const snapshotHtml = keys.length === 0 ? `<div class="rounded-md bg-slate-50 p-3 text-sm text-slate-500">暂无行情快照。Runtime 可能未启动，或 K 线尚未加载。</div>` : keys.map((symbol) => {
          const snap = snapshots[symbol] || {};
          return `<div class="rounded-md border border-slate-200 p-2"><div class="mb-2 flex items-center justify-between"><strong>${esc(symbol)}</strong>${badge(get(snap, "ws_health", "UNKNOWN"))}</div><div class="kv-grid">${kv("price", get(snap, "price"))}${kv("ema_fast", get(snap, "ema_fast_5m", get(snap, "ema_fast")))}${kv("ema_slow", get(snap, "ema_slow_5m", get(snap, "ema_slow")))}${kv("rsi", get(snap, "rsi14_5m", get(snap, "rsi")))}${kv("atr", get(snap, "atr14_5m", get(snap, "atr")))}${kv("volume_ratio", get(snap, "volume_ratio_5m", get(snap, "volume_ratio")))}${kv("data_delay_seconds", get(snap, "data_delay_seconds"))}</div></div>`;
        }).join("");
        document.getElementById("strategy-body").innerHTML = `${snapshotHtml}<h3 class="text-sm font-bold text-slate-700">最近策略信号</h3>${listItems(signals, (row) => `<div class="rounded-md border border-slate-200 p-2 text-sm"><strong>${esc(get(row, "symbol"))}</strong> ${badge(get(row, "side"))} confidence ${esc(get(row, "confidence"))}<div class="text-slate-600">${esc(get(row, "reason"))}</div></div>`, "暂无最近策略信号。")}`;
      }
      function reviewPayload(row) { return get(row, "review", get(row, "output_json", row)); }
      function renderAI() {
        const rows = api.aiReviews.data || [];
        const summary = { total: rows.length, schema_valid: 0, schema_invalid: 0, decisions: {} };
        rows.forEach((row) => { if (get(row, "schema_valid", false) === true) summary.schema_valid += 1; else summary.schema_invalid += 1; const decision = get(reviewPayload(row), "decision", get(row, "decision", "UNKNOWN")); summary.decisions[decision] = (summary.decisions[decision] || 0) + 1; });
        document.getElementById("ai-body").innerHTML = `<div class="kv-grid">${kv("审查总数", summary.total)}${kv("schema_valid", summary.schema_valid)}${kv("schema_invalid", summary.schema_invalid)}${kv("decision 分布", JSON.stringify(summary.decisions))}</div>${listItems(rows, (row, index) => { const review = reviewPayload(row); return `<div class="rounded-md border border-slate-200 p-3 text-sm"><div class="flex flex-wrap items-center justify-between gap-2"><strong>${esc(get(row, "symbol", get(review, "symbol")))}</strong><div class="flex flex-wrap gap-2">${badge(get(row, "schema_valid", "UNKNOWN"), `schema_valid=${get(row, "schema_valid", "UNKNOWN")}`)}${badge(get(review, "decision", get(row, "decision", "UNKNOWN")))}</div></div><div class="mt-2 kv-grid">${kv("actual_model", get(row, "actual_model", get(row, "model")))}${kv("active_strategy_plan_id", get(row, "active_strategy_plan_id"))}${kv("side", get(review, "side", get(row, "side")))}${kv("confidence", get(review, "confidence", get(row, "confidence")))}${kv("risk_level", get(review, "risk_level"))}${kv("market_regime", get(review, "market_regime"))}${kv("requires_human_review", get(review, "requires_human_review"))}</div><p class="mt-2 text-sm text-slate-700">${esc(get(review, "reason", get(row, "reason")))}</p>${jsonBlock("warnings", get(review, "warnings", []))}<div class="mt-2 flex flex-wrap gap-2"><button class="btn-mini" onclick='copyJson("AI 审查记录", api.aiReviews.data[${index}])'>复制 JSON</button><button class="btn-mini" onclick='copyAIReviewPrompt(${index})'>复制 GPT 审查提示词</button></div></div>`; }, "暂无 AI 审查记录。")}`;
      }
      function renderRisk() {
        const rows = api.riskDecisions.data || [];
        const riskState = api.riskState.data || {};
        const h = api.health.data || {};
        const counts = {};
        rows.forEach((row) => { const reason = get(row, "reason", "UNKNOWN"); counts[reason] = (counts[reason] || 0) + 1; });
        const top = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 8);
        document.getElementById("risk-body").innerHTML = `<div class="kv-grid">${kv("orders_last_minute", get(h, "risk_runtime_status.orders_last_minute"))}${kv("seen_client_order_id_count", get(h, "risk_runtime_status.seen_client_order_id_count"))}${kv("risk_engine_reused", get(h, "risk_runtime_status.risk_engine_reused"))}${kv("kill_switch_enabled_config", get(h, "risk_runtime_status.kill_switch_enabled_config", get(riskState, "configured.kill_switch_enabled")))}${kv("kill_switch_enabled_runtime", get(h, "risk_runtime_status.kill_switch_enabled_runtime", get(riskState, "kill_switch_enabled")))}</div><h3 class="text-sm font-bold text-slate-700">最近主要拒绝原因</h3>${listItems(top, ([reason, count]) => `<div class="rounded-md bg-slate-50 p-2 text-sm"><strong>${esc(count)}</strong> ${esc(reason)}</div>`, "暂无拒绝原因。")}${listItems(rows, (row) => `<div class="rounded-md border border-slate-200 p-2 text-sm">${badge(get(row, "approved") ? "APPROVED" : "REJECTED")} <strong>${esc(get(row, "symbol"))}</strong><div class="text-slate-600">${esc(get(row, "reason"))}</div>${jsonBlock("risk_state_json", get(row, "risk_state_json", row))}</div>`, "暂无风控决策。")}`;
      }
      function renderOrders() {
        const orders = api.orders.data || [];
        const h = api.health.data || {};
        const dryRun = get(h, "dry_run", true);
        const execution = get(h, "order_execution_enabled", false);
        const possible = dryRun === false && execution === true;
        document.getElementById("orders-body").innerHTML = `<div class="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm"><div>当前 dry_run = <strong>${esc(dryRun)}</strong></div><div>当前 order_execution_enabled = <strong>${esc(execution)}</strong></div><div>当前是否可能触发真实 Binance new_order = <strong>${possible ? "理论上可能，但本 Dashboard 不提供真实下单按钮" : "不会，当前状态不会提交真实 Binance order"}</strong></div></div>${listItems(orders, (row) => `<div class="rounded-md border border-slate-200 p-2 text-sm"><div class="flex flex-wrap justify-between gap-2"><strong>${esc(get(row, "client_order_id"))}</strong>${badge(get(row, "status"))}</div><div class="kv-grid mt-2">${kv("symbol", get(row, "symbol"))}${kv("side", get(row, "side"))}${kv("order_type", get(row, "order_type"))}${kv("price", get(row, "price"))}${kv("quantity", get(row, "quantity"))}${kv("trading_mode", get(row, "trading_mode"))}${kv("created_at", get(row, "created_at"))}</div></div>`, "暂无最近订单。")}`;
      }
      function renderShadow() {
        const report = api.shadowReport.data || {};
        const open = api.shadowOpen.data || [];
        const recent = api.shadowRecent.data || [];
        document.getElementById("shadow-body").innerHTML = `<div class="kv-grid">${kv("total_decisions", get(report, "total_decisions"))}${kv("WOULD_PLACE_ORDER", get(report, "would_place_order_count"))}${kv("AI_REJECTED", get(report, "ai_rejected_count"))}${kv("RISK_REJECTED", get(report, "risk_rejected_count"))}${kv("DATA_QUALITY_BLOCKED", get(report, "data_quality_blocked_count"))}${kv("simulated_total_pnl_usdt", get(report, "simulated_total_pnl_usdt"))}${kv("simulated_win_rate", get(report, "simulated_win_rate"))}${kv("simulated_avg_pnl_pct", get(report, "simulated_avg_pnl_pct"))}</div>${jsonBlock("最佳 Shadow 交易", get(report, "best_shadow_trade", {}))}${jsonBlock("最差 Shadow 交易", get(report, "worst_shadow_trade", {}))}${jsonBlock("主要拒绝原因", get(report, "top_rejection_reasons", []))}<h3 class="text-sm font-bold text-slate-700">未结束 Shadow 决策</h3>${listItems(open, (row) => `<div class="rounded-md border border-slate-200 p-2 text-sm"><strong>${esc(get(row, "shadow_id"))}</strong> ${badge(get(row, "status"))} ${badge(get(row, "decision_type"))}<div>${esc(get(row, "symbol"))} ${esc(get(row, "side"))}</div></div>`, "暂无未结束 Shadow 决策。")}<h3 class="text-sm font-bold text-slate-700">最近 Shadow 决策</h3>${listItems(recent, (row) => `<div class="rounded-md border border-slate-200 p-2 text-sm"><strong>${esc(get(row, "shadow_id"))}</strong> ${badge(get(row, "decision_type"))}<div class="text-slate-600">${esc(get(row, "reason"))}</div></div>`, "暂无最近 Shadow 决策。")}`;
      }
      function renderAccount() {
        const status = get(api.health.data || {}, "account_position_status", {});
        const accountSource = get(status, "account_source");
        const positions = get(status, "positions", []);
        const simulated = accountSource === "simulated_default" || (Array.isArray(positions) && positions.some((p) => get(p, "source") === "simulated_default"));
        document.getElementById("account-body").innerHTML = `${simulated ? `<div class="rounded-md bg-amber-50 p-3 text-sm font-bold text-amber-900">当前账户/仓位数据是 simulated_default，不可视为真实 Testnet 账户状态。</div>` : ""}<div class="kv-grid">${kv("account_status", get(status, "account_status"))}${kv("account_source", accountSource)}${kv("equity_usdt", get(status, "equity_usdt"))}${kv("available_usdt", get(status, "available_usdt"))}${kv("safe_for_real_order", get(status, "safe_for_real_order"))}${kv("latest_created_at", get(status, "latest_created_at"))}${kv("reason_codes", (get(status, "reason_codes", []) || []).join(", "))}</div>${jsonBlock("positions", positions)}`;
      }
      function renderBudget() {
        const budget = get(api.health.data || {}, "budget_status", {});
        document.getElementById("budget-body").innerHTML = `<div class="kv-grid">${kv("每日预算", get(budget, "daily_budget_usd"))}${kv("每月预算", get(budget, "monthly_budget_usd"))}${kv("今日成本", get(budget, "openai_today_cost_usd", get(budget, "estimated_today_cost_usd")))}${kv("本月成本", get(budget, "openai_month_cost_usd", get(budget, "estimated_month_cost_usd")))}${kv("策略调用", get(budget, "strategy_calls_today"))}${kv("信号调用", get(budget, "signal_calls_today"))}${kv("budget_guard_enabled", get(budget, "budget_guard_enabled"))}${kv("budget_blocked", get(budget, "budget_blocked"))}</div>${jsonBlock("预算原始 JSON", budget)}`;
      }
      function renderAudit() {
        const report = api.auditLatest.data || {};
        if (report.status === "NO_AUDIT_REPORT") { document.getElementById("audit-body").innerHTML = `<div class="rounded-md bg-slate-50 p-3 text-sm text-slate-500">暂无 SystemAuditor 报告。可点击“运行系统审计”。</div>`; return; }
        document.getElementById("audit-body").innerHTML = `<div class="kv-grid">${kv("latest_overall_status", get(report, "overall_status", get(report, "latest_overall_status")))}${kv("latest_highest_severity", get(report, "highest_severity", get(report, "latest_highest_severity")))}${kv("latest_issue_count", get(report, "issue_count", get(report, "latest_issue_count")))}${kv("latest_report_created_at", get(report, "created_at", get(report, "latest_report_created_at")))}</div><p class="rounded-md bg-slate-50 p-3 text-sm text-slate-700">${esc(get(report, "summary", get(report, "latest_summary")))}</p>${jsonBlock("issues", get(report, "issues", get(report, "raw_output_json_sanitized.issues", [])))}${jsonBlock("recommended_next_human_steps", get(report, "recommended_next_human_steps", []))}`;
      }
      function renderLogs() {
        const logs = api.logs.data || [];
        const audits = api.pipelineAudit.data || [];
        document.getElementById("logs-body").innerHTML = `<h3 class="text-sm font-bold text-slate-700">最近 runtime 日志</h3>${listItems(logs.slice(0, 100), (row) => `<div class="rounded-md border border-slate-200 p-2 text-xs">${esc(get(row, "event", get(row, "message", "runtime_log")))} ${badge(get(row, "level", get(row, "status", "INFO")))}${jsonBlock("raw", row)}</div>`, "暂无 runtime 日志。")}<h3 class="text-sm font-bold text-slate-700">Pipeline audit</h3>${listItems(audits.slice(0, 100), (row) => `<div class="rounded-md border border-slate-200 p-2 text-xs"><strong>${esc(get(row, "stage"))}</strong> ${badge(get(row, "status"))}<div>${esc(get(row, "error_message"))}</div>${jsonBlock("raw", row)}</div>`, "暂无 pipeline audit 记录。")}`;
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
          document.getElementById("strategy-form").innerHTML = `<div class="rounded-md bg-slate-50 p-3 text-sm text-slate-500">点击“加载策略配置”后即可编辑 EMA Trend 参数。</div>`;
          document.getElementById("strategy-guide").innerHTML = "";
          document.getElementById("strategy-diff").innerHTML = "";
          return;
        }
        document.getElementById("strategy-form").innerHTML = `<div class="grid grid-cols-1 gap-3 md:grid-cols-2">${field("enabled", "enabled", "checkbox")}${selectField("entry_timeframe", "entry_timeframe")}${selectField("trend_timeframe", "trend_timeframe")}${field("ema_fast", "ema_fast")}${field("ema_slow", "ema_slow")}${field("rsi_period", "rsi_period")}${field("rsi_min", "rsi_min", "number", "0.1")}${field("rsi_max", "rsi_max", "number", "0.1")}${field("atr_period", "atr_period")}${field("volume_ratio_min", "volume_ratio_min", "number", "0.01")}${field("take_profit_r_multiple", "take_profit_r_multiple", "number", "0.1")}${field("stop_loss_atr_multiple", "stop_loss_atr_multiple", "number", "0.1")}</div>${jsonBlock("当前配置", api.strategyConfig.data || {})}`;
        const descriptions = get(api.strategyConfig.data || {}, "parameter_descriptions", {});
        document.getElementById("strategy-guide").innerHTML = Object.entries(descriptions).map(([key, value]) => `<li class="rounded-md bg-slate-50 p-2"><strong>${esc(key)}:</strong> ${esc(value)}</li>`).join("");
        const diff = strategyValidation ? strategyValidation.diff : [];
        document.getElementById("strategy-diff").innerHTML = `${jsonBlock("校验 / diff 预览", strategyValidation || { message: "尚未运行校验。" })}${listItems(diff, (row) => `<div class="rounded-md border border-slate-200 p-2 text-sm"><strong>${esc(row.field)}</strong>: ${esc(row.old)} -> ${esc(row.new)}</div>`, "暂无 diff 预览。")}`;
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
          document.getElementById("strategy-validation").innerHTML = payload.valid ? `${badge("VALID")} 草稿校验通过。` : `${badge("INVALID")} ${esc((payload.errors || []).join("; "))}`;
          renderStrategyCenter();
        } catch (error) { document.getElementById("strategy-validation").innerHTML = `${badge("ERROR")} ${esc(error.message || error)}`; }
      }
      async function saveStrategyDraft() {
        if (!window.confirm("保存策略参数只会写入 config/strategy.yaml。它不会热加载、不会重启 runtime、不会下单。保存后请运行 backtest 和 Shadow Mode 验证。确认保存？")) return;
        try {
          const payload = await fetchJson("/config/strategy/save", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(collectStrategyDraft()) });
          strategyValidation = payload;
          document.getElementById("strategy-validation").innerHTML = payload.saved ? `${badge("SAVED")} 已保存 config/strategy.yaml。pending_restart=true。请停止 dry-run 并重启 FastAPI/runtime 后再期待配置生效。` : `${badge("INVALID")} ${esc((payload.errors || []).join("; "))}`;
          await fetchModule("strategyConfig");
        } catch (error) { document.getElementById("strategy-validation").innerHTML = `${badge("ERROR")} ${esc(error.message || error)}`; }
      }
      function resetStrategyDraft() { strategyDraft = clone(strategyCurrent); strategyValidation = null; renderStrategyCenter(); }

      function renderRiskConfig() {
        const payload = api.riskConfig.data || {};
        const config = get(payload, "config", {});
        const risk = get(config, "risk", {});
        const live = get(config, "live_trading", {});
        document.getElementById("risk-config-body").innerHTML = `<div class="rounded-md border border-red-200 bg-red-50 p-3 text-sm font-bold text-red-800">只读。Dashboard V2 不能编辑 risk.yaml。</div><div class="kv-grid">${["max_single_trade_risk_pct","max_daily_loss_pct","max_position_pct_per_symbol","max_total_position_pct","max_consecutive_losses","cooldown_minutes_per_symbol","block_on_ws_disconnect","block_on_ai_schema_error","block_on_data_delay_seconds","allow_market_orders","allow_limit_orders","kill_switch_enabled","max_orders_per_minute"].map((key) => kv(`risk.${key}`, get(risk, key))).join("")}${kv("live_trading.enabled", get(live, "enabled"))}${kv("live_trading.require_manual_enable", get(live, "require_manual_enable"))}${kv("live_trading.require_env_live_enabled", get(live, "require_env_live_enabled"))}</div>${jsonBlock("risk 原始 JSON", payload)}`;
      }
      async function runReadinessCheck() {
        document.getElementById("readiness-body").innerHTML = `<div class="rounded-md bg-blue-50 p-3 text-sm text-blue-700">正在运行 readiness 检查。此操作只检查，不下单。</div>`;
        try {
          readinessData = await fetchJson("/runtime/readiness/check", { method: "POST" });
          api.readinessLatest.data = readinessData;
          api.readinessLatest.last = new Date().toLocaleTimeString();
          renderReadiness();
        } catch (error) { document.getElementById("readiness-body").innerHTML = `<div class="rounded-md bg-red-50 p-3 text-sm text-red-700">${esc(error.message || error)}</div>`; }
      }
      function renderReadiness() {
        const r = readinessData || (api.readinessLatest.data && api.readinessLatest.data.status !== "NO_READINESS_CHECK_RUN" ? api.readinessLatest.data : null);
        if (!r) { document.getElementById("readiness-body").innerHTML = `<div class="rounded-md bg-slate-50 p-3 text-sm text-slate-500">尚未运行 readiness 检查。请点击“运行 Readiness 检查”。</div>`; return; }
        document.getElementById("readiness-body").innerHTML = `<div class="kv-grid">${["trading_mode","live_disabled","dry_run","order_execution_enabled","testnet_keys_present","testnet_rest_ok","testnet_user_stream_possible","signed_account_ok","signed_test_order_ok","exchange_filters_ok","account_state_status","position_state_status","data_quality_status","kill_switch_enabled","strategy_plan_status","ready_for_dry_run","ready_for_test_order_only","ready_for_real_testnet_order","ready_for_live"].map((key) => kv(key, get(r, key))).join("")}</div>${jsonBlock("阻断项 blockers", get(r, "blockers", []))}${jsonBlock("警告 warnings", get(r, "warnings", []))}${jsonBlock("readiness 原始 JSON", r)}`;
      }
      async function loadOpenAIUsage(days) {
        document.getElementById("openai-usage-body").innerHTML = `<div class="rounded-md bg-blue-50 p-3 text-sm text-blue-700">正在加载最近 ${days} 天 OpenAI 用量...</div>`;
        try { openaiUsageData = await fetchJson(`/runtime/openai-usage?days=${days}`); renderOpenAIUsage(); }
        catch (error) { document.getElementById("openai-usage-body").innerHTML = `<div class="rounded-md bg-red-50 p-3 text-sm text-red-700">${esc(error.message || error)}</div>`; }
      }
      function renderOpenAIUsage() {
        const usage = openaiUsageData || {};
        const summary = get(usage, "summary", {});
        document.getElementById("openai-usage-body").innerHTML = `<div class="kv-grid">${kv("天数", get(usage, "days"))}${kv("总估算成本", get(summary, "estimated_cost_usd"))}${kv("调用总数", get(summary, "total_calls"))}${kv("每日预算", get(usage, "daily_budget_usd"))}${kv("每月预算", get(usage, "monthly_budget_usd"))}${kv("状态分布", JSON.stringify(get(usage, "status_breakdown", {})))}</div>${jsonBlock("按 role 分组", get(summary, "by_role", {}))}${jsonBlock("按 model 分组", get(summary, "by_model", {}))}${jsonBlock("警告", get(usage, "warnings", []))}${jsonBlock("usage 原始 JSON", usage)}`;
      }

      function render() {
        renderMeta(); renderSafety(); renderRuntime(); renderStreams(); renderDataQuality(); renderStrategy(); renderAI(); renderRisk(); renderOrders(); renderShadow(); renderAccount(); renderBudget(); renderAudit(); renderLogs(); renderStrategyCenter(); renderRiskConfig(); renderReadiness(); renderOpenAIUsage();
      }

      async function copyToClipboard(label, text) {
        const payload = String(text ?? "");
        try {
          if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(payload);
          else { const area = document.createElement("textarea"); area.value = payload; area.style.position = "fixed"; area.style.left = "-9999px"; document.body.appendChild(area); area.focus(); area.select(); document.execCommand("copy"); document.body.removeChild(area); }
          setAction(`${label}: 已复制`, "green");
        } catch {
          const area = document.createElement("textarea"); area.value = payload; document.body.appendChild(area); area.focus(); area.select(); setAction(`${label}: 剪贴板不可用，已选中文本，请手动复制`, "blue");
        }
      }
      function copyJson(label, data) { return copyToClipboard(label, JSON.stringify(data ?? {}, null, 2)); }
      function copyAIReviewPrompt(index) { const row = (api.aiReviews.data || [])[index] || {}; return copyToClipboard("GPT AI 审查提示词", `请分析以下 SignalReviewer 记录：AI 审查是否过于保守？schema 是否稳定？上下文是否不足？请判断应该优先优化 prompt、context_builder 还是策略本身。\n\nJSON:\n${JSON.stringify(row, null, 2)}`); }
      function copyShadowPrompt() { return copyToClipboard("GPT Shadow 复盘提示词", `请基于以下 Shadow Report 分析当前策略问题：样本是否不足、策略是否不产生信号、AI 是否拒绝过多、RiskEngine 是否拒绝过多、DataQualityGate 是否阻断过多、WOULD_PLACE_ORDER 的模拟 PnL 是否支持继续观察或优化。请指出优先检查哪个模块和文件。\n\nJSON:\n${JSON.stringify(api.shadowReport.data || {}, null, 2)}`); }
      function copyAuditPrompt() { return copyToClipboard("GPT 审计复盘提示词", `请分析以下 SystemAuditor 报告，找出主要运行风险和安全边界风险，并给出有边界的后续修改建议。不要建议绕过任何安全闸门。\n\nJSON:\n${JSON.stringify(api.auditLatest.data || {}, null, 2)}`); }
      function copyCostReviewPrompt() { return copyToClipboard("GPT 成本复盘提示词", `请分析以下 OpenAI 用量报告：哪些 role/model 成本较高、是否有预算风险、如何在不切换到更贵模型的前提下降低成本。\n\nJSON:\n${JSON.stringify(openaiUsageData || {}, null, 2)}`); }
      function copyTextArea(id) { return copyToClipboard("工作台段落", document.getElementById(id).value); }
      function frontendSnapshot() { return { safety: api.health.data || {}, status: api.status.data || {}, data_quality: api.dataQuality.data || {}, shadow_report: api.shadowReport.data || {}, ai_reviews: api.aiReviews.data || [], risk_decisions: api.riskDecisions.data || [], readiness: readinessData || api.readinessLatest.data || {}, strategy_config: api.strategyConfig.data || {}, openai_usage: openaiUsageData || {}, audit: api.auditLatest.data || {} }; }
      function copyFrontendSnapshot() { return copyJson("Frontend State Snapshot", frontendSnapshot()); }
      function autoFillWorkspace() { document.getElementById("workspace-shadow").value = JSON.stringify(api.shadowReport.data || {}, null, 2); document.getElementById("workspace-ai").value = JSON.stringify(api.aiReviews.data || [], null, 2); document.getElementById("workspace-risk").value = JSON.stringify(api.riskDecisions.data || [], null, 2); document.getElementById("workspace-extra").value = JSON.stringify({ safety_overview: api.health.data || {}, readiness: readinessData || api.readinessLatest.data || {}, strategy_config: api.strategyConfig.data || {}, openai_usage: openaiUsageData || {}, data_quality: api.dataQuality.data || {}, audit: api.auditLatest.data || {} }, null, 2); }
      function clearWorkspace() { ["workspace-shadow", "workspace-ai", "workspace-risk", "workspace-extra"].forEach((id) => { document.getElementById(id).value = ""; }); }
      function reviewPackageTemplate(kind) {
        const extra = document.getElementById("workspace-extra").value;
        return `项目：binance-ai-trader
当前目标：分析 Testnet dry-run / Shadow Mode 下的策略表现，并给出小步、安全、可验证的优化建议。

安全边界：
1. 不允许绕过 RiskEngine。
2. 不允许启用 Live。
3. GPT 不能直接下单。
4. 不允许修改 OrderManager 唯一订单入口。
5. 不允许新增 Futures、Margin、Leverage。
6. 不允许为了增加交易数量而关闭 DataQualityGate。
7. 所有策略参数修改必须先 backtest，再 Shadow Mode 验证。

复盘类型：${kind}

请判断：
1. 当前主要问题属于数据质量、本地策略、AI 审查、风控、样本不足、Shadow 评价还是执行链路。
2. EMA 参数是否过保守或过激进。
3. 应该优先检查哪 1-2 个参数或文件。
4. 哪些地方绝对不能改。
5. 给出一个有边界的 Codex 修改提示词。
6. 给出修改后的验证命令。

【Strategy Config】
${JSON.stringify(api.strategyConfig.data || {}, null, 2)}

【Shadow Report】
${document.getElementById("workspace-shadow").value || JSON.stringify(api.shadowReport.data || {}, null, 2)}

【AI Reviews】
${document.getElementById("workspace-ai").value || JSON.stringify(api.aiReviews.data || [], null, 2)}

【Risk Decisions】
${document.getElementById("workspace-risk").value || JSON.stringify(api.riskDecisions.data || [], null, 2)}

【DataQuality】
${JSON.stringify(api.dataQuality.data || {}, null, 2)}

【Readiness】
${JSON.stringify(readinessData || api.readinessLatest.data || {}, null, 2)}

【OpenAI Usage】
${JSON.stringify(openaiUsageData || {}, null, 2)}

【Audit】
${JSON.stringify(api.auditLatest.data || {}, null, 2)}

【用户补充】
${extra}
`;
      }
      function copyReviewPackage() { return copyToClipboard("完整 GPT 复盘包", reviewPackageTemplate("完整 Dashboard 复盘")); }
      function copyStrategyOptimizationPackage() { return copyToClipboard("策略优化包", reviewPackageTemplate("策略参数优化")); }
      function copyReadinessPackage() { return copyToClipboard("Readiness 复盘包", `请复盘以下 Testnet readiness 报告。不要建议新增 Dashboard 真实下单按钮；真实 lifecycle 必须保持 CLI-only。\n\n${JSON.stringify(readinessData || api.readinessLatest.data || {}, null, 2)}`); }

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
