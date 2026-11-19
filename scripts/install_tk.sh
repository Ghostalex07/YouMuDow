#!/usr/bin/env bash
# Install Tk (and Xvfb) with retries.
#
# GitHub's Ubuntu mirrors intermittently fail mid-download with
# "Could not wait for server fd - select (11: Resource temporarily
# unavailable)", which leaves apt with a partial archive set. A single
# `apt-get install` then fails the whole job even though nothing is wrong
# with the code, so retry with fresh package lists and longer timeouts.
set -uo pipefail

if python3 -c "import tkinter" >/dev/null 2>&1; then
  echo "tkinter is already available"
  exit 0
fi

apt_run() {
  sudo env DEBIAN_FRONTEND=noninteractive apt-get \
    -o Acquire::Retries=5 \
    -o Acquire::http::Timeout=60 \
    -o Acquire::https::Timeout=60 \
    "$@"
}

for attempt in 1 2 3 4 5; do
  apt_run update || true
  if apt_run install -y --no-install-recommends python3-tk xvfb; then
    if python3 -c "import tkinter" >/dev/null 2>&1; then
      echo "tkinter installed on attempt $attempt"
      exit 0
    fi
  fi
  echo "attempt $attempt failed, retrying in $((attempt * 15))s" >&2
  sleep $((attempt * 15))
done

echo "could not install python3-tk after 5 attempts" >&2
exit 1
