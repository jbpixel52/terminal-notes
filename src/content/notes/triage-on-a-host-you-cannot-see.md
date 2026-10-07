---
title: "Triage on a host you cannot see"
description: "Fixing a Linux server over SSH, with no console and no second opinion. The first five commands, the failure modes that look alike, and the fix nobody verifies."
pubDate: 2026-08-10
tags: [linux, servers, debugging, ssh]
minutes: 8
ascii:
  art: triage-on-a-host-you-cannot-see
---

A remote host gives you a shell and no keyboard. Every diagnostic has to be
typed, so the order of the first five commands matters more than the depth of
the twenty-fifth.

## First, classify the failure

Before logging in, work out *which* failure you have, because they are not
the same problem:

| symptom | means |
| --- | --- |
| name does not resolve | DNS, not the host |
| `Connection refused` | something answered, nothing listening on that port |
| timeout, no reply | firewall, wrong address, or the host is down |
| `Permission denied (publickey)` | the network is fine; it is auth |
| `Connection closed by remote host` | the host answered and then dropped you |
| hangs after auth | shell startup, disk, PAM, or resource exhaustion |

`ssh -vvv` prints the stage it reached, which separates "cannot reach" from
"reached, rejected". The last two rows are the interesting ones: a host that
accepts TCP and then closes is usually out of memory (the forked child
cannot start), out of disk (it cannot write its own session), or failing PAM.
The nastiest variant is a timeout when everything is healthy — that is often
a host-side ban from its own intrusion-prevention tooling, and it looks
exactly like a network problem.

## The five commands

```bash
uptime                      # load, and how long since boot
free -m                     # memory: look at 'available', not 'free'
df -h                       # every mount, not just /
systemctl --failed          # what the init system already knows is broken
journalctl -p err -n 60 --no-pager
```

Those five find a surprising share of real incidents. The reason to start
here rather than with the application's own logs is that the application's
logs are usually a *symptom*: "cannot connect to database" is rarely a
database problem.

## Full disk breaks everything, confusingly

The single most common remote emergency, and it never announces itself as
"disk full". Instead:

- `systemd` cannot write its journal, so logging stops and the *cause*
  disappears from `journalctl`;
- `sshd` cannot write a temp file for the session, and connections close
  right after authentication;
- the database refuses to start with a message about a lock file;
- `apt` fails with an unrelated-looking hash or I/O error.

Two traps inside the trap:

- **Check the mount that matters.** `df -h /` is clean while `/var` or
  `/srv` is at 100%; those are separate filesystems on any host someone
  configured properly.
- **Deleted files still hold space.** A process writing to a file that has
  been `rm`'d keeps the blocks allocated until the process closes it. `df`
  says full, `du` says the directory is small, and both are right:

```bash
sudo lsof +L1 | head -20      # files with link count 0 and a size
sudo systemctl restart <unit>  # frees the space, if the unit is restartable
```

## Memory exhaustion looks like a crash loop

A service that dies every few hours, restarts, works, and dies again is
frequently the OOM killer rather than a bug in the service. The evidence is
in the kernel ring buffer, not in the application log:

```bash
journalctl -k | grep -iE 'oom|killed process'
dmesg -T | tail -30
```

Watch `available` in `free -m`, not `free`: page cache is doing useful work
and Linux will use all of it by design. A host with 200 MB of "free" memory
is normal; a host with 200 MB of "available" is about to start killing
things.

## A read-only filesystem

When ext4 hits a serious I/O error it remounts itself read-only to protect
what is left. The symptom is anything trying to write: `Read-only file
system`, a service failing to update a state file, a database refusing to
start. The cause is in the kernel log (`EXT4-fs error ... remounting
filesystem read-only`) and the disk is usually the answer. Do not remount it
read-write and walk away; the filesystem stopped itself for a reason.

## High load with idle CPU

Load average counts runnable *and* blocked processes. A load of 40 with an
idle processor is usually I/O:

```bash
iostat -x 2          # needs sysstat; watch %util and await
nvidia-smi           # if there is a GPU in the path
cat /proc/pressure/io
```

## Fixing it without making it worse

- **Stabilise the link first.** A fix that takes four minutes over a
  connection that drops after two needs a resumable shell: `tmux`, or
  `ssh -o ServerAliveInterval=30`. Losing the session in the middle of a
  package upgrade is how a small problem becomes a rebuild.
- **Write down what you ran.** Either `script -a /root/triage.log` or a
  `tmux` session you capture at the end. A remote change with no record is a
  change nobody can undo.
- **Change one thing at a time.** On a host you cannot see, two simultaneous
  changes leave you unable to attribute the outcome.

## Verify the fix, including across a reboot

The mistake at the end: `systemctl start` makes the service run *now*, and
the incident is only over if it will also run after the next reboot — which
may be in three months, when everyone has forgotten the manual step.

```bash
systemctl is-enabled <unit>     # must say enabled
systemctl is-active <unit>
# and the honest version: reboot and check it came back on its own
```

`enable --now` covers both in one command. Whether the host survives a reboot
is a claim you have to test, not assume — and a scheduled reboot window is a
much better place to find out than an outage.
