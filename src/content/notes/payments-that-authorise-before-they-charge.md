---
title: "Payments that authorise before they charge"
description: "A zero-dollar check, a buffer on the authorisation, a capture for the exact total. The test surface is arithmetic, and the interesting failures are sums nobody reconciled."
pubDate: 2026-01-14
tags: [testing, payments, verification]
minutes: 8
ascii:
  art: payments-that-authorise-before-they-charge
---

An order flow that validates a card before the order exists, and charges it
when the order is placed, has a lifecycle with four distinct states — and the
mistakes in testing it are almost all about which state a number belongs to.

```
1. verify    a zero-value authorisation, to answer "is this card usable?"
2. authorise the total plus a buffer, to reserve the money
3. capture   the exact order total
4. release   the difference, or the whole thing if the order dies
```

## The zero-value authorisation

The cheap check is a zero-amount authorisation: it proves the card exists and is
usable without moving money. Two caveats worth knowing before it goes in a test
plan:

- not every issuer or processor accepts a zero-value authorisation; where it is
  refused, the fallback is a small real amount, immediately voided;
- it is still a request to the card network, so "free" is not quite true — it
  appears in the customer's list of pending items even when it resolves to zero.

## The buffer is a promise you have to keep

Authorising the total plus a margin (a percentage for tip, tax or late additions)
is a legitimate pattern, and it creates two obligations:

- **the capture must be for the exact final total**, not for the authorised
  amount. A capture larger than the order total is a defect, unless the flow
  documents it as a pre-authorisation and releases the difference;
- **the release must be verified**, not assumed. Read the transaction back from
  the processor and assert the released amount and the final state.

This is why the arithmetic is the test surface. Here is the failure that taught
me: a report showing a capture rate of **132%** of order value. Nothing had
double-charged. The report was dividing captured cents by *order subtotal*
cents, while the captures correctly included tax and the tip — two different
denominators compared as if they were the same. The bug was in the metric, and
a metric is as testable as a payment.

## Assert on money, in cents, in both directions

- Store and compare integer minor units. A float comparison of currency is a
  flaky test waiting to be written.
- For every captured transaction, assert `captured == order_total` to the cent,
  and for every abandoned order, assert `authorised − captured` was released.
- Watch the boundary rows as their own cases: a total of exactly zero (a fully
  discounted order — do you authorise nothing, or refuse?), a total that exceeds
  a per-transaction limit, and a currency with a different number of decimals.
- Time matters: authorisations expire. A test that takes twenty minutes to fill
  a basket will not exercise the same state as a user who takes two, so expiry
  needs a deliberately aged fixture rather than a real wait.

## Reconcile daily, not per test

Tests prove a single flow. The thing that catches the class of bug nobody
designed a test for is a nightly reconciliation between your order table and
the processor's transaction list:

| check | what a mismatch means |
| --- | --- |
| count of captures vs count of paid orders | a capture with no order, or the reverse |
| sum of captured cents vs sum of order totals | the 132% denominator bug, caught by arithmetic |
| authorisations older than seven days, still open | an expiry nobody handles |
| refunds without a matching capture | a support action that escaped the flow |

Four numbers, once a day. It is the cheapest test in the suite and the only one
that looks at the whole population instead of a sample.
