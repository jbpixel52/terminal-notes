---
title: "The steps only a human can do"
description: "Some of a setup belongs to a person: a consent screen, a code on a phone, a key visible only in a dashboard. A wizard script is how that handover stops being improvised."
pubDate: 2026-10-08
tags: [automation, agents, process]
minutes: 6
ascii:
  art: the-steps-only-a-human-can-do
---

Handing work to an agent works until it doesn't, and it stops at a predictable
line: the steps that need a human body. Creating an account. Approving an OAuth
consent screen. Reading a code off a phone. Copying a key that is displayed once,
in a dashboard, behind a login. Wiring a CI secret nobody can read back. Pulling
a cable.

Those steps are not hard. They are *tedious to do by hand and tedious to
re-explain*, which is the worst combination — so they get improvised every time,
in chat, with the instructions drifting a little on each pass.

## A wizard instead of a paragraph

The fix is unglamorous and works: a bash script that walks the human through the
procedure. It opens each URL in a browser, says exactly what to click and what to
copy, captures the value, writes it where it belongs — `.env`, a GitHub secret,
both — confirms at each stage, and shows how many stages are left.

Thirty lines of library (progress, confirmation gates, cross-platform URL
opening, hidden secret entry, idempotent `.env` writes) and then one stage per
step. The library is identical in every wizard, which is the point: the shape of
the interaction is solved once, and the human recognises it immediately even in a
procedure they have never run.

## The rules that make it good

- **Read the repository before writing stages.** Every `secrets.*` and `vars.*`
  reference in a workflow is a value somebody has to produce. Every `.env` key is
  a value somebody has to find. Ask the repo which steps exist; don't ask the
  user cold.
- **One focused task per stage, and clear the screen between them.** A stage that
  scrolls away takes its instructions with it, and the human ends up guessing.
- **Open the URL before asking for its value.** The order is the whole usability
  story: the page is in front of them when the question arrives.
- **Hidden entry for anything secret**, so a token is never visible over a
  shoulder or in a screen recording.
- **Only set the CI secrets CI actually reads.** `set_secret` is not a dumping
  ground; a name that no workflow references is a name nobody will ever rotate.
- **Confirm before irreversible actions** — deleting, cutting over, rotating,
  revoking.
- **Never invent a UI path.** "Dashboard → Developers → API keys → reveal" is
  only acceptable if you know it is current. Where you don't, say so and ask, or
  read the docs. A wizard that confidently sends someone to a menu that no longer
  exists is worse than no wizard.

## Prefer the non-interactive path

Interactive prompts are a trap, and not only for the wizard. A CLI that refuses a
login inside a pseudo-terminal usually has a flag for it — a non-interactive or
agent mode — and the real login belongs to the human, in their own terminal.
Anything that comes back as a one-time code in a chat message is single-use and
must never be the plan; it is a fallback with a countdown.

Same instinct throughout: script the tooling's non-interactive form, and let the
human do only the human part.

## Verify it without running it

You cannot test a wizard end to end — it opens browsers and blocks on a person.
So trace it statically instead:

```bash
bash -n setup.sh        # syntax
shellcheck setup.sh     # quoting, unset vars, bad conditionals
```

Then read it against the scope list: every value you identified is captured, each
one lands where you said it would, and every `set_secret` name matches a
`secrets.*` reference in CI exactly. That check is mechanical and it catches the
failure that matters — a stage that collects a value and then writes it nowhere.

## Ephemeral by default

A wizard is built for one run. Unless the user wants a repeatable setup path that
lives in the repository, it belongs in a scratch directory and gets deleted when
the job is done, because a stale wizard is a second, wrong copy of your setup
documentation. When it is worth keeping, commit it and link it from the README so
the next person runs the script instead of asking an agent to explain the
procedure again.

That is the division of labour the whole note is about: the agent does the parts
it can do, the human does the parts only they can, and the seam between them is a
script rather than a conversation.
