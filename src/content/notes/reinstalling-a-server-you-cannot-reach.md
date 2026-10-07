---
title: "Reinstalling a server you cannot reach"
description: "No console, no IPMI, no keyboard. How to prove an unattended install works on the real disk by installing it into an image first, and the boot details that decide whether it comes back."
pubDate: 2026-08-05
tags: [linux, virtualization, servers, hardware]
minutes: 8
ascii:
  art: reinstalling-a-server-you-cannot-reach
---

A headless box in another room with no serial console and no remote
management is a machine you can lose permanently with one wrong step. The
reinstall has to be unattended, because nobody will be there to press a key,
and it has to be *verified* before it is applied, because the failure path is
physical.

## Install into an image first

The technique that makes this safe: run exactly the same unattended install,
with exactly the same answer file, into a disk **image** the same size as the
real device, then boot that image standalone before it goes anywhere near the
hardware.

```bash
# an image byte-for-byte the size of the target SSD
qemu-img create -f raw target.img 512G

qemu-system-x86_64 -machine q35 -m 4096 \
  -drive if=pflash,format=raw,readonly=on,file=OVMF_CODE.fd \
  -drive if=pflash,format=raw,file=OVMF_VARS.fd \
  -drive file=target.img,format=raw,if=virtio \
  -device qemu-xhci,id=xhci \
  -device usb-storage,bus=xhci.0,drive=seed \
  -drive id=seed,if=none,format=raw,file=seed.img \
  -netdev user,id=n0 -device virtio-net,netdev=n0
```

The answer file travels as a cloud-init seed (`ds=nocloud`) on a small FAT
image. What the verification boot proves, in order:

1. the bootloader installed where UEFI can find it;
2. the kernel boots and mounts the root filesystem;
3. the network comes up unattended (this is the one that strands a remote box);
4. the SSH key you configured is present, so you can get back in;
5. the hostname and any first-boot service completed.

Then, and only then, the image is written to the device:

```bash
dd if=target.img of=/dev/sdX bs=16M status=progress conv=fsync
```

Five checks that cost an hour, against a physical recovery trip.

## The QEMU details that cost an afternoon

- **`-machine q35` has no USB bus.** `-device usb-storage` fails with
  `No 'usb-bus' bus found for device 'usb-storage'`. Add a controller first:
  `-device qemu-xhci,id=xhci`, then attach with `bus=xhci.0`.
- **Keep a persistent UEFI variable store.** A shared `OVMF_VARS.fd` between
  the install run and the verify run is what makes the install's boot entry
  survive into the verification boot. A fresh file each time tests a different
  machine.
- **Test against blank NVRAM as well.** Booting the installed image with a
  *wiped* `OVMF_VARS.fd` proves the removable fallback path
  (`\EFI\BOOT\BOOTX64.EFI`) works on its own — which is what saves you if the
  `efibootmgr` step silently failed. A good result shows both
  `EFI/<distro>/shimx64.efi` and `EFI/BOOT/BOOTX64.EFI` on the ESP.

## First-boot access is the part that locks people out

Two things decide whether you can get back in, and both are decided *before*
the install runs:

- **An unattended installer that sets an initial password creates a lockout
  trap.** The account's password is only assigned if the user does not already
  exist; removing that line before installing can leave a locked password
  entry, and the box then rejects password logins with no way to fix it
  remotely. On a declarative system, note that the initial password sits in a
  world-readable store — so the better order is: install with real
  `authorizedKeys` and password authentication disabled, keep the initial
  password only as a console fallback, then change it and remove the line.
- **Plan for the interfaces that do not exist yet.** An overlay network
  interface, a tailnet host key, root SSH — none of these are available on the
  first boot after a reinstall, so none can be the way in. The way in is a key
  that was installed by the answer file.

For the awkward middle case — an existing box where you only have a password —
a non-interactive password login is possible without extra packages by using
`SSH_ASKPASS` with `SSH_ASKPASS_REQUIRE=force` to get one password entry, then
installing a key and using keys from then on.

## Verify from outside, always

The install reporting success is a log line. The proof is what you can reach
from a different machine: SSH answers, the hostname is right, the root
filesystem is the expected size, and the services you configured are running.
A reinstall is the one operation where "it seemed to work" and "you have to
drive over with a keyboard" are one mistake apart — so the whole method is
built around testing the same artifact before the irreversible step.
