---
title: "Driving WSL from the Windows side"
description: "Two filesystems, two shells and three kinds of path. The interop quirks that cost the most time: path translation, the temp directory, the firewall, and Enter."
pubDate: 2026-08-19
tags: [wsl, windows, linux, tooling]
minutes: 7
ascii:
  art: driving-wsl-from-the-windows-side
---

Running a Linux environment inside Windows is the pragmatic choice for
anything that needs a real shell, and the seam between the two is where all
the time goes. Everything below is a thing that failed quietly.

## Paths do not translate themselves

A Windows shell (cmd, PowerShell, or a MSYS/git-bash layer) has its own idea
of a path, and *path translation is not consistent*: some tools convert
`/c/Users/me/x` on the way in, others pass it through untouched and fail with
`cannot change to` or `no such file or directory`. The rules that actually
hold:

- A POSIX-style path like `/c/Users/name/project` works for *shell builtins*
  and MSYS-aware tools (`cd`, `ls`, `cat`).
- Native Windows binaries (`node`, `python`, `git`, `rg`) want
  `C:/Users/name/project` — forward slashes, drive letter, no leading slash.
- `/tmp` is the MSYS temp directory, and a native Windows program usually
  cannot see it. Use `$LOCALAPPDATA/Temp` for scratch files that a native
  tool has to read.

The practical rule: **if the command crosses into a native binary, build the
path natively.** One `C:/...` argument is worth more than three attempts at
`/c/...`.

## Line endings and file modes

Two classic failures, both of which look like the tool is broken:

- A shell script with CRLF endings fails with
  `/bin/bash^M: bad interpreter: No such file or directory`. The `^M` is the
  carriage return. Fix it in the repository rather than on the machine, with a
  `.gitattributes` that pins the files that must stay LF:

  ```gitattributes
  *.sh text eol=lf
  *.py text eol=lf
  Dockerfile text eol=lf
  *.bat text eol=crlf
  ```

- Git on Windows may or may not record the executable bit. A script committed
  from Windows can arrive on Linux without `+x` and be unrunnable:
  `git update-index --chmod=+x script.sh`.

## Interactive programs expect a carriage return

Driving an interactive CLI through a pseudo-terminal on Windows has a specific
trap: the terminal's line terminator is `CR`, not `LF`. Writing `\n` to the
program's input does not submit the line — the prompt simply never returns,
and it looks like the program hung. Send `\r` (or `\r\n`). This is an hour of
debugging every time it is rediscovered, and it is invisible in logs.

## The firewall between the two halves

WSL2 is a separate virtual machine with its own virtual network. Traffic from
Windows *into* WSL is usually forwarded for localhost, but traffic from WSL
*out* to a service bound on the Windows host is not, by default: the Windows
firewall sees an inbound connection from the WSL subnet and drops it.

Symptoms: `curl` from inside WSL to a port on the Windows side hangs and then
times out, while the same request from Windows succeeds. The physical
connection to a debug port (a browser's remote-debugging port, a dev server,
a database) is where this bites, because you are usually trying to reach one
of those.

Two fixes, in order of preference:

1. Bind the Windows-side service to `0.0.0.0` and add one inbound rule for
   that port, scoped to the WSL subnet, instead of disabling the firewall.
2. Run the service inside WSL and let Windows reach it — the reverse
   direction generally works without changes.

Scoping the rule matters: an inbound allow on a debugging port with no scope
is an open port on the LAN.

## Where to keep the files

`/mnt/c/...` crosses a filesystem boundary with a translation layer, and it
is dramatically slower than the native Linux filesystem: file-watching,
`node_modules` installs and git status all suffer, sometimes by an order of
magnitude. The trade is legibility — files under `/mnt/c` are visible in
Windows Explorer and in Windows editors — against speed. Keep source in the
Linux filesystem and share it out, or keep it on Windows and accept the cost
of every `npm install`, but do not switch back and forth and wonder why
builds got slower.

## Clock drift and TLS

A WSL instance that has been suspended with the laptop drifts from the host
clock. This is invisible until something validates a certificate:
`certificate is not yet valid` from a build tool, an ACME client refusing to
issue, an SSH connection failing on a signature. Checking the date inside WSL
against the host is a two-second test that resolves a class of errors that
look like they belong to networking.

```bash
date; sudo hwclock -s     # resync from the hardware clock
```

## Shutting down

`wsl --shutdown` is the hammer that fixes most unrecoverable states — a
distro that will not start, a stuck mount, a networking glitch — and it kills
*every* running distribution, including the one you forgot about. Check what
is running first (`wsl -l -v`, `wsl --list --running`), and expect running
services inside to die with it.

## The mental model that helps

Treat it as two machines with a shared folder and an unreliable cable between
them, rather than as one machine with two shells. Nearly every quirk above is
obvious in that frame: paths need translating, the cable needs a firewall
rule, and the file share is slower than local disk.
