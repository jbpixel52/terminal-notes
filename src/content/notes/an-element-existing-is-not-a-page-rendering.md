---
title: "An element existing is not a page rendering"
description: "Scripted browser checks that pass against a broken page: hydration races, SPA navigation, case-folded text, zero-size canvases and the zombie dev server."
pubDate: 2026-08-02
tags: [testing, browser, verification]
minutes: 7
ascii:
  piece: spinners
  caption: "waiting for the right moment, not a fixed timeout"
---

Automated browser checks are the only way to prove a web page works, and they
fail in both directions: passing a page that is broken, and failing a page
that is fine. Both are expensive; the first is worse, because it stops you
looking.

These are the specific traps, each one a real false result rather than a
theoretical risk.

## Filling before hydration throws the values away

A React (or Vue, or Svelte) form that has been server-rendered exists in the
DOM before it is interactive. Filling the inputs immediately after
`domcontentloaded` looks like it worked: `input.value` reads back correctly
for a moment. Then hydration runs, the framework re-renders from its own
state as empty, and the values are gone. The subsequent submit hits native
`required` validation and nothing happens — with no error anywhere.

The fix is not a longer `sleep`. Wait for the framework to be interactive
(`networkidle`, or an explicit readiness signal), then *assert the value
took*, and re-fill in a loop if it did not:

```python
for _ in range(10):
    page.fill("#email", "chef@example.com")
    if page.input_value("#email") == "chef@example.com":
        break
    page.wait_for_timeout(100)
```

## Waiting for the wrong thing on client-side navigation

`wait_for_load_state("networkidle")` after a click that triggers an SPA route
change can return *immediately* — the route changed and no new resources were
requested, so there is nothing to be idle about. Anything read next may be
the old page.

Wait on the destination instead:

```python
page.click("text=Orders")
page.wait_for_url("**/orders")      # or wait_for_selector on the new H1
```

`networkidle` is also the slowest option available; it is a blunt instrument
that costs seconds per navigation and still races.

## Text is what is rendered, not what is in the markup

CSS `text-transform: uppercase` is invisible to the DOM but visible in
`inner_text()`. An assertion expecting `Apariciones · 2` fails against a page
rendering `APARICIONES · 2`, and the fix is to compare case-insensitively
(the same trap applies to `::first-letter` styling and non-breaking spaces in
labels).

## `count() >= 1` proves a node, not a load

The most common false pass:

```python
assert page.locator("img.hero").count() >= 1     # a node exists
```

An element can exist and be invisible, zero-sized, behind a failed layout,
or still the placeholder the framework shipped. For images, assert on
`naturalWidth` — the decoded image's actual size:

```python
w = page.eval_on_selector("img.hero", "el => el.naturalWidth")
assert w > 0, "image element present but not decoded"
```

The same logic applies to canvases and charts: check `canvas.width`,
`getBoundingClientRect()` height, and ideally a pixel or a data attribute the
renderer sets on success. A charting library that threw during render leaves
an empty canvas that satisfies every "is it there" assertion.

## The dev server can be a zombie

A dev server whose port is LISTENING but which times out on every request
(`curl` returning HTTP code `000`) is a real state, usually after a file
watcher has died. Every browser check then fails with a timeout, and the
natural conclusion — "my code broke" — is wrong.

Check the server before the page:

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3000/    # 000 = zombie
```

If it is `000`, kill the PID and start fresh. Also poll for readiness before
the *first* navigation: the first hit on a dev route compiles, and a short
navigation timeout can fire while the server is doing exactly what it should.

## Timestamps drift with the machine that rendered them

A date formatted without an explicit timezone renders differently on the CI
machine than on a laptop, so an assertion on the rendered string passes
locally and fails in the pipeline. Pin the zone in the application
(`toLocaleDateString(..., { timeZone: 'UTC' })`) and keep the check itself
loose — assert the presence and ordering of dates, not the exact string,
unless the string is the contract.

## Every check should leave evidence

A pass/fail line tells you *that* something broke; a screenshot tells you
what it looked like. Capture one at each key state, keep them with the run,
and name them after the state rather than a timestamp — the value of the
evidence is comparing this run against the last one.

## What good looks like

- The harness is in the repository, and re-runs after every change, so the
  checks are a regression suite and not a one-time investigation.
- It exits non-zero on failure, so it can be wired into CI.
- It asserts on outcomes the user would notice — the row appears, the total
  is right, the image decoded — rather than on implementation details.
- It fails loudly when misconfigured. A run that silently checks zero pages
  and reports success is worse than no check at all, so print the counts:

```
routes discovered: 19
checks passed: 141/141
```
