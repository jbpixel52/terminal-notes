---
title: "The terminal as a design language"
description: "Monospace, one accent colour, structure made of rules rather than shadows. What a text-first aesthetic buys, what it costs, and the accessibility rules it does not excuse you from."
pubDate: 2026-05-29
tags: [design, web, css]
minutes: 7
ascii:
  art: the-terminal-as-a-design-language
---

Designing a page to look like a terminal is not a novelty any more, which
means it has to be done well or not at all: the style makes a promise about
plainness, and a bloated version of it reads as decoration rather than
restraint.

What follows is the set of rules this site is built on. They are the
constraints that make the aesthetic hold together.

## One face, and a real hierarchy

Everything is monospace, which removes the usual crutch of mixing a display
face with a text face. Hierarchy has to come from elsewhere: size first,
weight second, colour third — and a page needs very few levels to be legible.

The temptation in a terminal pastiche is to render headings with a literal
`#` prefix. It is charming once and noisy on every page, so the prefix here is
CSS (`h2::before { content: "## " }`), decorative, and excluded from the
accessible name — the heading is still a heading to a screen reader.

## A palette of four, not twelve

Almost every tasteful terminal theme is a background, a foreground, a dimmed
foreground for secondary text, and one accent that means "here". Rules for
keeping that honest:

- the accent marks interactive and current things only — a link, the current
  page, a prompt — never decoration;
- secondary text is a *dimmed* foreground rather than a different hue, so the
  palette cannot drift;
- colour never carries meaning alone, because it will be lost on a poor
  display, in print, and for a reader who cannot distinguish the accent from
  the background.

A second accent (amber, for warnings) is allowed exactly one job.

## Structure from rules, not depth

No shadows, no rounded card stacks, no gradients standing in for hierarchy.
Boxes are drawn with one-pixel rules in a muted line colour, the way a
terminal draws a table, and the strongest structural device is the horizontal
rule:

```css
hr {
  border: 0;
  border-top: 1px dashed var(--line);
  margin: 2.5em 0;
}
```

Lists of things — notes, tags, results — become rows separated by a single
rule rather than separate cards. It reads as a report rather than a feed,
which is exactly right for reference material, and it costs one border.

## Measure, and pick a fight with monospace

Long prose in a monospace face is harder to read than in a proportional one,
because every character occupies the same width. The countermeasures are
mechanical and non-negotiable:

- keep the measure around 65–70 characters;
- increase line-height relative to a proportional face (about 1.7);
- do not set prose at a small size to "look technical".

Sizing the art separately from the prose is also worth the CSS: text-piece art
is laid out in character cells, so its size wants to scale with the viewport
(`font-size: clamp(5px, 1.1vw, 12px)`) rather than sit at a fixed pixel size
that overflows a phone.

## Motion is opt-in

A blinking cursor, a typing animation, a piece of animated ascii art — all of
them are motion, and some readers have asked their system to stop it:

```css
@media (prefers-reduced-motion: reduce) {
  * { animation-duration: 0.001ms !important; transition-duration: 0.001ms !important; }
  html { scroll-behavior: auto; }
}
```

The library this site draws its art with goes further and holds the first
frame for those readers, which is better than hiding the art: the page still
looks like the page. Where motion is the content, offer a control rather than
overriding the preference silently. And note that a blinking cursor is easy to
forget, because it is one line of CSS in a hero nobody revisits.

## An accessible version of the aesthetic

The style does not excuse skipping the basics, and a few of them need thought
here specifically:

- **The big ascii headline is not text.** Anything drawn in ascii art is
  invisible to a screen reader, so the page needs a real heading and the art
  needs a label (`role="img"` with an `aria-label`, which the library
  provides). Decorative art is `aria-hidden`.
- **Contrast, measured.** A "dimmed" foreground is where contrast quietly
  fails; keep secondary text at a ratio above 4.5:1 against the background
  rather than trusting it to feel right.
- **Visible focus.** A theme like this often removes the browser outline for
  aesthetics, which is the single most common accessibility regression in
  minimalist design. Replace it, do not delete it.
- **A skip link**, because the navigation is at the top of every page.

## The light theme is a translation, not an inversion

A terminal aesthetic in light mode is paper and ink: a warm off-white ground,
near-black text, and the accent darkened until it passes contrast on the light
background rather than being the bright phosphor green from the dark theme.
Mechanically this is a second block of custom properties selected by a
`data-theme` attribute, with a few lines of inline script in the head to apply
the stored choice before first paint — otherwise the reader sees the wrong
theme for a frame, which is the one flicker everyone notices.

```html
<script is:inline>
  try {
    const saved = localStorage.getItem('theme');
    if (saved === 'light' || (saved === null && matchMedia('(prefers-color-scheme: light)').matches))
      document.documentElement.dataset.theme = 'light';
  } catch {}
</script>
```

Note what the default is: the system preference, not the designer's. A dark
theme is not an opinion to impose on someone whose screen is in daylight.

## What it buys

A text-first page loads with almost nothing, tells the reader immediately that
nothing is being sold, and puts all the visual weight on the words — which,
for notes, is the whole point. The constraint is also a useful design tool:
with one face, one accent and rules instead of shadows, a page that looks
wrong is usually *wrong*, not merely unfashionable.
