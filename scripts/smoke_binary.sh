#!/usr/bin/env bash
# Start the packaged app under a virtual display and require that it stays up.
#
# A PyInstaller build can be broken in ways the test suite cannot see (missing
# Tk extensions, hooks that skip data files). This waits 25 s: exit code 124
# means the window was still open when the timeout fired, which is the pass.
set -u

BINARY="${1:-dist/YouMuDow}"
LOG="${HOME}/.config/youmudow/youmudow.log"

if [ ! -x "$BINARY" ]; then
  echo "No executable at ${BINARY}"
  exit 1
fi

RUNNER=()
if command -v xvfb-run >/dev/null 2>&1; then
  RUNNER=(xvfb-run -a)
elif [ -z "${DISPLAY:-}" ]; then
  echo "No display and no xvfb-run for the smoke test"
  exit 1
fi

rm -f "$LOG"
timeout 25 "${RUNNER[@]}" "$BINARY" > /tmp/binary-smoke.log 2>&1
code=$?

if [ "$code" -ne 124 ]; then
  echo "The packaged binary exited on its own (code ${code})"
  cat /tmp/binary-smoke.log 2>/dev/null || true
  exit 1
fi

if ! grep -q "Starting YouMuDow" "$LOG" 2>/dev/null; then
  echo "The binary never logged its startup line"
  cat /tmp/binary-smoke.log 2>/dev/null || true
  exit 1
fi

echo "Packaged binary stayed up for 25 s"
