---
title: "Testing a mobile app on an emulator"
description: "Blank screenshots, an emulator that cannot be typed into, and callouts placed by eye. The device is part of the test rig, and it has opinions."
pubDate: 2026-01-28
tags: [mobile, testing, automation]
minutes: 7
ascii:
  art: testing-on-an-emulator
---

An emulator makes mobile verification repeatable, and it also introduces a
second machine into every test whose defaults are wrong in ways that look like
application bugs. These are the ones that cost real time.

## A blank screenshot is a rendering mode, not a blank screen

Headless device screencaps came back as empty PNGs while the app was running
perfectly. Relaunching the emulator *windowed* with a software GPU fixed it:

```bash
emulator -avd test-avd -no-audio -no-boot-anim -gpu swiftshader_indirect
```

The lesson generalises: when a visual capture is empty, suspect the capture
path before the application. Verify the rig on a screen you know has content —
the launcher, a settings page — before debugging the app.

## The default device shape is not a phone

The stock virtual device was 320×640 at the lowest density, which is not a
device anyone owns: layouts that break at one width and look fine at another
were passing, and touch targets in millimetres were impossible to judge.
Create the AVD from a real profile (a current mid-range phone, 1080×2400,
density ~420) and turn animations off, or every timing assertion is measuring
an animation.

## You cannot reliably type into it

`adb shell input text` fights the on-screen keyboard: the emoji panel
intercepts the injection, and a back gesture closes the app instead of the
keyboard. Two fixes, in order of preference:

1. **a prefill affordance in the app** — environment variables read at startup
   that seed the form for a test build (`EXPO_PUBLIC_TEST_EMAIL`,
   `EXPO_PUBLIC_TEST_CASE=…`). The flow becomes deterministic and needs no
   typing at all, and it is a smaller change than it sounds.
2. drive the UI with `adb shell input keyevent` for navigation and accept that
   text entry is the one thing you cannot automate reliably.

## Place callouts from the dump, not from your eye

For annotated screenshots, dump the view hierarchy and use the coordinates the
platform reports:

```bash
adb shell uiautomator dump /sdcard/ui.xml
adb pull /sdcard/ui.xml
# parse text="…" and bounds="[x1,y1][x2,y2]" per node
```

Eyeballing coordinates produces annotations that are subtly wrong in a way
nobody notices until a screenshot is used to argue about a layout. And capture
at 2× (`device_scale_factor=2`) so a crop of a detail is still legible —
detail matters more for a grain or a shadow than for a label.

## The dev bundle's URL is not the one you guessed

Metro's entry point is not `/index.bundle`; it is the router's entry
(`…/node_modules/expo-router/entry.bundle?platform=android&dev=true`), and the
manifest is served at `/` with a platform header. After a bundler restart the
emulator can hold a dead hot-reload socket, which looks like a frozen app:

```bash
adb shell am force-stop <app-id>
adb reverse tcp:8081 tcp:8081
# then relaunch the deep link rather than the icon
```

## A recording is evidence, and it needs a check

A screen recording is the most convincing artifact and the easiest to ship
broken — the wrong window, a black first second, a frame where a dialog covers
the thing you meant to show. Generate a contact sheet (a grid of sampled
frames) and look at it: five seconds of attention catches the whole class of
"the evidence does not show what the report claims".
