#!/usr/bin/env bash
set -euo pipefail

export PYTHONHASHSEED=0
perl tests/benchmark_research_harness.pl
