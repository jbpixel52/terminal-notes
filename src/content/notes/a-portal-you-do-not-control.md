---
title: "Re-platforming onto a system you do not control"
description: "When the runtime belongs to someone else, your levers are the data model, the integration layer and the API. And the rollback plan is an export, not a revert."
pubDate: 2026-03-04
tags: [architecture, data, process]
minutes: 8
ascii:
  art: a-portal-you-do-not-control
---

Moving a working portal onto a hosted low-code platform is a different kind of
project from a rewrite. You do not own the runtime, the query engine or the
deployment; the platform's opinion is the specification, and your job is to
work out where it agrees with what the business asked for.

## The levers you actually have

- **the data model** — the platform's own shapes (lists, lookup columns,
  choice fields) become the schema. A lookup column is not a foreign key: it is
  a pointer the platform resolves, with its own limits and its own performance
  behaviour.
- **the integration layer** — webhooks, scheduled flows, triggers. This is
  where the application logic ends up, and it is the part nobody versions
  properly.
- **the API** — the escape hatch for everything the platform will not do. The
  moment a requirement genuinely cannot be met in the platform's model, the
  answer is an API call from the platform, not a cleverer workaround.

## The list-query trap

A list query that filters and sorts server-side behaves differently at 500
rows and at 100,000. Platforms with a delegated-query model impose limits: past
a threshold, a filter cannot be pushed to the server, and the query silently
falls back to reading rows and filtering them locally — which works, slowly,
until the page times out. The symptom is a report that "used to be fine".

The defence is to keep hot data in a shape the platform can query efficiently:
indexed columns, denormalised values the filter needs, and archived rows moved
out of the working set on a schedule rather than filtered out of every query.

## Two writers is not a sync

Any migration that runs alongside the old system for a period has two writers,
and unless the direction is declared *per field* you get a fight. For each
field, write down:

- which system owns it (source of truth);
- whether the other side may change it at all;
- what happens when both changed since the last sync.

The pragmatic answer is usually: the old system owns everything the business
still edits, the new system owns what it computes, and the overlap is reduced
to as few fields as possible before cutover. Anything else is a merge function
nobody will maintain.

## Rollback is not a deploy

There is no `git revert` for configuration living in someone else's tenant.
Before cutover, prove you can get out:

```bash
# the export, taken and restored on a scratch tenant before anyone moves
curl -s "$API/export?list=Orders" -o orders-$(date +%F).json
python tools/verify_export.py orders-2026-03-04.json     # counts + field diff
```

An export nobody has restored is the same hypothesis as a backup nobody has
restored. Take one, restore it into a scratch tenant, and compare counts per
list — that rehearsal is also the best way to find the field that does not
survive the round trip.

## Reconcile before you cut over

The check that matters on cutover day is a diff, not a click-through:

| check | expectation |
| --- | --- |
| row counts per entity | equal, or explained line by line |
| per-field hash of a sample | identical for fields the new system owns |
| attachment counts and total bytes | equal |
| the oldest and the newest record | both present |

Sampling a hundred records and hashing their fields finds the mapping bugs
(country codes, date formats, a lookup that resolves to the wrong row) that a
manual walkthrough of ten records will not. And when the numbers disagree, the
disagreement is the finding — resist the urge to explain it away.
