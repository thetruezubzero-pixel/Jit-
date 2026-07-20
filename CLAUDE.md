# Jit — project notes for Claude Code

## What this is

Two things in one repo:

1. **`jit/`** — a real Python accounting/legal/algorithms engine (tax
   calculator, deduction optimizer, AMT, quarterly estimator, document
   processor, compliance engine, decision trees, risk assessor), plus a
   FastAPI REST API (`jit/api/`) and a `JitPlatform` orchestrator
   (`jit/platform.py`) that runs a case through accounting → legal →
   algorithms with an audit trail.
2. **`docs/`** — a static frontend that runs those *same* engines entirely
   client-side via Pyodide (Python compiled to WebAssembly), deployed to
   GitHub Pages. No server, no backend, no paid API by default. Live at
   https://thetruezubzero-pixel.github.io/Jit-/

`docs/py/bridge.py` is a dispatch layer, not a reimplementation — it imports
straight from `jit/` (synced in at deploy time by
`scripts/sync_pyodide_source.sh`) so the browser and the local test suite
run identical logic.

## Commands

```bash
python3 -m pytest -q                                                   # full suite (200+ tests)
python3 -m flake8 jit/ tests/ docs/py/ --max-line-length=100 --extend-ignore=E203,W503
python3 -m black --check jit/ tests/ examples/ docs/py/
python3 -m black jit/ tests/ examples/ docs/py/                        # auto-format
```

(Or `make install` / `make test` / `make lint` / `make format` — see `Makefile`.)

CI runs the same lint/test commands (`.github/workflows/ci.yml`) on
`main`, `copilot/**`, and `claude/**` branches, plus PRs into `main`.

## Working on `docs/` (the chat frontend)

- `docs/py/bridge.py` — one `dispatch(module_name, payload_json)` entry
  point; `_HANDLERS` maps a name to a function. `chat()` is the free-text
  router: keyword/regex classification in `_classify_intent()`, a small
  built-in fact library in `_FACTS` for direct tax-law answers, and
  module-level `_conversation_context`/`_session_history` for cross-message
  memory (persisted to `localStorage` by the frontend via
  `chat_export_state`/`chat_import_state`, not by Python itself — Pyodide's
  interpreter is rebuilt from scratch on every page load).
- `tests/test_pyodide_bridge.py` imports `docs/py/bridge.py` directly via a
  `sys.path` hack and exercises it under plain CPython, so bridge changes
  are covered by the normal test suite without a browser. Module-level state
  (`_conversation_context`, `_session_history`) leaks across tests in the
  same file unless reset — every test class that touches `chat()` needs an
  autouse fixture calling `bridge.dispatch("chat_reset", "{}")` before *and*
  after each test.
- `docs/app.js` has no build step — it's loaded directly as an ES module.
  Test frontend changes with a real headless browser (Playwright,
  `python3 -m http.server` over `docs/`), not just by reading the code —
  several real bugs this session (a CSS layout bug, a stale-service-worker
  caching bug) were only visible that way, not in tests or by inspection.
- `docs/sw.js` caches the app shell. **Bump `CACHE_VERSION` any time you
  change `styles.css`, `app.js`, `index.html`, or `bridge.py`** — otherwise
  a real device can stay stuck on stale assets indefinitely; this has
  already caused one shipped fix to not visibly take effect.
- `docs/py/jit/`, `docs/py/manifest.json`, and `docs/vendor/` are
  git-ignored — generated at deploy time by
  `scripts/sync_pyodide_source.sh` and the Pyodide vendoring step in
  `.github/workflows/pages.yml`. Don't hand-edit or commit them.

## Constraints that have come up repeatedly

- **No paid API, no server, by default.** The chat's optional AI-assist
  (Gemini) is opt-in, uses the user's own free-tier key stored only in
  their browser, and only fires for messages the rule-based router
  genuinely can't classify — every deterministic calculation is unaffected
  either way.
- **Deploys via a `gh-pages` branch push** (`peaceiris/actions-gh-pages`),
  not the newer Pages Deployments API — that API had a sustained outage
  during development. Don't switch this back without checking
  https://www.githubstatus.com first.
- Don't build attack/surveillance tooling (DDoS, botnets, dossiers on third
  parties) under any framing — declined multiple times this session
  regardless of phrasing. This is a personal tax/legal calculator, not a
  security tool.
- Don't claim "self-aware AI" or similar — not a real capability from any
  vendor. `chat()` is keyword/regex routing plus a static fact table, full
  stop; describe it that way.

## Verifying a change actually works

Reading the diff is not enough for anything in `docs/`. Before calling a
frontend change done: run the full pytest suite, run flake8/black, then
boot a real headless browser against a local `http.server` over `docs/`
and drive the actual UI (fill the chat input, click send, read the
rendered bubble/card back out). This has caught real bugs — a CSS
flexbox conflict, a service-worker cache staleness issue, and a fallback
path that silently computed a full tax return for an off-topic message —
that neither the test suite nor a code read caught on their own.
