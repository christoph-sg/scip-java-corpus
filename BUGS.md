# Bugs found by the corpus

Status is **Open**, **Fixed locally** (uncommitted change in the
`kotlin-analysis-api-rebased` worktree, confirmed by a corpus run) or **Fixed
in `<commit>`**. Keep an entry until a corpus run on a pushed commit confirms
the fix. Line numbers are 1-based.

## Kotlin indexer (scip-kotlin-analysis)

1. **Partly fixed in `570c5fab`: references to functions named like a class don't
   match their definition.** In kotlinx-datetime, `public fun UtcOffset(hours:
   Int? = null, ...)` (`core/common/src/UtcOffset.kt:265`) was defined as
   `kotlinx/datetime/UtcOffset(+1).`, but call sites from tests (which see
   `main` as class files) referenced `kotlinx/datetime/UtcOffset().`.
   `DateTimePeriod(...)` had the same problem: 323 broken go-to-definition
   links. Cause: the source path counted every earlier same-named declaration
   in the file, including classes and properties; the binary path counted all
   same-named callables. Fix in `570c5fab` (scip-code/scip-java#1044): both count only
   functions, which also matches javac's numbering of Kotlin members.
   kotlinx-datetime: 327 → 26 dangling references.
   Still open: top-level overloads spread across files. The source path counts
   per file, the binary path per package, so `fun Month(number: Int)` in both
   `common/src/Month.kt` and `jvm/src/MonthJvm.kt` is `Month().` in source but
   `Month(+1).` from tests (22 references, also `DayOfWeek`). Numbering
   members by signature instead was tried and rejected: it breaks Java
   references to overloaded Kotlin members, which scip-javac numbers in
   declaration order.
2. **Fixed in `a4ff5746` (scip-code/scip-java#1044): malformed local symbols.** Members of local declarations got symbols
   like `local 5version.`, `local 5version.get().`, `local 15utoff.`
   (kotlinx-datetime `core/common/src/internal/tz/Tzfile.kt`, `InstantTest.kt`,
   `DateTimeComponentsFormatTest.kt`) and `local 0component1().`,
   `local 0copy().` (Thunderbird, local data classes). SCIP requires
   `local <simple-identifier>`, and `scip snapshot` rejects these documents
   unless run with `--strict=false`. Fix: synthetic members of local declarations
   share the per-document local ID allocator, keyed by owner and descriptor,
   instead of appending global descriptors to local symbols. Generated method
   references use the same IDs as their definitions. Corpus runs
   `bug2-before-570c5fab` → `bug2-after-570c5fab`: malformed local symbols
   kotlinx-datetime 26 → 0, Thunderbird 13 → 0; document coverage and dangling
   reference counts unchanged, with no new undefined local references.
3. **Fixed locally: inherited members are referenced under the subtype.**
   `interface LegacyAccountManager : AccountManager<LegacyAccount>` inherits
   `findById`, but Thunderbird callers reference
   `LegacyAccountManager#findById().`, which is never defined. Other examples:
   `GeneralSettingsManager#getConfig().`, `DrawerViewModel#state.`,
   `*ViewModel#updateState().`. Fix: unwrap external callables with the Analysis
   API's `fakeOverrideOriginal` before computing the owner and overload number.
   Real overrides retain their own symbols. Corpus runs `bug2-after-570c5fab`
   → `bug3-after-a4ff5746`: Thunderbird dangling references 3,313 → 2,308,
   matching 165,765 → 166,710; kotlinx-datetime dangling 26 → 22, matching
   26,011 → 26,013. Document coverage and occurrence counts are unchanged,
   with no new undefined locals. `LegacyAccount#equals().`, previously grouped
   here, is a generated data-class method, not an inherited member. The local
   follow-up emits definitions for generated `equals`, `hashCode`, and
   `toString`, including local data classes, without duplicating explicit or
   inherited final implementations. Overload numbering matches references,
   including `MessageReference#equals(+1).`. Corpus runs `bug3-after-a4ff5746`
   → `data-class-after-ba91d65a`: Thunderbird dangling 2,308 → 2,136, matching
   166,710 → 166,882; kotlinx-datetime dangling 22 → 22, matching
   26,013 → 26,013. Coverage is unchanged, with no new malformed locals,
   undefined locals, or duplicate definitions.
4. **Open: Kotlin property syntax on Java getters references a property.**
   nowinandroid's `NiaPreferencesDataSource.kt:161` reads
   `newsResourceChangeListVersion` from the protobuf-generated Java class
   `UserPreferences`; the reference is
   `UserPreferences#newsResourceChangeListVersion.`, but javac defines
   `UserPreferences#getNewsResourceChangeListVersion().`. Thunderbird:
   `com/fsck/k9/mail/Message#uid.` and `Part#mimeType.` (Java classes in
   `mail/common`).
5. **Fixed in `72c9c4f7` (scip-code/scip-java#1044): extensions on some receivers are defined
   top-level but referenced nested.** The protobuf-generated `UserPreferencesKt.kt:813` declares
   `fun com.google...UserPreferences.copy(block: ...)` (fully qualified
   receiver, Java class). The definition is `datastore/copy().`, callers
   (`ListToMapMigration.kt:29` and others) reference `UserPreferences#copy().`.
   Cause: `UserPreferences` is a Java class in the same module, which the
   Kotlin indexer couldn't resolve before bug 9 was fixed, so the receiver was
   unknown.
6. **Fixed locally: Java references to a Kotlin object's `INSTANCE` dangle.**
   Hilt-generated Java (`DispatchersModule_ProvidesIODispatcherFactory.java:38`)
   references `DispatchersModule#INSTANCE.`, which the Kotlin indexer never
   defines for `object DispatchersModule`. Companions have the same gap:
   `ProgressDialogFragment.Companion` from Java references
   `ProgressDialogFragment#Companion.`. scip-kotlinc on `main` doesn't define
   either. Fix: emit a static-field definition at the object's anchor,
   `Foo#INSTANCE.` for objects and `Owner#Companion.` (or the companion's
   name) for companions; object expressions get none. Corpus runs `all-fixes`
   → `bug6-after`: nowinandroid dangling 385 → 364, Thunderbird 2,005 →
   1,992; other projects unchanged.

## Gradle plugin, new with the Analysis API branch

7. **Fixed in scip-code/scip-java#1045 (open): `buildSrc` and included builds get paths relative to their
   own root.** kotlinx-datetime's `buildSrc/src/main/kotlin/...`,
   nowinandroid's `build-logic/convention/...` and Thunderbird's
   `components/ui/bolt/...` (197 production files) were indexed without their
   directory prefix, because `ScipGradlePlugin` used `project.getRootDir()` as
   source root. Fix: the init script passes the CLI's working directory as
   `scipSourceroot`. This also applies to Java.
8. **Fixed in `80510154` (scip-code/scip-java#1044): Android modules using AGP 9's built-in Kotlin are not
   indexed.** AGP 9 compiles Kotlin without applying a Kotlin plugin, so the
   `hasPlugin("kotlin")` check skipped the source dump. nowinandroid went from
   16/310 Kotlin files to 271/310. Fix: register the dump for every project; it
   already filters by the `KotlinCompile` task class.
9. **Fixed in `72c9c4f7` (scip-code/scip-java#1044): Kotlin doesn't resolve Java classes of the same module.**
   The source dump listed only `.kt` files, so in Thunderbird's `legacy/core`,
   `HtmlSignatureRemover.kt` had no reference to `AdvancedNodeTraversor` (a
   Java class in the same module); the import resolved only up to its package.
   Fix: also list the task's `javaSources`. The indexer still emits only Kotlin
   documents.

## Gradle integration and Java indexing (also on main)

10. **Fixed in scip-code/scip-java#1045 (open): Java in Android modules is not indexed** (issue scip-code/scip-java#177).
    The javac plugin was only attached in `java` plugin projects. Thunderbird:
    56/288 Java files indexed. Fix: in `com.android.*` projects, add the plugin
    jar to the `annotationProcessor` configurations (AGP always passes
    `-processorpath`). Thunderbird: 235/288.
11. **Open: the init script breaks isolated projects.** With
    `org.gradle.isolated-projects=true` (nowinandroid) or the older
    `org.gradle.unsafe.isolated-projects=true` (Thunderbird), configuration
    fails with `Project ':' cannot access 'ext' extension on subprojects via
    'allprojects'`. Workaround in `corpus.json`:
    `-Dorg.gradle[.unsafe].isolated-projects=false --no-configuration-cache`.
    scip-java could pass these flags itself.
12. **Open: `scipPrintDependencies` fails on Android modules.** In retrofit,
    `:retrofit:android-test:scipPrintDependencies` throws
    `java.util.ConcurrentModificationException` after skipping
    `debugAndroidTestCompileClasspath`. Breaks the default command.
13. **Open: `scipCompileAll` requires `compileKotlinJvm` in every multiplatform
    project.** Fails with "Task with name 'compileKotlinJvm' not found" in
    modules without a JVM target: kotlinx-datetime's js test modules, timber's
    Android-only multiplatform library (task `compileAndroidMain`). It also
    never triggers Android compile tasks. Breaks the default command.
14. **Fixed in scip-code/scip-java#1047 (draft): custom source sets don't get the javac plugin.**
    retrofit's `extra` source set fails in `:retrofit:compileExtraJava` with
    `error: plug-in not found: scip`: `-Xplugin:scip` is added to every
    `JavaCompile` task, but the jar is only on the main and test source sets.
    `:retrofit:compileJava` depends on it, so retrofit can't be indexed. Spring's
    multi-release `java21` source set has the same problem, hidden by bug 17.
    Fix: add the jar to every source set's `compileOnly` and processor
    configuration. Run `provider-main` (scip-code/scip-java#1047 on `main`): retrofit exit 0,
    Java 302/307, Kotlin 16/16.
15. **Open: Java class literals and `super` reference undefined symbols.**
    `CoroutineScopesModule.class` (Hilt) and `UserPreferences.class` (protobuf)
    reference `CoroutineScopesModule#class.`; `super.foo()` in generated Glide
    and Hilt classes references `GlideRequest#super.` and
    `Hilt_MainActivity#super.`. Nothing defines these. From the javac indexer,
    probably on main too (not checked).

16. **Main only: scip-kotlinc breaks builds with precompiled script
    plugins.** On `main`, Thunderbird fails to configure:
    `:build-plugin:compileKotlin` reports "Failed to query the value of
    property 'freeCompilerArgs'" because the plugin reads the compiler args
    before `generatePrecompiledScriptPluginAccessors` has run. The Analysis API
    branch doesn't touch compiler args and isn't affected.
17. **Fixed in scip-code/scip-java#1047 (draft): replacing javac compiler arguments silently
    removes the indexer.**
    Spring's `buildSrc/.../JavaConventions.java` calls `setCompilerArgs` in
    `afterEvaluate`, overwriting the `-Xplugin:scip` argument added by
    `ScipGradlePlugin`. After configuration, all six main/test Java compile
    tasks in `spring-core`, `spring-beans`, and `spring-context` lack that
    argument, even though the SCIP Gradle plugin is attached. The build and
    indexing command succeed, but none of these modules' Java sources are
    indexed. Baseline `spring-baseline-5fe1b55a`: 73 Kotlin files indexed
    (all selected production/test/fixture sources; the remaining Kotlin file
    in these modules is a JMH benchmark), 0 tracked Java files, 2,966 matching
    references, and 1,355 dangling references. The 20 Java documents in the
    index are buildSrc sources with incorrect paths (bug 7), not framework
    source coverage. Fix: pass the argument through
    `options.compilerArgumentProviders`, which `setCompilerArgs` doesn't touch.
    The fix exposed bugs 14 and 18, which scip-code/scip-java#1047 fixes as well. Run
    `provider-main` (scip-code/scip-java#1047 on `main`): exit 0, Java spring-core 1,093/1,101,
    spring-beans 579/583, spring-context 1,248/1,250; Kotlin 73 files as in the
    baseline.
18. **Fixed in scip-code/scip-java#1047 (draft): inherited annotation processors hide the javac
    plugin.** The plugin jar is only added to `annotationProcessor` when that
    configuration declares dependencies directly. Spring's
    `io.spring.nullability` applies the Error Prone Gradle plugin, which makes
    `annotationProcessor` extend `errorprone`, so Gradle passes
    `-processorpath` without the jar and `:spring-instrument:compileJava`
    fails with `plug-in not found: scip` (hidden by bug 17 before). Fix: check
    inherited dependencies too.
