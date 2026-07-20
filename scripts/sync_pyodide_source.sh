#!/bin/bash
# Syncs the pure-Python (stdlib-only) parts of the jit package into docs/py/jit/
# for the client-side, Pyodide-powered GitHub Pages frontend. Deliberately
# excludes jit/api/main.py, jit/api/routers/, and jit/database/ — those depend
# on FastAPI/SQLAlchemy, which the static site doesn't use or need.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO_ROOT/jit"
DEST="$REPO_ROOT/docs/py/jit"

rm -rf "$DEST"
mkdir -p "$DEST"

copy() {
  local rel="$1"
  mkdir -p "$DEST/$(dirname "$rel")"
  cp "$SRC/$rel" "$DEST/$rel"
}

copy "__init__.py"
copy "platform.py"

copy "core/__init__.py"
copy "core/models.py"
copy "core/config.py"
copy "core/services.py"
copy "core/plugins.py"
copy "core/events.py"

copy "accounting/__init__.py"
copy "accounting/tax_calculator.py"
copy "accounting/income_processor.py"
copy "accounting/deduction_optimizer.py"
copy "accounting/amt_calculator.py"
copy "accounting/quarterly_estimator.py"
copy "accounting/base.py"
copy "accounting/engine.py"

copy "legal/__init__.py"
copy "legal/document_processor.py"
copy "legal/statute_parser.py"
copy "legal/case_analyzer.py"
copy "legal/compliance_engine.py"
copy "legal/base.py"
copy "legal/engine.py"

copy "algorithms/__init__.py"
copy "algorithms/decision_tree.py"
copy "algorithms/optimizer.py"
copy "algorithms/risk_assessor.py"
copy "algorithms/base.py"
copy "algorithms/engine.py"

copy "api/__init__.py"
copy "api/gateway.py"

copy "utils/__init__.py"
copy "utils/formatters.py"

MANIFEST="$REPO_ROOT/docs/py/manifest.json"
(
  cd "$REPO_ROOT/docs/py"
  {
    echo "["
    find jit -name "*.py" | sort | sed 's/.*/"&"/' | paste -sd, -
    echo "]"
  } > "$MANIFEST"
)

echo "Synced $(find "$DEST" -name '*.py' | wc -l) files into $DEST"
echo "Wrote manifest: $MANIFEST"
