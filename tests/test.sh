#!/usr/bin/env bash
#
# Test entry point invoked by the Harbor verifier.
#
# Installs pytest and requests into a dedicated venv (the Main Container's
# Ubuntu 24.04 base enforces PEP 668, which forbids system-wide pip), runs
# the test suite, and writes the reward to /logs/verifier/reward.txt.

mkdir -p /logs/verifier

VENV=/opt/test-venv

# Idempotent install: only set up the venv once per container lifetime.
if [ ! -x "${VENV}/bin/pytest" ]; then
  python3 -m venv "${VENV}"
  "${VENV}/bin/pip" install --quiet --no-cache-dir \
    "pytest==8.4.1" \
    "requests==2.32.3"
fi

"${VENV}/bin/pytest" /tests/test_outputs.py -v --tb=short
PYTEST_RC=$?

if [ "${PYTEST_RC}" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi