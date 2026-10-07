---
title: "The conflict you resolve is the one you cannot see"
description: "Rebase swaps what 'ours' means, lockfiles should be regenerated rather than merged, and a file can be 'resolved' with its conflict markers still inside it."
pubDate: 2026-06-26
tags: [git, workflow]
minutes: 7
ascii:
  piece: maze
  caption: "two paths through the same history"
---

A merge conflict is a state machine with a few sharp edges. Nothing here is
obscure; all of it is forgotten between occurrences, at the exact moment when
a repository is half-merged and everyone is waiting.

## Know which operation you are in the middle of

There are several, and they have almost the same shape and different exits:

| marker file | operation | ways out |
| --- | --- | --- |
| `.git/MERGE_HEAD` | a merge | `git merge --abort`, or resolve and `git commit` |
| `.git/rebase-merge/` | a rebase | `git rebase --continue`, `--skip`, `--abort` |
| `.git/CHERRY_PICK_HEAD` | a cherry-pick | `git cherry-pick --continue`, `--abort` |
| `.git/REVERT_HEAD` | a revert | `git revert --continue`, `--abort` |

`git status` prints the current operation and the suggested next command, and
it is the only reliable map. Working out the state from the files themselves
is how people end up in a detached HEAD with a half-applied change.

## In a rebase, "ours" is the other branch

Conflict markers are always labelled `HEAD` and the incoming side. In a merge,
`HEAD` is your branch and `--ours` means your version. **In a rebase, Git
replays your commits onto the upstream branch, so `HEAD` is the upstream:**
`--ours` is the *other* branch's content, and `--theirs` is yours.

Getting this backwards is the classic way to resolve a conflict by confidently
deleting the work you were trying to keep:

```bash
git checkout --ours  -- path/to/file     # merge: your branch
git checkout --theirs -- path/to/file    # merge: the incoming branch
```

There is no flag that fixes this for you. When it matters, read the diff
before taking a side, and check the two sides with:

```bash
git log --merge -p -- path/to/file       # only the commits that conflict
git show :1:path/to/file                 # the common ancestor's version
git show :2:path/to/file                 # stage 2 = one side
git show :3:path/to/file                 # stage 3 = the other
```

`--ours`/`--theirs` is only correct when *one* side changed the file. If both
sides changed it, taking either side discards the other's work silently, and
the conflict is precisely Git telling you that happened.

## A file can be "resolved" with markers still in it

`git add` is a declaration: it says "this file is how I want it". Git does not
check the file for `<<<<<<<` — nobody does. The cheap, high-value check:

```bash
git grep -n -E '^(<<<<<<<|>>>>>>>|=======)$'
```

Run it before every commit that resolves a conflict, and wire it into a
pre-commit hook if conflicts are frequent. A stray marker in a YAML file
produces a syntax error at runtime, in the environment where you least want to
find it.

## Lockfiles: regenerate, do not merge

A dependency lockfile is a generated artifact and a merge of two generated
artifacts is meaningless. Take either side, then rebuild it:

```bash
git checkout --theirs package-lock.json      # any side, it does not matter
npm install                                  # regenerate from package.json
# or, for a strict lockfile workflow: npm ci after taking the merged manifest
```

The same applies to lockfiles in other ecosystems, and to any file a tool
generates. Merging generated files by hand is one of the few operations that
can produce a state nothing can reproduce.

## Verify a resolution, do not assume one

A merge that commits cleanly can still be wrong — that is the entire failure
mode. Two checks:

```bash
# what did this merge change relative to each parent?
git diff --stat HEAD^1
git diff --stat HEAD^2

# and the only real check: does the result still work?
<build> && <test>
```

A resolution that compiles is not a resolution that is correct; a resolution
that passes the test suite usually is. If the conflict touched a test and the
implementation, be suspicious of a "clean" resolution — it means Git could
merge both, not that they agree.

## Reduce how often this happens

Conflicts are proportional to divergence. Practical habits:

- merge or rebase the main branch *into* long-lived work regularly, in small
  steps, rather than once at the end;
- keep changes to generated files out of feature branches;
- prefer many small commits on a short-lived branch over one architectural
  commit that touches everything;
- when you must rewrite published history, use
  `git push --force-with-lease` rather than `--force`, so that a colleague's
  newer work is not silently deleted by your push.

## The one-line version

`git status` tells you what you are in the middle of; `git grep` for markers
tells you whether you are finished; running the tests tells you whether you
were right.
