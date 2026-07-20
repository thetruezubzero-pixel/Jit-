import { loadPyodide } from "./vendor/pyodide/pyodide.mjs";

// Caches the ~14MB Pyodide runtime + jit source after the first visit, so
// repeat visits (the common case on a phone) boot from cache instead of
// re-downloading everything.
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("sw.js").catch(() => {
    /* Non-fatal — the site still works without offline/repeat-visit caching. */
  });
}

const statusEl = document.getElementById("engine-status");

function setStatus(text, cls) {
  statusEl.textContent = text;
  statusEl.className = "engine-status" + (cls ? ` ${cls}` : "");
}

async function fetchText(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Failed to fetch ${path}: ${response.status}`);
  return response.text();
}

async function boot() {
  setStatus("Loading Pyodide runtime…");
  const pyodide = await loadPyodide({ indexURL: "vendor/pyodide/" });

  setStatus("Loading Jit engine source…");
  const base = pyodide.FS.cwd(); // e.g. "/home/pyodide" — relative writeFile paths are unreliable
  const manifest = JSON.parse(await fetchText("py/manifest.json"));
  for (const relPath of manifest) {
    const text = await fetchText(`py/${relPath}`);
    const dir = relPath.split("/").slice(0, -1).join("/");
    if (dir) pyodide.FS.mkdirTree(`${base}/${dir}`);
    pyodide.FS.writeFile(`${base}/${relPath}`, text);
  }

  const bridgeSource = await fetchText("py/bridge.py");
  pyodide.runPython(bridgeSource);
  const dispatch = pyodide.globals.get("dispatch");

  setStatus("Engine ready — running 100% in your browser", "ready");
  return dispatch;
}

const bootPromise = boot().catch((err) => {
  setStatus(`Failed to load engine: ${err.message}`, "error");
  throw err;
});

// ---------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------
const currency = (v) =>
  typeof v === "number" ? v.toLocaleString("en-US", { style: "currency", currency: "USD" }) : v;
const percent = (v) => (typeof v === "number" ? `${(v * 100).toFixed(2)}%` : v);

function kv(label, value, big = false) {
  return `<div class="kv"><span>${label}</span><span${big ? ' class="big"' : ""}>${value}</span></div>`;
}

function renderGeneric(data) {
  const rows = Object.entries(data)
    .filter(([, v]) => typeof v !== "object" || v === null)
    .map(([k, v]) => kv(k, typeof v === "number" ? (Math.abs(v) < 5 ? v : currency(v)) : String(v)));
  const lists = Object.entries(data).filter(([, v]) => Array.isArray(v) && v.length);
  const listHtml = lists
    .map(
      ([k, v]) =>
        `<div class="tag-list">${v.map((item) => `<span class="tag">${typeof item === "object" ? JSON.stringify(item) : item}</span>`).join("")}</div>`
    )
    .join("");
  return `<div class="card"><h3>Result</h3>${rows.join("")}${listHtml}</div>`;
}

const RENDERERS = {
  tax_calculate: (d) => `
    <div class="card"><h3>Tax Calculation</h3>
      ${kv("Gross income", currency(d.gross_income))}
      ${kv("AGI", currency(d.adjusted_gross_income))}
      ${kv("Taxable income", currency(d.taxable_income))}
      ${kv("Federal income tax", currency(d.federal_income_tax))}
      ${kv("Effective federal rate", percent(d.effective_federal_rate))}
      ${kv("Marginal federal rate", percent(d.marginal_federal_rate))}
      ${kv("Self-employment tax", currency(d.self_employment_tax))}
      ${kv("NIIT", currency(d.niit))}
      ${kv("State tax", currency(d.state_tax))}
      ${kv("Total tax", currency(d.total_tax), true)}
      ${kv("Effective total rate", percent(d.effective_total_rate))}
    </div>
    <div class="card"><h3>Recommendations</h3><div class="tag-list">${(d.recommendations || []).map((r) => `<span class="tag">${r}</span>`).join("") || "<em>None</em>"}</div></div>
  `,
  deduction_optimize: (d) => `
    <div class="card"><h3>Deduction Optimization</h3>
      ${kv("Standard deduction", currency(d.standard_deduction))}
      ${kv("Itemized deduction", currency(d.itemized_deduction))}
      ${kv("Recommended method", d.recommended_method)}
      ${kv("Recommended deduction", currency(d.recommended_deduction), true)}
      ${kv("Tax benefit difference", currency(d.tax_benefit_difference))}
      ${kv("Above-the-line total", currency(d.above_the_line_total))}
      ${kv("QBI deduction", currency(d.qbi_deduction))}
    </div>
    <div class="card"><h3>Opportunities</h3>${(d.opportunities || []).map((o) => `<div class="list-item">${o}</div>`).join("") || "<em>None</em>"}</div>
  `,
  amt_calculate: (d) => `
    <div class="card"><h3>AMT Result</h3>
      ${kv("Subject to AMT?", d.is_subject_to_amt ? "Yes" : "No", true)}
      ${kv("AMTI", currency(d.amti))}
      ${kv("AMT exemption", currency(d.amt_exemption))}
      ${kv("Tentative minimum tax", currency(d.tentative_minimum_tax))}
      ${kv("AMT owed", currency(d.amt_owed))}
      ${kv("Total tax (incl. AMT)", currency(d.total_tax))}
      ${kv("AMT credit generated", currency(d.amt_credit_generated))}
    </div>
    <div class="card"><h3>Preference / Adjustment Items</h3><div class="tag-list">${[...(d.preference_items || []), ...(d.adjustment_items || [])].map((i) => `<span class="tag">${i}</span>`).join("") || "<em>None</em>"}</div></div>
  `,
  quarterly_estimate: (d) => `
    <div class="card"><h3>Quarterly Estimate</h3>
      ${kv("Safe harbor amount", currency(d.safe_harbor_amount))}
      ${kv("Current-year safe harbor", currency(d.current_year_safe_harbor))}
      ${kv("Total required", currency(d.total_required), true)}
      ${kv("Total withholding", currency(d.total_withholding))}
      ${kv("Remaining to pay", currency(d.remaining_to_pay))}
      ${kv("Potential penalty", currency(d.potential_penalty))}
    </div>
    <div class="card"><h3>Quarterly Payments</h3>${(d.quarterly_payments || []).map((p) => `<div class="list-item">Q${p.quarter} (${p.due_date}): ${currency(p.required_payment)}</div>`).join("")}</div>
  `,
  document_analyze: (d) => `
    <div class="card"><h3>Document Analysis</h3>
      ${kv("Risk score", d.risk_score?.toFixed(2), true)}
      ${kv("Provisions found", (d.provisions || []).length)}
      ${kv("Citations found", (d.citations || []).length)}
      ${kv("Summary", d.summary)}
    </div>
    <div class="card"><h3>Risk Flags</h3><div class="tag-list">${(d.risk_flags || []).map((f) => `<span class="tag">${f}</span>`).join("") || "<em>None</em>"}</div></div>
    <div class="card"><h3>Keywords</h3><div class="tag-list">${(d.keywords || []).map((k) => `<span class="tag">${k}</span>`).join("") || "<em>None</em>"}</div></div>
  `,
  compliance_check: (d) => `
    <div class="card"><h3>Compliance</h3>
      ${kv("Overall risk", d.overall_risk, true)}
      ${kv("Compliance score", d.compliance_score?.toFixed(2))}
      ${kv("Compliant?", d.is_compliant ? "Yes" : "No")}
      ${kv("Summary", d.summary)}
    </div>
    <div class="card"><h3>Issues</h3>${(d.issues || []).map((i) => `<div class="list-item">[${i.risk_level}] ${i.title} — ${i.recommended_action}</div>`).join("") || "<em>None found</em>"}</div>
  `,
  filing_status_tree: (d) => `
    <div class="card"><h3>Filing Status Recommendation</h3>
      <p style="margin: 0 0 0.6rem;">${d.recommendation}</p>
      ${kv("Confidence", percent(d.confidence))}
    </div>
    <div class="card"><h3>Path Taken</h3><div class="tag-list">${(d.path_taken || []).map((p) => `<span class="tag">${p}</span>`).join("")}</div></div>
  `,
  deduction_method_tree: (d) => `
    <div class="card"><h3>Deduction Method Recommendation</h3>
      ${kv("Recommendation", d.recommendation, true)}
      ${kv("Confidence", percent(d.confidence))}
    </div>
  `,
  algorithm_optimize: (d) => `
    <div class="card"><h3>Optimization Summary</h3>
      ${kv("Current estimated tax", currency(d.current_estimated_tax))}
      ${kv("Optimized estimated tax", currency(d.optimized_estimated_tax))}
      ${kv("Total savings", currency(d.total_savings), true)}
      ${kv("Savings %", `${d.savings_percentage}%`)}
    </div>
    <div class="card"><h3>Strategies</h3>${(d.strategies || []).map((s) => `<div class="list-item"><strong>${s.title}</strong> — ${currency(s.estimated_savings)} (${s.implementation_complexity})<br/><span style="color:var(--muted)">${s.description}</span></div>`).join("") || "<em>None applicable</em>"}</div>
  `,
  risk_assess: (d) => `
    <div class="card"><h3>Risk Profile</h3>
      ${kv("Audit risk rating", d.audit_risk_rating, true)}
      ${kv("Overall risk rating", d.overall_risk_rating)}
      ${kv("Estimated audit probability", percent(d.estimated_audit_probability))}
      ${kv("Audit risk score", d.audit_risk_score?.toFixed(3))}
      ${kv("Penalty risk score", d.penalty_risk_score?.toFixed(3))}
    </div>
    <div class="card"><h3>Recommendations</h3>${(d.recommendations || []).map((r) => `<div class="list-item">${r}</div>`).join("")}</div>
  `,
  platform_analyze: (d) => {
    const { accounting, legal, algorithms } = d;
    return `
      <div class="card"><h3>Accounting</h3>
        ${kv("Gross income", currency(accounting.gross_income))}
        ${kv("Deduction recommendation", accounting.deduction_recommendation)}
        ${kv("Total tax", currency(accounting.total_tax), true)}
        ${kv("Quarterly estimate", currency(accounting.quarterly_estimate))}
        ${kv("AMT exposure", accounting.amt_exposure ? "Yes" : "No")}
      </div>
      <div class="card"><h3>Legal</h3>
        ${kv("Compliance status", legal.compliance_status)}
        ${kv("Risk score", legal.risk_score.toFixed(2), true)}
        <div class="tag-list">${(legal.citations || []).map((c) => `<span class="tag">${c}</span>`).join("")}</div>
      </div>
      <div class="card"><h3>Algorithms</h3>
        ${kv("Primary recommendation", algorithms.primary_recommendation, true)}
        ${kv("Total potential savings", currency(algorithms.total_potential_savings || 0))}
        ${kv("Filing status guidance", algorithms.filing_status_guidance || "—")}
      </div>
      <details><summary>Audit trail</summary><pre class="raw">${JSON.stringify(d.audit_trail, null, 2)}</pre></details>
    `;
  },
};

function renderResult(moduleName, resultEl, response) {
  if (!response.success) {
    resultEl.innerHTML = `<div class="error-box">${response.error}</div>`;
    return;
  }
  const renderer = RENDERERS[moduleName] || renderGeneric;
  try {
    resultEl.innerHTML = renderer(response.data);
  } catch (err) {
    resultEl.innerHTML =
      renderGeneric(response.data) +
      `<pre class="raw">${JSON.stringify(response.data, null, 2)}</pre>`;
  }
}

// ---------------------------------------------------------------------
// Chat: one free-text box routed to whichever engine(s) it matches
// ---------------------------------------------------------------------
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatLog = document.getElementById("chat-log");

function addChatBubble(role, html) {
  const bubble = document.createElement("div");
  bubble.className = `chat-msg ${role}`;
  bubble.innerHTML = html;
  chatLog.appendChild(bubble);
  chatLog.scrollTop = chatLog.scrollHeight;
  return bubble;
}

const INTENT_LABELS = {
  tax_calculate: "Tax Calculator",
  deduction_optimize: "Deductions",
  amt_calculate: "AMT",
  quarterly_estimate: "Quarterly",
  document_analyze: "Legal Document",
  compliance_check: "Compliance",
  filing_status_tree: "Filing Status",
  algorithm_optimize: "Optimizer",
  risk_assess: "Audit Risk",
  platform_analyze: "Full Case",
};

if (chatForm) {
  chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = chatInput.value.trim();
    if (!message) return;

    const sendBtn = chatForm.querySelector('button[type="submit"]');
    sendBtn.disabled = true;
    addChatBubble("user", message.replace(/</g, "&lt;"));
    chatInput.value = "";

    try {
      const dispatch = await bootPromise;
      const resultJson = dispatch("chat", JSON.stringify({ message }));
      const response = JSON.parse(resultJson);

      if (!response.success) {
        addChatBubble("assistant", `<div class="error-box">${response.error}</div>`);
        return;
      }

      const { intent, reply, result } = response.data;

      if (intent === "clarify") {
        // Just asking a question back — no engine ran yet, so there's no
        // result card to show, and "Routed to" would be misleading.
        addChatBubble("assistant", reply);
        return;
      }

      const label = INTENT_LABELS[intent] || intent;
      let cardHtml = "";
      try {
        cardHtml = (RENDERERS[intent] || renderGeneric)(result);
      } catch {
        /* If a specific renderer can't handle this shape, the reply text still stands alone. */
      }
      addChatBubble(
        "assistant",
        `<span class="intent-tag">Routed to: ${label}</span>${reply}${cardHtml}`
      );
    } catch (err) {
      addChatBubble("assistant", `<div class="error-box">${err.message || err}</div>`);
    } finally {
      sendBtn.disabled = false;
    }
  });
}

const chatResetBtn = document.getElementById("chat-reset");
if (chatResetBtn) {
  chatResetBtn.addEventListener("click", async () => {
    try {
      const dispatch = await bootPromise;
      dispatch("chat_reset", "{}");
    } catch {
      /* If the engine never finished booting, there's nothing to reset yet. */
    }
    chatLog.innerHTML = "";
  });
}
