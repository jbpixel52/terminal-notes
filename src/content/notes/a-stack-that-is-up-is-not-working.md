---
title: "A stack that is up is not a stack that works"
description: "Compose says Up, the proxy says routed, and nobody can reach it. The probes to run before starting a stack, and the timestamp on that error line you are about to believe."
pubDate: 2026-10-10
tags: [docker, servers, verification]
minutes: 8
ascii:
  art: a-stack-that-is-up-is-not-working
---

A compose file that lives in a repository is not a running stack. Deploying one
is mostly a negotiation with the target host's realities — the devices it has,
the directories it owns, the ports it has free, and the files an application
refuses to start without. Then comes the part people skip: proving it works from
somewhere other than the host.

## Before you press up

**Probe for the devices, cheaply.** A device that does not exist on this host
fails at container *creation*, which means the whole deploy dies before anything
starts:

```bash
docker run --rm --device /dev/dri/card0:/dev/dri/card0 <image-already-present> true
# error gathering device information while adding custom device
# "/dev/dri/card0": no such file or directory
```

Run the same probe against a device the host *does* have, so the syntax is never
the suspect. And prefer the host's own precedent: if another stack on that machine
maps the whole `/dev/dri` directory rather than naming a card, copy it — hosts
differ in which nodes they enumerate, and `card0` is a guess.

**Find out which host the stack belongs to.** Path conventions give it away:
`/mnt/user/...` with `PUID=99`/`PGID=100` is one appliance convention, `/mnt/appdata`
with real UIDs another. A compose file written for a different box references
directories this one does not have. Ask rather than silently retargeting — it may
simply belong on the other machine.

**Write the files an app exits without.** A broker with no configuration file
exits the moment it starts. The trap underneath is not the file, it is the path:
Docker **creates a missing bind-mount source directory as root**, so a config
written to the path you believe the compose references can land somewhere the
container is not looking, and the app crash-loops with "Unable to open config
file". Take the path from the container:

```bash
docker inspect <container> --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}'
```

Ownership has its own second-order trap. A daemon that reads its config as root
and then **drops privileges before opening its password file, log and data
directories** fails with a config that loads perfectly followed by
`password-file: Error: Unable to open pwfile`. The config file can stay
root-owned; the directories it drops into cannot.

`docker compose config` expands and normalises everything the daemon will
receive — labels, port resolutions, rendered device entries — without starting
anything. One second, and it catches the mapping that would have failed after
gigabytes of download. Pull first, separately, so a slow or failed pull is not
confused with a broken stack. And do not run an expensive, known-doomed operation
to re-derive an error a cheap probe already gave you.

## After it starts

`Up` is not success, and `healthy` is not either. What "working" means is that a
client can do the thing the app is for.

- **`Up` reports uptime, not health.** A container that has been up for eleven
  days may have been broken since its last restart. Read the *newest* startup in
  the log and confirm the app reached its own ready line, rather than a tail that
  is eleven days old.
- **Check the timestamp on every error line before attributing it to this run.**
  A log that spans a restart still contains the previous process's death rattle.
  `docker logs --since <window>` over a restart will happily show you errors from
  the run you already fixed, and `grep -c` will hand you a count of a dead
  process's last words. Compare against the container's start time and quote
  timestamps when you report a number.
- **Drive it the way a user does.** Follow the redirects the app issued, then
  fetch the URLs it emitted. Hand-crafted requests return 200 while the real page
  is broken, and a 200 on `/` is usually just the login page. Prove auth gates by
  checking the identity the app returns, or the status of a file that needs it.
- **Verify from a different machine than the host serving it.** A host always
  reaches its own service over loopback. That check proves nothing about
  reachability. And if the client has a VPN or mesh-network client installed but
  stopped, a stale resolver entry can still hand back a private address, so
  everything fails and the deployment looks broken — force the real address with
  `curl --resolve <host>:<port>:<ip>` before blaming the stack.
- **If the error names a file the app cannot open, test the primitive in the
  app's own directory and in a control directory.** Working in one and failing in
  the other means the mount, not the application.

## The layer in front

An app can be running and answering locally while rejecting every proxied
request, because it refuses to trust proxy headers until it is told to. The
symptom wears many faces — a bare `400`, a login loop, a security interlock — and
the isolation is always the same pair:

```bash
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:<port>/
curl -s -o /dev/null -w '%{http_code}' -H 'X-Forwarded-For: 203.0.113.9' \
     -H 'X-Forwarded-Proto: https' http://127.0.0.1:<port>/
```

Plain 2xx with header-carrying 4xx is the app's trust configuration, not the
proxy. Then read the app's own source for the message it logs, because it names
the exact condition — and remember it usually gates on the **connecting** address,
which behind a published port is the compose gateway, not the user.

## The general shape

The deploy is the easy half; the verification is the deliverable. Every item
above is a claim that was true of a container and false of the service: running,
healthy, routed, up. The only sentence worth putting in a status report is the one
a second machine already proved.
