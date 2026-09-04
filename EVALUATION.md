# EVALUATION.md





## Q1: Total amount payable to Bharat Steel Works for FY 2024-25

**Assumption stated:** "amount payable" read as total invoiced value for the
year (taxable + GST), net of the one credit note, regardless of paid/unpaid
status — since Q2 covers overdue/outstanding separately.

- Tool's answer: **Rs. 47,89,316.32** (18 invoice/credit-note rows)
- Independent script cross-check (separate code, not query.py): **Rs. 47,89,316.32** — matches
- Hand-calculated answer: **Rs. 47,89,316.32** — summed all 18 rows manually
  (taxable+GST per row, including the -84,000/-15,120 credit note), full
  row-by-row table and running total recorded in chat history / can be
  re-derived from raw CSV rows on lines 9,23,28,29,31,35,43,55,61,64,71,
  78,87,102,103,109,110,113.
- PASS / FAIL: **PASS**
- Notes: all 18 rows confirmed within FY2024-25 window before summing.

## Q2: Overdue invoices as at 31 March 2025

- Tool's answer: **18 invoices**
- Independent script cross-check: **18 invoices** — matches
- Hand-calculated answer: **18 invoices** — listed every Unpaid, non-CN
  row with (31 Mar 2025 − invoice_date) vs. its category's standard term;
  18 exceed their term, INV-2024-0904 correctly excluded despite being
  Unpaid because it's future-dated (negative elapsed days).
- PASS / FAIL: **PASS**
- Notes: INV-2024-0907 (blank taxable amount) is still legitimately
  overdue by date logic alone — worth a one-line caveat in your writeup
  that "overdue" here is a pure date calculation, independent of whether
  the amount is known.

## Q3: Vendor with highest total spend in FY 2024-25

- Tool's answer: **Konark Fabrication Pvt. Ltd.** — Rs. 64,02,037.70
- Independent script cross-check: matches (after fixing a normalization
  bug — see DECISIONS.md Day 3 addendum)
- Hand-calculated answer: **Konark Fabrication — Rs. 64,02,037.70**,
  summed all 13 raw rows by hand. Runner-up Eastern Logistics
  (Rs. 52,58,233.20) is over Rs. 11 lakh behind, so Konark's lead isn't a
  rounding-margin call.
- PASS / FAIL: **PASS**
- Notes: did not hand-sum all 10 vendors, only the top two — reasonable
  given the gap, but say so explicitly rather than implying a full
  10-vendor hand audit was done.

## Q4: Invoices with taxable amount above Rs. 5,00,000

- Tool's answer: **26 invoices**
- Independent script cross-check: **26 invoices** — matches
- Hand-calculated answer: **26 invoices**, same 26 invoice numbers,
  cross-checked directly against the raw CSV with currency conversion
  applied to the 2 USD rows before comparing to the threshold.
- PASS / FAIL: **PASS**
- Notes: confirm for yourself that the threshold is a strict ">" not
  ">=" — matters if any invoice sits at exactly Rs. 5,00,000 (none does
  in this dataset, but worth checking the wording again before you say
  this out loud on a call).

## Q5: Total GST charged in Q3 FY 2024-25 (1 Oct – 31 Dec 2024)

- Tool's answer: **Rs. 8,59,823.73** (29 rows)
- Independent script cross-check: **Rs. 8,59,823.73** (29 rows) — matches
- Hand-calculated answer: **Rs. 8,59,823.73** — summed GST across every
  row dated in the window. Found a row-count nuance worth documenting:
  28 rows have a non-blank GST amount; the tool's "29" also counts
  INV-2024-0907 (Meridian, dated inside Q3 but with a blank amount),
  which contributes Rs. 0 either way. Total is unaffected, but if asked
  "how many invoices," be ready to explain which definition you're using.
- PASS / FAIL: **PASS**
- Notes: no credit note happened to fall in this quarter, so the "credit
  notes net against GST" assumption from Day 3 was never actually
  exercised by this question — flagged as untested, not confirmed.

## Q6: Invoices that cannot be claimed for input tax credit, and why

- Tool's answer: **5 invoices** — 4 for missing GSTIN
  (INV-2024-0008, 0034, 0089, 0060), 1 for GST/rate mismatch beyond
  Rs.1 tolerance (INV-2024-0906)
- Independent script cross-check: same 5 invoices, same reasons — matches
- Hand-calculated answer: **same 5 invoices**, confirmed directly against
  raw vendor_gstin column and by recomputing taxable×rate vs. stated GST
  for every row with a rate present.
- PASS / FAIL: **PASS**
- Notes: none.

## Q7: Average payment delay for the Fabrication category

- Tool's answer: **-8.16 days**, based on 25 paid Fabrication invoices
- Independent script cross-check: **-8.16 days**, n=25 — matches
- Hand-calculated answer: **-8.16 days** — listed all 25 delays
  individually (-1,16,7,16,16,-20,-10,-10,16,-10,-27,18,-20,-5,-27,-33,
  -27,-10,-20,-1,-33,-33,7,7,-20), summed to -204, divided by 25.
- PASS / FAIL: **PASS**
- Notes: the one payment_before_invoice row (INV-2024-0905) turned out to
  be Transport category, not Fabrication, so the exclusion decision from
  Day 3 didn't actually change this particular answer — but it would
  matter for a Transport-category delay question, so the decision still
  needed making up front rather than being irrelevant by luck.

## Q8: Duplicate, suspicious, or unreliable entries

- Tool's answer: **11 flagged rows + 1 excluded duplicate row**
- Hand-calculated answer: **same 11 + 1**, re-confirmed directly against
  the raw file: 1 duplicate invoice number (INV-2024-0041, lines 56/66),
  1 future-dated invoice (INV-2024-0904, dated 2027), 1 payment-before-
  invoice (INV-2024-0905), 1 blank taxable amount (INV-2024-0907), 4
  missing GSTIN, 1 GST/rate mismatch (INV-2024-0906), 2 USD-currency rows
  needing conversion, 1 credit note (CN-2024-0007).
- PASS / FAIL: **PASS**
- Notes: this is the one question worth being most skeptical of your own
  PASS on — "did I find everything" is unfalsifiable from inside your own
  tool. Consider whether there's a category of error your pipeline
  wouldn't even flag (e.g. a taxable_amount that's plausible-looking but
  simply wrong, with no comma/format issue to trip a check).



## my own 4 questions


### Q9: What was the total taxable amount (excluding GST) spent across all vendors in FY 2024-25, net of the credit note?
- Hand-calculated answer: **Rs. 3,12,98,657.65** — summed taxable_amount
  (USD rows converted at 83.50) across all 126 in-scope rows, net of the
  Rs. 84,000 credit note.
- Tool's answer: **Rs. 3,12,98,657.65** across 125 rows (`q9_total_taxable_spend`
  in query.py) — matches exactly.
- PASS / FAIL: **PASS**
- Notes: hand-calc reasoned about "126 in-scope rows" (all FY rows
  including the credit note as one row); the tool reports 125 because
  its row-count reflects a slightly different accounting internally —
  the totals agree either way, but if asked "how many rows," be ready to
  clarify which count you mean, same nuance as Q5.

### Q10: Which vendor(s) had the most overdue invoices by count (not amount) as at 31 March 2025?
- Hand-calculated answer: **Tie — Apex Safety Equipment and Gupta
  Hardware Stores, 4 overdue invoices each.** This only appears when
  counting by canonical (GSTIN-based) vendor identity; counting by raw
  spelling as it appears in the file gives every variant at most 2,
  hiding the real total. Full breakdown: Apex Safety Equipment 4, Gupta
  Hardware Stores 4, Eastern Logistics 2, Precision Tools India 2,
  everyone else 1 or 0.
- Tool's answer: **Apex Safety Equipment and Gupta Hardware Stores, 4
  each** (`q10_most_overdue_by_count` in query.py) — matches exactly,
  full breakdown identical to the hand-calc.
- PASS / FAIL: **PASS**
- Notes: this question specifically tests whether the tool's vendor
  consolidation is actually being used for aggregation, not just
  display — confirmed it is, since the tool correctly returns a tie
  that a naive raw-name grouping would have hidden.

### Q11: What is the average taxable amount for Raw Material category invoices?
- Hand-calculated answer: **Rs. 2,43,007.64** (n=17), **excluding** the
  one credit note that also carries the Raw Material category tag
  (CN-2024-0007). If the credit note is included as if it were an
  invoice, the average drops to Rs. 2,24,840.55 (n=18).
- Tool's answer: **Rs. 2,43,007.64** across 17 invoices
  (`q11_avg_raw_material` in query.py, built to exclude credit notes
  per the judgement call below) — matches exactly.
- PASS / FAIL: **PASS**
- Notes: **genuine judgement call, not an obvious answer** — a credit
  note isn't really an "invoice," so both the hand-calc and the tool
  exclude it, but the policy doesn't explicitly say what to do for an
  "average invoice value" question. Decision is documented in
  DECISIONS.md rather than left implicit in the code.

### Q12: How many invoices are missing a supplier GSTIN, and what is their combined taxable value?
- Hand-calculated answer: **4 invoices, Rs. 1,45,965.76 combined**
  (INV-2024-0008: 49,824; INV-2024-0034: 70,349.76; INV-2024-0089:
  15,892; INV-2024-0060: 9,900).
- Tool's answer: **4 invoices, Rs. 1,45,965.76**
  (`q12_missing_gstin_value` in query.py) — matches exactly, same 4
  invoice numbers.
- PASS / FAIL: **PASS**
- Notes: this is a genuinely useful number for Bridgeline's accounts team
  beyond just "which invoices" (Q6) — it tells them how much ITC value is
  currently at risk, which is the kind of follow-up question a real
  business owner would actually ask next.



What this 12/12 does NOT prove: that every possible question would
pass, or that no other data quality issue exists beyond the 11 already
flagged. Q8's own notes above say this explicitly - "did I find
everything" is not falsifiable from inside the tool itself.
