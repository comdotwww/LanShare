#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
elif [ -x ".venv/Scripts/python.exe" ]; then
  PYTHON=".venv/Scripts/python.exe"
else
  python3 -m venv .venv
  if [ -x ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
  else
    PYTHON=".venv/Scripts/python.exe"
  fi
fi

"$PYTHON" -m pip install -r requirements.txt
"$PYTHON" -m PyInstaller --noconfirm --clean LanFileShare.spec

echo
if [ "$(uname -s)" = "MINGW64_NT-10.0" ] || [ -f "dist/LanFileShare.exe" ]; then
  echo "Build finished: dist/LanFileShare.exe"
else
  echo "Build finished: dist/LanFileShare"
fi
