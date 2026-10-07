---
title: "A mount check that stayed quiet through a full outage"
description: "findmnt --target walks up to the parent mount and calls a plain directory mounted. Zombie mounts, udev label races, and how to prove a health check can fail."
pubDate: 2026-08-14
tags: [linux, storage, monitoring, debugging]
minutes: 7
ascii:
  art: a-mount-check-that-stayed-quiet
---

Monitoring is the one part of a system whose bugs are invisible by default: a
check that always passes looks exactly like a healthy system. The three
failure modes below all produced days of silence during a storage incident,
and each is a small, specific mistake.

## `findmnt --target` walks up

`findmnt -n --target /mnt/disk1` does not ask "is `/mnt/disk1` a mount point".
It asks "which mount contains this path", and walks up to `/` if nothing is
mounted there. So a plain directory on the root filesystem answers with `/`,
`$?` is `0`, and the check reports MOUNTED during a complete outage.

The corrected test requires the target to be its *own* mount point:

```bash
p=/mnt/disk1
if [ "$(findmnt -n -o TARGET --target "$p")" = "$p" ]; then
  echo "ok: $p is mounted"
else
  echo "NOT MOUNTED: $p"
fi
```

Then prove the check can fail: run it against a directory that is not a mount
(`/tmp/not-a-mount`), and against the real one. A check that has only ever
returned "ok" has not been tested. After the fix, this monitor caught a live
`ZOMBIE MOUNT: /mnt/disk3 on /dev/sdd1 which no longer exists` within minutes.

## Zombie mounts

A mount whose source device node no longer exists. A drive drops,
re-enumerates as a different letter, and `/mnt/disk3` is still attached to the
old `/dev/sdd1` while the real partition sits unmounted. The directory looks
populated; writes go nowhere useful; the array that unions those branches is
now unioning a ghost.

```bash
src=$(findmnt -n -o SOURCE --target /mnt/disk3)
[ -e "$src" ] || echo "zombie: mounted on $src, which does not exist"
```

Clearing it: take the union/pool mount down first (it holds the branch busy),
then `umount` (or `umount -l` if it refuses) and remount on the new device.

## The udev label race at boot

The nastiest one, because everything *else* looks fine. At boot, drives appear
while the HBA is still adding and removing ports, so partitions can get device
nodes without their `/dev/disk/by-partlabel/<label>` symlink existing yet.
`blkid` shows the filesystem intact and clean; `fstab` cannot resolve the
label; nothing is mounted. No error anybody reads.

```bash
sudo udevadm trigger --subsystem-match=block --action=add
sudo udevadm settle
udevadm info --query=property --name=/dev/sdc1 | grep -i devlinks
```

If `by-id` and `by-path` links are present but `by-partlabel` is not, that is
the race, not a missing filesystem.

The durable lesson from the same reboot: device letters shuffled wholesale —
`sda`→`sde`, `sdb`→`sdc` — and only the label- and UUID-based mounts survived.
Never reference an `sdX` node in `fstab`. The strongest option is a systemd
mount unit, because it lets you say what "the disk is here" means:

```ini
[Unit]
Description=data disk
[Mount]
What=/dev/disk/by-uuid/00000000-0000-0000-0000-000000000000
Where=/mnt/data
Type=ext4
Options=defaults,nofail,x-systemd.device-timeout=10s
[Install]
WantedBy=local-fs.target
```

And verify it through the mechanism that actually runs at boot, not by reading
the file:

```bash
systemctl start mnt-data.mount
systemctl show mnt-data.mount -p WantedBy     # expect local-fs.target
```

Unmounting and letting systemd remount it proves the unit. "There is a line in
fstab" proves nothing.

## A drive that comes back damaged

After a drive drops, an ext4 filesystem can be stuck read-only for its own
protection. The state field says so:

```bash
sudo dumpe2fs -h /dev/sdd1 2>/dev/null | sed -n 's/^Filesystem state: *//p'
# clean | clean with errors | emergency_ro ...
sudo e2fsck -fy /dev/sdd1
```

Exit codes matter: `0` clean, `1` fixed, `2` fixed and a reboot is advised,
`4`/`8` **not** fixed. An empty `lost+found` afterwards is good evidence that
only metadata was repaired. And the right behaviour when the state is
`clean with errors` is to refuse to mount it and say so — a watcher that
prints `parity1 is 'clean with errors' - NOT mounting, run e2fsck` is doing
its job, where a watcher that mounts it anyway is manufacturing a worse
outage later.

## What to take from this

- A health check must be proven to fail on a known-bad input, or it is
  decoration.
- Prefer a precise predicate (`findmnt -o TARGET == path`) over a command
  that returns 0 for a looser question.
- Never address disks by kernel-assigned names.
- Read the filesystem's own state field before deciding whether to trust it.
