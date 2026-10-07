---
title: "Offline-first sync, and the queue that has to survive a crash"
description: "Local writes, a durable operation log, idempotent replay and a conflict policy you can defend. The parts that decide whether users trust the app."
pubDate: 2026-06-17
tags: [mobile, architecture, databases]
minutes: 8
ascii:
  piece: pond-ripples
  caption: "writes spreading out, arriving eventually"
---

An app that works in a basement with no signal is a different design from an
app that shows a spinner. The difference is not caching: it is deciding that
the local store is the source of truth for the user's session, and that the
network is a delivery mechanism that may be unavailable for hours.

## Two stores, one of them authoritative *now*

The UI reads from the local database, always. It never waits for a response
to render what the user just did, and it never renders a server payload that
may not arrive. The remote store is what everyone else sees; the local store
is what this device believes.

That has a consequence people find uncomfortable at first: for a period, the
local database contains rows the server does not. That is not a bug, it is
the definition of the design — and it means every screen has to be able to
say "not yet synced" honestly.

## Queue operations, not state

The instinct is to sync the current value of each dirty row. This loses
information: if a user renames a record twice, and then moves it, the
intermediate rename is gone, and the order of the operations is gone with it.

Queue the *intent* instead:

```
op_id        client-generated uuid
kind         create | update | delete
entity       "site"
entity_id    client-generated uuid
payload      the changed fields only
at           client time (for display only)
seq          per-device monotonic counter (for order only)
```

Three properties fall out of that list and each one is load-bearing:

- **`op_id` makes replay safe.** A request that times out may still have been
  applied; the retry carries the same `op_id`, and the server upserts on it.
  Idempotency is not an optimisation, it is what lets you retry at all.
- **`seq` orders operations without trusting clocks.** Device clocks are wrong
  (they drift, they get moved, they cross a daylight-saving boundary), so
  ordering by `at` produces reorders that look like corruption. Order by a
  counter the device increments; use time only for display.
- **`payload` holds changed fields, not the whole row.** Sending the whole row
  makes every sync a last-writer-wins overwrite of everything, which silently
  discards a concurrent edit to a field this device never touched.

## The queue lives in the database

Not in memory, not in a JS array, not in the framework's state container. A
process that is killed with thirty pending operations must lose none of them —
on mobile, being killed mid-sync is routine rather than exceptional.

The practical test: put the device in airplane mode, create twenty records,
force-quit the app, reopen it with the network restored, and count what
arrives. If the answer is fifty-nine, the queue was in memory and got
duplicated on restart.

## Deletes need care in both directions

Two cases that a naive queue gets wrong:

- **Create then delete, offline.** Sending both operations means the server is
  asked to delete a row it has never seen. It should treat that as success
  (idempotent), or the client should collapse the pair — ideally both.
- **Delete a row someone else has since edited.** Deciding who wins here is a
  product decision, not a technical one, and it needs to be made explicitly.
  "Deletes always win" and "edits resurrect" are both defensible; choosing by
  accident is not.

## Pick a conflict policy and write it down

Every offline-first system has one, whether or not it was decided. The
spectrum, cheapest first:

| policy | loses |
| --- | --- |
| whole-row last-write-wins | any concurrent edit to a different field |
| per-field last-write-wins | a concurrent edit to the same field |
| per-field with a change log and merge rules | very little, and it costs the most |

Per-field LWW is the usual sweet spot: broadcast the changed fields, compare
per field, and let the server's clock (a clock you control) decide ties. The
part to write down is the consequence — for a *same-field* conflict somebody's
edit disappears, and the UI should be able to show the losing value rather
than pretending it never happened.

## Media is a separate queue with the same discipline

Photos and attachments do not belong in the operation log: they are large,
slow, and fail independently of the data they belong to.

- write the file locally first, and store a local URI in the record;
- enqueue the upload separately, keyed by the same record id;
- keep the placeholder visible in the UI (a tile with a progress state beats a
  broken image);
- retry with backoff, and *verify* the upload rather than trusting the
  response: compare the byte size, or a hash, against what the server reports.

An upload that returns 200 and stores zero bytes is common enough — a
truncated body, a mis-set `Content-Length`, a proxy buffering limit — that
"check the size on the other side" is worth the line of code.

## Failed batches must not lose their tail

If thirty operations go up as one batch and the server fails at item
seventeen, the response needs per-operation statuses. A single 500 for the
batch leaves the client unable to tell what landed, which means either
duplicate writes or lost ones. Batch because it is efficient; report per item
because that is what makes the retry correct.

## Show the state to the user

A hidden sync queue generates "the app lost my data" reports, when what
happened is "the app kept it and never said so". Three states, visible and
small, remove most of that anxiety:

- saved here, not yet sent (count of pending items);
- sending, with a retry affordance rather than an automatic hammer;
- synced.

## Test it by breaking things, on purpose

The scenarios worth scripting, because each one has found a real bug:

- offline writes, then force-quit, then relaunch online;
- two devices editing the same record offline, then both syncing;
- a device whose clock is a day fast;
- a server that returns 500 for one operation in a batch;
- the same operation delivered twice;
- an upload that is interrupted at 90%;
- a sync running while the app is backgrounded and killed.

The verification is not "the local list looks right" — that proves the local
store. It is a *fresh* client, or a direct query of the server, showing the
data that was created in a basement an hour ago.
