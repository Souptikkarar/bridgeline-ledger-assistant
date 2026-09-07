"""
Day 4 — the actual CLI entrypoint. Run: python main.py



If Ollama is not reachable, the tool still works in a reduced mode:
it falls back to simple keyword matching for intent detection and prints
the raw structured result instead of an LLM-phrased sentence. This means
a customer machine that can't run any model is not left with nothing,
per the assignment's hardware note.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import urllib.error

import query as q

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b"  # change to whichever model you pulled; see MODEL_NOTES.md


# Fixed intent schema. The LLM must pick one of these names exactly and
# supply only the listed params. Python validates before trusting any of
# this - the LLM cannot invent a new function to call or free-form params.

INTENTS = {
    "q1_vendor_total": {
        "description": "Total amount payable/spent with a specific vendor for FY2024-25",
        "params": ["vendor"],
    },
    "q2_overdue_invoices": {
        "description": "Which invoices are overdue as at 31 March 2025, and how many",
        "params": [],
    },
    "q3_top_vendor": {
        "description": "Which vendor had the highest total spend in FY2024-25",
        "params": [],
    },
    "q4_high_value_invoices": {
        "description": "List invoices with taxable amount above a threshold (default Rs 5,00,000)",
        "params": [],
    },
    "q5_gst_q3": {
        "description": "Total GST charged in Q3 FY2024-25 (Oct-Dec 2024)",
        "params": [],
    },
    "q6_no_itc": {
        "description": "Which invoices cannot be claimed for input tax credit, and why",
        "params": [],
    },
    "q7_avg_delay_fabrication": {
        "description": "Average payment delay for the Fabrication category",
        "params": [],
    },
    "q8_data_quality_issues": {
        "description": "Duplicate, suspicious, or unreliable entries in the ledger",
        "params": [],
    },
    "q9_total_taxable_spend": {
        "description": "Total taxable amount (excluding GST) spent across all vendors, FY2024-25",
        "params": [],
    },
    "q10_most_overdue_by_count": {
        "description": "Which vendor(s) have the most overdue invoices by count",
        "params": [],
    },
    "q11_avg_raw_material": {
        "description": "Average taxable amount for Raw Material category invoices",
        "params": [],
    },
    "q12_missing_gstin_value": {
        "description": "Count and combined taxable value of invoices missing a GSTIN",
        "params": [],
    },
}

CANONICAL_VENDORS = [
    "Bharat Steel Works", "Konark Fabrication Pvt. Ltd.", "Eastern Logistics Co",
    "Apex Safety Equipment", "Precision Tools India", "Gupta Hardware Stores",
    "Nova Paints & Coatings", "Sundaram Engineering Ltd", "Sen Brothers Welding",
    "Meridian Consultants LLP",
]


def ollama_available() -> bool:
    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/tags", method="GET"
        )
        urllib.request.urlopen(req, timeout=2)
        return True
    except Exception:
        return False


def call_ollama(prompt: str, model: str = MODEL, timeout: int = 60) -> dict:
    """Returns {'text': str, 'tokens_per_sec': float|None}. Raises on failure."""
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"}
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    wall = time.time() - t0

    text = body.get("response", "")
    # Ollama returns eval_count (tokens generated) and eval_duration (ns)
    # measured on YOUR machine - this is the real, self-measured number
    # MODEL_NOTES.md needs, not a number copied from the internet.
    tok_s = None
    if body.get("eval_count") and body.get("eval_duration"):
        tok_s = body["eval_count"] / (body["eval_duration"] / 1e9)
    return {"text": text, "tokens_per_sec": tok_s, "wall_seconds": wall}


def classify_intent(question: str) -> dict | None:
    """Ask the LLM to pick an intent + params. Returns a validated dict
    {'intent':..., 'params':{...}} or None if unparseable/invalid, in
    which case the caller falls back to keyword matching."""
    intent_list = "\n".join(f"- {name}: {v['description']}" for name, v in INTENTS.items())
    prompt = f"""You are a strict classifier. Given a question about a vendor ledger,
pick EXACTLY ONE intent name from this list and output ONLY a JSON object,
no other text, no explanation, no markdown fences.

Intents:
{intent_list}

If the question asks about a specific vendor's total, extract the vendor
name as closely as possible into params.vendor.

Known vendors: {", ".join(CANONICAL_VENDORS)}

Output format (JSON only): {{"intent": "<intent_name>", "params": {{"vendor": "<name or omit>"}}}}

Question: {question}
JSON:"""
    try:
        result = call_ollama(prompt)
    except Exception as e:
        print(f"  [Ollama call failed: {e}]")
        return None

    raw = result["text"].strip()
    # strip accidental markdown fences, small models sometimes add them anyway
    raw = raw.strip("`")
    if raw.lower().startswith("json"):
        raw = raw[4:].strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        print(f"  [LLM did not return valid JSON, got: {raw[:200]!r}]")
        return None

    intent = parsed.get("intent")
    if intent not in INTENTS:
        print(f"  [LLM picked an unknown intent: {intent!r}]")
        return None

    params = parsed.get("params", {}) or {}
    # Validate/snap vendor param to a real canonical vendor - never trust
    # the LLM's spelling exactly, since it could hallucinate a close-but-
    # wrong name.
    if "vendor" in params:
        v = params["vendor"]
        match = next((c for c in CANONICAL_VENDORS if v.lower() in c.lower()
                      or c.lower() in v.lower()), None)
        if match is None:
            print(f"  [LLM named a vendor not in the ledger: {v!r}]")
            return None
        params["vendor"] = match

    result["parsed"] = {"intent": intent, "params": params}
    return result["parsed"]


def keyword_fallback(question: str) -> dict:
    """No-LLM fallback: simple keyword rules. Used if Ollama is down."""
    ql = question.lower()
    for vendor in CANONICAL_VENDORS:
        if vendor.lower() in ql or vendor.split()[0].lower() in ql:
            return {"intent": "q1_vendor_total", "params": {"vendor": vendor}}
    if "overdue" in ql and "count" in ql:
        return {"intent": "q10_most_overdue_by_count", "params": {}}
    if "overdue" in ql:
        return {"intent": "q2_overdue_invoices", "params": {}}
    if "highest" in ql or "most spend" in ql or "top vendor" in ql:
        return {"intent": "q3_top_vendor", "params": {}}
    if "5,00,000" in ql or "500000" in ql or "high value" in ql or "high-value" in ql:
        return {"intent": "q4_high_value_invoices", "params": {}}
    if "gst" in ql and ("q3" in ql or "quarter" in ql or "oct" in ql):
        return {"intent": "q5_gst_q3", "params": {}}
    if "itc" in ql or "input tax credit" in ql:
        return {"intent": "q6_no_itc", "params": {}}
    if "delay" in ql and "fabrication" in ql:
        return {"intent": "q7_avg_delay_fabrication", "params": {}}
    if "duplicate" in ql or "suspicious" in ql or "unreliable" in ql:
        return {"intent": "q8_data_quality_issues", "params": {}}
    if "total taxable" in ql:
        return {"intent": "q9_total_taxable_spend", "params": {}}
    if "raw material" in ql and "average" in ql:
        return {"intent": "q11_avg_raw_material", "params": {}}
    if "missing gstin" in ql or "no gstin" in ql:
        return {"intent": "q12_missing_gstin_value", "params": {}}
    return {"intent": None, "params": {}}


def run_intent(df, intent: str, params: dict):
    fn_map = {
        "q1_vendor_total": lambda: q.q1_vendor_total(df, params.get("vendor", "Bharat Steel Works")),
        "q2_overdue_invoices": lambda: q.q2_overdue_invoices(df),
        "q3_top_vendor": lambda: q.q3_top_vendor(df),
        "q4_high_value_invoices": lambda: q.q4_high_value_invoices(df),
        "q5_gst_q3": lambda: q.q5_gst_q3(df),
        "q6_no_itc": lambda: q.q6_no_itc(df),
        "q7_avg_delay_fabrication": lambda: q.q7_avg_delay_fabrication(df),
        "q8_data_quality_issues": lambda: q.q8_data_quality_issues(df, q.DATA_DIR / "excluded_rows.csv"),
        "q9_total_taxable_spend": lambda: q.q9_total_taxable_spend(df),
        "q10_most_overdue_by_count": lambda: q.q10_most_overdue_by_count(df),
        "q11_avg_raw_material": lambda: q.q11_avg_raw_material(df),
        "q12_missing_gstin_value": lambda: q.q12_missing_gstin_value(df),
    }
    return fn_map[intent]()


def phrase_answer(question: str, intent: str, result: dict, llm_ok: bool) -> str:
    if not llm_ok:
        # Reduced mode: no LLM, print the structured result directly.
        return f"[No-LLM mode] Result: {json.dumps(result, default=str, indent=2)}"

    prompt = f"""Answer the user's question in 1-3 plain English sentences,
using ONLY the numbers and facts given below. Do NOT calculate anything
yourself, do NOT add numbers not shown here, do NOT round differently
than shown. All amounts are in Indian Rupees - write them as "Rs." or
"₹", NEVER as "$" or "USD", regardless of how the number is formatted
below. If invoice numbers are listed, mention how many there are and
name a few as examples, citing them as the source.

Question: {question}

Computed result (already correct, from Python, do not recompute):
{json.dumps(result, default=str, indent=2)}

Answer:"""
    try:
        r = call_ollama(prompt)
        return r["text"].strip()
    except Exception as e:
        return f"[LLM phrasing failed ({e}), raw result: {json.dumps(result, default=str)}]"


def main():
    df = q.load_clean()
    llm_ok = ollama_available()
    if not llm_ok:
        print("*** Ollama not reachable at localhost:11434 - running in "
              "reduced (no-LLM) mode. Structured results only. ***\n")

    print("Bridgeline Ledger Assistant - type a question, or 'quit' to exit.\n")
    while True:
        question = input("> ").strip()
        if question.lower() in ("quit", "exit", "q"):
            break
        if not question:
            continue

        parsed = classify_intent(question) if llm_ok else None
        if parsed is None:
            parsed = keyword_fallback(question)
        intent, params = parsed["intent"], parsed["params"]

        if intent is None:
            print("Sorry, I couldn't match that to a question I know how to "
                  "answer. Try asking about a vendor total, overdue invoices, "
                  "GST, or data quality issues.\n")
            continue

        try:
            result = run_intent(df, intent, params)
        except Exception as e:
            print(f"[Error running {intent}: {e}]\n")
            continue

        answer = phrase_answer(question, intent, result, llm_ok)
        print(f"\n{answer}\n")
        print(f"[Source: query.py::{intent}, computed from ledger_clean.csv - "
              f"see raw result above for exact invoice numbers]\n")


if __name__ == "__main__":
    main()
