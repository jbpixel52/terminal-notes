# Terminal Notes

A blog built with [Astro](https://astro.build/) for things worth writing down
about tech, servers and coding. Every note carries one piece of animated ascii
art from [ascii.rest](https://ascii.rest/) by
[@bas3line](https://github.com/bas3line) (MIT).

19 notes, 25 tags, one piece of art each. Static output: no server, no
database, no analytics, no third-party scripts except the ascii runtime and a
3 KB font fallback that only browsers without block glyphs fetch.

## Run it

```bash
npm install
npm run dev        # http://localhost:4321
npm run build      # -> dist/
npm run preview    # serve dist/ on :4321
```

## Check it

```bash
npm run anon       # the privacy gate (see ANONYMIZATION.md)
npm run build
npm run verify     # every route in a real browser, screenshots to .verify/
```

`npm run verify` needs Playwright. On this machine the interpreter that has it
is a virtualenv:

```bash
"$HOME/.venvs/shots/Scripts/python.exe" scripts/verify_site.py
```

## Writing a note

One Markdown file in `src/content/notes/`. The frontmatter is validated
against a schema, and the ascii piece name is checked against the library's
catalogue at build time, so a typo fails the build:

```yaml
---
title: "A short, specific title"
description: "One sentence that earns the click."
pubDate: 2026-10-05
tags: [docker, servers]
minutes: 7
ascii:
  piece: whale            # must exist in ascii.rest
  caption: "a caption for the frame"
---

## Section

Prose. Commands in fenced blocks. Errors quoted verbatim.
```

## Layout of the thing

```
src/
  content.config.ts        the note schema (title, date, tags, ascii, …)
  content/notes/           one file per note
  components/Ascii.astro   the art wrapper: validates the piece, draws the frame
  layouts/                 BaseLayout (shell) + PostLayout (a note)
  pages/                   index, /notes, /notes/<slug>, /tags/<tag>, /art, …
  styles/global.css        the whole design system, ~450 lines
scripts/
  check-anonymized.mjs     privacy gate: shape checks + a git-ignored term list
  verify_site.py           browser harness: routes, headings, art, theme, screenshots
```

## Design notes

- Dark by default, with a light palette for readers whose system prefers it;
  the choice is stored and applied before first paint.
- One face (monospace), one accent, structure from hairline rules.
- Motion respects `prefers-reduced-motion`: the ascii art holds its first
  frame, the CSS stops.
- The only client-side JavaScript is the theme toggle and the ascii runtime.
- Dates are formatted in UTC so two builds of the same commit agree.

## Credits

- [Astro](https://astro.build/) — static site framework (MIT).
- [ascii.rest](https://ascii.rest/) by [@bas3line](https://github.com/bas3line)
  — the animated ascii pieces (MIT). Logos and distros are drawn from
  [devicon](https://github.com/devicons/devicon) (MIT) and
  [Simple Icons](https://github.com/simple-icons/simple-icons) (CC0), each a
  trademark of its owner, shown to name the language or distribution.
- JetBrains Mono (OFL) — a 3 KB cut served by ascii.rest as a fallback for
  box-drawing glyphs on systems that lack them.
