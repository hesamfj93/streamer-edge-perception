#!/usr/bin/env bash
# =====================================================================
# regenerate_ui.sh
# Regenerate windows_app/app/ui_main_window.py from
# windows_app/ui/main_window.ui via pyside6-uic.
#
# Run this whenever you edit main_window.ui in Qt Designer.
# =====================================================================
set -euo pipefail

REPO_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
UI_FILE="$REPO_ROOT/windows_app/ui/main_window.ui"
PY_OUT="$REPO_ROOT/windows_app/app/ui_main_window.py"

if [ ! -f "$UI_FILE" ]; then
    echo "UI file not found: $UI_FILE" >&2
    exit 1
fi

if ! command -v pyside6-uic >/dev/null 2>&1; then
    echo "pyside6-uic not found. Install with:" >&2
    echo "    pip install pyside6" >&2
    exit 1
fi

echo "Regenerating $PY_OUT"
pyside6-uic "$UI_FILE" -o "$PY_OUT"
echo "Done."
