#!/bin/bash
set -e

echo "============================================"
echo "  Dzack AI - Auto Setup Dependencies"
echo "============================================"
echo ""

cd /home/runner/workspace

echo "[1/3] Installing Node.js dependencies..."
if [ -f "package-lock.json" ]; then
  npm ci --silent 2>&1
else
  npm install --silent 2>&1
fi
echo "  -> Node.js dependencies installed."
echo ""

echo "[2/3] Installing Python dependencies..."
if command -v uv &> /dev/null; then
  uv sync --quiet 2>&1
else
  pip install -r <(python -c "
import tomllib
with open('pyproject.toml','rb') as f:
    d = tomllib.load(f)
for dep in d['project']['dependencies']:
    print(dep)
") 2>&1
fi
echo "  -> Python dependencies installed."
echo ""

echo "[3/3] Building frontend..."
npx --yes vite build 2>&1
echo "  -> Frontend built."
echo ""

echo "============================================"
echo "  Setup complete! Run: python backend/main.py"
echo "============================================"
