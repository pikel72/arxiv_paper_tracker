#!/bin/bash
set -euo pipefail
cd /data/Code/arxiv_paper_tracker
export TZ=Asia/Hong_Kong
exec /home/pikel/.local/share/arxiv-paper-tracker/venv/bin/python src/daily_retry.py "$@"
