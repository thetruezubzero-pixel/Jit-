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
// Tabs
// ---------------------------------------------------------------------
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.querySelector(`.panel[data-panel="${btn.dataset.tab}"]`).classList.add("active");
  });
});

// ---------------------------------------------------------------------
// Dynamic repeatable rows (income / deductions / documents)
// ---------------------------------------------------------------------
const ROW_BUILDERS = {
  incomes: () => `
    <select class="f-kind">
      <option value="w2">W-2</option>
      <option value="1099">1099/SE</option>
      <option value="capital_gains">LTCG</option>
      <option value="qualified_dividends">Qual. dividends</option>
      <option value="other">Other</option>
    </select>
    <input type="number" class="f-amount" placeholder="Amount" value="0" />
    <input type="text" class="f-source" placeholder="Source" />
    <button type="button" class="remove">&times;</button>`,
  "plat-deductions": () => `
    <input type="text" class="f-name" placeholder="Name" value="deduction" />
    <input type="number" class="f-amount" placeholder="Amount" value="0" />
    <select class="f-itemized"><option value="true">Itemized</option><option value="false">Above-the-line</option></select>
    <button type="button" class="remove">&times;</button>`,
  deductions: () => `
    <select class="f-type">
      <option value="mortgage_interest">Mortgage interest</option>
      <option value="state_local_tax">State/local tax</option>
      <option value="charitable_cash">Charitable (cash)</option>
      <option value="charitable_noncash">Charitable (non-cash)</option>
      <option value="medical_expenses">Medical expenses</option>
      <option value="traditional_ira">Traditional IRA</option>
      <option value="student_loan_interest">Student loan interest</option>
      <option value="hsa_contribution">HSA contribution</option>
      <option value="self_employed_sep_ira">SEP-IRA (self-employed)</option>
    </select>
    <input type="number" class="f-amount" placeholder="Amount" value="0" />
    <button type="button" class="remove">&times;</button>`,
  documents: () => `
    <input type="text" class="f-title" placeholder="Title" value="Document" style="flex:1 1 100%" />
    <textarea class="f-text" rows="3" placeholder="Document text" style="flex:1 1 100%"></textarea>
    <input type="text" class="f-citations" placeholder="Citations (comma-separated)" style="flex:1 1 100%" />
    <button type="button" class="remove">Remove</button>`,
};

function addRow(container, kind) {
  const row = document.createElement("div");
  row.className = "item-row";
  row.innerHTML = ROW_BUILDERS[kind]();
  row.querySelector(".remove").addEventListener("click", () => row.remove());
  container.appendChild(row);
  return row;
}

document.querySelectorAll("[data-add]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const kind = btn.dataset.add;
    const container = document.querySelector(`[data-rows="${kind}"]`);
    addRow(container, kind);
  });
});

function collectRows(container, kind) {
  const rows = [...container.querySelectorAll(".item-row")];
  if (kind === "incomes") {
    return rows
      .map((r) => ({
        kind: r.querySelector(".f-kind").value,
        amount: parseFloat(r.querySelector(".f-amount").value) || 0,
        source: r.querySelector(".f-source").value || "unknown",
      }))
      .filter((i) => i.amount > 0);
  }
  if (kind === "plat-deductions") {
    return rows
      .map((r) => ({
        name: r.querySelector(".f-name").value || "deduction",
        amount: parseFloat(r.querySelector(".f-amount").value) || 0,
        itemized: r.querySelector(".f-itemized").value === "true",
      }))
      .filter((d) => d.amount > 0);
  }
  if (kind === "deductions") {
    return rows
      .map((r) => ({
        deduction_type: r.querySelector(".f-type").value,
        amount: parseFloat(r.querySelector(".f-amount").value) || 0,
      }))
      .filter((d) => d.amount > 0);
  }
  if (kind === "documents") {
    return rows
      .map((r) => ({
        title: r.querySelector(".f-title").value || "Untitled",
        text: r.querySelector(".f-text").value,
        citations: r
          .querySelector(".f-citations")
          .value.split(",")
          .map((c) => c.trim())
          .filter(Boolean),
      }))
      .filter((d) => d.text.trim().length > 0);
  }
  return [];
}

// Seed the "Full Case" tab with a representative example.
{
  const incomesEl = document.querySelector('[data-rows="incomes"]');
  addRow(incomesEl, "incomes");
  incomesEl.querySelector(".item-row:last-child .f-amount").value = 120000;
  incomesEl.querySelector(".item-row:last-child .f-source").value = "Employer";
  addRow(incomesEl, "incomes");
  const secondIncome = incomesEl.querySelector(".item-row:last-child");
  secondIncome.querySelector(".f-kind").value = "capital_gains";
  secondIncome.querySelector(".f-amount").value = 4000;
  secondIncome.querySelector(".f-source").value = "Brokerage";

  const deductionsEl = document.querySelector('[data-rows="plat-deductions"]');
  addRow(deductionsEl, "plat-deductions");
  deductionsEl.querySelector(".item-row:last-child .f-name").value = "mortgage_interest";
  deductionsEl.querySelector(".item-row:last-child .f-amount").value = 10000;
  addRow(deductionsEl, "plat-deductions");
  deductionsEl.querySelector(".item-row:last-child .f-name").value = "charity";
  deductionsEl.querySelector(".item-row:last-child .f-amount").value = 4000;

  const documentsEl = document.querySelector('[data-rows="documents"]');
  addRow(documentsEl, "documents");
  const doc = documentsEl.querySelector(".item-row:last-child");
  doc.querySelector(".f-title").value = "Consulting Agreement";
  doc.querySelector(".f-text").value =
    "This agreement includes indemnification language and IRS reporting obligations.";
  doc.querySelector(".f-citations").value = "26 U.S.C. § 61";

  const deductionItemsEl = document.querySelector('[data-rows="deductions"]');
  addRow(deductionItemsEl, "deductions");
  deductionItemsEl.querySelector(".item-row:last-child .f-amount").value = 12000;
  addRow(deductionItemsEl, "deductions");
  deductionItemsEl.querySelector(".item-row:last-child .f-type").value = "charitable_cash";
  deductionItemsEl.querySelector(".item-row:last-child .f-amount").value = 4000;
}

// ---------------------------------------------------------------------
// Form value collection (plain inputs -> payload)
// ---------------------------------------------------------------------
function collectPlainFields(form) {
  const payload = {};
  form.querySelectorAll(":scope > .row > label, :scope > label").forEach((label) => {
    const field = label.querySelector("input, select, textarea");
    if (!field || !field.name) return;
    if (field.type === "checkbox") {
      payload[field.name] = field.checked;
    } else if (field.type === "number") {
      payload[field.name] = field.value === "" ? 0 : parseFloat(field.value);
    } else {
      payload[field.name] = field.value;
    }
  });
  return payload;
}

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
      ${kv("Recommendation", d.recommendation, true)}
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
// Form submission wiring
// ---------------------------------------------------------------------
document.querySelectorAll("form[data-module]").forEach((form) => {
  const moduleName = form.dataset.module;
  const resultEl = document.querySelector(`[data-result="${moduleName}"]`);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submitBtn = form.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    const originalLabel = submitBtn.textContent;
    submitBtn.textContent = "Running…";

    try {
      const dispatch = await bootPromise;
      const payload = collectPlainFields(form);

      if (moduleName === "platform_analyze") {
        payload.incomes = collectRows(document.querySelector('[data-rows="incomes"]'), "incomes");
        payload.deductions = collectRows(
          document.querySelector('[data-rows="plat-deductions"]'),
          "plat-deductions"
        );
        payload.legal_documents = collectRows(
          document.querySelector('[data-rows="documents"]'),
          "documents"
        );
      }
      if (moduleName === "deduction_optimize") {
        payload.deductions = collectRows(
          document.querySelector('[data-rows="deductions"]'),
          "deductions"
        );
      }

      const resultJson = dispatch(moduleName, JSON.stringify(payload));
      const response = JSON.parse(resultJson);
      renderResult(moduleName, resultEl, response);
    } catch (err) {
      resultEl.innerHTML = `<div class="error-box">${err.message || err}</div>`;
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = originalLabel;
    }
  });
});
