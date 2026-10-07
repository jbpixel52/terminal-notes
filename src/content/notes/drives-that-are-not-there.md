---
title: "Four drives, none of them mounted"
description: "A new server saw some of its disks and not others. The diagnostic ladder from the PCIe controller down to the mount, and the fstab habit that saves your data."
pubDate: 2026-09-04
tags: [linux, storage, servers, debugging]
minutes: 8
ascii:
  piece: vinyl
  caption: "spinning up, one platter at a time"
---

A mini-PC with four SATA drives, freshly installed, and storage that did not
exist. `lsblk` showed one disk. The reasons a Linux box does not see a disk
are mostly boring and entirely fixable, but only if you work down the stack
instead of guessing at the filesystem level.

## The ladder

Work from the bus outwards. Each rung tells you whether to look further down
or back up.

**1. Does the kernel see a controller?**

```bash
lspci -nnk | grep -A3 -i sata
```

You want a controller *and* a `Kernel driver in use:` line. A controller
listed with no driver is a missing module or a card the kernel does not
recognise yet — no amount of `fdisk -l` will help.

**2. Did the drives link up?**

```bash
dmesg | grep -iE 'ata[0-9]|scsi|link is' | tail -40
```

The interesting lines are the ones about link speed and failures:
`SATA link down`, `failed to IDENTIFY`, `COMRESET failed`. A port multiplier
problem looks like this: an enclosure exposing four bays through one port
shows a single device unless the controller and its driver support port
multiplier switching.

**3. Does the block layer see them?**

```bash
lsblk -o NAME,SIZE,MODEL,SERIAL,TRAN,ROTA
ls -l /dev/disk/by-id/
```

`lsblk` lists every block device the kernel has, with or without partitions.
A disk that appears here with no children is present and empty, not broken.

**4. Is there a partition table and a filesystem?**

```bash
sudo fdisk -l /dev/sdX
sudo blkid /dev/sdX1
sudo wipefs -n /dev/sdX      # what signatures exist, without writing
```

`blkid` printing nothing means "nothing mounted-able found" — the disk may
still be full of data in a format you have not asked about. `wipefs -n` is
read-only and lists every filesystem signature on the device, which is the
polite way to check before you create a table and destroy something.

**5. Is the drive healthy?**

```bash
sudo smartctl -i /dev/sdX
sudo smartctl -a -d sat /dev/sdX    # for drives behind a USB bridge
```

`-d sat` is the flag nobody remembers: many USB-SATA bridges do not pass
SMART through by default, so `smartctl` reports "device does not support
SMART" on a perfectly good drive.

## The mount, and the habit that saves data

`/dev/sdX` names are assigned in the order the kernel probes, and that order
is not stable across reboots, kernel updates, or a disk being added. An
`/etc/fstab` that says `/dev/sdb1` is a loaded gun: after a reboot, the same
device node can be a different disk, and the mount succeeds onto the wrong
filesystem.

Use a name that cannot shuffle:

```bash
# by UUID (the filesystem's identity)
lsblk -f                       # prints UUID and FSTYPE per partition
# by hardware id (the device's identity, survives a reformat)
ls -l /dev/disk/by-id/
```

If a dataset must appear as a fixed path, mount it with `nofail` and a
timeout so a missing disk produces a degraded boot instead of an emergency
shell — and prefer a systemd mount unit over fstab for anything you need to
control the ordering of:

```ini
# /etc/systemd/system/mnt-data.mount
[Unit]
Description=data disk
[Mount]
What=/dev/disk/by-uuid/00000000-0000-0000-0000-000000000000
Where=/mnt/data
Type=ext4
Options=defaults,nofail,x-systemd.device-timeout=10s
[Install]
WantedBy=multi-user.target
```

The unit name must match the path with slashes replaced by dashes
(`/mnt/data` → `mnt-data.mount`); a mismatch is the usual reason a hand-written
unit is silently ignored.

After creating partitions on a live system, `partprobe /dev/sdX` makes the
kernel re-read the table without a reboot. Without it, you can create
`/dev/sdX1` and have it not exist for five minutes, which is a confusing
five minutes.

## What actually fixed it

Two of the four drives were on a controller that had no driver bound, and
the other two had no partition table at all — two different problems
presenting as one symptom, which is why "the disks are broken" is the wrong
conclusion to jump to. Both were found by walking down the ladder from
`lspci` rather than by re-imaging the machine.
