#!/usr/bin/env python3
"""Print one line per corpus project of a results directory."""

import argparse
import json
from pathlib import Path


def summary(directory, names):
    columns = ("project", "exit", "seconds", "rss_mb", "kotlin", "java", "matching",
               "dangling", "bad_loc", "dups", "untracked", "generated")
    widths = (-20, -6, 8, 8, 10, 10, 9, 9, 8, 6, 10, 10)

    def row(values):
        print(" ".join(f"{str(value):{'<' if width < 0 else '>'}{abs(width)}}"
                       for value, width in zip(values, widths)))

    row(columns)
    for name in names:
        run_path = directory / name / "run.json"
        if not run_path.is_file():
            continue
        run = json.loads(run_path.read_text())
        metrics_path = directory / name / "metrics.json"
        metrics_text = metrics_path.read_text().strip() if metrics_path.is_file() else ""
        metrics = json.loads(metrics_text) if metrics_text else {}
        row([
            run["name"], run["exit_code"], run["seconds"], run["max_rss_mb"],
            metrics.get("coverage", {}).get("kotlin", "-"),
            metrics.get("coverage", {}).get("java", "-"),
            metrics.get("matching", {}).get("occurrences", "-"),
            metrics.get("dangling", {}).get("occurrences", "-"),
            metrics.get("invalid_locals", {}).get("count", "-"),
            len(metrics.get("duplicates", [])), len(metrics.get("untracked_documents", [])),
            metrics.get("generated_documents", "-"),
        ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("names", nargs="*", metavar="NAME")
    args = parser.parse_args()
    names = args.names or sorted(path.name for path in args.directory.iterdir())
    summary(args.directory, names)


if __name__ == "__main__":
    main()
