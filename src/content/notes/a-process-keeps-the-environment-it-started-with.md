---
title: "A process keeps the environment it started with"
description: "Config that looks right in the file and wrong in the running process: named providers, an error from the far end that proves the route, and the daemon that never saw your new key."
pubDate: 2026-10-15
tags: [config, tooling, debugging]
minutes: 7
ascii:
  art: a-process-keeps-the-environment-it-started-with
---

Pointing an agent at a new model provider is a small configuration change with a
large blast radius, because three different things can be wrong at once and they
produce the same symptom: a request that fails. The file, the route, and the
process. Each one has a check that distinguishes it, and I have now spent the time
on all three.

## The file: a proxy is not a bare custom endpoint

An OpenAI-compatible proxy — a gateway that re-serves many models behind one
address — is not configured by setting a base URL at the top level. That shape
carries no credential and dies immediately with a message about resolving a
provider *without credentials*. It wants a **named entry** under `providers:`,
with its own base URL and a key that comes from the environment rather than the
config file:

```yaml
providers:
  gateway:
    base_url: "http://gateway:4000/v1"
    key_env: GATEWAY_API_KEY
    session_affinity_header: x-gateway-session-id
```

…and the model's provider set to that name. Two details from the same afternoon:
unset the old top-level base URL and key name when you switch, or the stale route
and key linger and contradict the named entry; and expect the client to log the
route as `provider=custom` anyway, because that is what a named proxy *is*.
`provider=custom` in a log line does not mean your named entry was bypassed.

## The route: an error from the far end is evidence for the path

Here is the one I keep having to relearn. With the key missing, the request does
not fail locally — it returns the **proxy's own** 401, with the proxy's wording,
in the proxy's format. That is not a broken route; it is the strongest possible
proof that the route works. A local configuration error cannot produce a remote
server's error message.

The inverse trap is subtler: a failing probe is not always a failing service. One
endpoint looked like it was rejecting auth until it was probed with the *correct*
key — at which point it returned a model list and a live answer. A probe built on
the wrong credential produces a confident, wrong conclusion about someone else's
service, and the correction has to be said as plainly as the original claim.

Then the third layer: the model identifier you set is not a request for a model,
it is **a lookup key in the proxy's own list**. A vendor-prefixed slug that looks
right everywhere else fails with a model-not-found *after* auth passes, because
the proxy has never heard of that name. When the id and the proxy disagree, the
proxy wins, and the error only appears once everything else is correct.

## The process: the daemon started before your credentials existed

The best one, because it is invisible in every file. A long-running service — a
gateway, a worker pool, a scheduler — reads its environment **at start**. Add a
credential to the environment file afterwards and the file is correct, the
interactive shell is correct, and every request routed through the daemon still
fails, because the daemon is holding the environment it woke up with. New
sessions launched by hand work; the daemon, the bots and the cron jobs do not.

The fix is a restart, and the lesson is a general one: after changing
credentials, **restart everything that was already running**. "It works from my
shell" and "it works from the daemon" are different claims about different
processes, and only one of them is the one users hit.

## Verify with a turn, not with a grep

Configuration verification keeps trying to become text matching — grep the file,
confirm the key is present, declare victory. The only check that means anything is
a real request through the real path, with the answer read back:

```bash
hermes chat -q "reply with the single word: pong"
```

Which came back `pong`, from the intended model, through the proxy, in seven
seconds. Keep the previous endpoint reachable as its own named provider with a
short alias, so a rollback is a one-word switch instead of a re-edit — and verify
*that* with a turn too.

## Two habits that make this survivable

**Back the file up before you edit it, with the change in the name.** A config
file touched by more than one process is a file you will want to diff, and a
timestamped copy next to it costs nothing.

**Do not adopt changes you did not make.** The same file contained entries
written by the running service's own startup — unrelated integrations, a
newly-enabled toolset. They were not mine, they were not wrong, and the correct
move was to flag them and leave them alone rather than tidy them away. A config
file is shared state; the diff is the source of truth about who changed what.
