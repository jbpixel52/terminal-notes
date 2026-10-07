---
title: "Spreadsheets built by code lie quietly"
description: "Writing a formula is not calculating it. Cross-sheet references, division by zero and a recalc that never happens — how a generated workbook looks right and is wrong."
pubDate: 2026-02-11
tags: [data, tooling, testing]
minutes: 6
ascii:
  art: spreadsheets-built-by-code
---

Generating a workbook from code is a deliverable people open, trust and quote
from. The failures are quiet, and most of them come from one misunderstanding:
a library that writes workbooks does not have a spreadsheet engine, so it
writes formulas *as text* and never computes a value.

## What that means in practice

```python
ws["B10"] = "=SUM(B2:B9)"        # written
# the file now contains a formula whose cached value is None
```

Open it in a spreadsheet and it calculates. Read it back with the same library
and it is still a string. Feed it to anything that does not calculate — an
importer, a preview, a PDF renderer — and the cell is empty or zero. That
difference is invisible in the tool you developed with, which is the worst
property a bug can have.

## The reference trap

A formula written on one sheet referring to another sheet's cell must be
sheet-qualified:

```
=B15*0.1              # on sheet Options this means Options!B15 — not Takeoff!B15
=Takeoff!B15*0.1      # what was meant
```

Unqualified references silently read the *same* sheet, so the arithmetic uses
zeros, and the ratio columns then divide zero by zero and produce `#DIV/0!`.
Two defences, both cheap:

- build formulas through a helper that requires an explicit sheet name, so an
  unqualified reference cannot be written by accident;
- after generation, scan every cell for a value that starts with `#` — that is
  the entire error surface of a formula-bearing workbook in one loop:

```python
bad = [c.coordinate for row in ws.iter_rows() for c in row
       if isinstance(c.value, str) and c.value.startswith("#")]
if bad:
    raise SystemExit(f"formula errors in {ws.title}: {bad[:10]}")
```

## Recalculate before you ship

The honest check is to have something that calculates, and compare:

```bash
soffice --headless --convert-to xlsx --outdir recalc/ out/report.xlsx
# then read recalc/report.xlsx (now it has cached values) and assert
# the total row equals the sum computed independently in python
```

The independent computation is the important half. If code computes the total
and code fills the cells, asserting one against the other is circular; compare
against a second path — a SQL `SUM`, or the sum of the individual values you
wrote — and assert they agree to the cent.

## Treat the workbook as an artifact under test

Beyond the numbers, three properties are worth asserting because they break
silently:

| property | why it breaks |
| --- | --- |
| the sheet names and their order | downstream tools reference them by name |
| the used range | a stray write at row 500,000 makes the file enormous |
| the number formats | a currency column formatted as text is unusable |

And one habit for anything a person will read: never leave plausible numbers
hardcoded in a template to "fill the space". A workbook that ships with last
quarter's figures in a corner cell will be quoted, and nobody will notice.
