---
title: "A UNIQUE index that does not deduplicate"
description: "SQLite treats NULLs as distinct, so INSERT OR IGNORE becomes a plain insert and the table multiplies on every run. Expression indexes, idempotency tests, and WAL in a synced folder."
pubDate: 2026-02-04
tags: [databases, data, testing]
minutes: 6
ascii:
  art: a-unique-index-that-does-not-deduplicate
---

A loader that ran every few minutes produced a table with 104 rows for 26
records, and every count downstream was inflated by exactly four. The
constraint was there, it was correct-looking, and it did nothing:

```sql
UNIQUE (post_id, profile_id, kind, reaction_type)
```

## NULL is not equal to NULL

In SQLite — and in SQL generally — two NULLs are not considered equal, and a
UNIQUE constraint only rejects rows that *conflict*. If `reaction_type` is
NULL, the row conflicts with nothing, every time. So:

```sql
INSERT OR IGNORE ...   -- silently becomes INSERT
```

The fix is an expression index, which turns the NULL into a comparable value:

```sql
CREATE UNIQUE INDEX engagers_unique
  ON post_engagers (post_id, profile_id, kind, COALESCE(reaction_type, ''));
```

`COALESCE` is also the honest modelling choice: "no reaction type" is a
*value* in this data, not an absence, and the schema should say so.

## Prove idempotency by running it twice

The test that catches this class of bug is not about the constraint, it is
about the loader:

```python
n1 = load(path); count1 = db.execute("select count(*) from post_engagers").fetchone()[0]
n2 = load(path); count2 = db.execute("select count(*) from post_engagers").fetchone()[0]
assert count1 == count2, f"loader is not idempotent: {count1} -> {count2}"
```

Two runs, one assertion. It found the bug in one line where reading the schema
had not, and it protects every future change to the loader.

## Counts of distinct things, not rows

The same class of error appears whenever a number is reported: the count of
notes, of people, of pages. `COUNT(*)` over a joined-and-multiplied table is
not the count of the thing anyone is asking about. Where the answer should be
"how many *distinct* X":

```sql
select count(distinct profile_id) from post_engagers;   -- people
select count(*) from (select distinct post_id from post_engagers);  -- posts
```

Write the ambiguity down where the number is produced, so the report says which
of the two it means.

## WAL, and the folder that syncs

One adjacent trap, learned the hard way: SQLite in WAL mode keeps a `-wal` file
beside the database, and a background sync daemon that copies files mid-write
can capture an inconsistent pair. On a cloud-synced folder, use
`journal_mode=delete` and batch writes, or keep the database outside the synced
tree entirely. Incremental changes to hundreds of small files are also what
makes a sync client choke; writing a few large archives is faster and safer, for
the same reason a backup of two million small files is slower than one big one.
