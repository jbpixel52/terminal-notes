#!/usr/bin/env python3
"""
verify_site.py — prove the built site actually works in a real browser.

It does not trust the build log. For every page in dist/ it checks:

  * the route answers 200 (404.html is allowed to answer 404);
  * <title> and an <h1> exist and are non-empty;
  * where the page has an <ascii-art> element, that element has *rendered*
    something: a <canvas> with real width, or a <pre> with non-whitespace
    content. An element existing is not a page rendering;
  * no console errors were logged (except the browser's own warnings);
  * the theme toggle flips the document to the light palette and back.

Screenshots are written as evidence to .verify/.

Usage:
    python scripts/verify_site.py [--base-url http://127.0.0.1:4321] [--dist dist]

Interpreter: the environment that already has Playwright installed
(here: a virtualenv whose path is given by $PLAYWRIGHT_PY, default
"$HOME/.venvs/shots/Scripts/python.exe").
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

OK: list[str] = []
BAD: list[str] = []


def check(condition: bool, name: str, detail: str = "") -> bool:
    if condition:
        OK.append(name)
        print(f"PASS {name}")
    else:
        BAD.append(name)
        print(f"FAIL {name}{' — ' + detail if detail else ''}")
    return condition


def routes_from_dist(dist: Path) -> list[str]:
    """Every route the build produced, derived from the files it wrote."""
    routes = []
    for html in sorted(dist.rglob("*.html")):
        rel = html.relative_to(dist).as_posix()
        if rel == "index.html":
            routes.append("/")
        elif rel.endswith("/index.html"):
            routes.append("/" + rel[: -len("index.html")])
        else:
            routes.append("/" + rel)
    return routes


def wait_for_server(url: str, timeout: float = 60.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                if r.status < 500:
                    return True
        except urllib.error.HTTPError:
            return True
        except Exception:
            time.sleep(0.7)
    return False


ASCII_RENDERED = """
(el) => {
  const canvas = el.querySelector('canvas');
  if (canvas && canvas.width > 8 && canvas.height > 8) {
    return { kind: 'canvas', w: canvas.width, h: canvas.height };
  }
  const pre = el.querySelector('pre');
  if (pre && pre.textContent.trim().length > 8) {
    return { kind: 'pre', chars: pre.textContent.trim().length };
  }
  return null;
}
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:4321")
    ap.add_argument("--dist", default="dist")
    ap.add_argument("--out", default=".verify")
    args = ap.parse_args()

    dist = Path(args.dist)
    if not dist.is_dir():
        print(f"FAIL no build found at {dist} — run `npm run build` first")
        return 1

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    if not wait_for_server(args.base_url + "/"):
        print(f"FAIL nothing answering at {args.base_url} — is the preview server up?")
        return 1

    routes = routes_from_dist(dist)
    print(f"routes discovered from {dist}/: {len(routes)}")

    note_routes: list[str] = []
    ascii_routes: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        # dark, explicitly: the site's own default, not the headless default
        ctx = browser.new_context(
            viewport={"width": 1600, "height": 1000}, color_scheme="dark"
        )
        page = ctx.new_page()

        console_errors: list[str] = []
        page.on(
            "console",
            lambda m: console_errors.append(f"{m.type}: {m.text}")
            if m.type == "error"
            else None,
        )
        page.on("pageerror", lambda e: console_errors.append(f"pageerror: {e}"))

        for route in routes:
            console_errors.clear()
            url = args.base_url + route
            resp = page.goto(url, wait_until="networkidle", timeout=30_000)
            status = resp.status if resp else 0
            # the static preview server serves 404.html as a normal file
            expected = {200, 404} if route.endswith("404.html") else {200}

            check(
                status in expected,
                f"GET {route} -> {status}",
                f"expected {' or '.join(str(s) for s in expected)}",
            )
            check(page.title().strip() != "", f"title {route}")

            h1 = page.locator("h1").first
            check(
                h1.count() == 1 and h1.inner_text().strip() != "",
                f"h1 {route}",
                "no h1, or empty",
            )

            art = page.locator("ascii-art")
            n = art.count()
            if n:
                ascii_routes.append(route)
                for i in range(n):
                    el = art.nth(i)
                    el.scroll_into_view_if_needed()
                    page.wait_for_timeout(650)  # the runtime mounts on intersection
                    rendered = el.evaluate(ASCII_RENDERED)
                    piece = el.get_attribute("piece")
                    check(
                        rendered is not None,
                        f"ascii rendered {route} [{piece}]",
                        "element present but nothing drawn",
                    )

            # generated pieces: a canvas that must have actually painted, at the
            # container's width, once it scrolls into view. Two per page is
            # enough — the gallery page has 22 and each costs a decode.
            stages = page.locator(".art-stage")
            for i in range(min(stages.count(), 2)):
                stage = stages.nth(i)
                stage.scroll_into_view_if_needed()
                page.wait_for_timeout(1500)  # let the decode finish, then judge it
                canvas = stage.locator("canvas")
                slug = canvas.get_attribute("data-art")
                box = canvas.bounding_box()
                px = canvas.evaluate("(c) => [c.width, c.height]")
                check(
                    box is not None and box["width"] > 60 and px[0] > 60 and px[1] > 60,
                    f"art mounted {route} [{slug}]",
                    f"box={box} canvas px={px}",
                )
                # and the picture is not blank: some pixels differ from the ground
                distinct = canvas.evaluate(
                    """(c) => {
                      const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
                      const seen = new Set();
                      for (let i = 0; i < d.length; i += 4 * 97) {
                        seen.add((d[i] >> 4) + ',' + (d[i+1] >> 4) + ',' + (d[i+2] >> 4));
                        if (seen.size > 6) break;
                      }
                      return seen.size;
                    }"""
                )
                check(
                    distinct > 4,
                    f"art has detail {route} [{slug}]",
                    f"only {distinct} distinct colours sampled",
                )

            if route.startswith("/notes/") and route != "/notes/":
                note_routes.append(route)

            check(
                not console_errors,
                f"console clean {route}",
                "; ".join(console_errors[:3]),
            )

            shot = out / (route.strip("/").replace("/", "_") or "index")
            page.screenshot(path=str(shot.with_suffix(".png")), full_page=False)

        # --- the home page, full height, as the reader sees it -------------
        page.goto(args.base_url + "/", wait_until="networkidle")
        page.wait_for_timeout(1200)
        page.screenshot(path=str(out / "home-full.png"), full_page=True)

        # --- mobile width --------------------------------------------------
        mob = ctx.new_page()
        mob.set_viewport_size({"width": 390, "height": 844})

        def overflow_of(pg, url: str) -> int:
            pg.goto(url, wait_until="networkidle")
            pg.wait_for_timeout(900)
            return pg.evaluate(
                "() => document.documentElement.scrollWidth - window.innerWidth"
            )

        home_overflow = overflow_of(mob, args.base_url + "/")
        mob.screenshot(path=str(out / "home-mobile.png"), full_page=False)
        check(
            home_overflow <= 2,
            f"mobile: no horizontal overflow on / ({home_overflow}px)",
            f"{home_overflow}px wider than the viewport",
        )

        # a note page: the art is wider than a phone, and the frame around it
        # must scroll internally rather than pushing the page sideways
        mob_note = overflow_of(mob, args.base_url + (note_routes[0] if note_routes else "/notes/"))
        mob.screenshot(path=str(out / "note-mobile.png"), full_page=False)
        check(
            mob_note <= 2,
            f"mobile: no horizontal overflow on a note page ({mob_note}px)",
            f"{mob_note}px wider than the viewport",
        )

        # --- a note page, top and bottom ------------------------------------
        target = note_routes[0] if note_routes else "/notes/"
        page.goto(args.base_url + target, wait_until="networkidle")
        page.wait_for_timeout(900)
        page.screenshot(path=str(out / "note-top.png"), full_page=False)
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(400)
        page.screenshot(path=str(out / "note-bottom.png"), full_page=False)

        # --- theme toggle (order-independent: read, flip, read) -------------
        # the ground colour is on <html> (the body is transparent so the grain
        # gradient can sit behind it), so measure there and on the washes
        page.goto(args.base_url + "/", wait_until="networkidle")
        probe = (
            "() => [getComputedStyle(document.documentElement).getPropertyValue('--bg').trim(),"
            " getComputedStyle(document.documentElement).backgroundColor,"
            " getComputedStyle(document.documentElement).getPropertyValue('--wash-1').trim(),"
            " document.documentElement.dataset.theme || 'dark']"
        )
        r0 = page.evaluate(probe)
        page.click("[data-theme-toggle]")
        page.wait_for_timeout(250)
        r1 = page.evaluate(probe)
        check(
            r1[3] != r0[3] and r1[0] != r0[0] and r1[1] != r0[1] and r1[2] != r0[2],
            "theme toggle switches palette",
            f"{r0} -> {r1}",
        )
        page.reload(wait_until="networkidle")
        after_theme = page.evaluate("() => document.documentElement.dataset.theme || 'dark'")
        check(
            after_theme == r1[3],
            "theme choice survives a reload",
            f"after reload: {after_theme}, expected {r1[3]}",
        )
        page.screenshot(path=str(out / "home-toggled.png"), full_page=False)

        # --- what a reader with a light OS preference gets -------------------
        light_ctx = browser.new_context(
            viewport={"width": 1280, "height": 900}, color_scheme="light"
        )
        lp = light_ctx.new_page()
        lp.goto(args.base_url + "/", wait_until="networkidle")
        lp.wait_for_timeout(900)
        light_bg = lp.evaluate("() => getComputedStyle(document.body).backgroundColor")
        check(
            lp.evaluate("() => document.documentElement.dataset.theme") == "light",
            "light OS preference gets the light palette",
            f"bg={light_bg}",
        )
        lp.screenshot(path=str(out / "home-os-light.png"), full_page=False)
        light_ctx.close()

        # --- the grain gradient is actually painted --------------------------
        # two fixed layers behind the content: washes and grain. A stylesheet
        # that failed to load, or a pseudo-element that never rendered, would
        # leave both empty.
        page.goto(args.base_url + "/", wait_until="networkidle")
        layers = page.evaluate(
            """() => {
              const w = getComputedStyle(document.body, '::before');
              const g = getComputedStyle(document.body, '::after');
              return {
                washes: (w.backgroundImage.match(/radial-gradient/g) || []).length,
                washAnim: w.animationName,
                grain: g.backgroundImage.includes('svg') && g.backgroundImage.length > 200,
                grainOpacity: parseFloat(g.opacity),
                grainAnim: g.animationName,
                position: w.position,
              };
            }"""
        )
        check(
            layers["washes"] >= 4 and layers["grain"] and layers["grainOpacity"] > 0.01,
            "grain gradient layers are painted",
            str(layers),
        )
        check(
            layers["position"] == "fixed",
            "the gradient sits behind the page and does not scroll",
            str(layers),
        )

        browser.close()

    # --- counts must agree with the build -------------------------------
    # every picture must be in the HTML itself, for readers without JavaScript
    missing_still = []
    for html in sorted(dist.rglob("*.html")):
        text = html.read_text(encoding="utf-8", errors="ignore")
        if "art-stage" in text and '<pre class="art-still"' not in text:
            missing_still.append(str(html.relative_to(dist)))
    check(
        not missing_still,
        f"no-JS still present in every built page with art ({len(missing_still)} missing)",
        ", ".join(missing_still[:3]),
    )

    print()
    print(f"routes checked      : {len(routes)}")
    print(f"note pages          : {len(note_routes)}")
    print(f"routes with ascii   : {len(ascii_routes)}")
    print(f"screenshots         : {len(list(out.glob('*.png')))} in {out}/")

    total = len(OK) + len(BAD)
    print(f"\n{len(OK)}/{total} checks passed")
    if BAD:
        print("\nfailures:")
        for name in BAD:
            print(f"  - {name}")
    return 0 if not BAD else 1


if __name__ == "__main__":
    sys.exit(main())
