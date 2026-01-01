#!/bin/bash
# Question Generator Script - Runs Mistral generators

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QG_DIR="$SCRIPT_DIR/question_generator"

echo "Starting question generators..."

# Start parallel_mistral.py
nohup python3 "$QG_DIR/parallel_mistral.py" >> "$QG_DIR/parallel_mistral.log" 2>&1 &
echo "Started parallel_mistral.py (PID: $!)"

# Start mistral_riddles.py
nohup python3 "$QG_DIR/mistral_riddles.py" >> "$QG_DIR/mistral_riddles.log" 2>&1 &
echo "Started mistral_riddles.py (PID: $!)"

echo "Both generators running. Check logs in $QG_DIR/"
