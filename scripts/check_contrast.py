#!/usr/bin/env python3
"""
check_contrast.py — prove the site is readable, in a browser, in both themes.

WCAG 2.1 contrast is a property of the *painted* page, not of the stylesheet:
a colour is only readable against whatever ends up behind the glyphs. This
script therefore loads the built site in Chromium, and for every text style the
site actually uses:

  1. resolves the effective background by walking up the ancestors until it
     finds one that paints something opaque, and
  2. fails if the first thing behind the text is a *pattern* (a dither, a
     gradient, or the desktop's dot grid) rather than a flat colour — because a
     checkerboard under 16px type costs contrast however good it looks, and
  3. computes the WCAG 2.1 ratio and checks it against the right threshold:
     4.5:1 normally, 3:1 for large text (>=24px, or >=18.66px and bold).

Gradient-filled text (the wordmark) is checked stop by stop: each colour in the
gradient is measured against the paper it is painted on.

Run:  python3 scripts/check_contrast.py        (or: npm run contrast)
Needs: npm run build first; Playwright's chromium (see README).
"""

from __future__ import annotations

import functools
import http.server
import re as _re
import re
import socketserver
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
BASE = "/terminal-notes"  # the deploy prefix the built URLs carry


# --- what to check -----------------------------------------------------------
# (label, page path, css selector) — nth is a :nth-child() suffix for list rows
CHECKS: list[tuple[str, str, str]] = [
    # the menu bar
    ("menu bar: app name", "/", ".menubar-app"),
    ("menu bar: nav item", "/", ".menubar-nav .menubar-item:nth-child(1)"),
    ("menu bar: current page", "/", ".menubar-item[aria-current='page']"),
    ("menu bar: invert button", "/", "[data-theme-toggle]"),
    ("menu bar: clock", "/", ".menubar-clock"),
    # windows
    ("window title (active)", "/", ".title-bar--active .title"),
    ("window title (inactive)", "/", ".title-bar--inactive .title"),
    ("window body text", "/", ".lede"),
    ("wordmark, gradient stop", "/", ".wordmark"),
    # the front page's list
    ("note title", "/", ".finder-name h3 a"),
    ("note title on a tinted row", "/", ".finder-list > li:nth-child(even) .finder-name h3 a"),
    ("note description", "/", ".finder-desc"),
    ("note description on a tinted row", "/", ".finder-list > li:nth-child(even) .finder-desc"),
    ("note date", "/", ".finder-time"),
    ("reading time", "/", ".finder-min"),
    ("note date on a tinted row", "/", ".finder-list > li:nth-child(even) .finder-time"),
    # chrome around the list
    ("list header cell", "/notes/", ".finder-head span:nth-child(1)"),
    ("rail heading", "/", ".rail-title"),
    ("rail term", "/", ".rail-meta dt"),
    ("rail value", "/", ".rail-meta dd"),
    ("rail link", "/", ".rail-links a"),
    ("tag chip 1", "/notes/", ".finder-tags .tag:nth-of-type(1)"),
    ("tag chip 2", "/notes/", ".finder-tags .tag:nth-of-type(2)"),
    ("prompt line", "/", ".prompt"),
    ("desktop icon label", "/", ".icon-label"),
    ("button", "/", ".btn"),
    ("footer text", "/", ".site-footer .footer-grid"),
    ("footer link", "/", ".site-footer a"),
    # a note
    ("post title", "@note", ".post-header h1"),
    ("post meta", "@note", ".post-header .meta"),
    ("prose paragraph", "@note", ".prose p"),
    ("prose lead paragraph", "@note", ".prose > p:first-of-type"),
    ("prose heading", "@note", ".prose h2"),
    ("prose list item", "@note", ".prose li"),
    ("inline code", "@note", ".prose :not(pre) > code"),
    ("code block", "@note", ".prose pre code"),
    ("figure caption", "@note", ".ascii-figure figcaption"),
    ("prose link", "@link", ".prose a"),
    ("blockquote text", "@quote", ".prose blockquote"),
    ("table cell", "@table", ".prose td"),
    ("post footer", "@note", ".post-footer"),
]

THEMES = [("paper", None), ("invert", "invert")]


def note_paths() -> list[tuple[str, str]]:
    """(url path, html) for every built note, so the harness can measure a
    real instance of each construct instead of a hard-coded slug — and never
    report "selector not found" for a note that simply does not use it."""
    return [
        (f"/notes/{p.parent.name}/", p.read_text(errors="ignore"))
        for p in sorted((DIST / "notes").glob("*/index.html"))
    ]


def first_note_with(pattern: str) -> str | None:
    """A note whose *body* contains `pattern` — searching the whole page would
    match the rail and the nav, which is exactly the mistake that made this
    harness report "not found" for a construct the note did not have."""
    for path, html in note_paths():
        match = _re.search(r'class="[^"]*\bprose\b[^"]*"[^>]*>(.*?)(?:<footer|</article>)',
                           html, _re.S)
        if not match:
            continue
        # a code sample may contain the very markup we are looking for
        body = _re.sub(r"<pre.*?</pre>", "", match.group(1), flags=_re.S)
        if pattern in body:
            return path
    return None


NOTES = note_paths()
if not NOTES:
    raise SystemExit("no built notes found under dist/notes/")
NOTE = NOTES[0][0]
NOTE_TABLE = first_note_with("<table") or NOTE
NOTE_LINK = first_note_with('<a href="/terminal-notes/notes/')   # None if unused
NOTE_QUOTE = first_note_with("<blockquote")                      # None if unused
_NOTES = {"@note": NOTE, "@link": NOTE_LINK, "@quote": NOTE_QUOTE, "@table": NOTE_TABLE}
CHECKS = [(label, _NOTES.get(path, path), sel) for label, path, sel in CHECKS]


def serve_dist() -> tuple[socketserver.TCPServer, str]:
    """Serve dist/ and treat /terminal-notes/... as its root — the URL shape
    the deployed site has."""

    class Handler(http.server.SimpleHTTPRequestHandler):
        def translate_path(self, path: str) -> str:  # noqa: D102
            if path.startswith(BASE):
                path = path[len(BASE):]
            return super().translate_path(path)

        def log_message(self, *args) -> None:  # silence
            pass

    handler = functools.partial(Handler, directory=str(DIST))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]
    return httpd, f"http://127.0.0.1:{port}{BASE}"


MEASURE = r"""
({ selector, all }) => {
  const measure = (el) => {
  const cs = getComputedStyle(el);
  const text = (el.textContent || '').trim().slice(0, 40);

  // gradient text (background-clip: text) paints its glyphs with the
  // background-image, so that image is the text, not the background behind it
  const clip = (cs.webkitBackgroundClip || cs.backgroundClip) === 'text';

  // walk up for the first thing that paints: a colour or an image
  let node = el, bg = null, patterned = null, first = true;
  while (node && node !== document.documentElement.parentNode) {
    const s = getComputedStyle(node);
    const image = !(first && clip) && s.backgroundImage && s.backgroundImage !== 'none';
    const colour = s.backgroundColor;
    const opaque = colour && !/^(rgba\(0, 0, 0, 0\)|transparent)$/.test(colour);
    if (opaque) { bg = colour; break; }
    if (image && patterned === null) {
      patterned = s.backgroundImage.slice(0, 60);
      break;
    }
    first = false;
    node = node.parentElement;
  }
  // nothing opaque beneath the text but the root: if the desk has a pattern on
  // it, the text is sitting on that pattern
  let onDesktopPattern = false;
  if (bg && node && ['HTML', 'BODY'].includes(node.tagName)) {
    const desk = getComputedStyle(document.body, '::before');
    onDesktopPattern = desk.backgroundImage && desk.backgroundImage !== 'none';
  }

  // gradient text has no usable `color`; collect its stops instead
  const stops = clip
    ? Array.from(cs.backgroundImage.matchAll(/rgba?\([^)]+\)/g)).map((m) => m[0])
    : [];

  return {
    text,
    color: cs.color,
    fontSize: parseFloat(cs.fontSize),
    weight: parseInt(cs.fontWeight, 10) || 400,
    fontFamily: cs.fontFamily.split(',')[0].replace(/["']/g, ''),
    bg,
    patterned,
    onDesktopPattern,
    clipStops: stops,
    node: node ? node.tagName + (node.className && typeof node.className === 'string' ? '.' + node.className.trim().split(/\s+/)[0] : '') : null,
  };
  };
  const els = Array.from(document.querySelectorAll(selector));
  if (all) return els.map(measure);
  return els.length ? measure(els[0]) : { missing: true };
}
"""

# sweeps measure *every* match and are reported one row per distinct colour
# pair, so a palette with five hues cannot pass on two of them
SWEEPS = [
    ("tag hue", "/notes/", ".finder-tags .tag"),
    ("tag hue (cloud)", "/", ".tag-cloud .tag"),
]



def srgb(colour: str) -> tuple[float, float, float]:
    nums = [float(n) for n in re.findall(r"[\d.]+", colour)[:3]]
    return tuple(c / 255 for c in nums)  # type: ignore[return-value]


def luminance(colour: str) -> float:
    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(c) for c in srgb(colour))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def threshold(px: float, weight: int) -> float:
    large = px >= 24 or (px >= 18.66 and weight >= 700)
    return 3.0 if large else 4.5


def main() -> int:
    if not (DIST / "index.html").exists():
        print("dist/ is missing — run `npm run build` first", file=sys.stderr)
        return 2

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright is not installed — see the README", file=sys.stderr)
        return 2

    httpd, origin = serve_dist()
    failures: list[str] = []
    rows: list[tuple] = []
    patterned_hits: list[str] = []
    skipped = sorted({c[0] for c in CHECKS if c[1] is None})

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 1000})

            for theme, attribute in THEMES:
                for page_path in dict.fromkeys(c[1] for c in CHECKS if c[1] is not None):
                    page.goto(f"{origin}{page_path}", wait_until="load")
                    page.evaluate(
                        "attr => { const r = document.documentElement;"
                        " if (attr) r.dataset.theme = attr; else delete r.dataset.theme; }",
                        attribute,
                    )
                    page.wait_for_timeout(60)

                    queued: list[tuple[str, dict]] = []
                    for label, path, selector in [c for c in CHECKS if c[1] == page_path]:
                        info = page.evaluate(MEASURE, {"selector": selector, "all": False})
                        queued.append((label, info))
                    for label, path, selector in [s for s in SWEEPS if s[1] == page_path]:
                        seen: set[tuple] = set()
                        for info in page.evaluate(MEASURE, {"selector": selector, "all": True}):
                            key = (info["color"], info["bg"], info["fontSize"], info["weight"])
                            if key in seen:
                                continue
                            seen.add(key)
                            queued.append((f"{label}: {info['text']}", info))

                    for label, info in queued:
                        if info.get("missing"):
                            failures.append(f"{theme:6s} {label:34s} selector not found")
                            continue
                        if info["patterned"]:
                            patterned_hits.append(
                                f"{theme} {label} — pattern behind text: {info['patterned']}"
                            )
                        if info["onDesktopPattern"]:
                            patterned_hits.append(f"{theme} {label} — text sits on the desktop dither")
                        if info["clipStops"]:
                            # gradient text: check every stop against the paper
                            for stop in info["clipStops"]:
                                r = contrast(info["bg"] or "#ffffff", stop)
                                rows.append((theme, label + f" [{stop}]", info, r,
                                             threshold(info["fontSize"], info["weight"])))
                            continue
                        bg = info["bg"]
                        if not bg:
                            failures.append(f"{theme:6s} {label:34s} no background found behind it")
                            continue
                        rows.append((theme, label, info, contrast(bg, info["color"]),
                                     threshold(info["fontSize"], info["weight"])))

            browser.close()
    finally:
        httpd.shutdown()

    print(f"{'theme':6s} {'text style':36s} {'size/weight':12s} {'colour on':40s} {'ratio':>7s}  need")
    print("-" * 118)
    for theme, label, info, ratio, need in rows:
        ok = ratio >= need
        if not ok:
            failures.append(
                f"{theme} {label} — {ratio:.2f}:1, needs {need} "
                f"({info['fontSize']:.0f}px/{info['weight']})"
            )
        size = f"{info['fontSize']:.0f}px/{info['weight']}"
        pair = f"{info['color']} on {info['bg'] or '?'}"
        print(f"{theme:6s} {label[:36]:36s} {size:12s} {pair[:40]:40s} {ratio:6.2f}:1  {need}")

    print()
    if patterned_hits:
        print(f"PATTERNS BEHIND TEXT ({len(patterned_hits)}):")
        for hit in patterned_hits:
            print("  ✗", hit)
        print()
    if skipped:
        print(f"skipped, not in the content: {', '.join(skipped)}")
    print(f"{len(rows)} text styles measured; {len(patterned_hits)} sitting on a pattern")
    if failures:
        print(f"\nFAILED ({len(failures)}):")
        for f in failures:
            print("  ✗", f)
        return 1
    print("\nall contrast checks pass (WCAG 2.1 AA: 4.5:1 body, 3:1 large)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
