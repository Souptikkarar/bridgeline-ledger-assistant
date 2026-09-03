
#Day 2 — cleaning pipeline for the Bridgeline ledger.

from __future__ import annotations

import re
from pathlib import Path
from datetime import datetime

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent

# Look in a few likely places so this works whether clean.py sits in a
# src/ subfolder next to data/, or directly in the project root next to
# the CSV, or next to a data/ subfolder in the same place as the script.
_CANDIDATE_DIRS = [
    SCRIPT_DIR.parent / "data",   
    SCRIPT_DIR / "data",          
    SCRIPT_DIR,                  
]




RAW_PATH =  "ledger_2024_25.csv"

USD_TO_INR = 83.50  # fixed rate per policy section 4, does not float
REPORTING_DATE = datetime(2025, 3, 31)  # policy section 9

# Standard payment terms by category, in days (policy section 3)
STANDARD_TERMS_DAYS = {
    "Raw Material": 30,
    "Fabrication": 45,
    "Transport": 15,
    "Consumables": 30,
    "Tooling": 30,
    "Safety": 30,
    "Services": 45,
}

DATE_FORMATS = ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%b-%Y", "%d-%m-%Y"]


# Vendor alias fallback for the 4 rows with a blank GSTIN (see Day 1
# findings: their vendor name spelling already appears elsewhere in the
# ledger WITH a GSTIN, so we can anchor them by name instead of guessing).
# Verified manually against explore.py output on Day 1 - do not extend
# this list without re-checking the source rows.

BLANK_GSTIN_NAME_TO_GSTIN = {
    "eastern logistics": "19AAECE3456N1Z1",
    "sen brothers": "19AAJCS0123T1Z3",
    "nova paints & coatings": "24AAHCN6789R1Z6",
    "sundaram engg": "33AADCS9012M1Z8",
}

# Canonical display name per GSTIN. Picked the fullest/most formal
# spelling that actually occurs in the ledger for each vendor.
GSTIN_TO_CANONICAL_NAME = {
    "21AACCK5678L1Z2": "Konark Fabrication Pvt. Ltd.",
    "07AAKCA4567U1Z7": "Apex Safety Equipment",
    "19AAECE3456N1Z1": "Eastern Logistics Co",
    "10AAFCG7890P1Z4": "Gupta Hardware Stores",
    "19AABCB1234K1Z5": "Bharat Steel Works",
    "24AAHCN6789R1Z6": "Nova Paints & Coatings",
    "33AADCS9012M1Z8": "Sundaram Engineering Ltd",
    "19AAJCS0123T1Z3": "Sen Brothers Welding",
    "29AALCM8901V1Z0": "Meridian Consultants LLP",
    "27AAGCP2345Q1Z9": "Precision Tools India",
}


def parse_date(raw: str):
    """Return (datetime|None, error_note|None)."""
    s = (raw or "").strip()
    if not s:
        return None, "blank_date"
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt), None
        except ValueError:
            continue
    return None, f"unparseable_date:{s}"


def parse_amount(raw: str):
    """Return (float|None, error_note|None). Handles 'Rs.' prefix and
    comma-thousands grouping (both international 781,057 and Indian
    lakh-style 1,11,000 collapse correctly once commas are stripped,
    since we don't rely on comma POSITION, just remove them all)."""
    s = (raw or "").strip()
    if not s:
        return None, "blank_amount"
    s = s.replace("Rs.", "").replace("Rs", "").strip().strip('"')
    s = s.replace(",", "")
    try:
        return float(s), None
    except ValueError:
        return None, f"unparseable_amount:{raw}"


def loose_key(name: str) -> str:
    n = (name or "").strip().lower()
    n = re.sub(r"[.,]", "", n)
    n = re.sub(r"\b(pvt|ltd|llp|india|the|co)\b", "", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def resolve_gstin(row) -> tuple[str | None, bool]:
    """Return (gstin, was_fallback). Uses the ledger's own GSTIN when
    present; falls back to the manual name map for the 4 known blank
    rows. Returns (None, False) for anything unrecognised so it surfaces
    as a flag rather than failing silently."""
    gstin = (row["vendor_gstin"] or "").strip()
    if gstin:
        return gstin, False
    key = loose_key(row["vendor_name"])
    fallback = BLANK_GSTIN_NAME_TO_GSTIN.get(key)
    return fallback, fallback is not None


def load_raw() -> pd.DataFrame:
    df = pd.read_csv(RAW_PATH, dtype=str, keep_default_na=False)
    df["_source_line"] = df.index + 2  # +2: header is line 1, 0-indexed
    return df


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (clean_df, excluded_df)."""
    records = []
    excluded = []

    # Pass 1: parse every field, compute flags, keep everything 
    for _, row in df.iterrows():
        flags = []

        inv_date, d_err = parse_date(row["invoice_date"])
        if d_err:
            flags.append(d_err)
        elif inv_date > REPORTING_DATE:
            flags.append("future_dated")

        pay_date = None
        if row["payment_date"].strip():
            pay_date, p_err = parse_date(row["payment_date"])
            if p_err:
                flags.append(f"payment_{p_err}")
            elif inv_date and pay_date < inv_date:
                flags.append("payment_before_invoice")

        taxable, t_err = parse_amount(row["taxable_amount"])
        if t_err:
            flags.append(t_err)

        gst_amt, g_err = parse_amount(row["gst_amount"])
        if g_err:
            flags.append(g_err)

        rate_str = row["gst_rate"].strip().rstrip("%")
        rate = None
        if rate_str:
            try:
                rate = float(rate_str) / 100
            except ValueError:
                flags.append(f"unparseable_gst_rate:{rate_str}")

        if taxable is not None and gst_amt is not None and rate is not None:
            expected_gst = taxable * rate
            if abs(expected_gst - gst_amt) > 1.0:
                flags.append(
                    f"gst_mismatch:expected={expected_gst:.2f}:stated={gst_amt:.2f}"
                )

        gstin, was_fallback = resolve_gstin(row)
        if not row["vendor_gstin"].strip():
            flags.append("missing_gstin_no_itc")  # policy sec 7: no GSTIN -> no ITC
            if was_fallback:
                flags.append("vendor_matched_by_name_fallback")
            else:
                flags.append("vendor_unresolved")

        canonical_vendor = GSTIN_TO_CANONICAL_NAME.get(gstin, row["vendor_name"].strip())

        is_credit_note = row["invoice_no"].strip().startswith("CN-")

        currency = row["currency"].strip() or "INR"
        taxable_inr = None
        gst_inr = None
        if taxable is not None:
            taxable_inr = taxable * USD_TO_INR if currency == "USD" else taxable
        if gst_amt is not None:
            gst_inr = gst_amt * USD_TO_INR if currency == "USD" else gst_amt
        if currency == "USD":
            flags.append(f"usd_converted_at_{USD_TO_INR}")

        records.append({
            "source_line": row["_source_line"],
            "invoice_no": row["invoice_no"].strip(),
            "invoice_date": inv_date,
            "vendor_gstin": gstin,
            "vendor_name_raw": row["vendor_name"].strip(),
            "vendor_name_canonical": canonical_vendor,
            "category": row["category"].strip(),
            "state": row["state"].strip(),
            "description": row["description"].strip(),
            "taxable_amount_orig": taxable,
            "gst_amount_orig": gst_amt,
            "gst_rate": rate,
            "currency": currency,
            "taxable_amount_inr": taxable_inr,
            "gst_amount_inr": gst_inr,
            "payment_status": row["payment_status"].strip(),
            "payment_date": pay_date,
            "is_credit_note": is_credit_note,
            "standard_term_days": STANDARD_TERMS_DAYS.get(row["category"].strip()),
            "flags": flags,
        })

    full = pd.DataFrame(records)

    #  Pass 2: resolve duplicate invoice numbers (policy sec 6) 
    # Rule: later/revised description wins. We treat a description
    # containing "(revised)" as the superseding entry; if neither has
    # that marker, keep the row that appears later in the file (higher
    # source_line) as the more recent re-key, and flag it either way so
    # a human can double check the ledger's real intent.
    keep_mask = pd.Series(True, index=full.index)
    for inv_no, group in full.groupby("invoice_no"):
        if len(group) <= 1:
            continue
        revised = group[group["description"].str.contains(r"\(revised\)", case=False, na=False)]
        if len(revised) == 1:
            winner_idx = revised.index[0]
        else:
            winner_idx = group["source_line"].idxmax()
        loser_idxs = [i for i in group.index if i != winner_idx]
        for li in loser_idxs:
            keep_mask[li] = False
            excluded.append({
                **full.loc[li].to_dict(),
                "exclusion_reason": f"superseded_duplicate_of_line_{full.loc[winner_idx, 'source_line']}",
            })
        full.at[winner_idx, "flags"] = full.at[winner_idx, "flags"] + ["duplicate_resolved_kept"]

    clean_df = full[keep_mask].reset_index(drop=True)
    excluded_df = pd.DataFrame(excluded)

    # flags list -> pipe-separated string for CSV friendliness
    def dedupe_join(fl):
        seen = []
        for f in fl:
            if f not in seen:
                seen.append(f)
        return "|".join(seen)

    clean_df["flags"] = clean_df["flags"].apply(dedupe_join)
    if not excluded_df.empty:
        excluded_df["flags"] = excluded_df["flags"].apply(dedupe_join)

    return clean_df, excluded_df


def main():
    print(f"Using data directory: {DATA_.resolve()}\n")
    raw = load_raw()
    clean_df, excluded_df = clean(raw)

    out_clean = DATA_ / "ledger_clean.csv"
    out_excluded = DATA_ / "excluded_rows.csv"
    clean_df.to_csv(out_clean, index=False)
    excluded_df.to_csv(out_excluded, index=False)

    print(f"Rows in:  {len(raw)}")
    print(f"Rows out: {len(clean_df)} -> {out_clean}")
    print(f"Excluded: {len(excluded_df)} -> {out_excluded}")
    print()
    flagged = clean_df[clean_df["flags"] != ""]
    print(f"Rows with at least one flag: {len(flagged)}")
    for _, r in flagged.iterrows():
        print(f"  line {r['source_line']} {r['invoice_no']}: {r['flags']}")


if __name__ == "__main__":
    main()
