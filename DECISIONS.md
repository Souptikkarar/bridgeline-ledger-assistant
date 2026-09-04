## Day 1 — 2026-09-02 

### What I did
Read `vendor_payment_policy.md` twice and the full 127-row ledger CSV line by line
(not just head -10). Wrote a read-only exploration script (`notes/explore.py`) to
verify anomalies programmatically rather than trust a manual skim — a human eye
misses things in 127 rows of mixed date/number formats, and I wanted evidence I
could re-run, not a one-time impression.

### Architecture decision
The LLM will NOT do arithmetic. Language models are fluent but unreliable at sums,
comparisons across rows, and date math. All totals, filters, ageing, and delay
calculations will be plain Python functions running against a cleaned pandas
dataframe. The LLM's job is limited to two things:
1. Classify an incoming English question into one of a fixed set of query intents
   (or a fallback "can't answer" path).
2. Phrase the Python-computed result as a natural sentence, citing the specific
   invoice rows or policy section the number came from.
This means the tool's correctness depends on the cleaning + query code, not on the
model — which also means it keeps working (in a reduced, code-only mode) even if
Ollama isn't available on a given machine.

### Verified data quality findings (from notes/explore.py)

1. **Duplicate invoice number**: `INV-2024-0041` appears twice (line 56 and line 66),
   same date, different description and taxable amount. Line 66's description
   contains "(revised)" — per policy §6 this supersedes line 56. Line 56 must be
   excluded from totals.
2. **Future-dated invoice**: `INV-2024-0904`, dated 2027-02-14 — after the
   31 Mar 2025 reporting date. Flag per policy §8, don't silently drop it.
3. **Payment before invoice date**: `INV-2024-0905` — invoice dated 2024-12-18,
   payment dated 2024-11-02. Impossible in reality; flag per policy §8.
4. **Missing taxable amount**: `INV-2024-0907` (Meridian Consultants) — described
   as "awaiting final bill", quantity/rate/taxable/GST all blank. Flag, exclude
   from sums that need a taxable amount.
5. **Missing GSTIN (4 rows)**: `INV-2024-0008`, `INV-2024-0034`, `INV-2024-0089`,
   `INV-2024-0060`. Per policy §7, these can't be claimed for input tax credit and
   must be listed separately each quarter.
6. **GST reconciliation failure**: `INV-2024-0906` — taxable ₹244,000 at stated
   rate 18% should be ₹43,920 GST, but the ledger shows ₹29,280 (which is actually
   244,000 × 12%). Rate field and amount field disagree by more than the ₹1
   tolerance in policy §7 — flag for accounts, exclude from ITC claims until fixed.
7. **USD invoices**: `INV-2024-0901`, `INV-2024-0902` (both Precision Tools India,
   imported items). Must convert at the fixed 83.50 rate before adding to any INR
   total, per policy §4 — never sum raw.
8. **One credit note**: `CN-2024-0007` (Bharat Steel Works, −₹84,000, status
   "Adjusted"). Included in vendor totals as a negative, never treated as overdue,
   per policy §5.
9. **Vendor identity**: confirmed that GSTIN is a reliable canonical key — every
   spelling/case/abbreviation variant of a vendor name (e.g. "Konark Fab" /
   "KONARK FABRICATION" / "Konark Fabrication Pvt. Ltd.") shares one GSTIN. The
   4 rows with blank GSTIN (see #5) are the exception and will need a manual
   name-alias fallback in the cleaning step, since they can't be matched on GSTIN.
10. **Date format chaos**: invoice_date and payment_date both mix `DD.MM.YYYY`,
    `YYYY-MM-DD`, `DD/MM/YYYY`, and `DD-Mon-YYYY` formats within the *same column*
    — sometimes even between two rows for the same vendor. All parsed successfully
    once I handled all four formats; no truly unparseable dates found, but a naive
    single-format parser would have silently misread many of these.
11. **Amount formatting chaos**: taxable_amount and gst_amount mix plain numbers,
    `Rs. 12345` prefixed strings, and comma-thousands formatting (some
    international-style `781,057`, at least one Indian lakh-style `1,11,000` for
    INV-2024-0903). A naive "strip commas" approach works for both styles here by
    coincidence (both resolve to the same value once commas are removed), but I'm
    flagging this as something to double check row-by-row in Day 2, since a lakh
    misparse would be a silent, high-value error.

### What I have NOT yet checked (carrying into Day 2)
- Whether any *other* rows besides #6 have GST reconciliation mismatches under
  ₹1 that are still materially wrong (tolerance edge cases).
- Whether quantity × unit_rate reconciles to taxable_amount (not required by the
  policy, but worth a sanity pass — could surface more data entry errors).
- Full validation that every state/category combination is internally consistent.

### Blocking
Nothing blocking. Ready to start the cleaning module (`clean.py`) on Day 2.

### Tomorrow
Build `clean.py`: canonical vendor mapping keyed on GSTIN with manual alias
fallback for the 4 blank-GSTIN rows, robust date parser (4 formats), robust
amount parser (Rs./comma handling), duplicate resolution, and a `flags` column
capturing every exception in finding #1–8 above without dropping the row.



## Day 2 — 3.9.26

### What I did
Built `src/clean.py`. Input: raw 127-row CSV. Output: `data/ledger_clean.csv`
(126 rows kept, fully typed) and `data/excluded_rows.csv` (1 row, the
superseded half of the INV-2024-0041 duplicate, kept for audit rather than
silently deleted).

### Key decisions
- **Vendor identity is keyed on GSTIN, not name.** Confirmed on Day 1 that
  every spelling/case variant of a vendor name shares one GSTIN. The 4 rows
  with a blank GSTIN are resolved via a small, manually-verified name→GSTIN
  lookup table (not fuzzy matching) — I checked each of the 4 vendor names
  actually appears elsewhere in the ledger with a GSTIN before adding it to
  the table. Anything that doesn't match gets flagged `vendor_unresolved`
  rather than guessed.
- **Nothing is silently fixed.** Per policy section 8, every exception
  (future date, payment-before-invoice, missing amount, missing GSTIN, GST
  mismatch, duplicate) is recorded in a `flags` column on the row itself,
  not corrected or dropped. The one exception is the superseded duplicate
  line, which policy section 6 explicitly says must be excluded from totals
  — but even that row is preserved in `excluded_rows.csv`, not deleted.
- **Comma-stripping handles both grouping styles by coincidence, not
  design.** International grouping (`781,057`) and Indian lakh grouping
  (`1,11,000`) both parse correctly once every comma is removed, because
  removing separators and reading the digit sequence gives the same result
  regardless of where the separators sit. Confirmed this explicitly against
  INV-2024-0903 (`1,11,000` → 111000), rather than assuming it would work.
- **Amounts kept in original currency AND a converted `_inr` column.** Never
  overwrote the original — `taxable_amount_orig`/`gst_amount_orig` preserve
  what was actually on the invoice; `taxable_amount_inr`/`gst_amount_inr` are
  what totals should sum. This makes it possible to audit a USD conversion
  later without re-deriving it from a summed number.
- **Dates written back out in ISO format** (`YYYY-MM-DD`) in the clean CSV
  specifically so Day 3's query code never has to re-guess a date format.

### Verification (not just "it ran")
- Row count: 127 in → 126 kept + 1 excluded, matches exactly.
- Re-derived unique vendor count after cleaning: 10, matching the 10 distinct
  GSTINs in the raw file — confirms no vendor got split or wrongly merged.
- Manually recomputed Bharat Steel Works' total by hand from the raw file
  (18 rows including the credit note) and it matches
  `taxable_amount_inr.sum()` from the clean output.
- USD conversion spot-checked by hand: 6200 × 83.50 = 517700 ✓,
  8700 × 83.50 = 726450 ✓.
- All 11 flags match the Day 1 `explore.py` findings exactly — same 11 rows,
  same issues, now attached to structured data instead of printed text.

### What I have NOT yet done
- Full quantity × unit_rate reconciliation sweep (still open from Day 1).
- No check yet for GST mismatches *within* the ₹1 tolerance that might still
  be slightly off due to rounding conventions — accepted as within policy
  tolerance for now.
- `clean.py` has no automated tests yet — verification above was manual.
  Given the time budget I judged manual verification against hand
  calculation as sufficient for a 127-row dataset, but would add pytest
  cases around the date/amount parsers and the duplicate-resolution rule
  if this were going into production.

### Blocking
Nothing blocking.

### Tomorrow
Day 3: write the deterministic query functions for Q1–Q8 against
`ledger_clean.csv`, and hand-calculate all 8 answers independently before
running any code, so I have a real answer key to check the tool against.


## Day 3 — 4.9.26
### What I did
Built `src/query.py` — one deterministic Python function per required
question (Q1–Q8), each returning a numeric/list answer plus the exact
source invoice numbers it came from. No LLM involved anywhere in this file;
this is the layer Day 4's language model will call, never replace.

### Assumptions I had to make (the policy doesn't fully specify these)
- **Q1 "amount payable"**: read as total invoiced value for the vendor in
  FY2024-25 (taxable+GST, net of credit notes), not just the outstanding
  unpaid balance — since Q2 already covers overdue amounts separately.
  This is a genuine judgement call; a reasonable person could argue the
  other way, so I documented it rather than picking silently.
- **Q5 GST for Q3**: credit notes dated inside the quarter would net
  against the GST total, same treatment as everywhere else in the ledger.
  Didn't end up mattering this quarter (no credit note fell in Oct–Dec),
  but the rule needed deciding regardless.
- **Q7 payment delay**: excluded the one row flagged
  `payment_before_invoice` from the average, treating it as a data-entry
  error rather than a genuine (impossible) negative delay. Reported which
  invoice was excluded and why, rather than folding it in silently.

### Verification
Ran `query.py` end to end against the 126-row clean file. Spot-checked by
hand:
- Q3 (top vendor): recomputed Konark Fabrication's total by filtering the
  clean CSV manually and summing — matches Rs. 64,02,037.70.
- Q6: manually confirmed all 5 listed invoices against the flags column
  from Day 2 — matches exactly, no vendor missing and nothing over-listed.
- Still need to do the FULL hand-calculation pass for all 8 questions
  independently (in a spreadsheet, not by re-reading the code) before I
  can honestly mark PASS/FAIL in EVALUATION.md — that's the actual task
  for finishing Day 3, not optional.

### What I have NOT yet done
- Full independent hand-calculation of all 8 answers (in progress).
- The 4 extra questions of my own, required for EVALUATION.md.
- Haven't yet decided whether Q2's inclusion of INV-2024-0907 (overdue by
  date logic despite having no recorded taxable amount) is the right call
  — flagging this as something to think about rather than deciding
  silently.

### Blocking
Nothing blocking.

### Tomorrow
Day 4: install Ollama, get 2 models running locally, wire up the
intent-classification layer so an English question routes to the right
query.py function, and get the end-to-end CLI working.


### what i did today — Q9-Q12 (own questions) promoted from hand-calc to real functions

Initially worked out Q9-Q12 by hand only, planning to wire them into the
tool once Day 4's CLI existed. Decided that leaving "Tool's answer" blank
in EVALUATION.md wasn't good enough to call Day 3 finished, so added
`q9_total_taxable_spend`, `q10_most_overdue_by_count`,
`q11_avg_raw_material`, and `q12_missing_gstin_value` to query.py now,
following the exact same pattern as Q1-Q8 - Python does the arithmetic,
nothing here waits on the LLM layer.

All 4 match their hand-calculated answers exactly. Q11 required a judgement
call (whether a credit note tagged "Raw Material" should count toward an
average invoice value) that both the hand-calc and the function now make
the same way, and it's documented rather than left implicit in the code.

Full result: 12/12 PASS across required + custom questions. 
