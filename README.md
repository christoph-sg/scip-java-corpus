# scip-java-corpus

Indexes real-world Java and Kotlin projects with a local
[scip-java](https://github.com/scip-code/scip-java) checkout and reports
statistics that catch silently wrong indexes. The projects cover Android,
Kotlin Multiplatform, and mixed Java/Kotlin builds; see `corpus.json`.
Bugs found so far are tracked in [BUGS.md](BUGS.md).

## Running

Only [Nix](https://nixos.org) with flakes is required.

```sh
# Index every project with ../scip-java (or $SCIP_JAVA_DIR)
bin/run.py

# Index some projects with another checkout
bin/run.py --scip-java ../scip-java-feature timber retrofit

# Name the run instead of using <branch>-<commit>[-dirty]
bin/run.py --label my-fix kotlinx-datetime
```

`bin/run.py` re-enters itself through `nix develop`, builds the scip-java CLI
with the checkout's own flake (always rebuilt for a dirty checkout), clones each
project at its pinned commit into `cache/repos/`, and runs `scip-java index` in
the project's dev shell. Gradle uses a dedicated `cache/gradle-home`, toolchains
resolve only to the flake's JDKs (8, 11, 17, 21, 25), and the build cache is
cleared before each project.

## Statistics

```sh
# One line per project of a run
bin/summary.py results/<label>

# Two runs side by side, plus snapshot diff statistics per project
bin/compare.py <label-a> <label-b> [NAME ...]

# Full snapshot diff of one project
git diff --no-index results/<label-a>/<name>/snapshot results/<label-b>/<name>/snapshot
```

| Column | Meaning |
| --- | --- |
| `exit` | Exit code of `scip-java index` |
| `kotlin`, `java` | Tracked source files with a document, out of all tracked files. Modules the build doesn't compile count as missing; per-module numbers are in `metrics.json`. |
| `matching` | References with a definition in the index |
| `dangling` | References without one: broken go-to-definition links |
| `bad_loc` | Malformed `local` symbols |
| `dups` | Documents with duplicate paths |
| `untracked` | Documents whose path isn't a tracked file (wrong source root) |
| `generated` | Documents for generated sources under `build/` |

`matching` and `dangling` count only references to non-local symbols in
packages the index defines, excluding Android `R` and `BuildConfig`. Compare
both when judging a change: indexing more code usually raises both.

Each project's results are in `results/<label>/<name>/`: `index.log`,
`run.json` (exit code, wall time, peak RSS), `index.scip`, `snapshot/`, and
`metrics.json` (per-module coverage, distinct symbol counts, and the 25 most
frequent dangling symbols).

## Adding a project

Add an entry to `corpus.json`: pin `ref` to a commit, set `java` to the JDK the
build needs, and `android` if it has an Android Gradle Plugin module. Leave
`build_command` empty to use scip-java's default, or list Gradle tasks and
flags. Add missing Android SDK platforms or build tools to `androidSdk` in
`flake.nix`.
