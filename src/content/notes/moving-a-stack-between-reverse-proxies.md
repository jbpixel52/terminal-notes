---
title: "Moving a docker stack from one reverse proxy to another"
description: "Both proxies want port 443. The order of the cutover, how to check a route before it is public, and why the labels are not the risky part."
pubDate: 2026-09-12
tags: [docker, networking, servers]
minutes: 7
ascii:
  piece: train
  caption: "same rails, different engine"
---

A reverse proxy that reads Docker labels is a very pleasant thing: a stack
declares `host=app.example.net, port=8080` and the routing table updates
itself. Changing to a *different* label-reading proxy is mostly a text edit —
and it is still the kind of change that takes a site down for twenty minutes
if the order is wrong.

## Labels are the routing table

The important consequence: the routing configuration no longer lives in a
config file you can diff and roll back; it lives in the labels of the
containers that are running right now. Which means:

- Editing a label means recreating the container. The proxy picks it up, and
  so does everything else about that container — including anything that was
  changed inside the running container and never written to a volume.
- A typo does not error. A misspelled `host=` produces no route, and the
  request lands on whatever the default backend is; a misspelled scheme
  produces a 502 to an app that is perfectly healthy.
- Two proxies watching the same Docker socket will both try to claim the
  ports and the certificates.

## The order that works

**1. Bring the new proxy up on a different port, without touching anything
else.** No `443`, no host port publishing for the old one, no restarts of
the stacks under test.

**2. Check every route through the new proxy before it is public.** A
routing table is not correct because the proxy says it loaded; it is correct
when it serves. From another machine on the private network, talk to the
proxy's temporary port and set the `Host` header by hand:

```bash
for h in app.example.net api.example.net admin.example.net; do
  printf '%-24s ' "$h"
  curl -s -o /dev/null -w '%{http_code} %{time_total}s\n' \
    -H "Host: $h" http://10.0.0.12:8080/
done
```

Three lines of output, one per route. A missing route shows up as the
default backend's `404`, which is exactly what you want to see *now* rather
than after the certificate has been reissued.

**3. Only then take the ports.** Stop the old proxy, start the new one on
`80`/`443`, and re-run the loop above against `https://` with certificate
verification left on:

```bash
curl -svI https://app.example.net/ 2>&1 | grep -E '^(\*|HTTP|<)'
```

Watch for the certificate's subject — a proxy serving *a* valid certificate
for the wrong hostname is a common half-broken state, and browsers hide it
while every scripted client fails.

**4. Keep the old labels for a while.** The rollback is a `git revert` of the
compose file plus `docker compose up -d`. That rollback stops being available
the moment you delete the old labels, so delete them in a separate change,
after the new proxy has served real traffic for a full cycle.

## The traps I hit

- **The old proxy is still holding the ports.** `docker compose up -d` for
  the new one logs a bind error, but only in that container's log — the rest
  of the stack comes up green. `docker compose ps` plus a real request is the
  check; the absence of an error message is not.
- **ACME rate limits are not an abstraction.** Cutting over three times in
  an afternoon to fix a label typo can exhaust the weekly limit for a domain
  and leave you unable to issue a certificate for days. Use the staging
  directory while testing, and issue for real once, at the end.
- **Containers get new addresses when recreated.** Anything that pinned a
  container IP — firewall rules, an allowlist, a database host entry —
  breaks silently. Refer to services by their compose service name on the
  shared network and let DNS do the work.
- **Health checks that only check the port.** A proxy answering on `443`
  proves nothing about routing. Check a route, with a hostname, and assert
  on the body.

## What the labels are not

The labels are the boring part: a small, reviewable text change with a
revert path. The risk is all in the *ordering* — who holds the ports, when
certificates are requested, and whether anyone verified a route before it
became the public one. Write the cutover down as four numbered steps and the
migration is a maintenance window instead of an incident.
