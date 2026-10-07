---
title: "Delegating work to parallel agents without losing the thread"
description: "Fan out, then reconcile: give each worker everything it needs, demand a verifiable handle back, and never believe a self-report of a side effect."
pubDate: 2026-05-20
tags: [automation, workflow, agents]
minutes: 7
ascii:
  piece: starlings
  caption: "many small decisions, one shape"
---

Splitting a job across several autonomous workers is mostly a coordination
problem, and the coordination failures are all the same shape: the parent
believes a summary instead of checking an artifact. The rest of this is the
set of habits that stop that.

## Fan out, then reconcile

The productive pattern is: dispatch independent pieces in parallel, have each
one write its result somewhere durable, and then aggregate with *code*, not
prose. The parent's job after the fan-out is counting:

```
dispatched:      6
returned:        6
files on disk:   6
records in file: 5      <-- the discrepancy is the finding
```

A child that reports "all 42 items extracted" while its output file holds 41
is the ordinary case, not a rare one, and an aggregation step that counts does
the verification for free.

## Every task must be self-contained

A worker does not inherit the conversation. It has no idea why the task
exists, what was decided, or which file matters. So the brief has to carry:

- the goal, stated as an outcome rather than an activity;
- the background it cannot look up (paths, schemas, why this is being done);
- the exact shape of the deliverable — and where to write it;
- the constraints that are not obvious, including the style and the audience.

The failure mode of a thin brief is confident, plausible work that answers a
different question. The failure mode of a verbose one is slower workers, which
is much cheaper.

## Ask for a handle, not an adjective

The deliverable of a task should be something the parent can open:

| ask for this | not this |
| --- | --- |
| an absolute file path that exists | "wrote a summary" |
| a URL and the HTTP status you read back | "published successfully" |
| an id the database returns | "created the record" |
| the command you ran and its output | "tested it" |

A self-report of a side effect is a claim about a *different machine's*
memory. For anything crossing a boundary — an upload, a remote write, an API
call, a message sent — the parent reads it back itself, through a different
path than the one the child wrote with.

## Isolate the blast radius

Two workers writing the same file is a silent last-write-wins: both report
success, one of them is gone. Two conventions prevent it cheaply:

- one output file per task, named for the task;
- workers edit only inside their own directory, and the parent does the
  merging.

It also helps to forbid the things that need judgement a worker cannot have:
closing tracked work, sending anything to a human, force-pushing. A worker
that finishes a piece of a pipeline returns *findings*, and the parent — which
can see the whole board — makes the state transition.

## Read the transcript when it drifts

Long-running workers should stream what they are doing somewhere inspectable.
The value is not surveillance, it is early correction: a worker that has
misread the task is visibly consistent about it within the first minute, and
steering it then is cheap. The same worker after ten minutes has built a lot
of confidence on the wrong foundation.

Ask for progress in a form that survives a timeout: append partial results to
a file as they are produced, rather than holding everything in memory for a
single final answer. A worker that times out having written 80% is useful; one
that times out having written 0% is a retry.

## Parallelism has a budget

Workers run against the same rate limits, the same disk, and the same budget
as each other. Practical limits:

- six to ten at a time is usually plenty; beyond that, coordination costs more
  than the time saved;
- heterogeneous tasks parallelise well; homogeneous ones are better batched in
  one worker;
- a task that must ask a human a question is not a candidate — workers cannot
  ask, and a blocked worker burns its budget discovering that.

## When to fan out at all

Fan out when the subtasks are genuinely independent, when each produces
intermediate output too large to keep in one context, or when each needs a
different specialism. Do not fan out:

- a decision that needs one coherent voice (use one worker, or do it
  yourself);
- a five-minute single-tool operation (the dispatch overhead exceeds the
  work);
- anything where the pieces must negotiate with each other mid-flight.

## The habit that makes it work

Write the reconciliation before dispatching. If you cannot say how you will
check the combined result — what you will count, what you will open, what you
will request — then the fan-out is not ready, because "it all came back
green" is not a result you can defend.
