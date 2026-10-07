---
title: "Moving Docker's storage to another disk"
description: "The root filesystem filled up and Docker was the reason. How to relocate the data root without losing a container, and the flags that matter when you copy the directory."
pubDate: 2026-09-20
tags: [docker, servers, storage]
minutes: 7
ascii:
  piece: whale
  caption: "the whale moved house"
---

A host with a small system disk and a large data disk, filling up anyway. The
culprit is predictable: everything Docker knows lives under
`/var/lib/docker` — images, container layers, volumes, build cache — and on
a default install that directory sits on `/`.

## See what is actually consuming it

Before moving anything, get the numbers, because the interesting one is
usually not images:

```bash
df -h /var/lib/docker
docker system df -v | head -30
sudo du -sh /var/lib/docker/* | sort -h
```

`docker system df` splits images, containers, local volumes and build
cache. In my case most of the disk was in `overlay2` (image layers) rather
than in volumes, and the fix was relocation, not deletion — deleting a
volume that holds the only copy of something is not a cleanup.

## Two ways to move it

**Bind-mount the old path.** Put the new disk's filesystem at
`/var/lib/docker` via `/etc/fstab`. Simple, and everything else in the
world keeps working because the path never changes.

**Change the data root.** Tell the daemon to use a different directory:

```json
// /etc/docker/daemon.json
{
  "data-root": "/srv/docker"
}
```

I use the second when the new disk is dedicated to Docker and I want the
path to say so. Either way the copy step is identical, and that is where
the trap is.

## The copy that has to be right

`cp -r` on `/var/lib/docker` produces a directory that *looks* correct and
is not. `overlay2` stores layers as hard-linked files; a recursive copy
without the hard-link flag duplicates every layer, so the destination can
be several times larger than the source and the deduplication Docker
depends on is gone.

```bash
sudo systemctl stop docker docker.socket
sudo rsync -aHAX --info=progress2 /var/lib/docker/ /srv/docker/
```

- `-a` archive, `-H` preserve hard links, `-A` ACLs, `-X` extended
  attributes.
- The trailing slash on the source copies the *contents* of the directory,
  not the directory itself.
- `-X` matters on SELinux and on filesystems storing labels; without it
  the daemon may start and then fail to read its own layers.

Then two checks that catch the copy being wrong *before* the daemon is
pointed at it:

```bash
sudo du -sh /var/lib/docker /srv/docker      # sizes should be close
sudo rsync -aHAXn --delete /var/lib/docker/ /srv/docker/   # -n: dry run, expect no transfers
```

`rsync -n` reporting nothing to transfer is a good equality check between
two trees, hard links included — better than comparing `du`, which can
agree while metadata differs.

## Cut over and prove it

```bash
# edit /etc/docker/daemon.json to set data-root, then:
sudo systemctl start docker
docker info | grep -i "root dir"
docker images | wc -l        # compare to the count before the move
docker run --rm hello-world  # a real pull + run, not just a listing
```

The last line earns its place: `docker images` reads a local store and
proves the daemon can find its metadata. Running a container proves it can
also unpack layers and start a process, which is where a botched ACL or
xattr copy shows up.

Two failure modes to recognise:

- **"failed to start daemon: error while opening volume store metadata
  database: timeout"** — almost always another daemon process still holding
  the old directory, or `docker.socket` restarted by demand. Stop the
  socket unit too, not just `docker.service`.
- **The daemon starts and containers are missing.** Check `data-root` took
  effect (`docker info | grep "Root Dir"`); a JSON typo means the file was
  ignored, Docker keeps using the old path, and now you have two stores.

## What I would do differently

Set the data root *at install time*. The migration is twenty minutes of
work and an hour of checking; the parameter is one line in a config file
that nobody sets until it hurts. If a host is going to run containers long
term, give `/var/lib/docker` its own filesystem from the start — and
remember that `docker system prune` is a disk-space tool, not a policy.
