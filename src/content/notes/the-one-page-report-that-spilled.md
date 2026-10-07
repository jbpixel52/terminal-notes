---
title: "The one-page report that spilled to page two"
description: "A footer on its own page is a spacing bug, not a page-break bug. Trimming the layout, and asserting the page count instead of opening the file."
pubDate: 2026-01-21
tags: [tooling, testing, design]
minutes: 5
ascii:
  art: the-one-page-report-that-spilled
---

A generated report is specified as one page: it is meant to be read in ten
seconds, printed, pinned, or attached to a message. It came out as two pages,
the second holding only the footer — which is what "the content is 3 mm too
tall" looks like in a PDF.

## Render it with a browser, measure it with a script

Headless Chrome (or Edge) produces a very good PDF from ordinary HTML and CSS,
and gives you the page's real typography rather than a library's approximation:

```bash
chrome --headless=new --disable-gpu --no-pdf-header-footer \
       --print-to-pdf="$PWD/out.pdf" "file://$PWD/out.html"
```

`--no-pdf-header-footer` removes the URL-and-date furniture that otherwise
eats a centimetre of every page — and which is the first thing to check when a
layout spills for no visible reason.

Then assert on the artifact rather than trusting your eyes:

```python
import pymupdf
doc = pymupdf.open("out.pdf")
assert doc.page_count == 1, f"{doc.page_count} pages: {doc.page_count} pages of content"
for page in doc:
    print(len(page.get_text()))     # page 2 held 149 characters: the footer
```

A page count assertion plus a per-page text length is enough to catch the
spill, and it belongs in the build so the report cannot regress quietly.

## Where the space actually goes

The fix is almost always arithmetic in the layout, not a page-break hint:

- trim ~30 pt of vertical space rather than fighting the break — a footer that
  just fits does not need to be told where to break;
- set the page margins deliberately (`@page { margin: 0.34in }`), because the
  default plus a body margin quietly adds up to more than A4;
- stop a chart from growing with its container: give it an explicit height in
  points, since a percentage height in a print context resolves against a page
  box you did not choose;
- remember that fonts load asynchronously: print too early and the layout is
  measured with a fallback face, which is why a local render and a CI render
  can disagree by a line.

## One number, one page, no exceptions

The reports worth automating are the ones with a fixed shape: a title, a row of
figures, one chart, a footer. Once the shape is fixed, the page count is a
property of the artifact and can be asserted — and the assertion is the
difference between "we believe it fits" and "it fits, and here is the check
that says so on every build".
