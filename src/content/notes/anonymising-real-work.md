---
title: "Anonymising real work into publishable notes"
description: "Technical writing about paid work is a redaction problem. Names are the easy part; the sums, the paths and the screenshots are what actually give a client away."
pubDate: 2026-10-05
tags: [privacy, process, writing]
minutes: 7
ascii:
  piece: scramble
  caption: "the same facts, with the identifying bits scrambled"
---

I keep notes about work. Publishing them means making sure that nothing in
them points at a person, a company, or a system that belongs to someone
else. The first version of that rule — *don't use the client's name* — is
nearly useless, because names are almost never what identifies a subject.

## Names are the cheap part

A paragraph containing "a franchise ordering portal, migrated to a
headless CMS, three regional call centres" has no name in it and still
belongs to exactly one customer. The identifying information is carried by
the *combination*: an industry, a scale, a set of vendor products, a
sprint of dates. Any two of those are innocuous. All five together are a
signature.

The fix is not to write less, it is to move the story up one level of
abstraction until the technical point survives and the subject does not. A
note about a slow query does not need to say which business the query
served. A note about a reverse-proxy cutover does not need the ports or
the hostnames, only the shape of the mistake.

## The classes of identifier

The list I actually work from, because each one has caught something at
least once:

| class | what leaks |
| --- | --- |
| people | names, handles, email addresses, job titles with a unique combination |
| organisations | company, brand, product, project codenames, ticket prefixes |
| hosts | hostnames, internal DNS names, `<name>.local`, cloud account ids |
| addresses | IPv4/IPv6, MAC addresses, phone numbers |
| paths | `/home/<person>/…`, `C:\Users\<person>\…`, share names |
| secrets | tokens, keys, password-shaped strings, PEM headers |
| metadata | git author, EXIF, PDF/DOCX author fields, screenshot window titles |
| sums | dates, headcounts, counts, prices, regional breakdowns |

That last row is the one people forget. Redacting nouns while keeping the
numbers can leave the subject perfectly identifiable.

## Enforce it, don't promise it

A rule in a README is a wish. A script that fails the build is a policy. The
checker here lives in `scripts/check-anonymized.mjs` and does two things:

1. **Shape checks** for data that is never allowed: email addresses,
   IPv4 addresses outside the documentation ranges, absolute paths
   containing a username, credential-looking strings, phone numbers.
2. **A term list** — the actual names and identifiers that must not be
   published — read from a file that is *git-ignored*.

The second half deserves that emphasis. A denylist committed to the
repository is itself the leak: the file that says "never publish these
words" spells the words out in a public tree. Keeping the terms in a
git-ignored file means the repository holds the *mechanism* and the local
machine holds the *data*.

## A scan that reports nothing is not a scan that passed

This is the same failure mode as a backup that has never been restored, and
it looks like this:

```
$ node scripts/check-anonymized.mjs
✓ no private data found
```

Was that every file? Was the term list empty? Did the walker follow the
directory you thought it did? A checker must report its own inputs:

```
scanned 41 files (612 KB) across src/, public/, dist/
term list: 23 terms from .private-terms
0 findings
```

Now "0 findings" is a claim about something. A term count of `0 terms`
is a visible bug rather than a silent pass — which is exactly what
happened the first time: the file had a `.txt` extension I had not
listed, the loader found nothing, and the check cheerfully reported
success for a week.

## Things that defeat a naive text scan

- **Encodings.** A name inside a base64 blob, a URL-encoded query string,
  or a quoted-printable email body is invisible to a plain substring
  search. Decode before scanning, or accept that you are scanning for the
  easy cases.
- **Binary containers.** PDFs, DOCX and XLSX files store their text
  compressed. A byte scan will not find a name in one. Extract the text
  first, or do not publish the file.
- **Line wrapping.** A scanner matching on raw text misses a term split
  across a newline. Normalise whitespace before matching.
- **Git history.** Deleting a file from the working tree does not delete it
  from `.git`. If the repository is published, so is every past version of
  every file. Removing it needs a history rewrite, not a commit.
- **Screenshots.** A cropped image still shows the window title bar, the
  filename in the sidebar, the hostname in a shell prompt. Redaction is a
  pixel operation or it is nothing.

## The rule I use now

Write the note, then name every party that could recognise itself in it.
If any of them could, change what the note says until none of them can —
and then have a script check that the change stayed changed.
