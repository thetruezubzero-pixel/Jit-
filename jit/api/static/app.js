const incomesEl = document.getElementById("incomes");
const deductionsEl = document.getElementById("deductions");
const documentsEl = document.getElementById("documents");
const form = document.getElementById("case-form");
const submitBtn = document.getElementById("submit-btn");
const resultsEl = document.getElementById("results");
const resultsGridEl = document.getElementById("results-grid");
const errorEl = document.getElementById("error");
const auditTrailEl = document.getElementById("audit-trail");

const currency = (value) =>
  typeof value === "number"
    ? value.toLocaleString("en-US", { style: "currency", currency: "USD" })
    : value;

const percent = (value) => (typeof value === "number" ? `${(value * 100).toFixed(2)}%` : value);

function addIncomeRow(kind = "w2", amount = "", source = "") {
  const row = document.createElement("div");
  row.className = "item-row";
  row.dataset.type = "income";
  row.innerHTML = `
    <label>Kind
      <select class="kind">
        <option value="w2">W-2 wages</option>
        <option value="1099">1099 / self-employment</option>
        <option value="capital_gains">Long-term capital gains</option>
        <option value="qualified_dividends">Qualified dividends</option>
        <option value="other">Other</option>
      </select>
    </label>
    <label>Amount
      <input type="number" class="amount" min="0" step="100" value="${amount}" />
    </label>
    <label>Source
      <input type="text" class="source" value="${source}" placeholder="Employer" />
    </label>
    <button type="button" class="remove" title="Remove">&times;</button>
  `;
  row.querySelector(".kind").value = kind;
  row.querySelector(".remove").addEventListener("click", () => row.remove());
  incomesEl.appendChild(row);
}

function addDeductionRow(name = "", amount = "", itemized = true) {
  const row = document.createElement("div");
  row.className = "item-row";
  row.dataset.type = "deduction";
  row.innerHTML = `
    <label>Name
      <input type="text" class="name" value="${name}" placeholder="mortgage_interest" />
    </label>
    <label>Amount
      <input type="number" class="amount" min="0" step="100" value="${amount}" />
    </label>
    <label>Itemized?
      <select class="itemized">
        <option value="true">Yes</option>
        <option value="false">No (above-the-line)</option>
      </select>
    </label>
    <button type="button" class="remove" title="Remove">&times;</button>
  `;
  row.querySelector(".itemized").value = String(itemized);
  row.querySelector(".remove").addEventListener("click", () => row.remove());
  deductionsEl.appendChild(row);
}

function addDocumentRow(title = "", text = "", citations = "") {
  const row = document.createElement("div");
  row.className = "item-row";
  row.dataset.type = "document";
  row.innerHTML = `
    <label style="flex: 1 1 100%">Title
      <input type="text" class="title" value="${title}" placeholder="Consulting Agreement" />
    </label>
    <label style="flex: 1 1 100%">Text
      <textarea class="text" placeholder="Paste the document text...">${text}</textarea>
    </label>
    <label style="flex: 1 1 100%">Citations (comma-separated)
      <input type="text" class="citations" value="${citations}" placeholder="26 U.S.C. § 61" />
    </label>
    <button type="button" class="remove" title="Remove">Remove document</button>
  `;
  row.querySelector(".remove").addEventListener("click", () => row.remove());
  documentsEl.appendChild(row);
}

document.querySelectorAll("[data-add]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const kind = btn.dataset.add;
    if (kind === "income") addIncomeRow();
    if (kind === "deduction") addDeductionRow();
    if (kind === "document") addDocumentRow();
  });
});

function collectIncomes() {
  return [...incomesEl.querySelectorAll(".item-row")]
    .map((row) => ({
      kind: row.querySelector(".kind").value,
      amount: parseFloat(row.querySelector(".amount").value) || 0,
      source: row.querySelector(".source").value || "unknown",
    }))
    .filter((i) => i.amount > 0);
}

function collectDeductions() {
  return [...deductionsEl.querySelectorAll(".item-row")]
    .map((row) => ({
      name: row.querySelector(".name").value || "deduction",
      amount: parseFloat(row.querySelector(".amount").value) || 0,
      itemized: row.querySelector(".itemized").value === "true",
    }))
    .filter((d) => d.amount > 0);
}

function collectDocuments() {
  return [...documentsEl.querySelectorAll(".item-row")]
    .map((row) => ({
      title: row.querySelector(".title").value || "Untitled",
      text: row.querySelector(".text").value,
      citations: row
        .querySelector(".citations")
        .value.split(",")
        .map((c) => c.trim())
        .filter(Boolean),
    }))
    .filter((d) => d.text.trim().length > 0);
}

function card(title, rows, extra = "") {
  const div = document.createElement("div");
  div.className = "card";
  div.innerHTML =
    `<h3>${title}</h3>` +
    rows.map(([label, value, big]) => `<div class="kv"><span>${label}</span><span${big ? ' class="big"' : ""}>${value}</span></div>`).join("") +
    extra;
  return div;
}

function tagList(items) {
  if (!items || !items.length) return "";
  return `<div class="tag-list">${items.map((i) => `<span class="tag">${i}</span>`).join("")}</div>`;
}

function renderResults(payload) {
  resultsGridEl.innerHTML = "";
  const { accounting, legal, algorithms } = payload.data;

  resultsGridEl.appendChild(
    card("Accounting", [
      ["Gross income", currency(accounting.gross_income)],
      ["Itemized deductions", currency(accounting.itemized_deductions)],
      ["Deduction recommendation", accounting.deduction_recommendation],
      ["Taxable income", currency(accounting.taxable_income)],
      ["Marginal rate", percent(accounting.marginal_rate)],
      ["Effective rate", percent(accounting.effective_rate)],
      ["AMT exposure", accounting.amt_exposure ? "Yes" : "No"],
      ["Quarterly estimate", currency(accounting.quarterly_estimate)],
      ["Total tax", currency(accounting.total_tax), true],
    ], tagList(accounting.recommendations))
  );

  resultsGridEl.appendChild(
    card("Legal", [
      ["Documents reviewed", legal.results?.[0]?.document_count ?? 0],
      ["Compliance status", legal.compliance_status],
      ["Risk score", legal.risk_score.toFixed(2), true],
    ], tagList(legal.citations))
  );

  resultsGridEl.appendChild(
    card("Algorithms", [
      ["Primary recommendation", algorithms.primary_recommendation, true],
      ["Total potential savings", currency(algorithms.total_potential_savings ?? 0)],
      ["Filing status guidance", algorithms.filing_status_guidance ?? "—"],
    ], tagList((algorithms.optimization_strategies || []).map((s) => `${s.title} (${currency(s.estimated_savings)})`)))
  );

  auditTrailEl.innerHTML = payload.audit_trail
    .map((e) => `<li><code>${e.topic}</code> — ${JSON.stringify(e.payload)}</li>`)
    .join("");

  resultsEl.classList.remove("hidden");
  errorEl.classList.add("hidden");
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  submitBtn.disabled = true;
  submitBtn.textContent = "Analyzing...";
  errorEl.classList.add("hidden");

  const body = {
    case_id: document.getElementById("case_id").value || "case-1",
    filing_status: document.getElementById("filing_status").value,
    state: document.getElementById("state").value || "CA",
    incomes: collectIncomes(),
    deductions: collectDeductions(),
    legal_documents: collectDocuments(),
  };

  try {
    const response = await fetch("/api/v1/platform/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(`Server returned ${response.status}: ${detail}`);
    }
    const payload = await response.json();
    renderResults(payload);
  } catch (err) {
    errorEl.textContent = err.message || String(err);
    errorEl.classList.remove("hidden");
    resultsEl.classList.remove("hidden");
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Analyze case";
  }
});

// Seed the form with a representative example.
addIncomeRow("w2", 120000, "Employer");
addIncomeRow("capital_gains", 4000, "Brokerage");
addDeductionRow("mortgage_interest", 10000, true);
addDeductionRow("charity", 4000, true);
addDocumentRow(
  "Consulting Agreement",
  "This agreement includes indemnification language and IRS reporting obligations.",
  "26 U.S.C. § 61"
);
