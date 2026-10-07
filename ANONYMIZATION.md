# Anonymisation policy

This repository is published. Everything in it — sources, content, assets, the
build output — must be readable by a stranger without identifying any person,
company, customer or system that is not public.

The policy exists because the notes are written from real work. Real work is
full of names. Removing the names is the easy half; the other half is removing
the *combination* of details that adds up to a name.

## What must never appear

| class | examples |
| --- | --- |
| people | names, surnames, handles, email addresses, job titles in a unique combination |
| organisations | company, brand, product or client names; client-identifying project codenames |
| systems | hostnames, internal DNS names, cloud account ids, ticket prefixes and issue keys |
| addresses | IPv4/IPv6 addresses, MAC addresses, phone numbers |
| paths | `/home/<person>/…`, `C:\Users\<person>\…`, share names |
| secrets | tokens, API keys, passwords, PEM blocks, session ids |
| metadata | git author identities, image EXIF, PDF/DOCX author fields |
| sums | dates, counts, prices and regional breakdowns that, combined, identify a subject |

## How it is enforced

`npm run anon` runs `scripts/check-anonymized.mjs`. It fails (exit 1) if:

1. a **shape check** matches: email addresses, IPv4 addresses outside the
   documentation ranges, absolute paths containing a real username,
   credential-looking strings, PEM headers, bearer tokens, password-ish
   assignments, or phone numbers;
2. any term listed in **`.private-terms`** appears anywhere in the scanned
   text.

The script always reports what it scanned and how many terms it loaded, so an
empty term list is visible instead of silently passing everything.

## Why the term list is not in the repository

A denylist committed to the tree publishes the very names it protects. The
list lives in `.private-terms`, which is git-ignored; a template with
placeholder entries is committed as `.private-terms.example`.

Add a term, and the next run of `npm run anon` fails on every occurrence —
including occurrences inside the built HTML.

## Writing a note so it passes

- Describe the *shape* of the work, not the parties: "a franchise ordering
  portal", "a mini-PC with four SATA drives", "a self-hosted file-sharing
  container".
- Use documentation address ranges: `10.0.0.0/8`, `192.0.2.0/24`,
  `198.51.100.0/24`, `203.0.113.0/24`. Never a real address, even a private
  one, if it happens to be the real one.
- Write paths with a placeholder user: `C:/Users/<user>/…`, `/home/user/…`.
- Quote errors and commands verbatim; they are the point of the note and
  rarely identifying. Strip the hostname from a prompt line.
- Do not publish screenshots of real systems. If a screenshot is needed,
  redact it, or describe it in text instead.
- Check the *sums*: a version, a date, a headcount and an industry together
  can identify a customer with no name in sight.

## What the scan deliberately skips

Generated ascii art (`src/art/pieces/*.js`, and the same art rendered into the
built HTML) is machine output: thousands of cells of punctuation decoded from a
photograph. It matches address-shaped patterns by accident — the first run of
the gate flagged a run of digits and brackets as a phone number — so its glyphs
and colour blob are removed before scanning, while every human-written part of
the module (its header comment, the note text, the source url) is still scanned.

The run reports how many files had art removed, so the narrowing is visible
rather than silent. Everything else — prose, frontmatter, captions, code,
metadata — is scanned whole.

## Before publishing

```bash
npm run anon && npm run build && npm run anon
```

Running the check both before and after the build catches a term that appears
in the HTML through a template or a component — for example in a caption or a
generated listing — rather than in the source text.

Then, and this is the part no script does: read the diff out loud and ask
whether anyone mentioned in it could recognise themselves.
