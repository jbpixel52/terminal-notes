---
title: "Scraping a site you are logged into"
description: "A saved session, raw payloads stored before parsing, and an explicit check for the login page. Scrapers fail by scraping nothing and reporting success."
pubDate: 2026-02-25
tags: [scraping, automation, data]
minutes: 7
ascii:
  art: authenticated-scraping
---

Collecting your own data from a platform you have an account on looks like a
loop and a selector. It becomes a maintenance job the moment the platform
changes its markup, and a silent failure the moment a session expires.

## Use a session, never a password in the script

Store a session (cookies, or a token you refresh deliberately) and drive the
browser with it. A password typed by a script is a credential in a log file
waiting to happen, and it puts a login round trip — with its captchas and its
device checks — in the middle of every run. When the session is invalid, that
should be a loud, single, early error: log in once, save, then scrape.

## Store first, parse later

The most valuable interface in the whole pipeline is the one between *fetch*
and *parse*. The fetch step writes what it received, unchanged, to disk; the
parse step reads from disk. Then:

- a parser change does not require a re-scrape (which may not be possible if
  the page has changed since);
- a parse failure is reproducible offline, against the exact bytes that caused
  it;
- you can count what you fetched without trusting the parser.

```
.raw/2026-02-25/page-003.json     <- written by fetch, never edited
.parsed/2026-02-25/page-003.json  <- written by parse, disposable
```

## A 200 that contains a login page is a failed scrape

The single most common silent failure: the session expires, the platform
answers with the login page, the parser finds no records, and the run reports
"0 new items, success". Assert on *what came back*, not just the status:

```python
html = response.text
if "sign in" in html.lower() or "login" in response.url:
    raise SystemExit("session expired: got the login page, not the data")
```

and then assert against the expected shape: a known container element must
exist, and the item count must be greater than zero for a listing you know is
non-empty.

## Paginate until it is actually finished

Two habits that prevent the classic "it collected 60 of 300":

- stop when a page returns no items **and** check the platform's own total
  ("1–60 of 312") against your running count — if they disagree, the run is not
  complete and should say so;
- make the run resumable and incremental: a stable record id, a "seen up to"
  marker, and an upsert. A scrape that must restart from the beginning is a
  scrape you will stop running.

## Be a boring client

Rate-limit yourself below what the platform tolerates, back off exponentially
on 429 and on 5xx, and identify yourself in a user agent. This is not only
politeness: a scraper that gets throttled or blocked mid-run produces partial
data that looks exactly like complete data, so the slow version is also the
correct one. And read the terms — an account having access to a thing is not
the same as permission to extract it in bulk, and that distinction belongs to
whoever owns the account.
