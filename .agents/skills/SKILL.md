---
name: earnings-vs-guidance
description: >
  Compares a company's actual quarterly financial results against prior management
  guidance, computing precise variances and categorizing each metric as Beat, Miss,
  or Inline. Use this skill whenever the user asks to compare earnings results to
  guidance, check if a company beat or missed expectations, analyze actual-vs-guided
  financial metrics, or review quarterly performance against management forecasts.
  Also trigger when the user provides an earnings release alongside a prior earnings
  call transcript and wants a structured comparison. Do NOT use for consensus
  analyst estimates (this is guidance-only), full DCF/valuation work, or multi-quarter
  trend analysis.
---

# Earnings vs. Guidance Analyzer

## Purpose

Equity analysts routinely compare reported quarterly results against the guidance
management provided on the prior earnings call. This skill automates the
deterministic part of that workflow — precise variance math, beat/miss
categorization, and structured report formatting — so the analyst (or LLM) can
focus on the qualitative "why."

## When to Use

- User provides actual quarterly results and prior guidance figures
- User pastes an earnings release and a prior call transcript and asks for a comparison
- User asks "did the company beat guidance?" or "how did actuals compare to the guide?"
- User wants a structured beat/miss report for a specific quarter

## When NOT to Use

- Comparing actuals to **consensus analyst estimates** (Street expectations ≠ company guidance)
- Full valuation, DCF modeling, or price-target work
- Multi-quarter trend analysis or historical comparisons across several periods
- Guidance that is purely qualitative with no numeric ranges (e.g., "we expect strong growth")

## Expected Inputs

The workflow supports two input modes:

### Mode A — Structured JSON (direct)
User provides a JSON object (or the LLM constructs one) with this schema:

```json
{
  "company": "Acme Corp",
  "quarter": "Q3 FY2025",
  "currency": "USD",
  "metrics": [
    {
      "name": "Revenue",
      "unit": "millions",
      "actual": 5250,
      "guidance_low": 5000,
      "guidance_high": 5200
    }
  ]
}
```

### Mode B — Unstructured text (LLM-assisted)
User pastes raw text from an earnings release and/or a prior earnings call
transcript. In this case:

1. **You (the LLM) extract** the key financial metrics and guidance figures from
   the unstructured text into the JSON schema above.
2. Common metrics to look for: Revenue, Operating Income, Net Income, EPS
   (GAAP & Non-GAAP), Gross Margin, Operating Margin, Free Cash Flow, and any
   segment-level revenue the company guided on.
3. If guidance was given as a single point, set `guidance_low` = `guidance_high`.
4. If guidance was given as "approximately X," set a ±2% band unless context
   suggests otherwise.
5. If a metric's actual or guidance is missing, **omit it** rather than guess.

## Step-by-Step Instructions

### Step 1 — Gather and structure inputs
- If the user gave structured data, validate it matches the schema.
- If the user gave unstructured text, extract metrics into the JSON schema.
  Double-check extracted numbers against the source text.

### Step 2 — Run the comparison script
Execute the Python script to compute variances:

```bash
python /path/to/skills/earnings-vs-guidance/scripts/compare_earnings.py --input input.json
```

The script will:
- Compute the guidance midpoint for each metric
- Calculate absolute and percentage variance (actual vs. midpoint)
- Categorize each metric as **Beat** (actual > guidance_high), **Miss**
  (actual < guidance_low), or **Inline** (within the guided range)
- Compute a "surprise magnitude" percentage for beats and misses
- Output a structured JSON report and a formatted markdown table

### Step 3 — Analyze and reason about differences
After the script produces the quantitative comparison, **you (the LLM) provide
qualitative analysis**:
- For each Beat or Miss, hypothesize likely drivers (e.g., pricing power,
  volume shortfall, FX headwinds, one-time items)
- Note any metrics that were barely inline (within 1% of the boundary)
- Flag any metrics where guidance was unusually wide (>10% range), which
  suggests management uncertainty
- Summarize the overall earnings quality in 2–3 sentences

### Step 4 — Present the output
Combine the script's formatted table with your qualitative analysis into a
single coherent report. The report should include:
1. A header with company name, quarter, and currency
2. The comparison table (from the script)
3. Key takeaways section (from your analysis)
4. Any caveats or data quality notes

## Output Format

The final deliverable is a markdown report with a table like:

| Metric | Actual | Guidance (Low–High) | Midpoint | Δ vs Mid | Δ% | Verdict |
|--------|--------|---------------------|----------|----------|-----|---------|
| Revenue ($M) | 5,250 | 5,000 – 5,200 | 5,100 | +150 | +2.9% | Beat |
| EPS ($) | 1.42 | 1.35 – 1.45 | 1.40 | +0.02 | +1.4% | Inline |

Followed by qualitative analysis.

## Limitations

- This skill compares actuals to **company guidance only**, not Street consensus.
- The script performs arithmetic; it does not validate whether the numbers are correct.
  If the user provides wrong inputs, the output will be wrong.
- Percentage-based metrics (margins) and absolute metrics (revenue) are both supported,
  but the user should ensure units are consistent.
- The script does not fetch data from external APIs. All data must be provided by the user.
