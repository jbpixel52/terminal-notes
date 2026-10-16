---
title: "The version bump that deletes the mappings"
description: "A game dropped obfuscation and the whole mapping ecosystem collapsed with it. Porting a mod when the platform changes its contract: read the shipped jar, not the docs."
pubDate: 2026-10-09
tags: [modding, tooling, testing]
minutes: 8
ascii:
  art: a-version-jump-that-deletes-the-mappings
---

Most version upgrades are annoying in the ordinary way: some signatures moved, the
build tool got a new major, and the compiler tells you everything it knows. Every
few years a platform changes its *contract* instead, and then the compiler cannot
help you, because the thing you were compiling against no longer exists.

This one arrived as a single line in the release notes — the game stopped
obfuscating its own code — and it took the entire modding toolchain with it.

## What actually broke

- **The mappings ecosystem evaporated.** For years, mods compiled against
  human-readable names produced by community projects, and against the official
  mappings as a fallback. Both are gone for the new line: the version manifest
  carries **no `client_mappings` entry at all**, the community mapping project
  publishes nothing, and the parameter-name overlay stops at the previous
  release — `parchment-26.2` does not exist.
- **The mappings dependency must be deleted, not emptied.** An empty mappings
  configuration fails with `Configuration 'mappings' has no dependencies`; the
  official-mappings call fails with `Failed to find official mojang mappings for
  26.2`. Deleting the *line* is the fix; there is no valid spell for it.
- **Mod dependencies stop being remapped.** `modImplementation` becomes plain
  `implementation`, because nothing is being remapped any more.
- **The plugin identity changed**, and it is published for a much newer toolchain
  than before: the Gradle plugin targets JVM 25 and a plugin API version above
  the Gradle you are probably running.
- **The language level moved to 25, and it applies to the build, not just the
  mod.** That is the one that costs an afternoon: the plugin cannot even load on
  the older JDK, so the wrapper fails with an error that says nothing about Java.
  When a Jenkins-and-Gradle-adjacent build insists a JDK is missing, check whether
  a previously auto-provisioned one is a **broken partial install** — a `lib/`
  directory with no `bin/`.

## When the docs are gone, the artifacts are the docs

Without generated names, the shipped jar is now readable, which sounds like a
gift and is mostly a change of method. `javap` against the real artifact answers
every signature question exactly, including the ones no changelog mentions:

```bash
javap -p -cp client.jar net.minecraft.resources.Identifier
javap -p -c -cp client.jar <Class>   # -c when you need to see whether a
                                     # parameter is used unconditionally
```

Dump the classes you touch into files once and grep them, rather than one call per
symbol. On Windows, give the tool **native paths and semicolon separators** — the
Unix-style paths a shell accepts are not translated for native binaries.

The renames are then mechanical but numerous: a resource-identifier class renamed
with all its methods intact, `Protocol`-registration methods renamed on both
directions, `getX()` accessors returning `Optional` where they used to return a
default, the whole integer op-level API replaced by a permission object, and the
client's screen-rendering entry point replaced by a *state extraction* hook —
which is a different idea, not a rename.

## The persistent-data change nobody tests for

The biggest single change was not a name. Saved data stopped declaring its own
`save`/`load` and moved to a codec plus a data-fixer type:

```java
SavedDataType<T> TYPE = new SavedDataType<>(id, T::new, CODEC, DataFixTypes.X);
T data = server.overworld().getDataStorage().computeIfAbsent(TYPE);
```

Three facts that only show up at runtime:

- the identifier's **path** decides the file name (`data/<path>.dat`);
- the fixer type **may not be null** — the reader calls it unconditionally, so you
  need a real constant rather than "none";
- the new writer nests the codec output under a `data` key and stamps a version,
  so **a file written by the old build is not read by the new one.** Registrations
  do not survive the jump. Re-register after upgrading a world.

A codec that compiles is not a codec that loads. The test that proves it is a
**restart**: run the server against a fresh world, write the data, stop, start
again on the same world, and read it back. That second boot is the only pass that
exercises the loading path.

## The dev server that pauses itself

A quiet trap for any tick-driven test harness: the dedicated server **stops
ticking** when no player has been online for a while. The log says it plainly —
`Server empty for 60 seconds, pausing` — and the run simply stops mid-test, with
a process that never exits. Force the setting to zero in the dev run directory,
and know the cleanup consequences: killing an orphaned server can leave file
locks behind, so `rm -rf run-server` fails silently and a chained re-run never
starts. `jps -l` finds the survivor.

## Say what you did not verify

The port ends with a list, and the list is the honest part. Anything data-driven
that was measured against the *old* version — a hand-built table of font widths, a
layout constant, a tuned timing — is not validated by a successful compile. It
compiles because the types match, and it can still be wrong in the only place it
is used. Those items go in the results as explicit unknowns rather than being
implied by a green build.
