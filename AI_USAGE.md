# AI_USAGE.md

## Which assistant, and how

Used Claude (claude.ai) throughout the project as a coding and planning
collaborator — not to generate the assignment's answers wholesale, but to
help design the architecture, write and debug code, and stress-test my own
reasoning. Free tier only, no subscription purchased, per the assignment's
constraint.

## How I used it, day by day

- **Day 1:** Asked Claude to help plan the assignment day-by-day, then
  specifically to help read the ledger systematically rather than by eye
  — it wrote a verification script (`explore.py`) that programmatically
  checked for the data quality categories the policy document calls out
  (future dates, missing fields, GST mismatches, etc.), which I then
  cross-checked against the raw CSV myself.
- **Day 2:** Discussed the architecture decision (Python does arithmetic,
  LLM only does language) with Claude before writing any cleaning code,
  and had it help build `clean.py` around a GSTIN-anchored vendor
  identity approach, which I verified by hand against the raw file.
- **Day 3:** Used it to build the deterministic query functions, then
  specifically asked it to do an *independent* cross-check using
  different code than the main pipeline — this is where it caught (and
  I verified) a real bug, described below.
- **Day 4:** Had it design the LLM intent-classification layer with a
  validated schema (the LLM can't invent function calls or free-form
  parameters — Python checks everything it returns), and the no-LLM
  keyword fallback for hardware that can't run a model at all.
- **Day 5-6:** Used it to help interpret real benchmark output, spot that
  my benchmark script's simplified prompt wasn't a fair accuracy test
  (only a speed test), and draft this documentation.

## Most useful prompt

Asking it, before writing any cleaning code, to state explicitly which
part of the problem belongs to Python and which (if any) belongs to the
language model — and to justify that split. This single decision (LLM
never does arithmetic; it only classifies intent and phrases already-
computed results) shaped every file in the project and is the answer I'm
most confident defending on the follow-up call, precisely because it was
argued through rather than assumed.

## A place it gave me a wrong answer that I caught

While building an independent cross-check script for Q1/Q3/Q7 in Day 3
(deliberately separate code from the main pipeline, so two independent
implementations could confirm each other), Claude's first version of a
vendor-name normalizer had a real bug: it stripped the substring "co" as
a prefix using plain string replacement instead of a word-boundary regex.
This silently corrupted "Nova Paints & **Co**atings" into "Nova Paints &
atings" mid-word, which misrouted that vendor's rows into an "unresolved"
bucket and threw off its computed total by Rs. 20,341.72 in the
cross-check (the main `clean.py` pipeline was unaffected, since it
already used a proper `\bco\b` word-boundary regex).

I caught this by noticing the cross-check reported an unresolved vendor
bucket that shouldn't have existed, and asked Claude to trace exactly
which row failed and why, rather than accepting "close enough" totals.
It found and explained its own bug once asked to isolate it. This is
recorded in full in `DECISIONS.md`'s Day 3 addendum.

I'm including this example specifically because it's the kind of failure
that's easy to miss if you don't independently sanity-check aggregate
totals — a normalizer that "runs without errors" isn't the same as one
that's correct, and this was true of Claude's code exactly as much as it
would be true of my own.

## What I did NOT use AI for

- Deciding the genuine judgement calls documented throughout
  DECISIONS.md and EVALUATION.md (e.g. Q1's "amount payable"
  interpretation, Q7's and Q11's exclusion of certain rows) — these
  were discussed with Claude, but the final call and the reasoning
  behind it is mine, and I could defend either differently if pushed.
- Hand-calculating the answer key in EVALUATION.md — every hand-
  calculated figure was worked out from the raw CSV independently
  before comparing to the tool's output, specifically so this file
  isn't just the tool's own output copied backward.
