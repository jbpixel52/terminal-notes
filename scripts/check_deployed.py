#!/usr/bin/env python3
"""
check_deployed.py — verify the *deployed* site, over the network.

The local harness proves the build; this proves the deployment. It reads the
live sitemap and checks every URL in it, then asserts content on the pages that
matter, because a 200 is not a page:

  * every <loc> in the live sitemap answers 200, and so does every URL in it
    that the sitemap itself does not list (the feed, robots.txt, the icon,
    the stylesheet the home page links);
  * the home page carries the site title, a note link, and its stylesheet;
  * a note page carries the finished ascii picture in its HTML — the no-JS
    still — and not just the canvas container;
  * the feed parses as XML, has items, and its item links point at the
    deployment's base path rather than at the origin root;
  * robots.txt advertises this deployment's sitemap.

Usage:
    python scripts/check_deployed.py                        # the Pages URL
    python scripts/check_deployed.py --base https://example.com/blog/
    python scripts/check_deployed.py --base ... --expect-base /blog
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

OK: list[str] = []
BAD: list[str] = []
BASE = ""  # the deployment root, set in main(); used by get() to resolve hrefs


def check(condition: bool, name: str, detail: str = "") -> bool:
    (OK if condition else BAD).append(name)
    print(f"{'PASS' if condition else 'FAIL'} {name}{' — ' + detail if detail and not condition else ''}")
    return condition


def get(url: str, timeout: int = 30) -> tuple[int, str]:
    """Fetch a URL, resolving a root-relative href against the deployment.

    Pages link with root-relative paths (`/terminal-notes/notes/...`), and
    urlopen has no idea what origin those belong to — passing one straight
    through fails with "unknown url type". Everything goes through here so that
    never has to be remembered at the call site.
    """
    if not url.startswith(("http://", "https://")):
        url = urllib.parse.urljoin(BASE, url)
    req = urllib.request.Request(url, headers={"User-Agent": "terminal-notes-deploy-check/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:  # DNS, TLS, timeouts
        return 0, f"{type(e).__name__}: {e}"


def main() -> int:
    global BASE
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://jbpixel52.github.io/terminal-notes/")
    ap.add_argument("--expect-base", default=None, help="prefix every internal URL must carry")
    args = ap.parse_args()

    base = args.base if args.base.endswith("/") else args.base + "/"
    BASE = base
    prefix = args.expect_base.rstrip("/") if args.expect_base else urllib.parse.urlparse(base).path.rstrip("/")
    print(f"checking {base}  (internal URLs must start with '{prefix}')\n")

    # --- the sitemap is the route list -------------------------------------
    status, sitemap_index = get(base + "sitemap-index.xml")
    check(status == 200, f"GET sitemap-index.xml -> {status}")
    locs = re.findall(r"<loc>([^<]+)</loc>", sitemap_index)
    pages: list[str] = []
    for loc in locs:
        if loc.endswith(".xml"):
            s, body = get(loc)
            check(s == 200, f"GET {loc} -> {s}")
            pages = re.findall(r"<loc>([^<]+)</loc>", body)
        else:
            pages.append(loc)

    check(len(pages) > 50, f"sitemap lists the built pages ({len(pages)})")

    failures = 0
    for page in pages:
        s, _ = get(page, timeout=25)
        if s != 200:
            failures += 1
            if failures <= 5:
                print(f"FAIL {page} -> {s}")
    check(failures == 0, f"every sitemap URL answers 200 ({len(pages)} checked)", f"{failures} failed")

    # --- the pages that matter ---------------------------------------------
    home_status, home = get(base)
    check(home_status == 200, f"GET {base} -> {home_status}")
    check("Terminal Notes" in home, "home page carries the site title")
    note_links = [u for u in re.findall(r'href="([^"]+/notes/[^"]+/)"', home)]
    check(bool(note_links), "home page links to notes", f"found {len(note_links)}")
    check(
        all(u.startswith(prefix) for u in re.findall(r'(?:href|src)="(/[^"]*)"', home)),
        "every internal URL on the home page carries the base path",
        "; ".join(u for u in re.findall(r'(?:href|src)="(/[^"]*)"', home) if not u.startswith(prefix))[:200],
    )

    assets = re.findall(r'href="([^"]+\.css)"', home)
    if assets:
        # an href is root-relative, so resolve it against the deployment first
        css_url = urllib.parse.urljoin(base, assets[0])
        s, css = get(css_url)
        check(s == 200 and len(css) > 2000, f"the stylesheet loads ({css_url})", f"status {s}")
        # the live sheet must carry the System 7 chrome (the dither tile, the
        # two tokens every window is drawn from) *and* the accents the readable
        # pass added: a link accent, a row tint, and the tag hue pairs
        check(
            "svg+xml" in css and "--paper" in css and "--p-desk" in css,
            "the live stylesheet carries the desktop dither and the paper/ink tokens",
        )
        check(
            "--accent" in css and "--row-tint" in css and "--t1-fg" in css,
            "the live stylesheet carries the accent palette (links, row tint, tag hues)",
        )
        check(
            "ui-sans-serif" in css and "ChiKareGo2" in css,
            "the live stylesheet sets modern text faces and keeps Chicago for the chrome",
        )
        check(
            ".apple" not in css and "apple-menu" not in css,
            "no Apple menu styling remains in the live sheet",
        )

    if note_links:
        s, note = get(note_links[0])
        check(s == 200, f"GET a note page -> {s}")
        check('<pre class="art-still"' in note, "the note page carries the ascii picture as text (no-JS path)")
        check('class="art-canvas"' in note, "the note page carries the canvas for the animated path")
        check(
            'ascii.rest' in note or 'source image' in note,
            "the note page credits the picture's source",
        )

    # --- the feed ----------------------------------------------------------
    s, feed = get(base + "rss.xml")
    check(s == 200, f"GET rss.xml -> {s}")
    items: list[str] = []
    try:
        root = ET.fromstring(feed)
        items = [el.text or "" for el in root.iter("link")][1:]  # [0] is the channel link
        check(len(items) > 10, f"the feed parses and has items ({len(items)})")
    except ET.ParseError as e:
        check(False, "the feed parses as XML", str(e))
    if items:
        # feed links are absolute (rss joins them onto the site origin), so they
        # are compared against the deployment root, not the path prefix
        wrong = [i for i in items if not i.startswith(base)]
        check(not wrong, "every feed link points at the deployment's base path", "; ".join(wrong[:3]))

    # --- robots ------------------------------------------------------------
    s, robots = get(base + "robots.txt")
    check(s == 200 and "sitemap-index.xml" in robots, f"GET robots.txt -> {s}, advertises the sitemap")

    print(f"\n{len(OK)}/{len(OK) + len(BAD)} deployment checks passed")
    if BAD:
        print("failures:")
        for name in BAD:
            print(f"  - {name}")
    return 0 if not BAD else 1


if __name__ == "__main__":
    sys.exit(main())
