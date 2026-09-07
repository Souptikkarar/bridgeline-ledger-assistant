"""
Run this AFTER pulling your two models with `ollama pull <model>`.
It sends the same prompt to each model 3 times and reports the tokens/sec
Ollama itself measured (from eval_count / eval_duration in its API
response) - this is a real, self-measured number, not one copied from a
benchmark site, satisfying the "measured yourself" requirement in
MODEL_NOTES.md.

For RAM usage: while a model is loaded (e.g. mid-conversation in
`ollama run <model>`), open Task Manager > Performance > Memory, or run
`ollama ps` in a second terminal - it shows the resident size of each
loaded model directly.

Usage: python benchmark.py qwen2.5:3b phi3:mini
"""
import sys
import json
import time
import urllib.request

TEST_PROMPT = (
    "Classify this question into one intent from the list: "
    "q1_vendor_total, q2_overdue_invoices, q3_top_vendor. "
    "Output ONLY JSON like {\"intent\": \"...\"}. "
    "Question: How much do we owe Bharat Steel Works?"
)


def call_ollama(model: str, prompt: str) -> dict:
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/generate", data=payload,
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read().decode())
    wall = time.time() - t0
    tok_s = None
    if body.get("eval_count") and body.get("eval_duration"):
        tok_s = body["eval_count"] / (body["eval_duration"] / 1e9)
    return {
        "response": body.get("response", "")[:150],
        "eval_count_tokens": body.get("eval_count"),
        "tokens_per_sec": round(tok_s, 2) if tok_s else None,
        "wall_seconds": round(wall, 2),
        "load_duration_ms": round(body.get("load_duration", 0) / 1e6, 1),
    }


def main():
    models = sys.argv[1:] or ["qwen2.5:3b", "phi3:mini"]
    for model in models:
        print(f"\n=== {model} ===")
        results = []
        for i in range(3):
            try:
                r = call_ollama(model, TEST_PROMPT)
                results.append(r)
                print(f"  run {i+1}: {r['tokens_per_sec']} tok/s, "
                      f"{r['wall_seconds']}s wall, "
                      f"load={r['load_duration_ms']}ms, "
                      f"response={r['response']!r}")
            except Exception as e:
                print(f"  run {i+1}: FAILED - {e}")
        valid = [r["tokens_per_sec"] for r in results if r.get("tokens_per_sec")]
        if valid:
            print(f"  --> average tok/s across runs: {round(sum(valid)/len(valid), 2)}")
        print("  --> for RAM: run `ollama ps` in another terminal while this model is loaded")


if __name__ == "__main__":
    main()
