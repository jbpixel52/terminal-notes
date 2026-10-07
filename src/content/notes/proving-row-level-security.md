---
title: "Proving row-level security instead of trusting it"
description: "A policy that looks right and enforces nothing: table owners, bypass roles, security definer functions and views. How to test a tenant boundary with three probes per policy."
pubDate: 2026-07-15
tags: [databases, security, testing]
minutes: 8
ascii:
  piece: radar
  caption: "probing the perimeter, from the outside"
---

Row-level security is the mechanism that makes a multi-tenant database safe
when the application's query forgets a `where tenant_id = ...`. It is also
easy to configure in a way that reads correctly and enforces nothing, and the
failure is silent: no error, no log line, just rows the wrong customer can
see.

## The four ways a policy can be inert

**1. The role is the table owner.** In PostgreSQL, a table's owner bypasses
its own RLS policies unless the table is marked `force row level security`:

```sql
alter table orders enable row level security;
alter table orders force row level security;   -- owners are not exempt
```

Without the second line, a policy can be perfect and the owner — often the
migration role, often the same role the application connects as in a
development environment — sees everything.

**2. The role can bypass RLS.** Superusers and any role with `bypassrls`
ignore policies entirely. The realistic hazard is not a superuser: it is the
application connecting as `postgres` in one environment and as a limited role
in another, so the policy is tested in neither.

**3. The policy reads a claim nobody set.** Policies that key off a session
variable — a JWT claim, `current_setting('request.jwt.claims')`,
`current_user` — are only as good as the code that sets it. If the setting is
missing, many such policies evaluate to *null* rather than false, and a null
comparison in a `using` clause fails closed (no rows) while in a `with check`
clause it can fail *open*. Test the missing-claim case explicitly.

**4. The access path bypasses the table.** A view runs with its owner's
privileges, so a view over a protected table exposes everything the view's
owner can see. The query is against the view, the policy is on the table, and
the policy never runs. Recent PostgreSQL has
`create view ... with (security_invoker = true)` to close this; before that,
the workaround is a function with the right privileges, carefully written.

The same applies to functions: a `security definer` function is *designed* to
bypass the caller's restrictions, which is why it must pin its own search path
so a caller cannot shadow the objects it uses:

```sql
create function fn_my_orders() returns setof orders
language sql security definer set search_path = '' as $$
  select * from public.orders where tenant_id = current_tenant()
$$;
```

## Test with the role the application actually uses

The check that matters is not "does the policy exist" but "does a query as
this identity return only what it should". In SQL, assume the identity
explicitly inside a transaction that is rolled back:

```sql
begin;
  set local role app_user;
  set local request.jwt.claims = '{"sub":"user-a","tenant":"a"}';
  select count(*) from orders;            -- expected: only tenant a
  rollback;
```

Three probes per policy, every time:

| probe | expectation |
| --- | --- |
| the allowed case | returns exactly the rows owned by this identity |
| the neighbouring case | returns zero rows belonging to another tenant |
| the boundary case | writing a row tagged to another tenant is *rejected* |

The third is the one that gets skipped and the one that matters most: read
policies and write policies are separate clauses (`using` versus
`with check`), and a table can be perfectly protected on read while happily
accepting an insert that stamps someone else's tenant id.

## Make the probes a script, not a session

Ad-hoc checks are re-run by nobody. A file of assertions that raises an
exception on the first surprise turns a security property into a regression
test:

```sql
do $$
declare n int;
begin
  set local role app_user;
  select count(*) into n from orders where tenant_id <> 'a';
  if n > 0 then
    raise exception 'leak: % rows from another tenant visible', n;
  end if;
end $$;
```

Note what the assertion is: an inequality against the *other* tenant's rows,
not an equality against a magic expected number. Counting a fixed number of
rows makes the test break every time legitimate data changes, which is how
security tests get deleted.

## Inspect what is actually installed

Before testing behaviour, list the state:

```sql
select schemaname, tablename, rowsecurity, forcerowsecurity from pg_tables
 where schemaname = 'public';
select schemaname, tablename, policyname, cmd, roles, qual, with_check
 from pg_policies where schemaname = 'public';
```

Two things fall out of this list immediately: tables with a policy but no
`forcerowsecurity`, and tables with `rowsecurity = true` and no policies at
all — which denies everything and produces a different, confusing bug report
("the app returns no rows").

## The API surface is part of the boundary

If the application reaches the database through an HTTP layer that runs as an
anonymous role, then the anonymous key is a legitimate identity, and requests
made with it hit the same policies as any logged-in user — which is a
feature, and worth testing on purpose. It is also worth testing that a
request with *no* key and a request with an *expired* key are both refused
rather than falling back to something permissive.

Security tests that only exercise the happy identity prove the least
interesting half.
