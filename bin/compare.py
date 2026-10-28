#!/usr/bin/env python3
"""Compare two result labels: summaries followed by snapshot diff statistics.

For the full diff of one project, use:
    git diff --no-index results/A/NAME/snapshot results/B/NAME/snapshot
"""

import argparse
from pathlib import Path
import subprocess

from summary import summary

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("label_a")
    parser.add_argument("label_b")
    parser.add_argument("names", nargs="*", metavar="NAME")
    args = parser.parse_args()
    a = ROOT / "results" / args.label_a
    b = ROOT / "results" / args.label_b
    names = args.names or sorted({path.name for path in a.iterdir()} & {path.name for path in b.iterdir()})
    for directory in (a, b):
        print(f"== {directory.name}")
        summary(directory, names)
        print()
    for name in names:
        print(f"== snapshot diff: {name}", flush=True)
        before = a / name / "snapshot"
        after = b / name / "snapshot"
        if before.is_dir() and after.is_dir():
            subprocess.run(["git", "diff", "--no-index", "--shortstat", str(before), str(after)])
        else:
            print("(missing snapshot)")


if __name__ == "__main__":
    main()
