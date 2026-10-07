---
title: "Reaching a private service over a tailnet"
description: "The service was listening on loopback only, so joining the private network changed nothing. Tunnels, firewalls, DNS and the checks that tell relayed from direct."
pubDate: 2026-08-27
tags: [networking, security, homelab]
minutes: 6
ascii:
  art: reaching-a-service-over-a-tailnet
---

The pitch of a mesh VPN is that you stop opening ports: each machine gets
an address on a private overlay network, and anything on that network can
reach anything else that allows it. It is genuinely that good, and it can
still take an hour the first time, because *joining the network is not the
same as being reachable on it*.

## Three things have to be true

1. The device is on the tailnet and its key has not expired.
2. Something is listening on an address the overlay can reach.
3. The host's own firewall allows traffic arriving on the overlay interface.

Each has a distinct symptom, and they are easy to confuse because all three
look like "the connection times out".

```bash
tailscale status              # is it up, and are the peers listed?
tailscale ip -4                # this node's overlay address
ss -lntp | grep 8080           # what is actually listening, and on which address
```

That last command is the one that explains the most. A service bound to
`127.0.0.1:8080` is reachable only from inside the machine, no matter what
address the network hands out. `0.0.0.0:8080` is reachable from every
interface — including the public one, if there is one, which is exactly the
outcome the overlay was supposed to avoid.

## The safe pattern: proxy, don't rebind

Rather than moving the service onto a public interface, put the overlay's own
proxy in front of it and leave the application on loopback:

```bash
# serve a loopback service to the tailnet only (no public exposure)
tailscale serve --bg 8080
sudo ufw allow in on tailscale0
```

Two properties worth appreciating: the application keeps its
localhost-only assumption (which is often load-bearing for its own security
model), and the exposure is a deliberate, removable command rather than an
address it happens to bind.

## The firewall rule people miss

A host firewall with a default-deny policy drops packets arriving on the
overlay interface like any other. The fix is per-interface, not per-port:

```bash
sudo ufw allow in on tailscale0      # ufw
# nftables: iifname "tailscale0" accept
```

Granting the port on all interfaces is the mistake that turns "private
service on the tailnet" into "service on the internet".

## Relayed or direct?

A tailnet connection is either a direct path between the two machines or
relayed through an intermediary when NAT traversal fails. The difference is
latency and throughput, and it is one command to see which you have:

```bash
tailscale ping other-host      # says "via DERP" or "direct" per attempt
tailscale netcheck             # what the network looks like from here
```

Persistently relayed connections mean the two ends cannot find a shared
path — usually a symmetric NAT or a restrictive firewall on one side. This is
worth diagnosing rather than living with: a relayed link behaves like a
long-haul connection for everything, including SSH keystrokes.

## DNS and names

Overlay DNS only works if the client is using it: the machine names resolve
inside the tailnet and nowhere else, and a corporate resolver or a
`/etc/resolv.conf` managed by something else can shadow them. When a name
does not resolve, the device is not broken — use the address, and fix the
resolver setup separately.

## Keys expire

Nodes have rotating keys, and an unattended server that is not set to
"disable key expiry" will drop off the tailnet silently at some point,
months later, with no evidence on the machine itself. If a host is supposed
to be reachable forever, that is a setting to change when it is joined, not
a debugging session to have later.

## The verification that counts

From a *second* node — not from the host itself, where every localhost
request succeeds — prove the service is reachable, and prove it is not
reachable from anywhere it should not be:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' http://10.0.0.31:8080/
# and from the public interface of the host, which must fail:
curl -sS --max-time 5 -o /dev/null -w '%{http_code}\n' http://198.51.100.7:8080/ || echo "refused (good)"
```

Reachability without the negative test is half a check. The interesting
claim is never "it works" — it is "it works *and nothing else can get in*".
