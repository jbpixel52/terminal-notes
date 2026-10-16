---
title: "Changing a schema that already has data in it"
description: "A rebuild that cascades away every child row reports success. Why a destructive migration is verified by counting rows, and why a fixture built by hand proves nothing."
pubDate: 2026-10-12
tags: [databases, data, testing]
minutes: 7
ascii:
  art: changing-a-schema-with-data-already-in-it
---

Adding a column is easy. The migration that hurts is the one your engine cannot
express with `ALTER`: renaming a value inside a `CHECK` constraint, changing a
column's type, restructuring a table that other tables hold foreign keys to. On
SQLite none of those have an `ALTER` form, so the only path is a **rebuild** —
create a new table, copy the rows, drop the old one, rename.

The rebuild has a failure mode that looks like success. `DROP TABLE` on a table
other tables reference with `ON DELETE CASCADE` **cascades**: every child row is
deleted. No error is raised, nothing is reported, the migration exits clean — and
the database is empty. It is documented engine behaviour, and it is
indistinguishable from a working migration unless you count rows.

So the centre of the whole procedure is one rule: **a destructive operation is
verified by counting rows, not by reading an exit code.**

## The procedure

1. **Back up, and snapshot the row count of every dependent table** — both at the
   same moment, because those counts are the baseline for everything below. Keep
   the backup out of the repository.
2. **Find every dependent table from the schema and list them in the migration
   by name.** Not from memory: a list in your head is a list that will be wrong
   the one time it matters.
3. **Turn foreign keys off — outside a transaction.** On SQLite
   `PRAGMA foreign_keys=OFF` is a **silent no-op inside a transaction**, and most
   drivers open one implicitly. Take control of the transaction yourself, manage
   `BEGIN`/`COMMIT` explicitly, and restore the previous pragma value in a
   `finally`. Verify the pragma is actually off before the rebuild starts.
4. **Rebuild inside one explicit transaction.** Create the new table, `INSERT …
   SELECT` with the old values mapped in the select, drop the old table, rename
   the new one into place. Recreate any **named** index — a `UNIQUE` constraint
   keeps its implicit index, a `CREATE INDEX` does not, and it will be missing
   afterwards with no warning.
5. **Restore the pragma and check integrity.** Re-enable foreign keys, then run
   `PRAGMA foreign_key_check` and assert it returns nothing. Leaving the pragma
   off silently unguards every later write.
6. **Compare the counts and raise on any difference.** Every dependent table,
   against the snapshot. This is the guard the entire procedure exists for.

## Make it idempotent, because it will run again

Some applications run migrations on every connection open. Guard the work behind
a check that the change has not already happened — typically by inspecting the
stored table definition rather than tracking a version number — and prove it by
running the migration three times in a row and asserting nothing changes.

## The fixture is where the test lies

A migration test whose fixture **hand-stubs** the dependent tables is testing
tables the migration will never meet. It fails on the real schema's own indexes
before it ever reaches the migration, which means a green-looking test proves
nothing at all.

Build the fixture from the real schema creation path, then **downgrade only the
table under test**: drop it, recreate it in the pre-migration shape, seed it, and
let the real migration run over it.

And assert in this order, because the first one is the only one that catches
silent loss:

1. **row counts survive**, per table;
2. the value mapping happened — renamed, not dropped;
3. foreign keys are clean and the pragma is back on;
4. running it twice more changes nothing;
5. the old value is now **rejected** by the new constraint, with an integrity
   error — which proves the constraint was replaced rather than bypassed.

## The same shaped problem in application code

Two cousins of this bug live one level up, and both are quiet:

- **`CREATE TABLE IF NOT EXISTS` does not notice a changed definition.** Change a
  column and the "no-op" statement is a no-op, leaving the old shape in place
  forever. Changing a definition means dropping and re-initialising, deliberately.
- **A new unique index cannot be built over data that already has duplicates.**
  The index fails, or it succeeds and every later insert starts behaving
  differently. Deduplicate explicitly first, and prove the result by loading the
  same batch twice and asserting the row count is identical.

## The general shape

Wherever the engine cannot express a change, the change becomes a copy, and a
copy is a place where data disappears without a message. Count before, count
after, and treat "no error" as noise rather than evidence.
