---
title: "A test suite you can regenerate"
description: "Three hundred cases are a data problem, not a writing problem. Draft with placeholder keys, map coverage as data, and regenerate instead of hand-editing."
pubDate: 2026-02-18
tags: [testing, process, tooling]
minutes: 7
ascii:
  art: a-test-suite-you-can-regenerate
---

A suite of a few hundred cases in a test-management tool becomes unusable for a
predictable reason: every change to the requirements means editing rows by hand,
and hand-edited rows drift from the specification within one release.

## Cases are data; the suite is a generator

The shape that survives contact:

```
test-cases/
  cases.yaml            <- one entry per case: title, objective, steps, expected
  criteria.yaml         <- the acceptance criteria, by id, quoted from the spec
  generate.py           <- cases + criteria -> import file, and a coverage report
  out/cases.csv         <- generated; never edited by hand
```

The generated file is disposable. The source is reviewable in a pull request,
which is the whole point: "the requirements changed" becomes a diff of a few
lines and a re-run, not a session in a web form.

## Draft with real-looking ids

Two conventions keep this workable for humans and machines at once:

- **while drafting**, write placeholder ids (`TEST-XXX-01`) so a reviewer can
  refer to a specific case, and so the file reads like a suite;
- **on export**, blank the id column entirely and let the tool assign keys.
  A placeholder that escapes into the tool is a record with the wrong identity,
  and identities are the one thing that is genuinely painful to change later.

The transformation is explicit and testable: `generate.py --final` blanks the
column, and the check is that the exported file has the id column present and
empty.

## Coverage as a printed number, not a feeling

Each case declares which acceptance criterion it covers, and the generator
prints the matrix:

```
AC-01  ✓ 4 cases   (1 positive, 2 negative, 1 edge)
AC-02  ✓ 3 cases
AC-03  ✗ 0 cases   <-- gap
criteria covered: 11/12
```

That output is the deliverable as much as the CSV is. It turns "we have good
coverage" into an assertion a reviewer can check, and it fails loudly when a
criterion quietly loses its last case. Two related habits: require at least one
*negative* case per criterion that has a validation rule, and mark the cases
that exist only for regression as such, so the count does not grow with
duplicates.

## Re-import must update, not duplicate

The second import is where a generated suite earns or loses its value. Give
every case a stable external reference — a slug from `cases.yaml`, not the
tool's key — and import as an update keyed on that. Then the flow is
idempotent: edit the YAML, regenerate, re-import, and nothing is duplicated.

And when the import format has quirks — a delimiter the tool expects, an
encoding that keeps accented text intact — those belong in the generator, not
in a note to release through the team. The generator is the one place where an
annoying format detail is paid for once.
