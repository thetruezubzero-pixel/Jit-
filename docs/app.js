import { loadPyodide } from "./vendor/pyodide/pyodide.mjs";

// Caches the ~14MB Pyodide runtime + jit source after the first visit, so
// repeat visits (the common case on a phone) boot from cache instead of
// re-downloading everything.
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("sw.js").catch(() => {
    /* Non-fatal — the site still works without offline/repeat-visit caching. */
  });

  // Without this, a new deploy's service worker installs in the background
  // but a page already open (or reopened from cache) keeps being served by
  // the OLD worker until it's closed and reopened a second time — a shipped
  // fix can look like it never went out. Reload once, automatically, the
  // moment a new worker actually takes control.
  let reloadedForUpdate = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (reloadedForUpdate) return;
    reloadedForUpdate = true;
    window.location.reload();
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

// Persists chat's remembered context (income/filing status/etc.) and
// session-insights history across page reloads. Pyodide's Python
// interpreter is rebuilt from scratch on every visit, so without this,
// closing the tab would forget everything — this applies uniformly to
// every intent/domain, since bridge.py shares one context across all of
// them. Stored only in this browser, nothing is sent anywhere.
const CHAT_STATE_STORAGE = "jit_chat_state";

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

  try {
    const saved = localStorage.getItem(CHAT_STATE_STORAGE);
    if (saved) dispatch("chat_import_state", saved);
  } catch {
    /* Corrupt or missing saved state — just start fresh. */
  }

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

// ---------------------------------------------------------------------
// Optional AI assist (Google Gemini) — only used for questions the
// rule-based router genuinely can't classify. The API key is entered by
// the user and stored solely in this browser's localStorage; it's sent
// directly from this device to Google, never to any server of ours.
// ---------------------------------------------------------------------
const GEMINI_KEY_STORAGE = "jit_gemini_api_key";
const AI_ASSIST_STORAGE = "jit_ai_assist_enabled";
const GEMINI_MODEL = "gemini-2.0-flash";

const getGeminiKey = () => localStorage.getItem(GEMINI_KEY_STORAGE) || "";
const setGeminiKey = (key) =>
  key ? localStorage.setItem(GEMINI_KEY_STORAGE, key) : localStorage.removeItem(GEMINI_KEY_STORAGE);
const isAiAssistEnabled = () => localStorage.getItem(AI_ASSIST_STORAGE) === "1";
const setAiAssistEnabled = (enabled) => localStorage.setItem(AI_ASSIST_STORAGE, enabled ? "1" : "0");

async function askGemini(apiKey, message) {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${encodeURIComponent(apiKey)}`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      contents: [{ parts: [{ text: message }] }],
      generationConfig: { maxOutputTokens: 400 },
    }),
  });
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`Gemini request failed (${response.status}): ${text.slice(0, 200)}`);
  }
  const data = await response.json();
  const parts = data?.candidates?.[0]?.content?.parts || [];
  const text = parts.map((p) => p.text || "").join("").trim();
  return text || "(Gemini returned no text.)";
}

const aiAssistToggle = document.getElementById("ai-assist-toggle");
const geminiKeyInput = document.getElementById("gemini-key-input");
const geminiKeySave = document.getElementById("gemini-key-save");
const geminiKeyClear = document.getElementById("gemini-key-clear");

if (aiAssistToggle) {
  aiAssistToggle.checked = isAiAssistEnabled();
  aiAssistToggle.addEventListener("change", () => setAiAssistEnabled(aiAssistToggle.checked));
}
if (geminiKeyInput) {
  geminiKeyInput.value = getGeminiKey();
}
if (geminiKeySave) {
  geminiKeySave.addEventListener("click", () => {
    setGeminiKey(geminiKeyInput.value.trim());
  });
}
if (geminiKeyClear) {
  geminiKeyClear.addEventListener("click", () => {
    setGeminiKey("");
    geminiKeyInput.value = "";
    if (aiAssistToggle) {
      aiAssistToggle.checked = false;
      setAiAssistEnabled(false);
    }
  });
}

// ---------------------------------------------------------------------
// Session insights — rule-based pattern detection over this session's
// chat history (income variance, deduction ratio, unchecked self-employment
// income). Refreshed after every computed chat turn.
// ---------------------------------------------------------------------
const insightsPanel = document.getElementById("session-insights");

async function refreshSessionInsights() {
  if (!insightsPanel) return;
  try {
    const dispatch = await bootPromise;
    const response = JSON.parse(dispatch("session_insights", "{}"));
    if (!response.success) return;
    const { insights, attention_level } = response.data;
    // attention_level cross-references how many independent signals fired
    // at once into one summary level — reflected here as a border color
    // rather than making the user read every flag to gauge how urgent it is.
    insightsPanel.classList.remove("attention-mild", "attention-elevated");
    if (attention_level && attention_level !== "clear") {
      insightsPanel.classList.add(`attention-${attention_level}`);
    }
    insightsPanel.innerHTML = insights.length
      ? `<h3>Session insights</h3><ul>${insights.map((i) => `<li>${i.replace(/</g, "&lt;")}</li>`).join("")}</ul>`
      : "";
  } catch {
    /* Insights are a nice-to-have; a failure here shouldn't disrupt chat. */
  }
}

function persistChatState(dispatch) {
  try {
    const response = JSON.parse(dispatch("chat_export_state", "{}"));
    if (response.success) localStorage.setItem(CHAT_STATE_STORAGE, JSON.stringify(response.data));
  } catch {
    /* Persistence is a nice-to-have; a failure here shouldn't disrupt chat. */
  }
}

// ---------------------------------------------------------------------
// Compact/detailed layout toggle — applies to every rendered result card
// uniformly via one CSS class, regardless of which intent produced it.
// ---------------------------------------------------------------------
const COMPACT_LAYOUT_STORAGE = "jit_compact_layout";
const compactToggle = document.getElementById("compact-toggle");

function applyCompactLayout(enabled) {
  document.body.classList.toggle("compact", enabled);
}

if (compactToggle) {
  const savedCompact = localStorage.getItem(COMPACT_LAYOUT_STORAGE) === "1";
  compactToggle.checked = savedCompact;
  applyCompactLayout(savedCompact);
  compactToggle.addEventListener("change", () => {
    localStorage.setItem(COMPACT_LAYOUT_STORAGE, compactToggle.checked ? "1" : "0");
    applyCompactLayout(compactToggle.checked);
  });
}

// ---------------------------------------------------------------------
// Share/export — sends the visible conversation out through the phone's
// normal share sheet (Messages, Mail, Notes, etc.), with a clipboard/file
// fallback wherever the Web Share API isn't available.
// ---------------------------------------------------------------------
const chatShareBtn = document.getElementById("chat-share");

function getTranscriptText() {
  return Array.from(document.querySelectorAll("#chat-log .chat-msg"))
    .map((el) => `${el.classList.contains("user") ? "You" : "Jit"}: ${el.innerText.trim()}`)
    .join("\n\n");
}

async function shareTranscript() {
  const text = getTranscriptText();
  if (!text) return;

  if (navigator.share) {
    try {
      await navigator.share({ title: "Jit conversation", text });
      return;
    } catch {
      /* User cancelled, or share isn't actually usable here — fall through. */
    }
  }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      const original = chatShareBtn.textContent;
      chatShareBtn.textContent = "Copied!";
      setTimeout(() => {
        chatShareBtn.textContent = original;
      }, 1500);
      return;
    } catch {
      /* Clipboard access denied — fall through to a plain file download. */
    }
  }
  const blob = new Blob([text], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "jit-conversation.txt";
  link.click();
  URL.revokeObjectURL(url);
}

if (chatShareBtn) {
  chatShareBtn.addEventListener("click", shareTranscript);
}

// ---------------------------------------------------------------------
// Jit Pro — an optional paid unlock (via a Gumroad license key) for
// features beyond the free core, starting with PDF export. Still fully
// static/serverless: Gumroad's public license-verification API is called
// directly from the browser, so no backend of ours is involved in
// checking a purchase.
// ---------------------------------------------------------------------
const PRO_UNLOCKED_STORAGE = "jit_pro_unlocked";
const PRO_LICENSE_KEY_STORAGE = "jit_pro_license_key";

// Set this to your own Gumroad product's permalink (the part of the URL
// after gumroad.com/l/) once you've created a "Jit Pro" product there.
const GUMROAD_PRODUCT_PERMALINK = "REPLACE_WITH_YOUR_GUMROAD_PERMALINK";
const isProConfigured = () => GUMROAD_PRODUCT_PERMALINK !== "REPLACE_WITH_YOUR_GUMROAD_PERMALINK";

// Flip to false once Jit Pro is actually for sale (a real Gumroad product
// is set up above) — until then, every Pro feature is unlocked for
// everyone by default rather than gating something nobody can yet pay
// for. The licensing UI/verification below stays fully wired up either
// way, so flipping this back on is the only step needed at launch.
const PRO_FREE_FOR_NOW = true;

const isProUnlocked = () => PRO_FREE_FOR_NOW || localStorage.getItem(PRO_UNLOCKED_STORAGE) === "1";

async function verifyGumroadLicense(licenseKey) {
  const response = await fetch("https://api.gumroad.com/v2/licenses/verify", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      product_permalink: GUMROAD_PRODUCT_PERMALINK,
      license_key: licenseKey,
    }),
  });
  const data = await response.json();
  return Boolean(data.success);
}

const proStatusEl = document.getElementById("pro-status");
const proKeyInput = document.getElementById("pro-key-input");
const proActivateBtn = document.getElementById("pro-activate");
const proDeactivateBtn = document.getElementById("pro-deactivate");
const exportPdfBtn = document.getElementById("chat-export-pdf");

if (proKeyInput) {
  proKeyInput.value = localStorage.getItem(PRO_LICENSE_KEY_STORAGE) || "";
}

function renderProStatus() {
  if (exportPdfBtn) exportPdfBtn.disabled = !isProUnlocked();
  if (!proStatusEl) return;
  if (PRO_FREE_FOR_NOW) {
    proStatusEl.textContent = "✓ All Jit Pro features are free for everyone for now — no license needed.";
  } else {
    proStatusEl.textContent = isProUnlocked() ? "✓ Jit Pro is active on this device." : "";
  }
}

if (proActivateBtn) {
  proActivateBtn.addEventListener("click", async () => {
    const key = (proKeyInput?.value || "").trim();
    if (!key || !proStatusEl) return;

    if (!isProConfigured()) {
      proStatusEl.textContent = "Jit Pro isn't set up yet on this site — no product to verify against.";
      return;
    }

    const original = proActivateBtn.textContent;
    proActivateBtn.disabled = true;
    proActivateBtn.textContent = "Checking…";
    proStatusEl.textContent = "";
    try {
      const valid = await verifyGumroadLicense(key);
      if (valid) {
        localStorage.setItem(PRO_UNLOCKED_STORAGE, "1");
        localStorage.setItem(PRO_LICENSE_KEY_STORAGE, key);
      } else {
        proStatusEl.textContent = "That license key didn't verify — double-check it and try again.";
      }
    } catch {
      proStatusEl.textContent = "Couldn't reach the license server — check your connection and try again.";
    } finally {
      proActivateBtn.disabled = false;
      proActivateBtn.textContent = original;
      renderProStatus();
    }
  });
}

if (proDeactivateBtn) {
  proDeactivateBtn.addEventListener("click", () => {
    localStorage.removeItem(PRO_UNLOCKED_STORAGE);
    localStorage.removeItem(PRO_LICENSE_KEY_STORAGE);
    if (proKeyInput) proKeyInput.value = "";
    renderProStatus();
  });
}

if (exportPdfBtn) {
  exportPdfBtn.addEventListener("click", () => {
    if (!isProUnlocked()) return;
    window.print();
  });
}

renderProStatus();

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

// ---------------------------------------------------------------------
// Browse topics — nobody guesses that "SALT cap" or "NIIT" are things
// worth asking about unless they already study tax law. This lists every
// built-in fact in plain language (bridge.py's fact_topics(), not a
// restated acronym) so a topic can be found by browsing instead of
// requiring the exact jargon term up front.
// ---------------------------------------------------------------------
const topicsList = document.getElementById("topics-list");

async function loadTopics() {
  if (!topicsList) return;
  try {
    const dispatch = await bootPromise;
    const response = JSON.parse(dispatch("fact_topics", "{}"));
    if (!response.success) return;
    topicsList.innerHTML = response.data.topics
      .map(
        (t) =>
          `<button type="button" class="topic-chip" data-query="${t.query.replace(/"/g, "&quot;")}">${t.label}</button>`
      )
      .join("");
  } catch {
    /* Topic browsing is a nice-to-have; a failure here shouldn't disrupt chat. */
  }
}
loadTopics();

if (topicsList) {
  topicsList.addEventListener("click", (event) => {
    const chip = event.target.closest(".topic-chip");
    if (!chip) return;
    chatInput.value = chip.dataset.query;
    chatForm.requestSubmit();
  });
}

// A short, human-readable gloss on bridge.py's routing_reason/matched_keywords
// — real, inspectable routing metadata (not a fabricated confidence score),
// surfaced here so "why did it answer that" isn't a black box.
function formatRoutingNote(routingReason, matchedKeywords) {
  switch (routingReason) {
    case "keyword_match": {
      const kws = Object.values(matchedKeywords || {}).flat();
      return kws.length ? `matched: "${kws.join('", "')}"` : "";
    }
    case "resumed_suggestion":
      return "continuing from the suggestion above";
    case "resumed_pending_clarify":
      return "using what you just told me";
    default:
      return "";
  }
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

      // Persisted once here, right after every successful dispatch, so it
      // covers every intent/domain uniformly — clarify, fact, AI-assisted,
      // or a real calculation all update the same underlying context.
      persistChatState(dispatch);

      const { intent, matched, reply, result, routing_reason, matched_keywords, citation } =
        response.data;

      if (intent === "clarify" || intent === "fact") {
        // Either asking a question back, or answering straight from the
        // built-in fact library — neither ran an engine, so there's no
        // result card to show, and "Routed to" would be misleading.
        // A fact answer traces back to a real statute/IRC citation (not a
        // generated summary) — shown so the source is checkable, not just
        // asserted.
        const citationHtml =
          intent === "fact" && citation ? `<span class="citation-note">Source: ${citation}</span>` : "";
        addChatBubble("assistant", `${reply}${citationHtml}`);
        return;
      }

      if (intent === "platform_analyze" && matched === false) {
        // The rule-based router found no real topic keyword here — bridge.py
        // doesn't run (or claim) a full-case computation for this, so there's
        // never a card to show. Either hand it to Gemini if configured, or
        // just relay the "not sure what you're asking" reply plainly.
        if (isAiAssistEnabled() && getGeminiKey()) {
          try {
            const aiReply = await askGemini(getGeminiKey(), message);
            addChatBubble(
              "assistant",
              `<span class="intent-tag">AI-assisted (Gemini) — not verified by Jit's calculators</span>${aiReply.replace(/</g, "&lt;")}`
            );
          } catch (err) {
            addChatBubble(
              "assistant",
              `<div class="error-box">${(err && err.message) || err}</div>`
            );
          }
        } else {
          addChatBubble("assistant", reply);
        }
        return;
      }

      // A compound question ("should I itemize and am I at audit risk")
      // comes back as a "+"-joined intent with a result keyed by each
      // sub-intent — render every sub-result's own card in sequence.
      const subIntents = intent.split("+");
      const label = subIntents.map((i) => INTENT_LABELS[i] || i).join(" + ");
      let cardHtml = "";
      try {
        cardHtml = subIntents
          .map((i) => (RENDERERS[i] || renderGeneric)(subIntents.length > 1 ? result[i] : result))
          .join("");
      } catch {
        /* If a specific renderer can't handle this shape, the reply text still stands alone. */
      }
      const routingNote = formatRoutingNote(routing_reason, matched_keywords);
      addChatBubble(
        "assistant",
        `<span class="intent-tag">Routed to: ${label}</span>${routingNote ? `<span class="routing-note">${routingNote}</span>` : ""}${reply}${cardHtml}`
      );
      refreshSessionInsights();
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
    localStorage.removeItem(CHAT_STATE_STORAGE);
    chatLog.innerHTML = "";
    if (insightsPanel) insightsPanel.innerHTML = "";
  });
}
