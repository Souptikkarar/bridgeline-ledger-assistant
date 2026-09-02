"""
Day 1 exploration script — NOT the cleaning pipeline (that's Day 2).
Purpose: read the raw ledger row by row and surface every anomaly called
out in vendor_payment_policy.md section 8, plus anything else that looks
off, so we go into Day 2 with a verified list instead of guesses.

Deliberately does NOT fix anything. Only reports.
"""
import csv
import re
from collections import defaultdict
from datetime import datetime

PATH = "../data/ledger_2024_25.csv"
REPORTING_DATE = datetime(2025, 3, 31)

DATE_FORMATS = [
    "%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%b-%Y", "%d-%m-%Y",
]

def parse_date(s):
    s = s.strip()
    if not s:
        return None, "blank"
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt), None
        except ValueError:
            continue
    return None, f"UNPARSEABLE format: {s!r}"

def parse_amount(s):
    """Return (float or None, note). Handles Rs. prefix, commas, blanks,
    and flags anything that looks like Indian lakh-grouping vs plain
    thousands-grouping so we can eyeball which rule applies."""
    raw = s
    s = s.strip()
    if not s:
        return None, "blank"
    s = s.replace("Rs.", "").replace("Rs", "").strip()
    s = s.strip('"')
    s = s.replace(",", "")
    try:
        return float(s), None
    except ValueError:
        return None, f"UNPARSEABLE amount: {raw!r}"

rows = []
with open(PATH, newline="", encoding="utf-8") as f: PATH = '"C:\vendor Payment\ledger_2024_25.csv"

    reader = csv.DictReader(f)
    for i, row in enumerate(reader, start=2):  # start=2: line 1 is header
        row["_line"] = i
        rows.append(row)

print(f"Total data rows: {len(rows)}\n")

# ---------------------------------------------------------------
# 1. Invoice number duplicates
# ---------------------------------------------------------------
by_invno = defaultdict(list)
for r in rows:
    by_invno[r["invoice_no"].strip()].append(r)

print("=== 1. Duplicate invoice numbers ===")
for inv, group in by_invno.items():
    if len(group) > 1:
        print(f"  {inv}: {len(group)} entries")
        for g in group:
            print(f"    line {g['_line']}: desc={g['description']!r} "
                  f"taxable={g['taxable_amount']!r} date={g['invoice_date']!r}")
print()

# ---------------------------------------------------------------
# 2. Date parsing / future dates / payment-before-invoice
# ---------------------------------------------------------------
print("=== 2. Date issues ===")
unparseable_inv_dates = []
future_dated = []
unparseable_pay_dates = []
payment_before_invoice = []

for r in rows:
    idate, ierr = parse_date(r["invoice_date"])
    if ierr:
        unparseable_inv_dates.append((r["_line"], r["invoice_no"], ierr))
    elif idate > REPORTING_DATE:
        future_dated.append((r["_line"], r["invoice_no"], idate.date()))

    pay_raw = r["payment_date"].strip()
    if pay_raw:
        pdate, perr = parse_date(pay_raw)
        if perr:
            unparseable_pay_dates.append((r["_line"], r["invoice_no"], perr))
        elif idate and pdate < idate:
            payment_before_invoice.append(
                (r["_line"], r["invoice_no"], idate.date(), pdate.date())
            )

print(f"  Unparseable invoice_date formats: {len(unparseable_inv_dates)}")
for l in unparseable_inv_dates:
    print(f"    {l}")
print(f"  Future-dated invoices (after {REPORTING_DATE.date()}): {len(future_dated)}")
for l in future_dated:
    print(f"    line {l[0]} {l[1]}: {l[2]}")
print(f"  Unparseable payment_date formats: {len(unparseable_pay_dates)}")
for l in unparseable_pay_dates:
    print(f"    {l}")
print(f"  Payment date earlier than invoice date: {len(payment_before_invoice)}")
for l in payment_before_invoice:
    print(f"    line {l[0]} {l[1]}: invoice={l[2]} payment={l[3]}")
print()

# ---------------------------------------------------------------
# 3. Missing taxable amount / GSTIN
# ---------------------------------------------------------------
print("=== 3. Missing required fields ===")
missing_taxable = [(r["_line"], r["invoice_no"]) for r in rows if not r["taxable_amount"].strip()]
missing_gstin = [(r["_line"], r["invoice_no"], r["vendor_name"]) for r in rows if not r["vendor_gstin"].strip()]
print(f"  Missing/blank taxable_amount: {len(missing_taxable)}")
for l in missing_taxable:
    print(f"    {l}")
print(f"  Missing/blank vendor_gstin: {len(missing_gstin)}")
for l in missing_gstin:
    print(f"    {l}")
print()

# ---------------------------------------------------------------
# 4. GST reconciliation: taxable * rate vs stated gst_amount (tolerance Rs 1)
# ---------------------------------------------------------------
print("=== 4. GST reconciliation (stated rate x taxable vs stated GST amount, tol=Rs.1) ===")
gst_mismatches = []
for r in rows:
    taxable, terr = parse_amount(r["taxable_amount"])
    gst_amt, gerr = parse_amount(r["gst_amount"])
    rate_str = r["gst_rate"].strip().rstrip("%")
    if terr or gerr or not rate_str or taxable is None or gst_amt is None:
        continue
    try:
        rate = float(rate_str) / 100
    except ValueError:
        continue
    expected = taxable * rate
    if abs(expected - gst_amt) > 1.0:
        gst_mismatches.append((r["_line"], r["invoice_no"], taxable, rate_str, gst_amt, round(expected, 2)))

print(f"  Mismatches beyond Rs.1 tolerance: {len(gst_mismatches)}")
for l in gst_mismatches:
    print(f"    line {l[0]} {l[1]}: taxable={l[2]} rate={l[3]}% stated_gst={l[4]} expected_gst={l[5]}")
print()

# ---------------------------------------------------------------
# 5. Vendor name variants (case/whitespace/suffix differences)
# ---------------------------------------------------------------
print("=== 5. Distinct raw vendor_name spellings (group by loose normalization) ===")
def loose_key(name):
    n = name.strip().lower()
    n = re.sub(r"[.,]", "", n)
    n = re.sub(r"\b(pvt|ltd|llp|india|the)\b", "", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n

groups = defaultdict(set)
for r in rows:
    groups[loose_key(r["vendor_name"])].add(r["vendor_name"])

for key, variants in groups.items():
    if len(variants) > 1:
        print(f"  cluster ~'{key}': {sorted(variants)}")
print()

# ---------------------------------------------------------------
# 6. Currency check
# ---------------------------------------------------------------
print("=== 6. Non-INR currency rows ===")
for r in rows:
    if r["currency"].strip() != "INR":
        print(f"  line {r['_line']} {r['invoice_no']}: {r['currency']} vendor={r['vendor_name']}")
print()

# ---------------------------------------------------------------
# 7. Credit notes
# ---------------------------------------------------------------
print("=== 7. Credit notes (CN- prefix) ===")
for r in rows:
    if r["invoice_no"].strip().startswith("CN-"):
        print(f"  line {r['_line']} {r['invoice_no']}: vendor={r['vendor_name']} "
              f"taxable={r['taxable_amount']} status={r['payment_status']}")
print()

# ---------------------------------------------------------------
# 8. Payment status sanity
# ---------------------------------------------------------------
print("=== 8. Distinct payment_status values ===")
print("  ", sorted(set(r["payment_status"].strip() for r in rows)))
