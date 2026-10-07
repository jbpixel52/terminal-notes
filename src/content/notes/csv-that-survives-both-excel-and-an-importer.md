---
title: "CSV that survives both Excel and an importer"
description: "Semicolons, a byte-order mark, quoted commas and a blank key column. The spreadsheet format rules that are not in any specification, learned by breaking an import twice."
pubDate: 2026-07-24
tags: [data, tooling, testing]
minutes: 7
ascii:
  piece: heatmap
  caption: "rows and columns, all of them accounted for"
---

Generating a CSV that a person opens in a spreadsheet *and* a system imports
is a small, annoying compatibility problem with no specification that covers
both ends. These are the rules that survived contact.

## Three bytes at the front

UTF-8 text with a byte-order mark (`EF BB BF`) is what a spreadsheet wants in
order to read non-ASCII characters correctly — without it, a name with an
accent or a non-Latin script arrives as mojibake. Most importers are
indifferent to the mark, because they detect the encoding before parsing.

Writing it is one flag in Python:

```python
import csv

with open(path, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["Key", "Summary", "Step 1", "Expected Result 1"])
    writer.writerows(rows)
```

`encoding="utf-8-sig"` writes the mark; `utf-8` does not.
**`newline=""` is not optional**: with it omitted, the `csv` module's own
line endings are translated by the text layer, and on Windows you get a blank
line between every row. The file still looks right in a text editor and
imports as every-other-row-is-empty.

## The delimiter is a locale decision

A comma-separated file opened in a locale where the decimal separator is a
comma is ambiguous, and spreadsheets in those locales read semicolons
instead. Semicolons then become the safer default for a file that a human
will open — which brings the opposite problem:

- a *comma* inside a field is now unquoted-legal but confusing to readers in
  the other convention;
- a *semicolon* inside a field must be quoted, or the row gains a column.

`csv.QUOTE_MINIMAL` quotes exactly the fields that need it. Enumerating
delimiters and quotes by hand is where multi-line "notes" fields go wrong:
an embedded newline inside a quoted field is legal CSV and will break any
tool that reads the file line by line.

## Which is why you count rows, not lines

The classic verification mistake:

```bash
wc -l cases.csv        # 42
```

That is not 42 records. There is a header, there may be no trailing newline,
and a single quoted field containing a newline adds a line while adding no
record. Count with a parser:

```python
import csv
with open(path, encoding="utf-8-sig") as f:
    rows = list(csv.reader(f, delimiter=";"))
print(f"records: {len(rows) - 1}")     # minus the header
```

Compare that against the number of records you *intended* to write, and fail
loudly on a mismatch. The time this mattered: a generator produced 21 rows
from a source document with 22 entries, because one entry was preceded by a
blank line and the paragraph splitter merged it. The import succeeded, the
sheet looked right, and one test case was simply absent.

## The blank key column

When the target system generates its own record identifiers, the key column
has to be *present but empty* — not absent, and not filled with a
placeholder. Two habits make this workable:

- during drafting, write human-readable placeholder keys (`TEST-XXX-01`) so
  the file is reviewable in a spreadsheet;
- in the final export, blank the column entirely and let the importer assign
  keys.

Do this as an explicit, reviewable transformation at export time rather than
by remembering — a placeholder that reaches production is a record with the
wrong identity, and renaming an identifier later is never as easy as it
sounds.

## Types the spreadsheet will guess wrong

Spreadsheets infer types on open, and the inference is silently destructive:

- a code like `0012` becomes the number `12`;
- a long numeric ID becomes `1.23457E+14` in display, and the underlying
  value is now a float;
- a date-like string is reinterpreted in the machine's locale;
- a value that starts with `=`, `+`, `-` or `@` is treated as a formula.

The defensive forms, in order of intrusiveness:

1. quote the field (`="0012"` is a spreadsheet idiom that keeps it textual);
2. prefix with an explicit type marker the importer strips;
3. accept the mangling, and tell people to import rather than open — the only
   option that survives a user double-clicking the file.

## Import into a scratch target first

An import is a write. Run it against an empty project or a staging instance,
then read back: count the records, open two of them, check that a field with
an accent came through, check that a multi-line field kept its line breaks.
The rules above were each discovered by skipping that step, and each cost an
hour of "the file looks fine to me".
