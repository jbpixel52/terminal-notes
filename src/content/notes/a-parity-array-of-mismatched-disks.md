---
title: "A parity array built from mismatched disks"
description: "JBOD plus snapshot parity: one mount over four different disks, and a protection window you have to understand. Roles from SMART, the unmounted-pool trap, and a spin-down loop that drops drives off the bus."
pubDate: 2026-10-13
tags: [storage, homelab, linux]
minutes: 8
ascii:
  art: a-parity-array-of-mismatched-disks
---

Four drives of four different sizes, no RAID controller worth using, and a
requirement that any single disk can be lost without losing the files on it. The
shape that fits is **JBOD plus snapshot parity**: the disks are merged into one
mount point, and a separate disk holds parity computed over the whole set.

It is the right answer for a media library and the wrong answer for a database,
and the reason is a single property: parity is **scheduled, not real-time**.
Everything written since the last sync is unprotected. Say that out loud before
building it, and find out what the data actually is first.

## Assign roles from SMART, not from capacity

Parity must be at least as large as the biggest data disk — that is a hard
constraint. Health decides *which* large disk gets the job, and the counters that
matter are the ones people skip: uncorrectable sectors, reallocated sectors,
grown defect lists, and power-on hours. One drive in my set had **367 offline
uncorrectables** while every sibling read **0**, at roughly three times the
power-on hours of the rest — and it was "passing" every simple check. The drive
with no error log is the parity candidate. A disk too small to be parity is a data
disk whatever its health, and that gets said out loud rather than quietly
assigning a weak drive a heavy role.

## Prepare the disks properly

`wipefs` alone is not enough: an array superblock lives at the **end** of the
disk and will happily re-assemble the old array you thought you erased. Zero it
explicitly, then lay down one GPT partition per disk with a meaningful label.

```bash
for d in sda sdb sdc sdd; do
  mdadm --zero-superblock /dev/$d 2>/dev/null || true
  wipefs -a /dev/$d
done
sgdisk --new=1:0:0 --typecode=1:8300 --change-name=1:parity1 /dev/sda
```

At multi-terabyte scale two format flags earn their keep: `-m 0` reclaims the
five percent of blocks reserved for root (~0.64 TiB on a 14 TB disk), and the
large-file inode density **matters more than it sounds** — the default on a 14 TB
disk builds an inode table a couple of hundred gigabytes wide, because it assumes
many small files.

## Mount by label, and close the unmounted-pool trap

Reference `/dev/disk/by-partlabel/...` in `fstab`, never `/dev/sdX`: the letters
shuffle across a reboot, and the arrays that survive are the ones identified by
label or UUID. Add `noatime` (a read-mostly store should not write metadata per
read), and `nofail` **on every line**, so a storage fault can never wedge a
headless machine into emergency mode.

Then the trap that catches everybody: **when the pool is not mounted, its mount
point is an ordinary directory on the root filesystem**, and writes land there
silently until the root disk fills. Make the directory immutable *while it is
unmounted* — mounting over an immutable directory still works, which is what makes
this usable:

```bash
umount /mnt/storage
chattr +i /mnt/storage
mount /mnt/storage
```

Prove it in both directions: a write while unmounted is refused, and a write
through the mounted pool succeeds.

There is a version trap in the merge layer, too: mount options for waiting on
branches need a recent release. On an older one the mount fails with `fuse:
unknown option`, which reads like a syntax error and is a version problem. Check
the version before you write the fstab line.

## A sync that succeeds proves nothing

On an empty array the first sync finishes instantly and tells you nothing. The
acceptance test is a **restore**:

1. Write distinctly named files directly to each data disk and record checksums.
2. Sync.
3. Simulate a dead disk: unmount the pool, delete one disk's entire tree.
4. Restore that disk from parity.
5. Re-checksum and compare against the recorded list.

Byte-identical, zero unrecoverable errors, then clean up and sync again. Without
step 5 the array is a hypothesis with a config file.

## The spin-down loop that takes the pool down

The daemon that schedules syncs also probes disks for changes, and a probe has to
wake the disk to read its SMART data. Ship the stock settings — a probe every few
minutes and a spin-down after fifteen idle minutes — and the two requirements
contradict each other: the disk is woken before it can ever be idle, forever.

The cost is not the power. A command that lands *inside the spin-up window* of a
large drive returns `Not Ready / Logical unit not ready`; the SCSI error handler
escalates, and the transport layer removes the target **from the bus entirely**.
The drive comes back as a new target with a new kernel name, so the mount unit
bound to the old device never remounts it — and because the merged pool needs
every branch, the whole array goes down with one disk's spin-up.

The fingerprint is a chain in the journal: `device_block` → `Sense Key : Not
Ready` → `Synchronize Cache(10) failed: DID_NO_CONNECT` → the transport removal.
The tell is a ratio: hundreds of probes to a handful of spin-downs means thrash.

Two things follow. Set spin-down to **zero** until you have proved your probe
interval comfortably exceeds the drive's spin-up time. And when the kernel logs
`Aborting journal` and "shut down requested" after a transport removal, do not
assume corruption — those lines read like disaster and usually mean the filesystem
lost its device. Confirm with a **read-only** check first:

```bash
e2fsck -fn /dev/sdX1
```

If that passes and the filesystem state reads `clean`, a plain remount is enough.
Repairing "just in case" is the riskier move.

## The guards are the feature

Two refusals worth recognising rather than working around. The sync refuses when
*every* tracked file has vanished — the message says it could be a symptom of
disks not being mounted, and it is exactly right, because syncing an unmounted
array destroys the parity. And it refuses when a data disk and the parity file
resolve to the same device, which is what happens when data disks are unmounted
and their empty mount points all live on the root filesystem.

Both messages exist to stop you. Read them as instructions, not as obstacles.
