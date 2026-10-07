---
title: "Declarative config: the machine is the file"
description: "NixOS as an example of configuring a whole system from one description. Generations, rollback, and the two traps: secrets in the store, and options nobody can name."
pubDate: 2026-07-06
tags: [linux, nixos, config, servers]
minutes: 8
ascii:
  art: declarative-config-the-machine-is-the-file
---

Most servers are a history: a base image, then a series of commands somebody
ran, then a wiki page describing about seventy percent of them. A declarative
configuration replaces the history with a description, and the interesting
part is not the syntax — it is what becomes possible when the description is
the only way to change the machine.

## Build first, then activate

Editing a configuration file on a live system and hoping is replaced by:

```bash
sudo nixos-rebuild test --flake .#web-01     # build and activate
sudo nixos-rebuild switch --flake .#web-01   # activate and make it default
sudo nixos-rebuild boot --flake .#web-01     # take effect on next boot
```

`test` activates a new configuration in the running system without committing
to it as the boot default; `switch` makes it the one that boots; `boot` leaves
the running system alone until the next reboot. That third one is the pattern
for anything risky: build it now, verify, reboot in a window.

The build phase matters more than the activate phase. A typo, a wrong option
name, or a missing package fails *before* anything changes — the running
system is untouched, which is a different risk profile from editing a service
file and reloading.

## Generations are the real feature

Every activation creates a new generation in the boot menu, and the previous
one still boots. That means rollback is not a procedure to remember under
pressure:

```bash
sudo nixos-rebuild switch --rollback    # previous generation, now
# at the boot prompt: pick an older generation and carry on working
```

I have used this to recover a machine that would not bring up its network,
from the bootloader, in about ninety seconds. It is worth more than every
configuration-management nicety combined.

## The two traps

**Secrets in the store.** The Nix store is world-readable and copied to every
machine that shares the closure. A password, token or private key written into
a configuration file lands there in plain text, readable by any user on the
box, and duplicated wherever the configuration is deployed. Secrets need a
dedicated module that decrypts at activation time (there are several) — and
checking `/nix/store` for a string you assumed was secret is a worthwhile
exercise.

**Option names.** The syntax is easy; the naming scheme is the work. Options
are typed and namespaced
(`services.openssh.settings.PermitRootLogin = "no";`), and the error messages
do point at the path you got wrong, but finding the right path requires a
search (`nixos-option`, or the web option search). The pattern is
`<area>.<service>.<setting>`, and the fastest way to learn it is to read the
module you are configuring rather than guess.

## The firewall catches everyone once

A service enabled in the configuration listens on the machine and is *still*
unreachable, because the host firewall is also declared and does not open the
port:

```nix
networking.firewall.allowedTCPPorts = [ 80 443 ];
```

This is the same class of mistake as forgetting an `ufw` rule, with one
advantage: the fix is a line in the same file as the service, so it is
visible in review rather than remembered. Making "the port and the service
are declared together" a habit removes a whole category of afternoon.

## Flakes, and the lock file

A flake pins the inputs (the package set, the modules you import) in a
`flake.lock`, which is what makes "this configuration builds the same machine
in six months" true rather than aspirational. Two habits around it:

- commit `flake.lock` — that file *is* the reproducibility;
- update deliberately (`nix flake update` as its own change, with a rebuild
  and a look at what moved), not as a side effect of rebuilding.

Without the lock, an unpinned input means a rebuild can pull a different
version of something, and you are back to "it worked yesterday".

## Disk space is the cost

Every generation keeps its closure in the store. The design is honest about
this: the price of rollback is disk. Garbage collection is part of the
configuration rather than a cron job someone remembers:

```nix
nix.gc.automatic = true;
nix.gc.dates = "weekly";
nix.gc.options = "--delete-older-than 30d";
```

`nix-collect-garbage -d` is the manual version. Keep enough generations to
roll back a week, not enough to fill the disk.

## What it changes about how you work

- **You debug the description, not the machine.** If the machine is wrong,
  the description is wrong. That is a much smaller search space than
  "something on this host changed at some point".
- **Two machines are identical or they are not.** Differences are lines in
  files, visible in a diff, rather than drift discovered during an incident.
- **One-off tools do not need an install.** `nix-shell -p htop` gives you a
  tool for the length of the command, which quietly removes the "I'll just
  install it and clean up later" excuse.
- **Reading is harder.** A command you would type is now an option you have
  to find, and the learning curve is real. The compensation is that the
  answer is a git history rather than an incident channel.
