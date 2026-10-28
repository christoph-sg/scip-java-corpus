#!/usr/bin/env python3
"""Print quality metrics for an index as JSON.

Matching and dangling references use the same scope: non-local, non-package
symbols in packages defined by the index, excluding Android R and BuildConfig.
"""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import subprocess


def language(path):
    return "kotlin" if path.endswith(".kt") else "java" if path.endswith(".java") else "other"


def module_name(path):
    if re.search(r"(^|/)(src|test|tests)/", path):
        return re.sub(r"/?(src|test|tests)/.*$", "", path) or "."
    return "(other)"


def package_name(symbol):
    descriptor = " ".join(symbol.split(" ")[4:])
    return descriptor.rsplit("/", 1)[0] + "/" if "/" in descriptor else ""


def metrics(index, tracked):
    documents = index["documents"]
    paths = [doc["relative_path"] for doc in documents]
    doc_paths = set(paths)
    tracked_paths = set(tracked)
    occurrences = [occ for doc in documents for occ in doc.get("occurrences", [])]
    defined = {occ["symbol"] for occ in occurrences if occ.get("symbol_roles", 0) & 1}
    defined.update(symbol["symbol"] for doc in documents for symbol in doc.get("symbols", []))
    packages = {package_name(symbol) for symbol in defined if not symbol.startswith("local ")}
    packages.discard("")
    matching = Counter()
    dangling = Counter()
    for occ in occurrences:
        symbol = occ["symbol"]
        if (occ.get("symbol_roles", 0) & 1 or symbol.startswith("local ")
                or symbol.endswith("/") or re.search(r"/(R|BuildConfig)#", symbol)
                or package_name(symbol) not in packages):
            continue
        counts = matching if symbol in defined else dangling
        counts[symbol] += 1

    def coverage(files):
        result = {}
        for lang in ("kotlin", "java"):
            sources = [path for path in files if language(path) == lang]
            result[lang] = f"{sum(path in doc_paths for path in sources)}/{len(sources)}"
        return result

    modules = defaultdict(list)
    for path in tracked:
        if language(path) != "other":
            modules[module_name(path)].append(path)
    invalid_locals = sorted({
        occ["symbol"] for occ in occurrences
        if occ["symbol"].startswith("local ") and not re.fullmatch(r"local [\w+$-]+", occ["symbol"])
    })
    generated = [path for path in paths if re.search(r"(^|/)build/", path)]
    generated_paths = set(generated)
    return {
        "documents": dict(Counter(language(path) for path in paths)),
        "occurrences": len(occurrences),
        "coverage": {
            **coverage(tracked),
            "modules": [{"module": name, **coverage(modules[name])} for name in sorted(modules)],
        },
        "generated_documents": len(generated),
        "untracked_documents": [path for path in paths if path not in tracked_paths and path not in generated_paths],
        "duplicates": sorted(path for path, count in Counter(paths).items() if count > 1),
        "invalid_locals": {"count": len(invalid_locals), "examples": invalid_locals[:5]},
        "matching": {"symbols": len(matching), "occurrences": sum(matching.values())},
        "dangling": {
            "symbols": len(dangling),
            "occurrences": sum(dangling.values()),
            "top": [{"symbol": symbol, "count": count} for symbol, count in
                    sorted(dangling.items(), key=lambda item: (-item[1], item[0]))[:25]],
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=Path)
    parser.add_argument("repo", type=Path)
    args = parser.parse_args()
    index = json.loads(subprocess.check_output(["scip", "print", "--json", str(args.index)]))
    tracked = subprocess.check_output(["git", "-C", str(args.repo), "ls-files"], text=True).splitlines()
    print(json.dumps(metrics(index, tracked), indent=2))


if __name__ == "__main__":
    main()
