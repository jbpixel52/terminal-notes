---
title: "A successful command is not a successful task"
description: "Exit code 0 proves a program ran, not that anything changed. The habits that catch silent failures: read back, count, and compare against the input."
pubDate: 2026-09-28
tags: [testing, methodology, verification]
minutes: 6
ascii:
  art: a-successful-command-is-not-a-successful-task
---

Most of the expensive mistakes I have made were not crashes. They were
commands that returned success and did nothing, or did something slightly
different from what was asked, and were believed because the output looked
like progress.

## The two categories

There is a real distinction between these, and it decides how much
checking you need:

- **Internal effects** the tool itself can confirm. A file edit where the
  writer has verified the content hash on disk. Believing that is fine;
  re-reading it is theatre.
- **External effects**: anything crossing a boundary — an HTTP write, a
  database `UPDATE`, a file upload, an email sent, a row appended to
  someone else's system. A 200 response is a statement that a request was
  accepted. It is not a statement about state.

For the second category the only evidence is a *read back from the other
side*, and ideally through a different path than the one you wrote with.

## Read back, don't trust the write

The minimal version of the pattern:

```bash
# write
psql "$DB" -c "update orders set state='paid' where id=42;"
# read back — separate statement, separate session
psql "$DB" -tAc "select state from orders where id=42;"
```

If the second command prints `paid`, the write landed. If it prints
nothing, the row does not exist and the first command updated zero rows
while reporting success — which `UPDATE 0` in the output would have told
you, if anyone reads that line.

## Count, and compare the count to the input

This is the habit that has caught the most real errors, and it costs
almost nothing. Any operation over a set should end with a number on both
sides:

```
input rows:    53
written rows:  53
```

The day this stopped being theoretical: a script built a spreadsheet of
test cases from a source document, and the sheet had 21 rows where the
source had 22. Nothing failed. The missing row was the one that had a
blank line above it — a paragraph-break heuristic that only misfired once
per file. A count at the end turns a silent omission into a one-line
failure.

The same rule applies to destructive operations, in the other direction.
`rm -rf` a directory and then assert the target is empty; if you cannot
assert it, you have not deleted it, you have only asked.

## Watch out for the totals the tool tells you

Tools lie about totals in a specific way: they report the page, not the
set. An API that answers with `{"items": [...], "has_more": true}` has
told you that what you have is incomplete. Declared totals —
`reply_count`, `total`, `…and 12 more` — are assertions, and if your own
count disagrees with a declared total, the declared total is not the one
that is wrong by default. Fetch again, or parse the whole thing
programmatically, before writing anything down.

## Verify with a different lens

Where possible, confirm through a second channel that does not share the
first one's bugs:

- wrote a file → `sha256sum` it, or open it with an unrelated reader;
- published a page → request it over HTTP and assert on the returned body,
  not on the build log saying the file was written;
- copied a tree → compare counts and `du -s` on both ends;
- deployed a container → `docker compose ps` for health *and* a request to
  the actual route.

A build that says "complete" and a route that answers 200 with the right
content are different claims, and only the second one is the deliverable.

## The one-line version

If you cannot say what you would read back to prove it worked, you have
not finished the task — you have finished the command.
