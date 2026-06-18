#!/usr/bin/env bash
set -euo pipefail
# Resolve this script's directory and run the driver module so the process exit
# code IS the driver's return value. No make, no install, no network.
cd "$(dirname "$0")"
export PYTHONPATH="$(pwd)/src:$(pwd)/vendor${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m audit_packet.verify "$@"
