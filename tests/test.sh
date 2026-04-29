#!/usr/bin/env bash
#
# Test entry point invoked by the Harbor verifier.

mkdir -p /logs/verifier

# Ensure python3-venv is available (Main Container ships only curl + ca-certificates)
apt-get update -qq
apt-get install -y --no-install-recommends python3-venv

VENV=/opt/test-venv

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