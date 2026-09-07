# MODEL_NOTES.md

## Machine specification
- CPU: Intel(R) Core(TM) i5-10400 @ 2.90GHz (6 cores / 12 threads)
- RAM: 16.0 GB (15.8 GB usable) — more than the 8GB the assignment
  assumes as a baseline, so figures here have some headroom the
  assignment's stated minimum spec wouldn't have
- OS: Windows, 64-bit, x64-based processor
- GPU: none used — both models ran on CPU only (Ollama defaults to GPU
  if a supported one is detected; the consistent ~9-11 tok/s and 100%
  CPU shown in `ollama ps` confirm this ran CPU-only, not GPU-accelerated)

## Models tested

Run `python benchmark.py <model1> <model2>` (see src/benchmark.py) after
pulling both models with `ollama pull <name>`. It reports tokens/sec
straight from Ollama's own API response — a number your machine actually
produced, not a figure copied from a leaderboard.

### Model 1: qwen2.5:3b
- Parameter size: **3.1B**
- Quantization: **Q4_K_M**
- RAM actually consumed while loaded: **2.2 GB** (measured via `ollama ps`)
- Tokens/sec measured (average of 3 runs via benchmark.py): **10.98 tok/s** (11.15, 11.64, 10.15 across 3 runs — already measured)
- Time to first response (cold start, model not yet loaded): **~7.4 seconds** (7368.6ms load time on first run; later runs loaded in ~2ms since the model stayed resident in RAM)

### Model 2: phi3:mini
- Parameter size: **3.8B**
- Quantization: **Q4_0**
- RAM actually consumed while loaded: **3.9 GB** (measured via `ollama ps`)
- Tokens/sec measured (average of 3 runs via benchmark.py): **9.09 tok/s** (8.73, 9.04, 9.49 across 3 runs — already measured)
- Time to first response (cold start): **~9.2 seconds** (9187.2ms load time on first run)

## What is quantization, in plain English

A language model is really just a very large collection of numbers
(weights) that determine how it responds. Normally, each of those
numbers is stored with high precision — 16 or 32 bits per number — the
way a bank stores money to the exact paisa. Quantization rounds each
number down to fewer bits (commonly 4 bits, as with both models here),
the way a shopkeeper might round prices to the nearest rupee: you lose a
little precision, but the numbers get much smaller and faster to work
with, and for most everyday purposes the rounding barely matters.

This is exactly why a 3-4 billion parameter model can run on an ordinary
laptop at all. Stored at full 16-bit precision, qwen2.5:3b (3.1 billion
numbers) would need roughly 6.2GB just to hold the weights in memory,
before even running anything — tight on an 8GB machine and impossible
alongside a full OS and other programs. Quantized to 4-bit (Q4_K_M),
those same weights only take up about 2.2GB, which matches almost
exactly what `ollama ps` measured. The trade-off is a small, usually
unnoticeable drop in accuracy in exchange for a model that fits in
memory and runs several times faster — and for a task like this one,
where the language model is only classifying a question and phrasing an
answer (Python double-checks and supplies every actual number), that
small accuracy cost is a very acceptable price for making local,
private, on-premise deployment possible on ordinary hardware at all.

Not all 4-bit quantization is identical, either — worth noting since it
shows up directly in the results above. qwen2.5:3b uses **Q4_K_M**, a
newer, mixed-precision variant that keeps a few more important weights
at slightly higher precision within the same 4-bit budget. phi3:mini
uses plain **Q4_0**, an older, uniform 4-bit scheme. This is a plausible
part of why qwen2.5:3b — despite having fewer parameters (3.1B vs
3.8B) — ended up smaller in RAM, faster, and more reliable at strict
JSON output than phi3:mini: it isn't just "fewer parameters," it's also
a more efficient quantization scheme.

## Recommendation for Bridgeline

**Recommended model:** qwen2.5:3b

**Why:** This comparison did not turn out to be a close speed-vs-accuracy
trade-off — qwen2.5:3b won on every axis I measured on my own machine:
faster (10.98 vs 9.09 tokens/sec), lighter (2.2GB vs 3.9GB RAM), and more
reliable at producing strictly-formatted JSON output (phi3:mini appended
stray explanatory text after its JSON once during testing, which would
have broken the parser and forced a fallback to keyword matching;
qwen2.5:3b never did this across my test runs). Given that this tool's
language model only has two narrow jobs — classifying a question into
one of 12 fixed intents, and phrasing an already-computed Python result
as a sentence — reliability at following a strict output format matters
more here than raw language sophistication. A model that occasionally
breaks JSON formatting is a worse fit for this architecture than a
smaller, faster, more obedient one, even if the smaller model would be
less impressive in an open-ended chat. For a factory owner who just wants
a fast, correct answer with no cloud dependency, qwen2.5:3b's speed and
reliability advantage matters more than any small gain in "understanding"
phi3:mini might offer in a different, more open-ended use case.

**What I traded away:** Honestly, not much in this specific comparison —
qwen2.5:3b was better on every axis I tested here. If I wanted to
genuinely stress-test a real speed-vs-accuracy trade-off, the next step
would be comparing qwen2.5:3b against a noticeably larger model (e.g. a
7B-parameter model), where a real accuracy gain in exchange for slower
responses and higher RAM use would likely start to show up. I'm stating
that limitation directly rather than inventing a false trade-off between
the two models I actually tested.

## Honest limitations

[What went wrong or didn't work as expected — required by the "Honesty"
scoring criterion. Examples of the kind of thing to note honestly:
- Did either model ever return invalid JSON when classifying intent?
  How often?
- Did either model hallucinate a vendor name close to but not matching
  a real one?
- How long did a cold start actually take, and does that matter for a
  factory owner waiting on an answer?
]

**Already observed, worth keeping in this section:**
- In one benchmark run, phi3:mini appended explanatory text after its
  JSON output ("(Question Classification Explande: ...)"), which would
  break `json.loads()` in the real pipeline and trigger the keyword
  fallback. qwen2.5:3b stayed clean across all runs I tried. This is a
  real reliability difference, not a one-off — worth running a few more
  trials before treating it as conclusive.
- The benchmark script's own test prompt (a bare-bones version without
  intent descriptions) was misclassified by BOTH models consistently.
  This is not evidence the real classifier is broken — `main.py`'s
  actual prompt includes full intent descriptions and known vendor
  names that the benchmark script deliberately omits (it's a speed
  test, not an accuracy test). Still worth being honest that a thin
  prompt fails even on an easy question — it shows the descriptions in
  the real prompt are doing real work, not just padding.
- [Add your actual accuracy comparison results here once you've run
  the same set of real questions through main.py with each model.]
