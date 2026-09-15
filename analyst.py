"""
LLM orchestration layer.
- One Anthropic API call per vendor (batched with rate-limit guard)
- Structured JSON output parsed and validated before returning
- Demo mode returns pre-generated analysis when no API key is set
"""

import os, json, time
import anthropic
from prompts import (
    SYSTEM_PROMPT,
    vendor_analysis_prompt,
    executive_summary_prompt,
    anomaly_detection_prompt,
)

MODEL   = "claude-haiku-4-5"   # Fast + cheap; swap to claude-sonnet-4-5 for higher quality
MAX_TOKENS = 1024
RATE_LIMIT_DELAY = 0.5          # seconds between calls — keeps well under API rate limits


def _get_client() -> anthropic.Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise ValueError(
            "ANTHROPIC_API_KEY not set. Add it to your .env file or set it as an environment variable.\n"
            "Get a free key at https://console.anthropic.com"
        )
    return anthropic.Anthropic(api_key=key)


def _call_llm(client: anthropic.Anthropic, user_prompt: str) -> dict:
    """Single LLM call. Returns parsed JSON dict."""
    msg = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    raw = msg.content[0].text.strip()
    # Strip markdown code fences if model wraps in ```json ... ```
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def analyse_vendor(
    client: anthropic.Anthropic,
    vendor: str,
    vendor_type: str,
    period: str,
    metrics: dict,
    context: dict,
) -> dict:
    """Run LLM analysis for a single vendor. Returns enriched dict."""
    prompt = vendor_analysis_prompt(vendor, vendor_type, period, metrics, context)
    result = _call_llm(client, prompt)
    return {
        "vendor":    vendor,
        "period":    period,
        "otif_pct":  metrics["otif_pct"],
        "sla_score": metrics["sla_score"],
        **result,
    }


def analyse_all_vendors(
    vendor_data_list: list[dict],
    progress_callback=None,
) -> tuple[list[dict], dict]:
    """
    Batch-analyse every vendor for a given month.
    vendor_data_list: list of {vendor, vendor_type, period, metrics, context}
    progress_callback: optional fn(vendor_name, i, total) — used by Streamlit progress bar
    Returns (vendor_analyses, executive_summary)
    """
    client    = _get_client()
    results   = []
    n         = len(vendor_data_list)

    for i, vd in enumerate(vendor_data_list):
        if progress_callback:
            progress_callback(vd["vendor"], i, n)
        try:
            result = analyse_vendor(
                client,
                vd["vendor"],
                vd["vendor_type"],
                vd["period"],
                vd["metrics"],
                vd["context"],
            )
            results.append(result)
        except Exception as e:
            results.append({
                "vendor":    vd["vendor"],
                "period":    vd["period"],
                "otif_pct":  vd["metrics"].get("otif_pct", 0),
                "sla_score": vd["metrics"].get("sla_score", 0),
                "error":     str(e),
                "risk_level": "Unknown",
                "escalate_flag": False,
            })
        time.sleep(RATE_LIMIT_DELAY)   # gentle rate limiting

    if progress_callback:
        progress_callback("Executive summary", n, n)

    period = vendor_data_list[0]["period"] if vendor_data_list else "Unknown"
    exec_prompt = executive_summary_prompt(period, results)
    try:
        exec_summary = _call_llm(client, exec_prompt)
    except Exception as e:
        exec_summary = {"error": str(e), "headline": "Summary unavailable."}

    return results, exec_summary


def detect_anomaly(
    client: anthropic.Anthropic,
    vendor: str,
    current_metrics: dict,
    prior_metrics: dict,
) -> dict:
    """MoM anomaly detection for a single vendor."""
    prompt = anomaly_detection_prompt(vendor, current_metrics, prior_metrics)
    try:
        return _call_llm(client, prompt)
    except Exception as e:
        return {"anomaly_detected": False, "severity": "Unknown", "description": str(e)}


# ── Demo mode ──────────────────────────────────────────────────────────────────
# Pre-baked responses so the UI is fully functional without an API key.
# Used when DEMO_MODE=1 is set or when the API key is missing and the user
# explicitly enables demo mode in the UI.

DEMO_VENDOR_ANALYSIS = {
    "performance_summary": (
        "DHL Express achieved an OTIF of 93.2% in December 2024, comfortably above the 90% SLA "
        "target, with an average delay of 0.8 days on late shipments. The SLA score of 91.4 "
        "reflects consistent delivery performance across the APAC region, particularly in "
        "Singapore and Malaysia corridors."
    ),
    "root_cause_analysis": (
        "Strong performance is driven by DHL's established last-mile network in core APAC markets "
        "and pre-cleared customs arrangements in Singapore and Australia. The residual 6.8% miss "
        "rate is concentrated in Indonesian domestic routes, where port congestion and multi-leg "
        "customs handoffs introduce variability beyond carrier control."
    ),
    "risk_level": "Low",
    "risk_rationale": "OTIF above target with improving MoM trend; no invoice anomalies detected.",
    "recommended_actions": [
        "Negotiate Q1 2025 SLA commitment for Indonesia routes — current 4-day SLA may need extending to 5 days to reflect realistic transit times.",
        "Request customs pre-clearance documentation checklist from DHL for Indonesia-bound IT equipment shipments to reduce holds.",
        "Review cost-per-shipment trajectory — 3.2% MoM increase warrants a rate review before Q2.",
    ],
    "escalate_flag": False,
    "escalation_reason": None,
}

DEMO_EXEC_SUMMARY = {
    "headline": "APAC courier fleet is stable heading into Q1 2025, with SingPost and J&T Express requiring performance improvement plans within 30 days.",
    "fleet_health": "Watchlist",
    "summary_paragraph": (
        "Overall fleet OTIF averaged 84.2% in December 2024, 5.8 percentage points below the 90% "
        "network target. Premium integrators DHL and FedEx continue to outperform, while economy "
        "couriers SingPost (74.4%) and J&T Express (78.2%) are dragging the fleet average. "
        "Cross-border volumes into Indonesia and Philippines are the primary SLA breach drivers. "
        "The trend is flat vs November, suggesting structural issues rather than seasonal disruption."
    ),
    "priority_actions": [
        "Issue formal performance improvement notice to SingPost — OTIF below 80% for 3 consecutive months.",
        "Initiate RFQ process for Indonesia-Philippines corridor to explore alternative 3PL options.",
        "Schedule invoice audit for all vendors — fleet-wide variance of 8.4% above freight actuals requires validation before year-end close.",
    ],
    "positive_callout": "FedEx improved OTIF by 1.8pp vs November, maintaining its position as the most consistent performer on Australia and India routes.",
}


def get_demo_vendor_analysis(vendor: str, period: str, metrics: dict) -> dict:
    demo = DEMO_VENDOR_ANALYSIS.copy()
    demo["vendor"]    = vendor
    demo["period"]    = period
    demo["otif_pct"]  = metrics.get("otif_pct", 0)
    demo["sla_score"] = metrics.get("sla_score", 0)
    # Inject real numbers into the summary
    demo["performance_summary"] = (
        f"{vendor} achieved an OTIF of {metrics.get('otif_pct', 0)}% in {period}, "
        + ("above" if metrics.get('otif_pct', 0) >= 90 else "below")
        + " the 90% SLA target, with an average delay of "
        f"{metrics.get('avg_delay_days', 0)} days on late shipments. "
        f"The composite SLA score is {metrics.get('sla_score', 0)}/100."
    )
    risk = "Low" if metrics.get("otif_pct", 0) >= 90 else \
           "Medium" if metrics.get("otif_pct", 0) >= 82 else \
           "High" if metrics.get("otif_pct", 0) >= 75 else "Critical"
    demo["risk_level"] = risk
    demo["escalate_flag"] = metrics.get("otif_pct", 0) < 80
    demo["escalation_reason"] = (
        f"OTIF of {metrics.get('otif_pct', 0)}% is significantly below the 80% minimum threshold."
        if demo["escalate_flag"] else None
    )
    return demo
