#!/bin/bash
set -euo pipefail

cd /Users/adzter/internal-tools/followup-tool

./launch_arc_debug.sh

python3 followup_gmail.py --profile advaith --arc

