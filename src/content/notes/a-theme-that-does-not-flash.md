---
title: "A theme that does not flash"
description: "Four ways dark mode breaks and the check that catches each: the flash before first paint, the resolver that runs twice, print that falls through, and contrast measured instead of assumed."
pubDate: 2026-10-07
tags: [css, web, design, accessibility]
minutes: 8
ascii:
  art: a-theme-that-does-not-flash
---

Theming a site looks like a palette swap and is not one. Every failure I have hit
is invisible in the stylesheet: the flash of the wrong theme is a timing bug, the
palette with holes is a token bug, the dark print-out is a scoping bug, and the
contrast regression is a measurement nobody took. This note is the four checks,
in the order they bite.

## 1. Resolve the theme before the first paint

On a static site there is no server that knows anything about the reader, and the
HTML ships carrying no theme at all. If the client resolves light/dark after
hydration, every cold load paints full brightness first, then corrects itself.
That is the one dark-mode bug that is worse than not having dark mode.

The fix is a blocking script in `<head>`:

- **Inline, not deferred, not `async`, no `src`.** Only a classic inline script
  runs during parsing, before the body exists.
- **Read it from its own source file at build time** and inline those bytes,
  rather than pasting a copy. Then the file the test executes is the file that
  ships, and they cannot drift apart.
- **A missing file must fail the build loudly.** A page whose theme never
  resolves looks like "dark mode is broken" with no error anywhere.

And verify it in the *built* output, not the source: find the script that
contains your marker and assert it has no `src`, no `defer`, no `async`. Do not
assume a framework preserves your `<head>` order — check what it emitted.

## 2. One resolver owns the decision

Two implementations of "what does *system* mean" produce a theme that depends on
which one ran last. Keep resolution, persistence and the mode list in the
bootstrap, and treat the toggle as a view over it. Always write a **concrete**
`light` or `dark` onto the document element — never a third state like `system`
that exists by accident — and keep a second tab in step with a `storage`
listener. That listener fires in every document *except* the one that changed the
value, which is exactly the cross-tab case and exactly why a self-dispatched
custom event does not cover it.

The toggle itself is where a fix can make things worse. The complaint was that a
JS-off reader saw a control that did nothing — a false affordance. The first fix
rendered the button only after mount, which made the navigation **reflow on every
page load** for everybody. The repair was to render it on the server and hide it
with a `<noscript>` rule: the small lie goes away where it actually lives, and
nothing shifts.

## 3. Print is a theme too

Printing a dark page wastes ink and looks broken. The cheap fix is one line: wrap
the dark token block in `@media screen`, so print falls through to the light
tokens with no second palette to maintain.

The catch is subtler than the fix. `color-scheme` written **inline on the root
element by the bootstrap** outranks a `:root` declaration and is not
screen-scoped, so printing from dark keeps the browser's dark form controls and
scrollbars on white paper. The only thing that outranks an inline style is
`!important`, and inside a print block that is exactly the right use of it. Prove
it by emulating print and reading the recorded values: the attribute can say
`dark` while the paper is white, and only one of those is what the reader sees.

## 4. Measure the contrast, then decide the bar

The tempting rule — dark must be at least as legible as light on every pair — is
wrong, and measuring shows why. Primary ink in a light theme commonly runs to
18:1 or beyond; pushing near-white text towards pure white on a dark ground is
**halation**, where glyphs bloom and get harder to read, especially for readers
with astigmatism. Chasing a bigger number there trades legibility for a score.

Bind parity where it actually matters instead:

1. every pair clears an absolute floor;
2. where the light theme is already tight, the dark one must be strictly better —
   there is no headroom to give away;
3. where light is generous, dark may sit lower, but still far above the
   minimum.

Two measurement traps. A translucent wash has no contrast of its own, so read the
pair as *foreground over (wash over ground)* or you measure the wrong thing. And
do not judge a palette from a downscaled preview: borders that vanish and small
secondary text that turns to mush are invisible in a small screenshot and in
every numeric check.

## The pitfall that outlives the theme

A test that grepped the stylesheet for `"color-scheme"` passed — because the
literal also appeared in a code comment. Deleting the actual declaration would
not have failed it. Assertions must read the *effect* the harness recorded, not
the presence of text.

And when you repair a test like that, break the behaviour it guards, watch it go
red, restore it, then confirm the file is byte-identical. A repaired test that
has never failed is still an unproven test.

The page you are reading is the current version of all four: one inline resolver,
a concrete theme on the root element, dark scoped so print is light, and the
counts above taken from measurements rather than taste.
