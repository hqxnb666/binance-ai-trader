from __future__ import annotations

# ruff: noqa: E501


def dashboard_html() -> str:
    """Return the local operations dashboard HTML."""

    return r"""
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Binance AI Trader 控制台</title>
    <style>
      :root {
        --bg: #f5f7fb;
        --card: #ffffff;
        --border: #e5e7eb;
        --text: #101827;
        --muted: #64748b;
        --green: #0f766e;
        --green-bg: #ecfdf5;
        --yellow: #a16207;
        --yellow-bg: #fffbeb;
        --red: #b91c1c;
        --red-bg: #fef2f2;
        --blue: #2563eb;
        --blue-bg: #eff6ff;
        --shadow: 0 10px 28px rgba(15, 23, 42, 0.07);
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        background: var(--bg);
        color: var(--text);
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }
      main { max-width: 1440px; margin: 0 auto; padding: 24px; }
      @media (max-width: 760px) { main { padding: 14px; } }
      .hero, .card, details.advanced {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 16px;
        box-shadow: var(--shadow);
      }
      .hero { padding: 22px; margin-bottom: 18px; }
      .card { padding: 18px; min-width: 0; }
      .grid { display: grid; gap: 16px; }
      .grid-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }
      .grid-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .grid-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      @media (max-width: 1180px) { .grid-4, .grid-3 { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
      @media (max-width: 760px) { .grid-4, .grid-3, .grid-2 { grid-template-columns: 1fr; } }
      h1 { margin: 0; font-size: 30px; letter-spacing: -0.02em; }
      h2 { margin: 0 0 8px; font-size: 18px; }
      h3 { margin: 14px 0 8px; font-size: 14px; color: var(--muted); }
      p { margin: 0; line-height: 1.6; color: var(--muted); }
      .top-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
      .tag-row, .actions, .mini-actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
      .tag-row { margin-top: 12px; }
      .section { margin-top: 16px; }
      .section-title { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin: 22px 0 10px; }
      .section-title h2 { margin: 0; }
      .badge {
        display: inline-flex; align-items: center; gap: 6px;
        border-radius: 999px; padding: 5px 10px; font-size: 12px; font-weight: 800;
        background: #f3f4f6; color: #374151; border: 1px solid #e5e7eb;
        white-space: nowrap;
      }
      .ok { background: var(--green-bg); color: var(--green); border-color: #99f6e4; }
      .warn { background: var(--yellow-bg); color: var(--yellow); border-color: #fde68a; }
      .bad { background: var(--red-bg); color: var(--red); border-color: #fecaca; }
      .info { background: var(--blue-bg); color: var(--blue); border-color: #bfdbfe; }
      button {
        border: 0; border-radius: 12px; padding: 10px 14px; font-weight: 800; cursor: pointer;
        background: #e5e7eb; color: #111827; transition: transform .08s ease, opacity .12s ease;
      }
      button:hover { transform: translateY(-1px); }
      button:disabled { opacity: .55; cursor: not-allowed; transform: none; }
      .btn-primary { background: var(--blue); color: white; }
      .btn-safe { background: var(--green); color: white; }
      .btn-danger { background: var(--red); color: white; }
      .btn-muted { background: #f8fafc; color: #1f2937; border: 1px solid var(--border); }
      .primary-action { min-height: 44px; font-size: 14px; }
      .control-card { border: 1px solid var(--border); border-radius: 16px; padding: 16px; background: linear-gradient(180deg, #ffffff, #fbfdff); }
      .metric { border: 1px solid var(--border); border-radius: 14px; padding: 14px; background: #fbfdff; min-width: 0; }
      .metric .label { color: var(--muted); font-size: 12px; font-weight: 800; text-transform: uppercase; letter-spacing: .04em; }
      .metric .value { margin-top: 6px; font-size: 18px; font-weight: 900; overflow-wrap: anywhere; }
      .list { display: grid; gap: 8px; margin-top: 10px; }
      .row { display: flex; justify-content: space-between; gap: 12px; padding: 8px 0; border-top: 1px solid #f1f5f9; align-items: flex-start; }
      .row:first-child { border-top: 0; }
      .row span { min-width: 0; overflow-wrap: anywhere; }
      .row strong { text-align: right; overflow-wrap: anywhere; }
      .small { font-size: 12px; color: var(--muted); }
      .notice { padding: 12px; border-radius: 14px; background: var(--blue-bg); border: 1px solid #bfdbfe; color: #1e40af; }
      .warning { background: var(--yellow-bg); border-color: #fde68a; color: #92400e; }
      .error { background: var(--red-bg); border-color: #fecaca; color: #991b1b; }
      .success { background: var(--green-bg); border-color: #99f6e4; color: #115e59; }
      .toast { margin-top: 12px; min-height: 44px; display: flex; align-items: center; gap: 10px; }
      .toast-dot { width: 10px; height: 10px; border-radius: 999px; background: var(--blue); flex: 0 0 auto; }
      .toast.success .toast-dot { background: var(--green); }
      .toast.error .toast-dot { background: var(--red); }
      .toast.warning .toast-dot { background: var(--yellow); }
      details.advanced { padding: 16px; margin-top: 18px; }
      details.advanced > summary { cursor: pointer; font-weight: 900; font-size: 16px; }
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
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <div class="top-row">
          <div>
            <h1>Binance AI Trader 控制台</h1>
            <p>Testnet / Dry-run 安全控制台。页面默认展示摘要和关键阻断原因，完整原始数据放在诊断包里复制给 GPT 复盘。</p>
            <p class="small">安全边界：没有真实下单按钮，没有 Live 开关，没有关闭 dry-run 按钮，没有开启 order execution 按钮。</p>
            <div class="tag-row" id="env-tags"></div>
          </div>
          <div class="small">最后刷新：<strong id="last-refresh">-</strong></div>
        </div>
        <div id="action-toast" class="toast notice"><span class="toast-dot"></span><span class="small">操作结果：</span><span id="action-result">等待操作。建议：启动 Dry Run → 一键运行检查 → 加载诊断包 → 复制 GPT 复盘包。</span></div>
      </section>

      <section class="grid grid-2 section">
        <div class="control-card">
          <h2>运行控制</h2>
          <p>启动/停止 Testnet dry-run。这里不会开启真实下单，也不会触发 Live。</p>
          <div class="actions">
            <button class="btn-safe runtime-action" onclick="postAction(this, '启动 Dry Run', '/runtime/testnet/start-dry-run')">启动 Dry Run</button>
            <button class="btn-muted runtime-action" onclick="postAction(this, '停止 Dry Run', '/runtime/testnet/stop-dry-run')">停止 Dry Run</button>
          </div>
          <div id="runtime-hint" class="small">正在读取运行状态...</div>
        </div>
        <div class="control-card">
          <h2>一键诊断中心</h2>
          <p>推荐流程：一键运行检查 → 加载完整诊断包 → 复制 GPT 完整复盘包。</p>
          <div class="actions">
            <button class="btn-primary primary-action" onclick="refreshAll(this)">一键刷新状态</button>
            <button class="btn-primary primary-action" onclick="runAllChecks(this)">一键运行检查</button>
            <button class="btn-primary primary-action" onclick="loadDiagnosticSnapshot(this)">加载完整诊断包</button>
            <button class="btn-safe primary-action" onclick="copyFullDiagnosticReviewPackage(this)">复制 GPT 完整复盘包</button>
          </div>
          <div class="mini-actions">
            <button class="btn-muted" onclick="copyDiagnosticSnapshot(this)">复制原始 Diagnostic JSON</button>
            <button class="btn-muted" onclick="copyMissingDataChecklist(this)">复制缺失数据清单</button>
          </div>
        </div>
      </section>

      <div class="section-title"><h2>安全总览</h2><span class="small">一眼判断当前是否安全、是否在运行、是否会真实下单。</span></div>
      <section class="grid grid-4" id="safety-overview"></section>

      <section class="section grid grid-2">
        <div class="card">
          <h2>当前结论</h2>
          <p>用诊断包、Shadow、StrategyPlan、DataQuality 汇总出的可读结论。</p>
          <div id="current-diagnosis" class="list"></div>
        </div>
        <div class="card">
          <h2>诊断包内容预览</h2>
          <p>复制诊断包时会包含这些数据。页面只展示摘要，不直接展开完整 JSON。</p>
          <div id="diagnostic-preview" class="list"></div>
        </div>
      </section>

      <div class="section-title"><h2>核心模块摘要</h2><span class="small">模块都保留，但每个默认只展示 Top 5 / 最近 5 条摘要。</span></div>
      <section class="grid grid-3">
        <div class="card"><h2>运行状态 Runtime</h2><p>主控负责行情流、REST 轮询、策略、AI、风控、Shadow 和审计。</p><div id="runtime-summary"></div></div>
        <div class="card"><h2>行情与网络 Streams</h2><p>判断 Binance Testnet 行情流、用户流和网络状态是否正常。</p><div id="streams-summary"></div></div>
        <div class="card"><h2>数据质量闸门 DataQualityGate</h2><p>判断当前数据是否可信，是否允许 AI 审查和订单路径继续。</p><div id="data-quality-summary"></div></div>
        <div class="card"><h2>策略快照 Strategy Snapshot</h2><p>EMA Trend 只生成候选信号，不直接下单。</p><div id="strategy-snapshot-summary"></div></div>
        <div class="card"><h2>AI 信号审查 SignalReview</h2><p>只输出结构化 JSON，不能下单。</p><div id="ai-summary"></div></div>
        <div class="card"><h2>风控引擎 RiskEngine</h2><p>硬风控层。所有交易意图必须经过它。</p><div id="risk-summary"></div></div>
        <div class="card"><h2>订单管理 OrderManager</h2><p>唯一订单入口。dry-run/order execution off 时不会提交 Binance new_order。</p><div id="orders-summary"></div></div>
        <div class="card"><h2>Shadow Mode</h2><p>记录“如果真的下单会怎样”，并计算模拟 PnL；不下单。</p><div id="shadow-summary"></div></div>
        <div class="card"><h2>账户与仓位</h2><p>查看 Testnet 账户状态、仓位状态和真实 Testnet 前置条件。</p><div id="account-summary"></div></div>
        <div class="card"><h2>OpenAI 成本预算</h2><p>控制 StrategyPlanner、SignalReviewer、SystemAuditor 等调用成本。</p><div id="budget-summary"></div></div>
        <div class="card"><h2>系统审计 SystemAuditor</h2><p>只读审计器，不能改代码、不能改配置、不能下单。</p><div id="audit-summary"></div></div>
        <div class="card"><h2>日志与链路</h2><p>定位 snapshot、signal、AI、risk、order、user stream、reconciliation 等链路。</p><div id="logs-summary"></div></div>
      </section>

      <details class="advanced">
        <summary>高级操作与配置（低频/谨慎使用）</summary>
        <div class="advanced-grid">
          <div>
            <h3>安全与检查</h3>
            <div class="actions">
              <button class="btn-danger" onclick="postAction(this, '打开熔断', '/control/kill-switch/on')">Kill Switch ON</button>
              <button class="btn-danger" onclick="postAction(this, '关闭熔断', '/control/kill-switch/off', '关闭 runtime kill switch 会解除数据库层熔断。仅在确认 dry-run/testnet 安全状态后使用。确认关闭？')">Kill Switch OFF</button>
              <button class="btn-muted" onclick="runDataQuality(this)">运行 DataQuality</button>
              <button class="btn-muted" onclick="runReadiness(this)">运行 Readiness</button>
              <button class="btn-muted" onclick="runShadowEvaluation(this)">运行 Shadow 评估</button>
              <button class="btn-muted" onclick="runSystemAudit(this)">运行系统审计</button>
              <button class="btn-muted" onclick="loadOpenAIUsage(this, 1)">加载 1 天 OpenAI 用量</button>
              <button class="btn-muted" onclick="loadOpenAIUsage(this, 7)">加载 7 天 OpenAI 用量</button>
            </div>
            <h3>复制工具</h3>
            <div class="actions">
              <button class="btn-muted" onclick="copyFrontendSnapshot(this)">复制前端状态快照</button>
              <button class="btn-muted" onclick="copyReadinessPackage(this)">复制 Readiness 复盘包</button>
              <button class="btn-muted" onclick="copyStrategyOptimizationPackage(this)">复制策略优化包</button>
            </div>
            <details>
              <summary>调试 JSON 预览（默认折叠，高度限制）</summary>
              <pre class="compact-json" id="debug-json">尚未加载完整诊断包。</pre>
            </details>
          </div>
          <div>
            <h3>策略参数设置中心</h3>
            <p>只写入 config/strategy.yaml；不热加载、不重启 runtime、不下单、不改 risk/live/order execution。保存后需要 backtest 和 Shadow 验证。</p>
            <div class="actions">
              <button class="btn-muted" onclick="loadStrategyConfig(this)">加载策略配置</button>
              <button class="btn-muted" onclick="validateStrategyDraft(this)">校验草稿</button>
              <button class="btn-primary" onclick="saveStrategyDraft(this)">保存策略配置</button>
              <button class="btn-muted" onclick="resetStrategyDraft()">重置草稿</button>
            </div>
            <div id="strategy-form" class="form-grid"></div>
            <div id="strategy-validation" class="small">尚未运行校验。</div>
          </div>
        </div>
      </details>

      <section class="card section">
        <h2>复盘工作台</h2>
        <p>自动汇总当前 Dashboard 已加载的数据，生成可复制给 GPT 的复盘包。</p>
        <div class="actions">
          <button class="btn-muted" onclick="autoFillWorkspace()">从当前页面自动填充</button>
          <button class="btn-primary" onclick="copyReviewPackage(this)">复制完整复盘包</button>
          <button class="btn-muted" onclick="copyStrategyOptimizationPackage(this)">复制策略优化包</button>
          <button class="btn-muted" onclick="clearWorkspace()">清空工作台</button>
        </div>
        <div class="grid grid-2">
          <label class="small"><strong>Shadow Report</strong><textarea id="workspace-shadow"></textarea></label>
          <label class="small"><strong>AI Reviews</strong><textarea id="workspace-ai"></textarea></label>
          <label class="small"><strong>Risk Decisions</strong><textarea id="workspace-risk"></textarea></label>
          <label class="small"><strong>综合优化请求 / 用户补充问题</strong><textarea id="workspace-extra"></textarea></label>
        </div>
      </section>
    </main>

    <script>
      const api = {
        summary: mod('/runtime/dashboard-summary'),
        health: mod('/runtime/health'),
        snapshots: mod('/runtime/last-snapshots'),
        aiReviews: mod('/runtime/last-ai-reviews'),
        riskDecisions: mod('/runtime/last-risk-decisions'),
        dataQuality: mod('/runtime/data-quality/latest'),
        shadowReport: mod('/runtime/shadow/report'),
        shadowRecent: mod('/runtime/shadow/recent'),
        shadowOpen: mod('/runtime/shadow/open'),
        auditLatest: mod('/runtime/audits/latest'),
        orders: mod('/orders/recent'),
        signals: mod('/signals/recent'),
        logs: mod('/runtime/logs/recent'),
        strategyConfig: mod('/config/strategy'),
        riskConfig: mod('/config/risk'),
        readinessLatest: mod('/runtime/readiness/latest'),
        diagnostic: mod('/runtime/diagnostic-snapshot'),
      };
      let diagnosticSnapshot = null;
      let readinessData = null;
      let openaiUsageData = null;
      let strategyDraft = null;
      let strategyCurrent = null;

      function mod(url) { return { url, data: null, error: null, loading: false, last: null }; }
      function get(obj, path, fallback = '—') {
        try {
          const value = String(path).split('.').reduce((acc, key) => acc == null ? undefined : acc[key], obj);
          return value == null || value === '' ? fallback : value;
        } catch { return fallback; }
      }
      function asArray(value) { return Array.isArray(value) ? value : []; }
      function esc(value) {
        return String(value ?? '—').replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
      }
      function badge(value, label) {
        const text = String(label ?? value ?? 'UNKNOWN');
        const upper = String(value ?? '').toUpperCase();
        let cls = 'badge';
        if (['TRUE', 'OK', 'SAFE', 'RUNNING', 'TESTNET', 'SUCCESS', 'APPROVED'].includes(upper)) cls += ' ok';
        else if (upper === 'FALSE' && /live|order execution|真实下单/i.test(text)) cls += ' ok';
        else if (['WATCH', 'WARNING', 'WARN', 'DEGRADED', 'UNKNOWN', 'STOPPED'].includes(upper)) cls += ' warn';
        else if (['ERROR', 'CRITICAL', 'FAILED', 'BLOCKED', 'LIVE'].includes(upper)) cls += ' bad';
        else cls += ' info';
        return `<span class="${cls}">${esc(text)}</span>`;
      }
      function metric(label, value, state) {
        return `<div class="metric"><div class="label">${esc(label)}</div><div class="value">${badge(state ?? value, value)}</div></div>`;
      }
      function row(label, value) { return `<div class="row"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`; }
      function list(items, renderer, empty = '暂无数据。') {
        const rows = asArray(items).slice(0, 5);
        if (!rows.length) return `<p class="small">${esc(empty)}</p>`;
        return `<div class="list">${rows.map(renderer).join('')}</div>`;
      }
      function setAction(text, type = 'info') {
        const host = document.getElementById('action-toast');
        host.className = `toast notice ${type}`;
        document.getElementById('action-result').textContent = text;
      }
      function setButtonBusy(btn, busy, label) {
        if (!btn) return;
        if (busy) {
          btn.dataset.oldText = btn.textContent;
          btn.textContent = label || '处理中...';
          btn.disabled = true;
        } else {
          btn.textContent = btn.dataset.oldText || btn.textContent;
          btn.disabled = false;
        }
      }
      async function fetchJson(url, options = {}) {
        const res = await fetch(url, { cache: 'no-store', ...options });
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
          if (name === 'strategyConfig') applyStrategyConfig(item.data);
        } catch (error) {
          item.error = error.message || String(error);
        } finally {
          item.loading = false;
        }
      }
      async function refreshAll(btn) {
        setButtonBusy(btn, true, '刷新中...');
        setAction('正在刷新 Dashboard 摘要...', 'info');
        const names = ['summary', 'health', 'snapshots', 'aiReviews', 'riskDecisions', 'dataQuality', 'shadowReport', 'shadowRecent', 'shadowOpen', 'auditLatest', 'orders', 'signals', 'logs', 'strategyConfig', 'riskConfig', 'readinessLatest'];
        await Promise.all(names.map(fetchModule));
        if (api.readinessLatest.data && api.readinessLatest.data.status !== 'NO_READINESS_CHECK_RUN') readinessData = api.readinessLatest.data;
        document.getElementById('last-refresh').textContent = new Date().toLocaleTimeString();
        render();
        setAction('刷新完成。页面展示摘要，完整数据可通过诊断包复制。', 'success');
        setButtonBusy(btn, false);
      }
      async function postAction(btn, label, url, confirmText) {
        if (confirmText && !window.confirm(confirmText)) return;
        setButtonBusy(btn, true, '处理中...');
        setAction(`${label} 处理中...`, 'info');
        try {
          const data = await fetchJson(url, { method: 'POST' });
          setAction(`${label} 成功：${JSON.stringify(data).slice(0, 180)}`, 'success');
          await refreshAll();
        } catch (error) {
          setAction(`${label} 失败：${error.message || error}`, 'error');
        } finally {
          setButtonBusy(btn, false);
        }
      }
      async function runDataQuality(btn) { return postAction(btn, 'DataQuality 检查', '/runtime/data-quality/check'); }
      async function runShadowEvaluation(btn) { return postAction(btn, 'Shadow 评估', '/runtime/shadow/evaluate'); }
      async function runSystemAudit(btn) { return postAction(btn, '系统审计', '/runtime/audits/run'); }
      async function runReadiness(btn) {
        setButtonBusy(btn, true, '检查中...');
        setAction('Readiness 检查中...', 'info');
        try {
          readinessData = await fetchJson('/runtime/readiness/check', { method: 'POST' });
          api.readinessLatest.data = readinessData;
          setAction('Readiness 检查完成。', 'success');
          await refreshAll();
        } catch (error) { setAction(`Readiness 检查失败：${error.message || error}`, 'error'); }
        finally { setButtonBusy(btn, false); }
      }
      async function runAllChecks(btn) {
        setButtonBusy(btn, true, '检查中...');
        const steps = [
          ['DataQuality', () => fetchJson('/runtime/data-quality/check', { method: 'POST' })],
          ['Readiness', async () => { readinessData = await fetchJson('/runtime/readiness/check', { method: 'POST' }); return readinessData; }],
          ['Shadow', () => fetchJson('/runtime/shadow/evaluate', { method: 'POST' })],
          ['Audit', () => fetchJson('/runtime/audits/run', { method: 'POST' })],
        ];
        const results = [];
        setAction('一键检查开始：DataQuality → Readiness → Shadow → Audit。', 'info');
        for (const [name, fn] of steps) {
          try { await fn(); results.push(`${name}: 成功`); setAction(`${name} 完成，继续下一步...`, 'info'); }
          catch (error) { results.push(`${name}: 失败 ${String(error.message || error).slice(0, 120)}`); }
        }
        await refreshAll();
        setAction(`一键检查完成：${results.join('；')}`, results.some((x) => x.includes('失败')) ? 'warning' : 'success');
        setButtonBusy(btn, false);
      }
      async function loadDiagnosticSnapshot(btn) {
        setButtonBusy(btn, true, '加载中...');
        setAction('正在加载完整诊断包（只读，不下单，不改配置）...', 'info');
        try {
          diagnosticSnapshot = await fetchJson('/runtime/diagnostic-snapshot?shadow_limit=100&signal_limit=50&plan_limit=10');
          api.diagnostic.data = diagnosticSnapshot;
          document.getElementById('debug-json').textContent = JSON.stringify(diagnosticSnapshot, null, 2);
          await fetchModule('summary');
          render();
          setAction('完整诊断包已加载。页面只展示摘要，完整 JSON 已保存在内存中供复制。', 'success');
        } catch (error) { setAction(`加载完整诊断包失败：${error.message || error}`, 'error'); }
        finally { setButtonBusy(btn, false); }
      }

      function render() {
        const s = api.summary.data || {};
        renderHeader(s); renderSafety(s); renderDiagnosis(s); renderDiagnosticPreview(); renderRuntime(); renderStreams(); renderDataQuality(); renderStrategySnapshot(); renderAI(); renderRisk(); renderOrders(); renderShadow(s); renderAccount(); renderBudget(); renderAudit(s); renderLogs(); renderStrategyForm(); renderRuntimeHint(s);
      }
      function renderHeader(s) {
        const safety = s.safety || {};
        document.getElementById('env-tags').innerHTML = [
          badge(safety.trading_mode || 'testnet', `交易模式 ${safety.trading_mode || 'testnet'}`),
          badge(safety.dry_run === true ? 'OK' : 'CRITICAL', `dry-run ${safety.dry_run}`),
          badge(safety.order_execution_enabled === false ? 'OK' : 'CRITICAL', `真实下单 ${safety.order_execution_enabled}`),
          badge(safety.live_trading_enabled === false ? 'OK' : 'CRITICAL', `Live ${safety.live_trading_enabled}`),
        ].join('');
      }
      function renderRuntimeHint(s) {
        const safety = s.safety || {};
        const text = safety.runtime_state === 'RUNNING' ? 'Runtime 正在运行。可以运行检查并加载诊断包。' : 'Runtime 未运行。请先启动 Dry Run，否则行情快照、数据质量和 readiness 可能为空。';
        document.getElementById('runtime-hint').textContent = text;
      }
      function renderSafety(s) {
        const safety = s.safety || {};
        document.getElementById('safety-overview').innerHTML = [
          metric('Runtime', safety.runtime_state, safety.runtime_state),
          metric('交易模式', safety.trading_mode, safety.trading_mode),
          metric('Dry Run', safety.dry_run, safety.dry_run === true ? 'OK' : 'CRITICAL'),
          metric('真实下单', safety.order_execution_enabled, safety.order_execution_enabled === false ? 'OK' : 'CRITICAL'),
          metric('Live Trading', safety.live_trading_enabled, safety.live_trading_enabled === false ? 'OK' : 'CRITICAL'),
          metric('熔断开关', safety.kill_switch_enabled, safety.kill_switch_enabled ? 'WATCH' : 'OK'),
          metric('行情流', safety.market_stream_connected, safety.market_stream_connected ? 'OK' : 'UNKNOWN'),
          metric('数据质量', safety.data_quality || 'UNKNOWN', safety.data_quality || 'UNKNOWN'),
        ].join('');
      }
      function renderDiagnosis(s) {
        const items = asArray(get(s, 'diagnosis.human_summary', []));
        document.getElementById('current-diagnosis').innerHTML = list(items, (item) => `<div class="notice warning">${esc(item)}</div>`, '暂无诊断结论。请先启动 dry-run、运行检查或加载完整诊断包。');
      }
      function renderDiagnosticPreview() {
        const snap = diagnosticSnapshot || api.diagnostic.data || {};
        const available = Boolean(snap.schema_version);
        const sections = available ? [
          '运行状态', '安全配置', '策略配置', '风控配置', '当前策略计划', '最近策略计划', '最新行情指标', '最近策略信号', 'AI 审查记录', '风控决策记录', '数据质量', 'Shadow 汇总报告', 'Shadow 最近明细', '未关闭 Shadow 记录', 'Testnet 准备度', 'OpenAI 用量', '系统审计', '阻断归因'
        ] : ['尚未加载完整诊断包'];
        document.getElementById('diagnostic-preview').innerHTML = list(sections, (item) => `<div class="row"><span>${esc(item)}</span><strong>${available ? '包含' : '待加载'}</strong></div>`);
      }
      function renderRuntime() {
        const h = api.health.data || {};
        document.getElementById('runtime-summary').innerHTML = [
          row('状态', get(h, 'state')), row('交易模式', get(h, 'trading_mode')), row('交易对', asArray(get(h, 'symbols', [])).join(', ') || '—'), row('dry-run', get(h, 'dry_run')), row('AI 启用', get(h, 'ai_enabled')), row('真实下单开关', get(h, 'order_execution_enabled')), row('最后错误', get(h, 'last_error')),
        ].join('');
      }
      function renderStreams() {
        const h = api.health.data || {};
        document.getElementById('streams-summary').innerHTML = [
          row('行情流连接', get(h, 'market_stream_connected')), row('用户流连接', get(h, 'user_stream_connected')), row('最后 K 线时间', get(h, 'last_kline_time')), row('最后用户事件', get(h, 'last_user_event_time')), row('数据延迟秒数', get(h, 'data_delay_seconds')), row('网络 Binance Testnet', get(h, 'network_readiness.binance_testnet_rest')),
        ].join('');
      }
      function renderDataQuality() {
        const dq = api.dataQuality.data || get(api.summary.data, 'data_quality', {});
        const issues = asArray(get(dq, 'issues', []));
        document.getElementById('data-quality-summary').innerHTML = [
          row('总体状态', get(dq, 'overall_status', get(dq, 'status'))), row('动作', get(dq, 'action')), row('允许策略规划', get(dq, 'safe_for_strategy_planner')), row('允许信号审查', get(dq, 'safe_for_signal_review')), row('允许订单路径', get(dq, 'safe_for_order')), row('允许真实 Testnet', get(dq, 'safe_for_real_testnet_order')), '<h3>前 5 个问题</h3>', list(issues, (x) => `<div class="row"><span>${badge(get(x, 'severity'))} ${esc(get(x, 'title'))}</span><strong>${esc(get(x, 'category'))}</strong></div>`, '暂无数据质量问题或尚未生成快照。')
        ].join('');
      }
      function renderStrategySnapshot() {
        const snapshots = api.snapshots.data || {};
        const entries = Object.entries(snapshots).slice(0, 5);
        const signals = asArray(api.signals.data).slice(0, 5);
        document.getElementById('strategy-snapshot-summary').innerHTML = `${list(entries, ([symbol, snap]) => `<div class="row"><span>${esc(symbol)}<br><span class="small">RSI ${esc(get(snap, 'rsi14_5m'))} / ATR ${esc(get(snap, 'atr14_5m'))} / 量比 ${esc(get(snap, 'volume_ratio_5m'))}</span></span><strong>${esc(get(snap, 'price'))}</strong></div>`, '暂无行情快照。') }<h3>最近信号</h3>${list(signals, (x) => `<div class="row"><span>${esc(get(x, 'symbol'))} ${esc(get(x, 'side'))}<br><span class="small">${esc(get(x, 'reason'))}</span></span><strong>${esc(get(x, 'created_at'))}</strong></div>`, '暂无策略信号。')}`;
      }
      function renderAI() {
        const summary = api.summary.data || {};
        const ai = summary.ai_reviews || {};
        const reviews = asArray(api.aiReviews.data).slice(0, 5);
        document.getElementById('ai-summary').innerHTML = [
          row('进入风控', get(ai, 'approve_count', 0)), row('需要人工复查', get(ai, 'human_review_count', 0)), row('拒绝信号', get(ai, 'reject_count', 0)), '<h3>最近 5 条</h3>', list(reviews, (x) => `<div class="row"><span>${esc(get(x, 'symbol'))} / ${esc(get(x, 'decision'))}<br><span class="small">schema_valid=${esc(get(x, 'schema_valid'))} model=${esc(get(x, 'model'))}</span></span><strong>${esc(get(x, 'created_at'))}</strong></div>`, '暂无 AI 审查记录。')
        ].join('');
      }
      function renderRisk() {
        const summary = api.summary.data || {};
        const risk = summary.risk || {};
        const decisions = asArray(api.riskDecisions.data).slice(0, 5);
        const h = api.health.data || {};
        document.getElementById('risk-summary').innerHTML = [
          row('通过数量', get(risk, 'approved_count', 0)), row('拒绝数量', get(risk, 'rejected_count', 0)), row('最近一分钟订单数', get(h, 'risk_runtime_status.orders_last_minute')), row('RiskEngine 复用', get(h, 'risk_runtime_status.risk_engine_reused')), '<h3>Top 拒绝原因</h3>', list(get(risk, 'top_reasons', []), (x) => `<div class="row"><span>${esc(get(x, 'reason'))}</span><strong>${esc(get(x, 'count'))}</strong></div>`, '暂无拒绝原因。'), '<h3>最近 5 条</h3>', list(decisions, (x) => `<div class="row"><span>${esc(get(x, 'symbol'))} / ${esc(get(x, 'reason'))}</span><strong>${esc(get(x, 'approved'))}</strong></div>`, '暂无风控决策。')
        ].join('');
      }
      function renderOrders() {
        const orders = asArray(api.orders.data).slice(0, 5);
        const h = api.health.data || {};
        const realOrderPossible = h.dry_run === false && h.order_execution_enabled === true;
        document.getElementById('orders-summary').innerHTML = [
          row('当前 dry-run', get(h, 'dry_run')), row('真实下单开关', get(h, 'order_execution_enabled')), row('是否可能触发真实 Binance new_order', realOrderPossible ? '可能，但本 Dashboard 不提供真实下单按钮' : '否，当前不会提交真实 Binance order'), '<h3>最近 5 个订单</h3>', list(orders, (x) => `<div class="row"><span>${esc(get(x, 'client_order_id'))}<br><span class="small">${esc(get(x, 'symbol'))} ${esc(get(x, 'side'))} ${esc(get(x, 'order_type'))}</span></span><strong>${esc(get(x, 'status'))}</strong></div>`, '暂无订单记录。')
        ].join('');
      }
      function renderShadow(s) {
        const sh = s.shadow || api.shadowReport.data || {};
        document.getElementById('shadow-summary').innerHTML = [
          row('总决策数', get(sh, 'total_decisions', 0)), row('WOULD_PLACE_ORDER', get(sh, 'would_place_order_count', 0)), row('Risk 拒绝', get(sh, 'risk_rejected_count', 0)), row('AI 拒绝', get(sh, 'ai_rejected_count', 0)), row('DataQuality 阻断', get(sh, 'data_quality_blocked_count', 0)), row('模拟总 PnL', get(sh, 'simulated_total_pnl_usdt', 0)), row('模拟胜率', get(sh, 'simulated_win_rate')), '<h3>Top 5 拒绝原因</h3>', list(get(sh, 'top_rejection_reasons', []), (x) => `<div class="row"><span>${esc(get(x, 'reason'))}</span><strong>${esc(get(x, 'count'))}</strong></div>`, '暂无 Shadow 拒绝原因。')
        ].join('');
      }
      function renderAccount() {
        const h = api.health.data || {};
        const acct = get(h, 'account_position_status', {});
        const positions = asArray(get(acct, 'positions', []));
        document.getElementById('account-summary').innerHTML = [
          row('账户状态', get(acct, 'account_status')), row('数据来源', get(acct, 'account_source')), row('可用于真实订单', get(acct, 'safe_for_real_order')), row('更新时间', get(acct, 'latest_created_at')), row('原因代码', asArray(get(acct, 'reason_codes', [])).join(', ') || '—'), '<h3>仓位摘要</h3>', list(positions, (x) => `<div class="row"><span>${esc(get(x, 'symbol'))} / ${esc(get(x, 'source'))}</span><strong>${esc(get(x, 'position_pct'))}%</strong></div>`, '暂无仓位摘要。')
        ].join('');
      }
      function renderBudget() {
        const h = api.health.data || {};
        const b = get(h, 'budget_status', {});
        document.getElementById('budget-summary').innerHTML = [
          row('今日估算成本', get(b, 'openai_today_cost_usd')), row('本月估算成本', get(b, 'openai_month_cost_usd')), row('策略调用次数', get(b, 'strategy_calls_today')), row('信号审查次数', get(b, 'signal_calls_today')), row('预算保护启用', get(b, 'budget_guard_enabled')), row('预算阻断', get(b, 'budget_blocked')),
        ].join('');
      }
      function renderAudit(s) {
        const audit = s.audit || api.auditLatest.data || {};
        const issues = asArray(get(audit, 'report.issues', [])).slice(0, 3);
        document.getElementById('audit-summary').innerHTML = [
          row('总体状态', get(audit, 'overall_status')), row('最高严重级别', get(audit, 'highest_severity')), row('问题数量', get(audit, 'issue_count')), row('报告时间', get(audit, 'created_at')), `<p>${esc(get(audit, 'summary', '暂无审计摘要。'))}</p><h3>前 3 个问题</h3>`, list(issues, (x) => `<div class="row"><span>${badge(get(x, 'severity'))} ${esc(get(x, 'title'))}</span><strong>${esc(get(x, 'category'))}</strong></div>`, '暂无审计问题。')
        ].join('');
      }
      function renderLogs() {
        const logs = asArray(api.logs.data).slice(0, 5);
        document.getElementById('logs-summary').innerHTML = list(logs, (x) => `<div class="row"><span>${esc(get(x, 'event', get(x, 'stage', 'log')))}<br><span class="small">${esc(get(x, 'message', get(x, 'status', '')))}</span></span><strong>${esc(get(x, 'created_at', get(x, 'time', '')))}</strong></div>`, '暂无 runtime 日志。');
      }

      function applyStrategyConfig(payload) {
        if (!payload || !payload.config) return;
        strategyCurrent = JSON.parse(JSON.stringify(payload.config));
        if (!strategyDraft) strategyDraft = JSON.parse(JSON.stringify(payload.config));
      }
      async function loadStrategyConfig(btn) { setButtonBusy(btn, true, '加载中...'); await fetchModule('strategyConfig'); renderStrategyForm(); setAction('策略配置已加载。', 'success'); setButtonBusy(btn, false); }
      function renderStrategyForm() {
        const host = document.getElementById('strategy-form');
        if (!strategyDraft || !strategyDraft.ema_trend) { host.innerHTML = '<p class="small">点击“加载策略配置”后可编辑 EMA Trend 参数。</p>'; return; }
        const fields = ['enabled','entry_timeframe','trend_timeframe','ema_fast','ema_slow','rsi_period','rsi_min','rsi_max','atr_period','volume_ratio_min','take_profit_r_multiple','stop_loss_atr_multiple'];
        host.innerHTML = fields.map((field) => `<label class="small"><strong>${field}</strong><input id="sp-${field}" value="${esc(strategyDraft.ema_trend[field])}" /></label>`).join('');
      }
      function collectStrategyDraft() {
        const fields = ['enabled','entry_timeframe','trend_timeframe','ema_fast','ema_slow','rsi_period','rsi_min','rsi_max','atr_period','volume_ratio_min','take_profit_r_multiple','stop_loss_atr_multiple'];
        const ints = new Set(['ema_fast','ema_slow','rsi_period','atr_period']);
        const floats = new Set(['rsi_min','rsi_max','volume_ratio_min','take_profit_r_multiple','stop_loss_atr_multiple']);
        const ema = {};
        fields.forEach((field) => {
          const raw = document.getElementById(`sp-${field}`)?.value;
          if (field === 'enabled') ema[field] = String(raw).toLowerCase() === 'true';
          else if (ints.has(field)) ema[field] = parseInt(raw, 10);
          else if (floats.has(field)) ema[field] = parseFloat(raw);
          else ema[field] = raw;
        });
        return { ema_trend: ema };
      }
      async function validateStrategyDraft(btn) {
        setButtonBusy(btn, true, '校验中...');
        try {
          const result = await fetchJson('/config/strategy/validate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(collectStrategyDraft()) });
          document.getElementById('strategy-validation').textContent = result.valid ? '校验通过。' : `校验失败：${(result.errors || []).join('; ')}`;
          setAction(result.valid ? '策略草稿校验通过。' : '策略草稿校验失败，请查看高级区域提示。', result.valid ? 'success' : 'warning');
        } catch (error) { document.getElementById('strategy-validation').textContent = `校验失败：${error.message || error}`; setAction(`策略校验失败：${error.message || error}`, 'error'); }
        finally { setButtonBusy(btn, false); }
      }
      async function saveStrategyDraft(btn) {
        if (!window.confirm('保存策略参数只会写入 config/strategy.yaml，不会热加载、不会重启 runtime、不会下单。保存后请运行 backtest 和 Shadow Mode 验证。确认保存？')) return;
        setButtonBusy(btn, true, '保存中...');
        try {
          const result = await fetchJson('/config/strategy/save', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(collectStrategyDraft()) });
          document.getElementById('strategy-validation').textContent = result.saved ? '已保存。pending_restart=true，请重启后生效。' : `未保存：${(result.errors || []).join('; ')}`;
          setAction(result.saved ? '策略配置已保存。当前 runtime 仍使用启动时配置，请重启后生效。' : '策略配置未保存。', result.saved ? 'success' : 'warning');
        } catch (error) { document.getElementById('strategy-validation').textContent = `保存失败：${error.message || error}`; setAction(`策略保存失败：${error.message || error}`, 'error'); }
        finally { setButtonBusy(btn, false); }
      }
      function resetStrategyDraft() { strategyDraft = JSON.parse(JSON.stringify(strategyCurrent || {})); renderStrategyForm(); setAction('策略草稿已恢复为当前加载配置。', 'success'); }
      async function loadOpenAIUsage(btn, days) {
        setButtonBusy(btn, true, '加载中...');
        try { openaiUsageData = await fetchJson(`/runtime/openai-usage?days=${days}`); setAction(`OpenAI ${days} 天用量已加载，可复制前端快照或 GPT 包。`, 'success'); }
        catch (error) { setAction(`OpenAI 用量加载失败：${error.message || error}`, 'error'); }
        finally { setButtonBusy(btn, false); }
      }
      function unavailableSections(snapshot) {
        const missing = [];
        Object.entries(snapshot || {}).forEach(([key, value]) => {
          if (value && typeof value === 'object' && String(value.status || '').startsWith('NO_')) missing.push(`${key}: ${value.status}`);
          if (value && typeof value === 'object' && value.status === 'NOT_AVAILABLE') missing.push(`${key}: ${value.reason || 'NOT_AVAILABLE'}`);
        });
        return [...new Set(missing)];
      }
      async function copyToClipboard(btn, label, payload) {
        setButtonBusy(btn, true, '复制中...');
        const text = String(payload ?? '');
        try {
          if (navigator.clipboard) await navigator.clipboard.writeText(text);
          else throw new Error('clipboard unavailable');
          setAction(`${label} 已复制。`, 'success');
        } catch {
          const area = document.createElement('textarea'); area.value = text; document.body.appendChild(area); area.focus(); area.select(); setAction(`${label}：剪贴板不可用，已选中文本，请手动复制。`, 'warning');
        } finally { setButtonBusy(btn, false); }
      }
      function frontendSnapshot() { return { summary: api.summary.data || {}, health: api.health.data || {}, snapshots: api.snapshots.data || {}, ai_reviews: api.aiReviews.data || [], risk_decisions: api.riskDecisions.data || [], orders: api.orders.data || [], logs: api.logs.data || [], readiness: readinessData || api.readinessLatest.data || {}, openai_usage: openaiUsageData || {}, diagnostic_snapshot_loaded: Boolean(diagnosticSnapshot) }; }
      function copyFrontendSnapshot(btn) { return copyToClipboard(btn, '前端状态快照', JSON.stringify(frontendSnapshot(), null, 2)); }
      function copyDiagnosticSnapshot(btn) { return copyToClipboard(btn, 'Diagnostic JSON', JSON.stringify(diagnosticSnapshot || api.diagnostic.data || {}, null, 2)); }
      function copyMissingDataChecklist(btn) {
        const missing = unavailableSections(diagnosticSnapshot || api.diagnostic.data || {});
        return copyToClipboard(btn, '缺失数据清单', missing.length ? missing.map((x) => `- ${x}`).join('\n') : '- 当前没有检测到缺失项。');
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
      function copyFullDiagnosticReviewPackage(btn) { return copyToClipboard(btn, 'GPT 完整复盘包', diagnosticReviewPackage()); }
      function copyReadinessPackage(btn) { return copyToClipboard(btn, 'Readiness 复盘包', JSON.stringify(readinessData || api.readinessLatest.data || {}, null, 2)); }
      function copyStrategyOptimizationPackage(btn) { return copyToClipboard(btn, '策略优化包', diagnosticReviewPackage()); }
      function autoFillWorkspace() {
        document.getElementById('workspace-shadow').value = JSON.stringify(api.shadowReport.data || {}, null, 2);
        document.getElementById('workspace-ai').value = JSON.stringify(api.aiReviews.data || [], null, 2);
        document.getElementById('workspace-risk').value = JSON.stringify(api.riskDecisions.data || [], null, 2);
        document.getElementById('workspace-extra').value = JSON.stringify({ summary: api.summary.data || {}, data_quality: api.dataQuality.data || {}, audit: api.auditLatest.data || {}, readiness: readinessData || api.readinessLatest.data || {}, diagnostic_snapshot_loaded: Boolean(diagnosticSnapshot) }, null, 2);
        setAction('复盘工作台已自动填充。', 'success');
      }
      function reviewPackageTemplate(kind) {
        return `项目：binance-ai-trader\n当前目标：${kind}\n\n安全边界：不允许绕过 RiskEngine；不允许启用 Live；不允许 GPT 直接下单；不允许修改 OrderManager 唯一订单入口；不允许新增 Futures/Margin/Leverage；所有建议必须先 backtest / Shadow 验证。\n\n【Shadow Report】\n${document.getElementById('workspace-shadow').value}\n\n【AI Reviews】\n${document.getElementById('workspace-ai').value}\n\n【Risk Decisions】\n${document.getElementById('workspace-risk').value}\n\n【补充材料】\n${document.getElementById('workspace-extra').value}`;
      }
      function copyReviewPackage(btn) { return copyToClipboard(btn, '完整复盘包', reviewPackageTemplate('分析 dry-run / Shadow Mode 的策略表现并给出小步优化建议。')); }
      function clearWorkspace() { ['workspace-shadow', 'workspace-ai', 'workspace-risk', 'workspace-extra'].forEach((id) => { document.getElementById(id).value = ''; }); setAction('复盘工作台已清空。', 'success'); }

      refreshAll();
      setInterval(() => refreshAll(), 15000);
    </script>
  </body>
</html>
"""
