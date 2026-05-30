#!/bin/bash
cd /root/trading_ai
clear
echo "=== ABA TRADING -- $(date +%H:%M:%S) ==="
uv run python3 /root/trading_ai/status_helper.py
echo "====================================="
