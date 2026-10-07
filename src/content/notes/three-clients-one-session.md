---
title: "Three clients, one session, and the one that must not be there"
description: "A server-rendered app on a database that enforces row-level security needs three separate clients. Using the wrong one in the wrong place fails quietly, not loudly."
pubDate: 2026-03-18
tags: [databases, security, web, testing]
minutes: 7
ascii:
  art: three-clients-one-session
---

An app that puts a hosted Postgres with row-level security under a
server-rendered front end has a deceptively small amount of wiring to get
right, and every mistake in it produces the same symptom: a page that works
locally and returns nothing — or too much — in production.

## The three roles, and where each one belongs

| where | which client | why |
| --- | --- | --- |
| server components, route handlers | the one bound to the request's cookies | it carries the user's session, so policies see the user |
| the browser | the public/anonymous client | it ships to the client anyway; RLS is the boundary, not secrecy |
| middleware / a route handler | the cookie refresher | tokens expire, and a server component cannot write cookies |

The classic bug is using the *browser* client inside server code. It runs as
the anonymous role, so every policy that filters by user identity evaluates
against nobody — and depending on the policies that means an empty list
(fails visibly) or the whole table (fails invisibly, and badly).

## What is and is not a secret

The public client key is not a secret; it is in the bundle, by design, and the
security model is that it can only do what the policies allow. The *service*
key is a different animal: it bypasses row-level security entirely. Two habits:

```bash
# after a build: the service key must not appear in anything shipped
grep -rIl "service_role\|SERVICE_KEY" dist/ || echo "clean"
```

and proving the boundary from the outside rather than trusting the config:

```bash
# the same query, three identities, three expectations
curl -s "$API/rest/v1/orders?select=id" -H "apikey: $ANON"          | jq length   # 0
curl -s "$API/rest/v1/orders?select=id" -H "apikey: $SERVICE"       | jq length   # all of them
curl -s "$API/rest/v1/orders?select=id" -H "apikey: $ANON" -H "Authorization: Bearer $EXPIRED" | jq length
```

An empty result and a refused result are different outcomes, and the tests
should expect the right one for each identity: an expired token must be
*refused*, not treated as anonymous.

## Cookies are read-only where you would like to write them

A session refresh writes a cookie, and a server component rendering a page
cannot do that. So the refresh belongs in middleware (or an explicit route),
and the failure mode of putting it in the wrong place is a user who is logged
in for one render and anonymous on the next navigation — intermittent, and
easy to blame on the cache.

Two related rules that save time:

- **Every cache key needs the identity in it.** A server-side cache keyed by
  URL alone will serve one user's rows to another. If the cache is per-request,
  say so in the code, loudly.
- **Verify with two users, not one.** The test that finds this class of bug is
  "log in as A, fetch, log in as B, fetch the same URL, assert the sets
  differ", and it has to run against the real deployment shape, not a local
  fixture.

## Where it shows up

Not as an exception. The symptoms I have chased:

- a list that renders empty for a signed-in user, because the query ran as
  `anon` and the policy asked for `auth.uid()`;
- a detail page that 404s, because a policy returned zero rows and the code
  treats "no rows" as "not found" rather than "not allowed";
- a dashboard that shows everything once, on the request where the session
  had not been attached yet — and never again, so nobody believes the report.

The fix is almost always structural rather than a policy edit: put the session
where the query can see it, and test it as two different people.
