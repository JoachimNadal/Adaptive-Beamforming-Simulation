"""Fail if any file of the Phase 1 baseline differs from its tag.

    python research/check_baseline.py

Phase 2 only adds files. The exceptions below are documents that must be able to point to it.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAG = "v1.0.0-phase1"
ALLOWED = {"README.md", "docs/README.md", "docs/ROADMAP.md"}


def main():
    command = ["git", "diff", "--name-status", "--no-renames", TAG, "--"]
    done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if done.returncode:
        print(done.stderr.strip(), file=sys.stderr)
        return 2
    changed = []
    for line in done.stdout.splitlines():
        status, path = line.split("\t", 1)
        if status != "A" and path not in ALLOWED:
            changed.append(f"{status} {path}")
    if changed:
        print(f"baseline {TAG} modified:\n  " + "\n  ".join(changed))
        return 1
    print(f"baseline {TAG} unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
