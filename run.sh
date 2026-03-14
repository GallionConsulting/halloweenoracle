#!/usr/bin/env bash
cd "$(dirname "$0")"
export PATH="$PWD/venv/bin:$PATH"
exec venv/bin/python3 crystal_ball.py --debug "$@"
