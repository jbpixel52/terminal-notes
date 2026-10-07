---
title: "A backup you have never restored is a hypothesis"
description: "Jobs that exit 0 and write nothing, databases that cannot be copied while running, and the two questions that determine whether a backup strategy is real."
pubDate: 2026-05-02
tags: [backups, storage, homelab, verification]
minutes: 7
ascii:
  art: a-backup-you-never-restored-is-a-hypothesis
---

Everyone has a backup. Almost nobody has a restore. The gap between those two
statements is where all the work is, and it is not the work people enjoy.

## Two questions, asked before anything else

- **How much can I lose?** (recovery point objective) — an hour of photo
  capture, or a week, or nothing at all. This decides how often the job runs.
- **How long can I be down?** (recovery time objective) — an afternoon of
  copying, or ten minutes. This decides whether you need snapshots and bare
  metal, or a directory and a tarball.

Without answers, "backups" tends to mean nightly copies of whatever happened
to be in a folder, kept for an indeterminate time, restored never.

## A backup job can succeed and write nothing

The most common failure in the world of backups is a run that exits `0`. A
wrong path, an exclude pattern that excluded everything, a source directory
that is now empty after a move, a scheduled job that has been running as a
user without read permission and skipping:

```bash
# the run is not the evidence; the snapshot is
restic snapshots --latest 3
restic stats latest
```

The cheap, durable habit is to *record the size and the file count of every
run* and compare against the previous one. An overnight delta of −99% is
identical to a catastrophic mistake, and the only difference between noticing
it tonight and noticing it in three months is a number in a log.

Alert on **absence** as well as failure: no successful backup in 26 hours is a
finding even if nothing reported an error. A cron job on a machine that has
been switched off reports nothing at all.

## A live database cannot be copied, only dumped

Copying a running database's data directory produces a file tree that looks
complete and may restore to a corrupt cluster: pages are being written while
you copy them. For anything transactional:

```bash
pg_dump --format=custom --file=/backup/db-$(date +%F).dump dbname
```

and then prove the dump is restorable, into a scratch database, on a schedule:

```bash
createdb verify_restore
pg_restore --dbname=verify_restore /backup/db-2026-05-01.dump
psql -tAc 'select count(*) from orders' verify_restore   # compare to source
```

The row count is the check. "pg_restore exited 0" is not — it can succeed
while restoring only the objects it understood.

## Scope is the hard part of the inventory

A backup is a claim about a set, so write the set down and check it against
the machine:

- **volumes and named data** — the container's own filesystem is disposable;
  the volumes are not, and they are easy to omit when every example backs up
  a directory;
- **configuration that lives outside a repository** — the reverse proxy's
  config, the scheduler's jobs, the cron entries, the certificates;
- **things that are not files** — database dumps, DNS records, the contents of
  a password manager, the library of a service, DNS zone files, a
  single-factor app's recovery codes;
- **the ignore list** — caches, `node_modules`, media that is expensive to
  copy and cheap to re-fetch.

The test of an inventory is a restore into an empty machine: does the service
come back, or does it start and fail because of one missing file nobody
thought of as data?

## 3-2-1, with the emphasis in the right place

Three copies, two media, one off-site, is the standard and it is right. Two
amendments from experience:

- **A copy on the same disk is not a copy.** Snapshots on the same volume
  protect against deletion, not against the disk dying. Useful, but they are
  version control, not backup.
- **The off-site copy is the one that is never verified**, because it is the
  least convenient to check. Pull a restore *from the off-site copy* into a
  scratch machine at least once, and start by checking that you can decrypt it.

## Encryption, and where the key lives

A backup on a removable disk or in object storage should be encrypted at rest
— and that means the key must not be inside the backup. If the key is in the
copy, the encryption protects nothing except a hypothetical thief who is also
unlucky. Keep the key with the credentials you would need anyway, and write
down what happens if you lose it, because "nobody can decrypt it" is a
different disaster from "the backup is gone".

Incremental snapshot tools (restic, borg and friends) give you two things
worth having: deduplication, so a decade of daily snapshots costs about as
much as the data does, and integrity checks:

```bash
restic check                 # structure
restic check --read-data     # re-read and verify every byte — slow, run rarely
```

Retention should be a policy, not an accumulating pile:
`--keep-daily 14 --keep-weekly 8 --keep-monthly 12`, and then verify that the
pruning did what you think.

## The ritual that makes it real

A restore drill, on a calendar, on the machine it would actually be needed
on:

1. Boot an empty VM or a scratch container.
2. Restore the most recent snapshot.
3. Start the services from the *restored* configuration.
4. Verify with a real check — a query with a row count, a page that renders, a
   file that opens.
5. Write down how long it took, and fix the one thing that was missing.

That last step is the entire point. Every drill I have run has found something:
a service that would not start because of a file nobody backed up, a
certificate that was not in the snapshot, a database that needed a manual
`ALTER` to accept the restored dump. A backup system's real specification is
written by its restores, and each one makes the next one shorter.
