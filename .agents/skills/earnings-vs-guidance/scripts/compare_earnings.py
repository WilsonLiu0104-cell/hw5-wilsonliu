#!/usr/bin/env python3
"""
compare_earnings.py — Earnings vs. Guidance Variance Analyzer

Reads a JSON file containing actual quarterly results and prior management
guidance, then computes precise variances and categorizes each metric as
Beat, Miss, or Inline.

This script is the load-bearing deterministic component of the
earnings-vs-guidance skill. LLMs cannot reliably perform consistent
percentage arithmetic, beat/miss boundary checks, or formatted table
generation across many metrics — this script guarantees correctness.

Usage:
    python compare_earnings.py --input data.json [--threshold 0.0] [--output report.json]

Input JSON schema:
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
      "guidance_high": 5200,
      "format": "number"        // optional: "number" (default), "percent", "ratio"
    }
  ]
}
"""

import argparse
import json
import sys
from pathlib import Path


# ── Verdict logic ────────────────────────────────────────────────────────────

def categorize(actual: float, low: float, high: float) -> str:
    """Categorize actual vs. guidance range as Beat / Miss / Inline."""
    if actual > high:
        return "Beat"
    elif actual < low:
        return "Miss"
    else:
        return "Inline"


def surprise_pct(actual: float, midpoint: float) -> float | None:
    """Percentage surprise vs. guidance midpoint. None if midpoint is zero."""
    if midpoint == 0:
        return None
    return round((actual - midpoint) / abs(midpoint) * 100, 2)


def guidance_width_pct(low: float, high: float) -> float | None:
    """How wide the guidance range is as a % of midpoint."""
    mid = (low + high) / 2
    if mid == 0:
        return None
    return round((high - low) / abs(mid) * 100, 2)


# ── Formatting helpers ───────────────────────────────────────────────────────

def fmt_number(value: float, fmt_type: str = "number", unit: str = "") -> str:
    """Format a number for display based on its type."""
    if fmt_type == "percent":
        return f"{value:.1f}%"
    elif fmt_type == "ratio":
        return f"{value:.2f}x"
    else:
        # Standard number: use commas, decide decimal places
        if abs(value) >= 100:
            return f"{value:,.0f}"
        elif abs(value) >= 1:
            return f"{value:,.2f}"
        else:
            return f"{value:,.4f}"


def fmt_delta(value: float, fmt_type: str = "number") -> str:
    """Format a delta with explicit +/- sign."""
    sign = "+" if value >= 0 else "-"
    if fmt_type == "percent":
        return f"{sign}{abs(value):.1f}pp"  # percentage points
    else:
        return f"{sign}{fmt_number(abs(value), fmt_type)}"


def fmt_surprise(pct: float | None) -> str:
    if pct is None:
        return "N/A"
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}%"


# ── Core analysis ────────────────────────────────────────────────────────────

def analyze_metric(metric: dict) -> dict:
    """Analyze a single metric and return enriched results."""
    name = metric["name"]
    unit = metric.get("unit", "")
    fmt_type = metric.get("format", "number")
    actual = float(metric["actual"])
    low = float(metric["guidance_low"])
    high = float(metric["guidance_high"])

    midpoint = round((low + high) / 2, 4)
    delta_abs = round(actual - midpoint, 4)
    delta_pct = surprise_pct(actual, midpoint)
    verdict = categorize(actual, low, high)
    width = guidance_width_pct(low, high)

    # Flag narrow beats/misses (within 1% of boundary)
    near_boundary = False
    if verdict == "Inline" and midpoint != 0:
        dist_to_high = abs(high - actual) / abs(midpoint) * 100
        dist_to_low = abs(actual - low) / abs(midpoint) * 100
        if dist_to_high < 1.0 or dist_to_low < 1.0:
            near_boundary = True

    return {
        "name": name,
        "unit": unit,
        "format": fmt_type,
        "actual": actual,
        "guidance_low": low,
        "guidance_high": high,
        "midpoint": midpoint,
        "delta_abs": delta_abs,
        "delta_pct": delta_pct,
        "verdict": verdict,
        "guidance_width_pct": width,
        "near_boundary": near_boundary,
    }


def build_summary(results: list[dict]) -> dict:
    """Build an overall summary from individual metric results."""
    beats = [r for r in results if r["verdict"] == "Beat"]
    misses = [r for r in results if r["verdict"] == "Miss"]
    inlines = [r for r in results if r["verdict"] == "Inline"]
    near_boundary = [r for r in results if r["near_boundary"]]
    wide_guidance = [r for r in results if r["guidance_width_pct"] and r["guidance_width_pct"] > 10]

    total = len(results)
    beat_rate = round(len(beats) / total * 100, 1) if total else 0

    # Overall signal
    if len(beats) > len(misses) and len(misses) == 0:
        overall = "Clean Beat"
    elif len(beats) > len(misses):
        overall = "Mixed — Net Positive"
    elif len(misses) > len(beats) and len(beats) == 0:
        overall = "Clean Miss"
    elif len(misses) > len(beats):
        overall = "Mixed — Net Negative"
    elif len(beats) == len(misses) and len(beats) > 0:
        overall = "Mixed — Balanced"
    else:
        overall = "Fully Inline"

    return {
        "total_metrics": total,
        "beats": len(beats),
        "misses": len(misses),
        "inlines": len(inlines),
        "beat_rate_pct": beat_rate,
        "overall_signal": overall,
        "near_boundary_metrics": [r["name"] for r in near_boundary],
        "wide_guidance_metrics": [r["name"] for r in wide_guidance],
    }


# ── Markdown table ───────────────────────────────────────────────────────────

def render_markdown(company: str, quarter: str, currency: str,
                    results: list[dict], summary: dict) -> str:
    """Render the full comparison as a markdown report."""
    lines = []
    lines.append(f"# {company} — {quarter} Earnings vs. Guidance")
    lines.append(f"**Currency:** {currency}\n")

    # Verdict emoji map
    emoji = {"Beat": "🟢", "Miss": "🔴", "Inline": "🟡"}

    # Table header
    lines.append("| Metric | Actual | Guidance (Low – High) | Midpoint | Δ vs Mid | Δ% | Verdict |")
    lines.append("|--------|-------:|----------------------:|--------:|---------:|----:|---------|")

    for r in results:
        ft = r["format"]
        unit_label = f" ({r['unit']})" if r["unit"] else ""
        name_col = f"{r['name']}{unit_label}"
        actual_col = fmt_number(r["actual"], ft)
        guide_col = f"{fmt_number(r['guidance_low'], ft)} – {fmt_number(r['guidance_high'], ft)}"
        mid_col = fmt_number(r["midpoint"], ft)
        delta_col = fmt_delta(r["delta_abs"], ft)
        dpct_col = fmt_surprise(r["delta_pct"])
        verdict_col = f"{emoji.get(r['verdict'], '')} {r['verdict']}"
        if r["near_boundary"]:
            verdict_col += " ⚠️"

        lines.append(f"| {name_col} | {actual_col} | {guide_col} | {mid_col} | {delta_col} | {dpct_col} | {verdict_col} |")

    # Summary section
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- **Overall Signal:** {summary['overall_signal']}")
    lines.append(f"- **Beat Rate:** {summary['beat_rate_pct']}% ({summary['beats']}/{summary['total_metrics']} metrics)")
    lines.append(f"- **Beats:** {summary['beats']}  |  **Misses:** {summary['misses']}  |  **Inline:** {summary['inlines']}")

    if summary["near_boundary_metrics"]:
        names = ", ".join(summary["near_boundary_metrics"])
        lines.append(f"- **⚠️ Near-boundary (within 1%):** {names}")

    if summary["wide_guidance_metrics"]:
        names = ", ".join(summary["wide_guidance_metrics"])
        lines.append(f"- **Wide guidance range (>10%):** {names}")

    lines.append("")
    return "\n".join(lines)


# ── Validation ───────────────────────────────────────────────────────────────

def validate_input(data: dict) -> list[str]:
    """Validate input data and return a list of error messages (empty = valid)."""
    errors = []

    if "company" not in data:
        errors.append("Missing required field: 'company'")
    if "quarter" not in data:
        errors.append("Missing required field: 'quarter'")
    if "metrics" not in data or not isinstance(data.get("metrics"), list):
        errors.append("Missing or invalid 'metrics' array")
        return errors  # Can't continue without metrics
    if len(data["metrics"]) == 0:
        errors.append("'metrics' array is empty — nothing to compare")
        return errors

    for i, m in enumerate(data["metrics"]):
        prefix = f"metrics[{i}]"
        if "name" not in m:
            errors.append(f"{prefix}: missing 'name'")
        for field in ("actual", "guidance_low", "guidance_high"):
            if field not in m:
                errors.append(f"{prefix} ({m.get('name', '?')}): missing '{field}'")
            elif not isinstance(m[field], (int, float)):
                errors.append(f"{prefix} ({m.get('name', '?')}): '{field}' must be a number, got {type(m[field]).__name__}")

        # Check logical consistency
        if "guidance_low" in m and "guidance_high" in m:
            if isinstance(m["guidance_low"], (int, float)) and isinstance(m["guidance_high"], (int, float)):
                if m["guidance_low"] > m["guidance_high"]:
                    errors.append(f"{prefix} ({m.get('name', '?')}): guidance_low ({m['guidance_low']}) > guidance_high ({m['guidance_high']})")

    return errors


# ── CLI entry point ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Compare quarterly earnings actuals against management guidance."
    )
    parser.add_argument("--input", required=True, help="Path to input JSON file")
    parser.add_argument("--output", default=None, help="Path to write JSON results (optional)")
    parser.add_argument(
        "--format", choices=["markdown", "json", "both"], default="both",
        help="Output format (default: both)"
    )
    args = parser.parse_args()

    # Load input
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    with open(input_path) as f:
        data = json.load(f)

    # Validate
    errors = validate_input(data)
    if errors:
        print("Validation errors:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    # Analyze
    company = data.get("company", "Unknown")
    quarter = data.get("quarter", "Unknown")
    currency = data.get("currency", "USD")

    results = [analyze_metric(m) for m in data["metrics"]]
    summary = build_summary(results)

    # Output
    output_data = {
        "company": company,
        "quarter": quarter,
        "currency": currency,
        "results": results,
        "summary": summary,
    }

    if args.format in ("json", "both"):
        json_str = json.dumps(output_data, indent=2)
        if args.output:
            out_path = Path(args.output)
            with open(out_path, "w") as f:
                f.write(json_str)
            print(f"JSON report written to {out_path}", file=sys.stderr)
        if args.format == "json":
            print(json_str)

    if args.format in ("markdown", "both"):
        md = render_markdown(company, quarter, currency, results, summary)
        print(md)


if __name__ == "__main__":
    main()
