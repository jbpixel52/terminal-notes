---
title: "Docker has two stores, and data-root only moves one"
description: "Setting the data root looked correct and the system disk kept filling: image layers live in containerd's snapshotter now. How to measure which disk a pull actually lands on."
pubDate: 2026-10-02
tags: [docker, storage, servers]
minutes: 6
ascii:
  piece: falling-sand
  caption: "data, landing somewhere you did not choose"
---

The recipe for getting Docker off the system disk is well known: set
`data-root` in `/etc/docker/daemon.json`, copy `/var/lib/docker` across,
restart the daemon, confirm with `docker info | grep "Root Dir"`. I did all of
that, confirmed the new root, and pulled an image — and the system disk grew
by 127 MB.

## The second store

Newer Docker uses the containerd **snapshotter** for images, and image layers
live in containerd's own root, which has nothing to do with `data-root`:

```bash
docker info | grep -E "Storage Driver|Driver"
# overlayfs  ...  and the disk-usage output shows
# "DISK USAGE" / "CONTENT SIZE" columns, which is the tell
```

The giveaway is in `docker system df`: a table with separate *disk usage* and
*content size* columns is reporting the containerd image store. On that setup:

- **`data-root`** covers containers, volumes, the build cache and the daemon's
  own state;
- **containerd's root** covers the image layers and snapshots.

So the fix is two config files, not one:

```toml
# /etc/containerd/config.toml
root = '/mnt/appdata/containerd'
state = '/run/containerd'
```

…plus migrating whatever is already there.

## Measure the delta, on both filesystems

The lesson is not the config line — it is that "the config looks right" is not
evidence. What settles it is a before/after measurement on both disks:

```bash
df -B1 /          | tail -1 > /tmp/before-root
df -B1 /mnt/appdata | tail -1 > /tmp/before-data
docker pull ubuntu:24.04
df -B1 /          | tail -1 > /tmp/after-root
df -B1 /mnt/appdata | tail -1 > /tmp/after-data
paste /tmp/before-root /tmp/after-root
paste /tmp/before-data /tmp/after-data
```

The run that proved the fix: the target disk grew by **+116 MB** and the system
disk by exactly **0 KB**. The run before it — the one that "looked correct" —
had the system disk go from 96 K to 127 M on a single pull.

Two more traps in the same neighbourhood:

- **Generated config files may use single quotes.** containerd's default is
  `root = '/var/lib/containerd'`. A `sed` written for double quotes silently
  matches nothing and the store does not move. `grep` the file you think you
  edited.
- **An immutable mount point turns a failed mount into an error instead of
  silent spill.** `chattr +i /mnt/appdata` means that if the disk is not
  mounted, the app cannot write into the root filesystem under that path. It
  fails loudly instead of quietly filling the wrong disk. Verify it while the
  filesystem is *unmounted* — `umount` returns EBUSY while Docker holds files
  open, and `lsattr` on a mounted directory reads the mounted filesystem and
  gives a false negative.

## The cheap check before any of this

Before pulling gigabytes to test a config change:

```bash
docker compose config      # what the daemon will actually receive
docker info | grep -i root # which store it thinks it is using
```

`docker compose config` expands and normalises a compose file — labels, port
resolutions, rendered device entries — without starting anything. It is the
fastest way to see a mapping the daemon would reject, and it costs a second
instead of a download.

## The general shape

Any storage-relocation task has the same failure mode: the configuration you
changed is not necessarily the configuration that routes the bytes. Believe
the disk, not the setting — measure the filesystem you were trying to move
data *onto*, and the one you were trying to move it *off*, before and after a
real workload. `docker info` agreeing with you is not a measurement.
