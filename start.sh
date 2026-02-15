#!/bin/bash
cd /home/runner/workspace
npx vite build 2>&1
cd /home/runner/workspace
python backend/main.py
