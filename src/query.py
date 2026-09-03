"""
Day 3 — deterministic query engine for the Bridgeline ledger.


"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
_CANDIDATE_DIRS = [
    SCRIPT_DIR.parent / "data",
    SCRIPT_DIR / "data",
    SCRIPT_DIR,
]
DATA_DIR = next((d for d in _CANDIDATE_DIRS if (d / "ledger_clean.csv").exists()), None)
if DATA_DIR is None:
    raise FileNotFoundError(
        "Could not find ledger_clean.csv. Run clean.py first, and make sure "
        "it's in the same folder as query.py, or in a data/ subfolder."
    )

FY_START = datetime(2024, 4, 1)
FY_END = datetime(2025, 3, 31)
REPORTING_DATE = datetime(2025, 3, 31)
Q3_START, Q3_END = datetime(2024, 10, 1), datetime(2024, 12, 31)


def load_clean() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "ledger_clean.csv")
    df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce")
    df["payment_date"] = pd.to_datetime(df["payment_date"], errors="coerce")
    df["flags"] = df["flags"].fillna("")
    return df


def _in_fy(df: pd.DataFrame) -> pd.DataFrame:
    """Rows dated within FY 2024-25 (policy sec 2). Excludes anything
    outside the window, including the future-dated INV-2024-0904."""
    return df[(df["invoice_date"] >= FY_START) & (df["invoice_date"] <= FY_END)]



# Q1: Total amount payable to Bharat Steel Works for FY 2024-25

def q1_vendor_total(df: pd.DataFrame, vendor: str = "Bharat Steel Works") -> dict:
    """
    ASSUMPTION (state this explicitly in EVALUATION.md): "amount payable"
    is read as total invoiced value for the year - taxable + GST - net of
    credit notes, regardless of paid/unpaid status. Q2 covers the
    outstanding/overdue angle separately, so Q1 is treated as "total spend
    with this vendor," which is the more natural reading of a
    year-end "how much do we owe/did we spend with X" question.
    """
    scope = _in_fy(df)
    rows = scope[scope["vendor_name_canonical"] == vendor]
    total = (rows["taxable_amount_inr"].fillna(0) + rows["gst_amount_inr"].fillna(0)).sum()
    return {
        "answer": round(float(total), 2),
        "assumption": "Total = sum(taxable+GST) for all invoices/credit notes "
                       "dated in FY2024-25, net of the credit note.",
        "source_invoices": rows["invoice_no"].tolist(),
        "row_count": len(rows),
    }



# Q2: Overdue invoices as at 31 March 2025

def q2_overdue_invoices(df: pd.DataFrame) -> dict:
    """Overdue = unpaid AND days elapsed since invoice_date > standard
    term for its category (policy sec 3). Credit notes are never overdue
    (policy sec 5)."""
    candidates = df[(df["payment_status"] == "Unpaid") & (~df["is_credit_note"])]
    days_elapsed = (REPORTING_DATE - candidates["invoice_date"]).dt.days
    is_overdue = days_elapsed > candidates["standard_term_days"]
    overdue = candidates[is_overdue].copy()
    overdue["days_overdue"] = days_elapsed[is_overdue] - candidates.loc[is_overdue, "standard_term_days"]
    return {
        "answer_count": len(overdue),
        "source_invoices": overdue[["invoice_no", "vendor_name_canonical", "category", "days_overdue"]]
            .to_dict("records"),
    }



# Q3: Vendor with highest total spend in FY 2024-25

def q3_top_vendor(df: pd.DataFrame) -> dict:
    scope = _in_fy(df).copy()
    scope["gross"] = scope["taxable_amount_inr"].fillna(0) + scope["gst_amount_inr"].fillna(0)
    totals = scope.groupby("vendor_name_canonical")["gross"].sum().sort_values(ascending=False)
    top_vendor = totals.index[0]
    return {
        "answer": top_vendor,
        "amount": round(float(totals.iloc[0]), 2),
        "all_vendor_totals": {k: round(float(v), 2) for k, v in totals.items()},
    }



# Q4: Invoices with taxable amount above Rs 5,00,000

def q4_high_value_invoices(df: pd.DataFrame, threshold: float = 500_000) -> dict:
    rows = df[df["taxable_amount_inr"] > threshold]
    return {
        "answer_count": len(rows),
        "source_invoices": rows[["invoice_no", "vendor_name_canonical", "taxable_amount_inr"]]
            .sort_values("taxable_amount_inr", ascending=False).to_dict("records"),
    }



# Q5: Total GST charged in Q3 FY2024-25 (1 Oct - 31 Dec 2024)

def q5_gst_q3(df: pd.DataFrame) -> dict:
    """
    ASSUMPTION: credit notes dated within Q3 net against the GST total
    (their gst_amount_inr is 0 in this dataset since CN rows only carry
    a taxable_amount - see source rows for confirmation either way).
    """
    rows = df[(df["invoice_date"] >= Q3_START) & (df["invoice_date"] <= Q3_END)]
    total = rows["gst_amount_inr"].fillna(0).sum()
    return {
        "answer": round(float(total), 2),
        "source_invoices": rows["invoice_no"].tolist(),
        "row_count": len(rows),
    }



# Q6: Invoices that cannot be claimed for ITC, and why

def q6_no_itc(df: pd.DataFrame) -> dict:
    """Per policy sec 7: missing GSTIN -> no ITC. Also, GST that doesn't
    reconcile to the stated rate within Rs.1 must be excluded from ITC
    claims until corrected."""
    missing_gstin = df[df["flags"].str.contains("missing_gstin_no_itc")]
    gst_mismatch = df[df["flags"].str.contains("gst_mismatch")]
    out = []
    for _, r in missing_gstin.iterrows():
        out.append({"invoice_no": r["invoice_no"], "reason": "missing supplier GSTIN"})
    for _, r in gst_mismatch.iterrows():
        out.append({"invoice_no": r["invoice_no"], "reason": "GST amount does not reconcile "
                                                               "to stated rate (>Rs.1 off)"})
    return {"answer_count": len(out), "source_invoices": out}



# Q7: Average payment delay for Fabrication category

def q7_avg_delay_fabrication(df: pd.DataFrame) -> dict:
    """
    payment delay = payment_date - invoice_date - standard_term_days
    (policy sec 3). Negative = paid early, kept as negative, not clipped.
    ASSUMPTION: rows flagged payment_before_invoice are a data-entry error
    (policy sec 8 exception), not a genuine early payment, so they are
    EXCLUDED from the average and reported separately for transparency.
    """
    fab = df[(df["category"] == "Fabrication") & (df["payment_status"] == "Paid")].copy()
    clean_fab = fab[~fab["flags"].str.contains("payment_before_invoice")]
    flagged_fab = fab[fab["flags"].str.contains("payment_before_invoice")]

    delay_days = (clean_fab["payment_date"] - clean_fab["invoice_date"]).dt.days - clean_fab["standard_term_days"]
    avg_delay = delay_days.mean()

    return {
        "answer_days": round(float(avg_delay), 2) if len(clean_fab) else None,
        "invoices_used": len(clean_fab),
        "invoices_excluded_as_data_quality_issue": flagged_fab["invoice_no"].tolist(),
        "source_invoices": clean_fab["invoice_no"].tolist(),
    }



# Q8: Duplicate, suspicious or unreliable entries

def q8_data_quality_issues(df: pd.DataFrame, excluded_path: Path | None = None) -> dict:
    flagged = df[df["flags"] != ""]
    issues = flagged[["invoice_no", "vendor_name_canonical", "flags"]].to_dict("records")
    excluded_note = None
    if excluded_path and excluded_path.exists():
        exc = pd.read_csv(excluded_path)
        excluded_note = exc[["invoice_no", "exclusion_reason"]].to_dict("records")
    return {
        "flagged_row_count": len(flagged),
        "flagged_rows": issues,
        "excluded_rows": excluded_note,
    }


def main():
    df = load_clean()
    print(f"Loaded {len(df)} cleaned rows from {DATA_DIR / 'ledger_clean.csv'}\n")

    print("=== Q1: Total payable to Bharat Steel Works (FY2024-25) ===")
    r = q1_vendor_total(df)
    print(f"  Rs. {r['answer']:,} across {r['row_count']} rows")
    print(f"  ({r['assumption']})\n")

    print("=== Q2: Overdue invoices as at 31 Mar 2025 ===")
    r = q2_overdue_invoices(df)
    print(f"  Count: {r['answer_count']}")
    for row in r["source_invoices"]:
        print(f"    {row}")
    print()

    print("=== Q3: Highest-spend vendor FY2024-25 ===")
    r = q3_top_vendor(df)
    print(f"  {r['answer']}: Rs. {r['amount']:,}")
    print(f"  All vendor totals: {r['all_vendor_totals']}\n")

    print("=== Q4: Invoices with taxable amount > Rs.5,00,000 ===")
    r = q4_high_value_invoices(df)
    print(f"  Count: {r['answer_count']}")
    for row in r["source_invoices"]:
        print(f"    {row}")
    print()

    print("=== Q5: Total GST charged in Q3 FY2024-25 (Oct-Dec 2024) ===")
    r = q5_gst_q3(df)
    print(f"  Rs. {r['answer']:,} across {r['row_count']} rows\n")

    print("=== Q6: Invoices ineligible for ITC, and why ===")
    r = q6_no_itc(df)
    print(f"  Count: {r['answer_count']}")
    for row in r["source_invoices"]:
        print(f"    {row}")
    print()

    print("=== Q7: Average payment delay - Fabrication category ===")
    r = q7_avg_delay_fabrication(df)
    print(f"  {r['answer_days']} days (based on {r['invoices_used']} paid invoices)")
    print(f"  Excluded as data-quality issue: {r['invoices_excluded_as_data_quality_issue']}\n")

    print("=== Q8: Data quality issues ===")
    r = q8_data_quality_issues(df, excluded_path=DATA_DIR / "excluded_rows.csv")
    print(f"  Flagged rows: {r['flagged_row_count']}")
    for row in r["flagged_rows"]:
        print(f"    {row}")
    print(f"  Excluded (superseded duplicates): {r['excluded_rows']}")


if __name__ == "__main__":
    main()
