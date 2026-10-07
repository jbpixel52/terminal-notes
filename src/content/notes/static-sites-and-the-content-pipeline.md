---
title: "Static sites, and putting the content pipeline in the build"
description: "Why a blog of notes wants no runtime: typed frontmatter that fails the build, JavaScript only where it earns its place, and the checks that become possible."
pubDate: 2026-06-08
tags: [astro, web, tooling]
minutes: 7
ascii:
  piece: rocket
  caption: "build, ship, nothing running"
---

The site you are reading is a directory of Markdown files and a build step.
There is no server process, no database, no session, and nothing that can be
slow at three in the morning. For a body of text that changes when a person
writes, that is not a compromise — it removes an entire category of
operational work.

## The content pipeline is the application

The interesting shift in modern static site generators is that the build has
become a program you write, and it fails loudly when the content is wrong.
Frontmatter is validated against a schema:

```ts
const notes = defineCollection({
  loader: glob({ base: './src/content/notes', pattern: '**/*.{md,mdx}' }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    tags: z.array(z.string()).default([]),
    ascii: z.object({ piece: z.string(), caption: z.string().optional() }),
  }),
});
```

A missing `description` is now a build error, not a page with an awkward gap
that a reader finds. That property — *invalid content cannot be published* —
is the reason to prefer this over a database-backed CMS for a personal
notebook, where the author is also the only reviewer.

The same principle extends to anything the page references. This site names
an ascii art piece in each note's frontmatter, and the build checks the name
against the library's catalogue:

```ts
if (!names.includes(piece)) throw new Error(`no piece named "${piece}"`);
```

A typo becomes a failed build instead of a page with an empty frame, which
is the difference between finding it now and finding it in six months.

## Ship JavaScript only where it does something

Most of a content site needs none. The useful question is not "which
framework" but "what must run in the browser":

- the theme toggle, because the reader chooses it;
- the animated ascii art, because it is the point of the decoration;
- nothing else.

Everything else — navigation, tags, listings, reading time, the RSS feed —
is computed at build time and served as HTML. The practical consequence is a
page that is readable before any script executes, and a site whose failure
mode (a script fails to load) is "less pretty" rather than "blank".

It also makes the offline story trivial: the whole site is a few hundred
kilobytes of HTML and CSS that a browser caches for free.

## What becomes testable

A build plus a directory of routes is a very good shape for verification,
because both halves can be checked mechanically:

```bash
npm run build                       # content errors, broken imports, bad frontmatter
python scripts/verify_site.py       # every route, in a real browser, with screenshots
```

The second script discovers routes from the *output* rather than from a list,
so a page that fails to generate is a missing route rather than a missing test.
Asserting that each note page contains a rendered piece of art — a canvas with
a real width, or a `<pre>` with content — catches the failure mode where the
container renders and the art does not.

Two details worth stealing:

- **Pin the timezone for anything formatted at build time.** Rendering a date
  without an explicit zone makes the HTML depend on the machine that built it,
  so a build on a laptop and a build in CI disagree. `{ timeZone: 'UTC' }`.
- **Print the counts.** "19 pages built" and "19 routes checked" are claims
  that can be compared. A build that silently generated nothing is a green
  tick with no pages.

## The honest trade-offs

- **No per-request personalisation.** A cookie cannot change the HTML, so
  anything personalised has to happen in the browser against an API — which
  means a second system, and a privacy notice you now need.
- **Drafts are not previewable without a rebuild.** A local `npm run dev` is
  the answer, but it is local; there is no dashboard where someone else edits
  and previews.
- **Redirects, headers and auth are the host's problem.** Cache headers,
  redirect rules and access control live in the platform's configuration, not
  in your repository — so they are the part of the deployment that git does
  not describe.
- **Large content sets get slow to build.** At a few hundred pages this is
  invisible; at fifty thousand it is a pipeline project.

## Why it fits this use case

A notebook of technical notes is text that changes rarely, read by people who
are usually searching for one paragraph. Static output serves that better than
any alternative: it is fast by construction, it is trivially cacheable, it has
nothing to breach, and — the property I care about most — the entire site,
its history and its build are in one directory that can be copied, diffed and
read.
