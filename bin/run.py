#!/usr/bin/env python3
"""Builds scip-java from a checkout and indexes corpus projects with it.

    bin/run.py [--scip-java DIR] [--label LABEL] [NAME ...]

DIR defaults to $SCIP_JAVA_DIR or ../scip-java. NAME defaults to every project
in corpus.json. Results go to results/<label>/<name>/, where the label defaults
to <branch>-<commit>[-dirty] of DIR.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def cli_label(scip_java):
    commit = git(scip_java, "rev-parse", "--short", "HEAD")
    branch = git(scip_java, "rev-parse", "--abbrev-ref", "HEAD").replace("/", "-")
    dirty = bool(git(scip_java, "status", "--porcelain", "--untracked-files=no"))
    return f"{branch}-{commit}" + ("-dirty" if dirty else ""), dirty


def build_cli(scip_java, label, dirty):
    """Clean builds are reused; dirty checkouts are rebuilt on every run."""
    cli_dir = ROOT / "cache" / "cli" / label
    if dirty or not (cli_dir / "bin" / "scip-java").exists():
        print(f"==> Building scip-java {label} from {scip_java}", flush=True)
        subprocess.run(
            ["nix", "develop", str(scip_java), "--command",
             "gradle", "-p", str(scip_java), "--no-daemon", "-q", ":scip-java:installDist"],
            check=True,
        )
        shutil.rmtree(cli_dir, ignore_errors=True)
        shutil.copytree(scip_java / "scip-java" / "build" / "install" / "scip-java", cli_dir, symlinks=True)
    return cli_dir / "bin" / "scip-java"


def checkout(entry):
    repo = ROOT / "cache" / "repos" / entry["name"]
    ref = entry["ref"]
    if not (repo / ".git").is_dir():
        repo.mkdir(parents=True, exist_ok=True)
        git(repo, "init", "-q")
        git(repo, "remote", "add", "origin", f"https://github.com/{entry['repository']}.git")
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "-q", "--verify", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    if head != ref:
        git(repo, "fetch", "-q", "--depth=1", "origin", ref)
    git(repo, "checkout", "-q", "-f", "--detach", ref)
    git(repo, "clean", "-q", "-ffdx")
    git(repo, "submodule", "-q", "update", "--init", "--recursive", "--depth", "1")
    return repo


def prepare_gradle_home():
    """A dedicated Gradle home keeps the user's ~/.gradle settings out of the
    results. Toolchains resolve only to the flake's JDKs. The local build cache is
    dropped so cached Kotlin compile tasks can't skip the source dump the Gradle
    plugin writes in doLast."""
    home = ROOT / "cache" / "gradle-home"
    home.mkdir(parents=True, exist_ok=True)
    (home / "gradle.properties").write_text(
        f"org.gradle.java.installations.paths={os.environ['CORPUS_TOOLCHAINS']}\n"
        "org.gradle.java.installations.auto-detect=false\n"
    )
    for cache in (home / "caches").glob("build-cache-*"):
        shutil.rmtree(cache)
    return home


def index(entry, repo, cli, out):
    shell = f"jdk{entry['java']}" + ("-android" if entry["android"] else "")
    command = [str(cli), "index", "--build-tool=gradle", f"--output={out / 'index.scip'}"]
    if entry["build_command"]:
        command += ["--", *entry["build_command"]]
    env = {**os.environ, "GRADLE_USER_HOME": str(prepare_gradle_home())}

    print(f"==> Indexing {entry['name']} ({entry['repository']}@{entry['ref'][:12]}, {shell})", flush=True)
    with open(out / "index.log", "w") as log:
        # GNU time from the project's dev shell measures the CLI and the Gradle
        # build it runs, not nix develop.
        exit_code = subprocess.run(
            ["nix", "develop", f"{ROOT}#{shell}", "--command",
             "time", "-o", str(out / "time.txt"), "-f", "%e %M", *command],
            cwd=repo, env=env, stdout=log, stderr=subprocess.STDOUT,
        ).returncode

    seconds, max_rss_kb = (out / "time.txt").read_text().splitlines()[-1].split()
    run = {**entry, "exit_code": exit_code, "seconds": float(seconds), "max_rss_mb": int(max_rss_kb) // 1024}
    (out / "run.json").write_text(json.dumps(run, indent=2) + "\n")

    scip = out / "index.scip"
    if scip.exists() and scip.stat().st_size > 0:
        # Not strict: invalid symbols are reported by metrics.py instead of
        # dropping the whole document from the snapshot.
        subprocess.run(["scip", "snapshot", "--strict=false", "--from", str(scip), "--to", str(out / "snapshot")],
                       capture_output=True)
        with open(out / "metrics.json", "w") as metrics:
            subprocess.run([sys.executable, str(ROOT / "bin" / "metrics.py"), str(scip), str(repo)], stdout=metrics, check=True)


def main():
    # Re-enter through the default dev shell for git, scip and the toolchains.
    if "CORPUS_TOOLCHAINS" not in os.environ:
        os.execvp("nix", ["nix", "develop", str(ROOT), "--command", "python3", __file__, *sys.argv[1:]])

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scip-java", type=Path,
                        default=Path(os.environ.get("SCIP_JAVA_DIR", ROOT.parent / "scip-java")))
    parser.add_argument("--label")
    parser.add_argument("names", nargs="*", metavar="NAME")
    args = parser.parse_args()

    corpus = {entry["name"]: entry for entry in json.loads((ROOT / "corpus.json").read_text())}
    names = args.names or list(corpus)
    unknown = [name for name in names if name not in corpus]
    if unknown:
        parser.error(f"unknown corpus project: {', '.join(unknown)}")

    scip_java = args.scip_java.resolve()
    label, dirty = cli_label(scip_java)
    label = args.label or label
    cli = build_cli(scip_java, label, dirty)

    results = ROOT / "results" / label
    for name in names:
        out = results / name
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True)
        index(corpus[name], checkout(corpus[name]), cli, out)

    subprocess.run([sys.executable, str(ROOT / "bin" / "summary.py"), str(results), *names])


if __name__ == "__main__":
    main()
