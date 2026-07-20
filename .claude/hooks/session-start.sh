#!/bin/bash
set -euo pipefail

# Only needed for Claude Code on the web — a local dev machine already has
# its own environment set up.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

python3 -m pip install --quiet -r requirements.txt
python3 -m pip install --quiet pytest pytest-asyncio pytest-cov httpx flake8 black
python3 -m pip install --quiet -e .
