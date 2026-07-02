#!/usr/bin/env bash
# MJS — atalho para cli.py de qualquer lugar
exec python3 "$(dirname "$(readlink -f "$0")")/FERRAMENTAS/cli.py" "$@"
