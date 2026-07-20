# Jit — Automatic Recursive Algorithmic Accounting & Legal Analysis System

[![CI](https://github.com/thetruezubzero-pixel/Jit-/actions/workflows/ci.yml/badge.svg)](https://github.com/thetruezubzero-pixel/Jit-/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A comprehensive, Python-based accounting and legal analysis platform for
American citizens. Jit provides automated tax calculation, deduction
optimization, legal document analysis, compliance verification, recursive
decision-making, and risk assessment.

> **Disclaimer**: Jit is an educational and analytical tool. It does **not**
> constitute legal or tax advice. Always consult a qualified CPA, enrolled
> agent, or tax attorney before filing or making financial decisions.

## Use it on your phone — free, GitHub-only, no server

`docs/` is a static frontend that runs the real `jit` engines **entirely in
the browser** via [Pyodide](https://pyodide.org) (Python compiled to
WebAssembly) — there is no backend to host, so it works from an iPhone,
Android, or desktop browser via GitHub Pages alone, at no cost:

1. Push to `main` or any `claude/**` branch. `.github/workflows/pages.yml`
   vendors the Pyodide runtime, syncs the current `jit/` source into `docs/`,
   and force-pushes the result to a `gh-pages` branch — so the site can
   never drift from the real engines.
2. In this repo (one-time, after the first successful run above creates the
   `gh-pages` branch): **Settings → Pages → Build and deployment → Source:
   Deploy from a branch → Branch: `gh-pages` → folder: `/ (root)`**.
3. Open `https://thetruezubzero-pixel.github.io/Jit-/` on any device.

(This deploys via a plain `git push` to a branch rather than GitHub's newer
Pages Deployments API, since that API's health-check call is a single point
of failure the site doesn't otherwise need.)

Every module gets its own tab (Tax Calculator, Deductions, AMT, Quarterly,
Legal Document, Compliance, Filing Status, Optimizer, Audit Risk) plus a
"Full Case" tab that runs the same cross-module `JitPlatform` orchestration
as the REST API — all client-side. No data ever leaves the device; there's
no server to send it to. See `docs/py/bridge.py` for the dispatch layer and
`scripts/sync_pyodide_source.sh` for what gets synced.

---

## Table of Contents

1. [Features](#features)
2. [Project Structure](#project-structure)
3. [Quick Start](#quick-start)
4. [Modules](#modules)
5. [API Reference](#api-reference)
6. [Examples](#examples)
7. [Testing](#testing)
8. [Configuration](#configuration)
9. [Contributing](#contributing)
10. [License](#license)

---

## Features

### Accounting Module
- **Federal income tax calculator** — 2024 tax year brackets, all filing statuses
- **FICA taxes** — Social Security, Medicare, Additional Medicare (IRC §3101)
- **Self-employment tax** — Schedule SE computation (IRC §1401)
- **Capital gains** — LTCG preferential rates, qualified dividends (IRC §1(h))
- **Net Investment Income Tax** — NIIT 3.8% (IRC §1411)
- **Income processor** — W-2, 1099-NEC, 1099-B, 1099-DIV, K-1, rental, SS benefits
- **Deduction optimizer** — Standard vs. itemized comparison, phase-outs, QBI §199A
- **AMT calculator** — Form 6251 computation, exemption phase-outs, AMT credit
- **Quarterly estimator** — Safe harbor calculations, payment schedules (Form 1040-ES)
- **State tax estimation** — All 50 states + DC

### Legal Analysis Module
- **Document processor** — Extracts provisions, citations, keywords, risk scores
- **Statute parser** — Parses USC, CFR, and state codes into structured sections
- **Case analyzer** — Indexes court opinions, relevance scoring, precedent research
- **Compliance engine** — FBAR, FATCA, 1099 filings, underpayment checks

### Recursive Algorithms
- **Decision trees** — Recursive evaluation engine with condition, calculation,
  recommendation, and aggregation nodes
- **Filing status recommender** — Pre-built tree for optimal IRS filing status
- **Deduction method selector** — Standard vs. itemized decision tree
- **Tax optimizer** — Retirement (401k, SEP-IRA), HSA, capital gains, charitable,
  QBI, and S-Corp strategies
- **Risk assessor** — Audit probability, penalty risk, compliance risk scoring

### API & Integration
- **FastAPI** REST API with OpenAPI documentation
- Pydantic v2 request/response validation
- Async SQLAlchemy database layer (SQLite/PostgreSQL)
- Health check, versioned endpoints

### Platform Orchestration
- **Core contracts** (`jit/core/`) — shared `AnalysisContext`/`ModuleResult` models,
  versioned feature config, a service registry, a generic plugin registry, and an
  observer-style event bus for cross-module communication
- **`JitPlatform`** — a single orchestration entry point that runs a case through
  accounting → legal → algorithms in sequence, feeding each module's output into the
  next, and records an audit trail of every stage
- **Pluggable engines** — `AccountingEngine`, `LegalAnalysisEngine`, and
  `AlgorithmEngine` wrap the real tax/legal/algorithm modules above behind swappable
  interfaces (`TaxCalculatorPlugin`, `LegalAnalyzerPlugin`, `RecommendationStrategy`),
  so a calculator, analyzer, or strategy can be registered and swapped in at runtime
  without touching the orchestrator
- **Versioned API gateway** (`jit/api/gateway.py`) — a lightweight, middleware-aware
  request pipeline used internally by `JitPlatform`, exposed over REST at
  `/api/v1/platform/analyze`

---

## Project Structure

```
Jit-/
├── jit/                         # Main package
│   ├── accounting/              # Tax and financial modules
│   │   ├── tax_calculator.py    # Federal income tax engine
│   │   ├── income_processor.py  # Income categorization
│   │   ├── deduction_optimizer.py  # Deduction analysis
│   │   ├── amt_calculator.py    # Alternative Minimum Tax
│   │   └── quarterly_estimator.py  # Quarterly payments
│   ├── legal/                   # Legal analysis modules
│   │   ├── document_processor.py   # Document parsing
│   │   ├── statute_parser.py    # Statute/CFR parsing
│   │   ├── case_analyzer.py     # Case law research
│   │   └── compliance_engine.py # Compliance verification
│   ├── algorithms/              # Recursive decision engines
│   │   ├── decision_tree.py     # Decision tree framework
│   │   ├── optimizer.py         # Tax optimization strategies
│   │   ├── risk_assessor.py     # Audit/risk assessment
│   │   ├── base.py              # RecommendationStrategy plugin interface
│   │   └── engine.py            # AlgorithmEngine (pluggable, real-data-backed)
│   ├── core/                    # Cross-module platform contracts
│   │   ├── models.py            # AnalysisContext, ModuleResult, SystemResponse, ...
│   │   ├── config.py            # AppConfig (versions, feature flags, rules)
│   │   ├── services.py          # ServiceRegistry
│   │   ├── plugins.py           # PluginRegistry
│   │   └── events.py            # EventBus
│   ├── platform.py              # JitPlatform orchestrator
│   ├── api/                     # REST API
│   │   ├── main.py              # FastAPI application
│   │   ├── models.py            # Pydantic request/response models
│   │   ├── gateway.py           # Versioned, middleware-aware request pipeline
│   │   └── routers/             # Route handlers (incl. platform.py)
│   ├── database/                # Data persistence
│   │   ├── models.py            # SQLAlchemy ORM models
│   │   └── session.py           # Async session management
│   └── utils/                   # Utility functions
│       └── formatters.py        # Currency/percentage formatters
├── tests/                       # Test suite
│   ├── accounting/              # Accounting unit tests
│   ├── legal/                   # Legal analysis tests
│   ├── algorithms/              # Algorithm tests
│   ├── api/                     # API integration tests
│   └── test_platform.py         # JitPlatform / cross-module orchestration tests
├── examples/                    # Usage examples
│   ├── full_analysis.py         # End-to-end example (direct module calls)
│   ├── platform_demo.py         # End-to-end example via JitPlatform orchestration
│   ├── sample_case.json         # Sample AnalysisContext payload
│   └── data/                    # Sample data files
├── .github/workflows/ci.yml     # GitHub Actions CI/CD
├── requirements.txt
├── setup.py
└── pyproject.toml
```

---

## Quick Start

### Prerequisites

- Python 3.9 or higher
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/thetruezubzero-pixel/Jit-.git
cd Jit-

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate.bat     # Windows

# Install dependencies
pip install -r requirements.txt

# Install the package in development mode
pip install -e .
```

### Run the Examples

```bash
# Direct module calls (tax calculation, deductions, AMT, compliance, etc.)
python examples/full_analysis.py

# Cross-module orchestration through JitPlatform (accounting -> legal -> algorithms)
python examples/platform_demo.py
```

### Start the API Server

```bash
python -m jit.api.main
# OR
uvicorn jit.api.main:app --reload
```

Visit http://localhost:8000/docs for interactive API documentation.

---

## Modules

### Tax Calculator

```python
from jit.accounting.tax_calculator import TaxCalculator, FilingStatus

calc = TaxCalculator(tax_year=2024)
result = calc.calculate(
    gross_income=120_000,
    filing_status=FilingStatus.SINGLE,
    w2_wages=120_000,
    state_code="CA",
)
print(f"Total Tax: ${result.total_tax:,.2f}")
print(f"Effective Rate: {result.effective_total_rate:.1%}")
```

### Deduction Optimizer

```python
from jit.accounting.deduction_optimizer import DeductionOptimizer, DeductionType
from jit.accounting.tax_calculator import FilingStatus

opt = DeductionOptimizer()
opt.add_deduction(DeductionType.MORTGAGE_INTEREST, 18_000)
opt.add_deduction(DeductionType.STATE_LOCAL_TAX, 10_000)
opt.add_deduction(DeductionType.TRADITIONAL_IRA, 7_000)

result = opt.optimize(agi=120_000, filing_status=FilingStatus.SINGLE, age=40)
print(f"Recommended: {result.recommended_method} (${result.recommended_deduction:,.0f})")
```

### Decision Tree

```python
from jit.algorithms.decision_tree import DecisionTree

tree = DecisionTree.build_filing_status_tree()
result = tree.evaluate({
    "is_married": False,
    "has_qualifying_dependent": True,
    "is_qualifying_surviving_spouse": False,
})
print(result.recommendation)
# → File as Head of Household (HOH)
```

### Compliance Check

```python
from jit.legal.compliance_engine import ComplianceEngine

engine = ComplianceEngine()
result = engine.check_individual_tax_compliance(
    gross_income=200_000,
    tax_year=2024,
    filing_status_str="single",
    taxes_withheld=35_000,
    taxes_paid=0,
    has_foreign_accounts=True,
    aggregate_foreign_balance=25_000,  # Triggers FBAR issue
)
print(f"Risk: {result.overall_risk.value}")
for issue in result.issues:
    print(f"  [{issue.risk_level.value}] {issue.title}")
```

### JitPlatform (Cross-Module Orchestration)

```python
from jit.core.models import AnalysisContext, IncomeRecord, DeductionRecord
from jit.platform import JitPlatform

platform = JitPlatform()
response = platform.analyze_case(
    AnalysisContext(
        case_id="demo-case",
        filing_status="single",
        state="CA",
        incomes=[IncomeRecord(kind="w2", amount=120_000)],
        deductions=[DeductionRecord(name="charity", amount=4_000)],
    )
)

print(response.data["accounting"]["total_tax"])
print(response.data["legal"]["risk_score"])
print(response.data["algorithms"]["primary_recommendation"])
print([event.topic for event in response.audit_trail])
# → ['accounting.completed', 'legal.completed', 'algorithms.completed']
```

Calculators, analyzers, and strategies can be swapped at runtime without touching the
orchestrator:

```python
platform.accounting.register_calculator("my_calculator", MyCalculator)
platform.accounting.use_calculator("my_calculator")
```

---

## API Reference

### Base URL
```
http://localhost:8000/api/v1
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health/` | Health check |
| POST | `/accounting/tax/calculate` | Calculate federal & state tax |
| POST | `/accounting/deductions/optimize` | Optimize deductions |
| POST | `/accounting/amt/calculate` | Calculate AMT |
| POST | `/accounting/quarterly/estimate` | Quarterly estimated payments |
| POST | `/legal/document/analyze` | Analyze legal document |
| POST | `/legal/compliance/check` | Compliance check |
| POST | `/algorithms/filing-status` | Recommend filing status |
| POST | `/algorithms/optimize` | Tax optimization strategies |
| POST | `/algorithms/risk/assess` | Audit risk assessment |
| POST | `/platform/analyze` | Run a case through the full accounting → legal → algorithms pipeline |

Full interactive documentation is available at `/docs` (Swagger UI) and `/redoc`.

---

## Examples

### API — Tax Calculation (curl)

```bash
curl -X POST http://localhost:8000/api/v1/accounting/tax/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "gross_income": 150000,
    "filing_status": "single",
    "tax_year": 2024,
    "w2_wages": 150000,
    "state_code": "NY"
  }'
```

### API — Compliance Check (curl)

```bash
curl -X POST http://localhost:8000/api/v1/legal/compliance/check \
  -H "Content-Type: application/json" \
  -d '{
    "gross_income": 200000,
    "tax_year": 2024,
    "filing_status": "single",
    "taxes_withheld": 35000,
    "taxes_paid": 5000,
    "has_foreign_accounts": true,
    "aggregate_foreign_balance": 50000
  }'
```

---

## Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov httpx

# Run all tests
pytest tests/ -v

# Run tests with coverage
pytest tests/ --cov=jit --cov-report=term-missing

# Run specific module tests
pytest tests/accounting/ -v
pytest tests/algorithms/ -v
pytest tests/api/ -v
```

---

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./jit.db` | Database connection URL |
| `SQL_ECHO` | (unset) | Enable SQLAlchemy query logging |

For production, use PostgreSQL:
```
DATABASE_URL=******localhost/jit
```

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes with clear messages
4. Run tests (`pytest tests/`)
5. Open a pull request

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

## Status

🚀 **Active Development** — v0.1.0
