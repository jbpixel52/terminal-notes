---
title: "Measure the part, not the datasheet"
description: "Hardware that has to fit: nominal dimensions, real dimensions, tolerances and a test coupon. The same discipline that stops a six-hour print and a two-day refactor."
pubDate: 2026-05-11
tags: [hardware, 3d-printing, process]
minutes: 6
ascii:
  piece: cube
  caption: "the part, before it exists"
---

Designing a case for a board, a bracket for a disk, or a panel for a
connector is the same discipline as any other build: the specification is a
hypothesis, and the first artifact is the experiment. Hardware just makes the
experiment more expensive than a compiler.

## The datasheet is a wish

A board's published dimensions are nominal: the PCB size, the hole spacing,
the connector positions. What they are not is what you have on the desk.

- **Hole spacing** is usually accurate; hole *diameter* is drilled with a
  tolerance and plated, so it is smaller than stated.
- **Component height** above the board is often not published at all, and
  the tallest thing is frequently a connector or a capacitor rather than the
  chip you were thinking about.
- **Cable connectors add depth.** A right-angle USB plug and a straight one
  differ by 15 mm, and the one that fits the drawing is not the one on the
  bench.
- **A case inside a case has two tolerances.** The enclosure you print has
  its own error, on top of the parts it holds.

The only measurement that counts is the one taken with calipers, on the
physical object, at the tolerance that matters. Measure three units if there
are three: batch variation is real, and it is usually the part you did not
expect.

## Clearances, in numbers

Two classes of fit, and confusing them is the usual mistake:

| fit | allowance | why |
| --- | --- | --- |
| a *slide* fit (a lid, a tray) | 0.3–0.5 mm total | the printer overshoots; parts are not square |
| a *press* fit (a pin in a hole) | 0.0–0.15 mm | and it varies per printer and per filament |
| a *hole* for a heat-set insert | insert OD − 0.1–0.3 mm, plus a chamfer | the plastic that is displaced has to go somewhere |
| a screw hole for a self-tapper | ~0.8 × screw OD | the thread is cut by the screw, not the model |

Add to that the printer's own error: a first layer that squashes, a printer
that slightly overshoots its nominal extrusion, filament that is not quite
1.75 mm. This is what calibration prints exist for, and it is per-machine —
the numbers that work on one printer are a starting point on another.

## Prove the fit before the big print

A six-hour enclosure that misses by 0.4 mm is a six-hour lesson. A twenty-
minute coupon that proves the same dimensions is a much better trade:

- print the *interfaces* at full size: the mating lip, the screw boss, the
  cut-out and its clearance;
- put a ruler or a scale on the plate as well, so the coupon measures itself;
- keep the coupon; it becomes the reference for the next part.

In code, the equivalent is a cheap test: measure the interface, not the whole
system. If the whole part is a parameterized model, the interface is a
function of two or three variables, and those are what the coupon proves.

## Model it parametrically, and keep the source

The printable artifact is an STL — a bag of triangles with no relationships
in it. The *design* is the source file: parameters for wall thickness,
clearance, screw size, and the board's mounting hole positions taken from the
measurement rather than from the drawing.

That matters the first time something changes by half a millimetre, which is
immediately: a parameterized model is a one-line change and a re-slice, an STL
is a fresh design session.

```scad
// the numbers measured with calipers, in one place, in mm
board_hole_dx = 58.4;
board_hole_dy = 41.2;
screw_clearance = 3.4;   // an M3 at a slide fit
wall = 2.4;              // 6 perimeters at a 0.4 nozzle
```

Units are millimetres, everywhere, without exception. A model that mixes
millimetres and inches is a bug that prints.

## Check for interference in the model, not on the plate

Two parts that collide can often be proved not to, from the geometry, before
anything is printed: take 2D projections and check the overlap, or render the
assembly and look for intersections. It is not a substitute for the print, but
it catches the class of error that wastes one.

And it transfers directly to software: you do not profile before you measure,
and you do not refactor before a test tells you which interface is actually
costly. "I am fairly sure the bottleneck is…" is a datasheet.

## The general rule

Measure the part. Build the smallest artifact that can falsify the design.
Keep the source of truth parameterized, in one set of units, with the numbers
you actually measured written down where the model can read them. Do that and
the expensive failure becomes a cheap one — which is the only kind of failure
worth having.
