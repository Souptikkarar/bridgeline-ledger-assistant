# DECISIONS.md

## Day 2 — [fill in your actual date]
What I did

Built src/clean.py. Input: raw 127-row CSV. Output: data/ledger_clean.csv (126 rows kept, fully typed) and data/excluded_rows.csv (1 row, the superseded half of the INV-2024-0041 duplicate, kept for audit rather than silently deleted).

## Key decisions
Vendor identity is keyed on GSTIN, not name. Confirmed on Day 1 that every spelling/case variant of a vendor name shares one GSTIN. The 4 rows with a blank GSTIN are resolved via a small, manually-verified name→GSTIN lookup table (not fuzzy matching) — I checked each of the 4 vendor names actually appears elsewhere in the ledger with a GSTIN before adding it to the table. Anything that doesn't match gets flagged vendor_unresolved rather than guessed.
Nothing is silently fixed. Per policy section 8, every exception (future date, payment-before-invoice, missing amount, missing GSTIN, GST mismatch, duplicate) is recorded in a flags column on the row itself, not corrected or dropped. The one exception is the superseded duplicate line, which policy section 6 explicitly says must be excluded from totals — but even that row is preserved in excluded_rows.csv, not deleted.
Comma-stripping handles both grouping styles by coincidence, not design. International grouping (781,057) and Indian lakh grouping (1,11,000) both parse correctly once every comma is removed. Confirmed this explicitly against INV-2024-0903 (1,11,000 → 111000), rather than assuming it would work.
Amounts kept in original currency AND a converted _inr column. Never overwrote the original — taxable_amount_orig/gst_amount_orig preserve what was actually on the invoice; taxable_amount_inr/gst_amount_inr are what totals should sum.
Dates written back out in ISO format (YYYY-MM-DD) specifically so Day 3's query code never has to re-guess a date format.
Verification (not just "it ran")
Row count: 127 in → 126 kept + 1 excluded, matches exactly.
Re-derived unique vendor count after cleaning: 10, matching the 10 distinct GSTINs in the raw file.
Manually recomputed Bharat Steel Works' total by hand and it matches taxable_amount_inr.sum() from the clean output.
USD conversion spot-checked by hand: 6200 × 83.50 = 517700 ✓, 8700 × 83.50 = 726450 ✓.
All 11 flags match the Day 1 explore.py findings exactly.
What I have NOT yet done
Full quantity × unit_rate reconciliation sweep (still open from Day 1).
No check yet for GST mismatches within the ₹1 tolerance that might still be slightly off.
clean.py has no automated tests yet — verification above was manual.
## Blocking

Nothing blocking.

## Tomorrow

Day 3: write the deterministic query functions for Q1–Q8 against ledger_clean.csv, and hand-calculate all 8 answers independently before running any code.