---
title: "Making a single-tenant app hold many tenants"
description: "Adding a tenant column is the easy part. Jobs, caches, unique constraints and file paths are where a conversion leaks rows between customers."
pubDate: 2026-03-11
tags: [databases, architecture, security]
minutes: 8
ascii:
  art: multi-tenant-by-default
---

Converting an application built for one customer into one that holds many is
usually described as "add a tenant id to every table". The column is an
afternoon. The rest is a search for every place where the application assumed
there was only one world.

## The boundaries that are not tables

Enumerate these before writing any migration, because each one is a separate
leak:

- **background jobs.** A cron worker has no request, so it has no "current
  tenant". Make it explicit: iterate tenants, or store the tenant on the job row
  and set it when the job starts. A job that queries without a tenant sees
  everyone's data and writes to whoever it finds first.
- **caches.** Any cache keyed by something that is not tenant-scoped will serve
  one customer's value to another. The key needs the tenant, and so does the
  invalidation.
- **unique constraints.** `unique(email)` becomes `unique(tenant_id, email)`, or
  the second customer cannot invite the same person. The same applies to slugs,
  reference codes and invoice numbers, which now need a per-tenant sequence.
- **file storage.** Every path gets a tenant prefix, and the access check moves
  from "the file exists" to "this tenant owns this path".
- **search and reporting.** An index needs the tenant as a filterable field, and
  every report needs a tenant parameter that cannot be omitted — make it a
  required argument rather than an optional filter.
- **the admin axis.** A customer's administrator and the platform's operator are
  different roles with different reach. Conflating them means every customer
  admin is a platform admin.

## Order of migration

The migration itself is boring if it is done in three steps instead of one:

1. add the column, nullable, with a default for existing single-tenant rows;
2. backfill and make it non-null, with the constraint added last;
3. only then add the composite unique constraints and the indexes that use the
   tenant as their leading column.

Adding a `not null` column without a safe default locks a table, and adding a
constraint before the backfill fails on the rows the backfill has not reached
yet. Both are avoidable by doing the boring version.

## Proving it, per endpoint

The verification that actually catches the leaks is a probe per endpoint with
two identities, expecting zero overlap:

```sql
-- as tenant A, ask for something that belongs to B
begin;
  set local role app_user;
  set local request.jwt.claims = '{"tenant":"a"}';
  select count(*) from invoices where tenant_id = 'b';   -- must be 0
  select count(*) from invoices;                          -- must equal A's rows
rollback;
```

Automate that as a loop over every table with a tenant column, and add one
job-level check: run the worker as tenant B and assert it wrote nothing to A.
A per-endpoint count diff is worth more than any amount of reading policies.

## The allowlist of genuinely global things

Some tables are global on purpose — currencies, countries, plan definitions,
feature flags. Write the list down in one place, with a reason per row, and let
the leak test skip exactly those. An allowlist makes "no tenant column" a
deliberate decision rather than a thing nobody has got to yet, and the next
person to add a table has something to copy.
