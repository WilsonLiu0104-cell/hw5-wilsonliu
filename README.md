# HW5 — `earnings-vs-guidance` Skill

**Video walkthrough:** *[(INSERT YOUR VIDEO LINK HERE)](https://youtu.be/xapkLRGcjno)*

## What the Skill Does

`earnings-vs-guidance` compares a company's actual quarterly financial results against the guidance management provided on the prior earnings call. It computes precise variances, categorizes each metric as **Beat**, **Miss**, or **Inline**, and produces a formatted comparison report — then lets the LLM provide qualitative analysis of *why* the differences exist.

This mirrors a core workflow in equity research: after every earnings release, analysts check actuals against the guide to assess management credibility and identify inflection points.

## Why I Chose It

I have experience in equity research (covering U.S. and HK-listed tech), and this is a task I've done manually many times. The key insight is that the workflow has two distinct halves:

1. **Deterministic math** — computing midpoints, variances, percentage surprises, and beat/miss boundaries. LLMs are unreliable at this: they round inconsistently, miscategorize edge cases (e.g., negative EPS), and produce inconsistent table formatting across metrics. A script must handle this.

2. **Qualitative reasoning** — hypothesizing *why* revenue beat (pricing power? volume? FX?) or why margins missed (input costs? mix shift?). This is where an LLM adds genuine value.

The script is genuinely load-bearing, not decorative. Without it, the skill would produce wrong numbers on edge cases (negative values, near-zero midpoints, wide guidance ranges).

## How to Use It

### Quick start (structured input)

Provide a JSON file with actual results and guidance:

```json
{
  "company": "Acme Corp",
  "quarter": "Q3 FY2025",
  "currency": "USD",
  "metrics": [
    {
      "name": "Revenue",
      "unit": "$M",
      "actual": 5250,
      "guidance_low": 5000,
      "guidance_high": 5200
    }
  ]
}
```

Run:
```bash
python .agents/skills/earnings-vs-guidance/scripts/compare_earnings.py --input data.json
```

### With an agent

Paste an earnings release and a prior call transcript, then ask:
> "Compare these actuals against the guidance from last quarter's call."

The agent will:
1. Extract key metrics from the unstructured text into JSON
2. Run the script for precise variance math
3. Provide qualitative analysis of the results

## What the Script Does

`scripts/compare_earnings.py` handles all deterministic computation:

- **Input validation** — checks for missing fields, non-numeric values, and logically inconsistent guidance ranges (low > high)
- **Variance math** — computes guidance midpoint, absolute delta, and percentage surprise for each metric
- **Beat/Miss categorization** — actual > guidance_high = Beat, actual < guidance_low = Miss, else Inline
- **Boundary flags** — warns when a metric is technically Inline but within 1% of the beat/miss boundary
- **Wide guidance detection** — flags metrics where the guidance range exceeds 10% of midpoint (signals management uncertainty)
- **Formatted output** — produces both structured JSON and a markdown comparison table

## Test Cases

| # | Case | File | What It Tests |
|---|------|------|---------------|
| 1 | Normal | `test_normal.json` | 6 metrics, mixed results (2 beats, 2 misses, 2 inline), wide guidance flag |
| 2 | Edge | `test_edge.json` | Point guidance (low=high), negative EPS, near-zero midpoint (N/A for Δ%), 4 metrics |
| 3 | Cautious | `test_cautious.json` | Invalid data — guidance_low > guidance_high, non-numeric actual → script catches and rejects |

## What Worked Well

- The **division of labor** feels natural: script does math, LLM does reasoning. Neither could do the other's job well.
- **Validation logic** catches real mistakes (swapped low/high, non-numeric inputs) before producing misleading results.
- The **near-boundary flag** (⚠️) is a small detail that adds real analytical value — a metric technically Inline at 1.42 vs. guidance of 1.35–1.45 is very different from one at 1.40.
- **Negative number handling** works correctly for loss-making companies (common in biotech/growth-stage).

## Limitations

- Compares actuals to **company guidance only**, not Street consensus estimates. A full earnings analysis would need both.
- Does not fetch data from APIs — all data must be provided or extracted by the LLM from pasted text.
- Percentage-based metrics (margins) and absolute metrics (revenue) both work, but the user must tag the `format` field correctly for percentage-point deltas vs. percentage deltas.
- The "overall signal" heuristic (Clean Beat, Mixed, etc.) is simple — a production version would weight by metric importance (e.g., revenue beat matters more than R&D expense inline).
- Single-quarter only. Multi-quarter guidance tracking (e.g., has management been consistently sandbagging?) is out of scope.
