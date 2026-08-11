#!/usr/bin/env bash
set +e
cd <redacted-local-path>
pwd
find . -maxdepth 3 \( -type f -name 'benchmark_chirla_reid.py' -o -type d -name scripts \) | head -30
find . -maxdepth 3 -type f -name 'benchmark_clipreid_support.py' | head -30
find scripts -maxdepth 1 -type f -printf '%f\n' | sort
find . -maxdepth 2 -type d | sort | head -80
exit 0
