"""
Prompt templates for the AI Supply Chain Analyst.
All domain context and instruction engineering lives here — kept separate
so prompts can be tuned without touching business logic.
"""

SYSTEM_PROMPT = """You are a senior supply chain analyst specialising in APAC logistics operations.
You have deep expertise in 3PL and courier performance management, SLA governance,
cross-border shipping, inventory operations, and logistics cost optimisation.

Your job is to interpret vendor performance data and produce clear, concise, actionable reports
that a supply chain manager can act on immediately — no filler, no generic advice.

When you see numbers, reason about *why* they look the way they do given APAC logistics realities:
customs complexity in Indonesia/Philippines, last-mile challenges in Tier 2 cities, peak season
spikes (11.11, Chinese New Year), and the cost-quality trade-off between economy couriers and
premium integrators.

Always respond in valid JSON matching the schema provided in each request."""


def vendor_analysis_prompt(vendor: str, vendor_type: str, period: str, metrics: dict, context: dict) -> str:
    return f"""Analyse the following performance data for {vendor} ({vendor_type}) for {period}.

PERFORMANCE METRICS:
- OTIF %: {metrics['otif_pct']}% (target: ≥90%)
- Average Delay (when late): {metrics['avg_delay_days']} days
- Total Shipments: {metrics['total_shipments']:,}
- SLA Score: {metrics['sla_score']}/100
- Cost per Shipment: USD {metrics['cost_per_ship']}
- Invoice Variance: USD {metrics['invoice_variance_usd']:+,.0f} ({metrics['invoice_variance_pct']:+.1f}% vs expected)

TREND VS PRIOR MONTH:
- OTIF change: {context['otif_delta']:+.1f}pp
- Cost change: {context['cost_delta']:+.1f}%
- Volume change: {context['volume_delta']:+.1f}%

TOP AFFECTED REGIONS: {', '.join(context['top_miss_regions'])}
TOP AFFECTED CATEGORIES: {', '.join(context['top_miss_categories'])}

Respond with this exact JSON schema:
{{
  "performance_summary": "2–3 sentence executive summary of this vendor's performance. Be specific about numbers.",
  "root_cause_analysis": "2–3 sentences identifying the most likely drivers of the performance level. Reference APAC logistics realities where relevant.",
  "risk_level": "Low | Medium | High | Critical",
  "risk_rationale": "One sentence explaining the risk rating.",
  "recommended_actions": [
    "Action 1 — specific and time-bound",
    "Action 2 — specific and time-bound",
    "Action 3 — specific and time-bound"
  ],
  "escalate_flag": true or false,
  "escalation_reason": "One sentence if escalate_flag is true, else null"
}}"""


def executive_summary_prompt(period: str, vendor_analyses: list[dict]) -> str:
    vendor_block = "\n".join([
        f"- {v['vendor']} | OTIF: {v['otif_pct']}% | SLA Score: {v['sla_score']} | Risk: {v['risk_level']}"
        for v in vendor_analyses
    ])
    escalations = [v['vendor'] for v in vendor_analyses if v.get('escalate_flag')]

    return f"""You have just completed individual vendor analyses for {period}. Here is the fleet summary:

{vendor_block}

Vendors flagged for escalation: {', '.join(escalations) if escalations else 'None'}

Write an executive summary for the APAC logistics lead. Respond with this exact JSON schema:
{{
  "headline": "One sentence: the most important thing leadership needs to know this month.",
  "fleet_health": "Good | Watchlist | At Risk | Critical",
  "summary_paragraph": "3–4 sentences covering overall network health, the top 1–2 issues, and whether the trend is improving or deteriorating.",
  "priority_actions": [
    "Most urgent action across the whole vendor fleet",
    "Second priority",
    "Third priority"
  ],
  "positive_callout": "One sentence highlighting the best-performing vendor or a genuine improvement — keeps the report balanced."
}}"""


def anomaly_detection_prompt(vendor: str, current: dict, prior: dict) -> str:
    return f"""Compare {vendor}'s performance between two periods and identify anomalies.

CURRENT PERIOD: {current['month']}
- OTIF: {current['otif_pct']}% | Delay: {current['avg_delay_days']}d | Cost/ship: ${current['cost_per_ship']} | Shipments: {current['total_shipments']}

PRIOR PERIOD: {prior['month']}
- OTIF: {prior['otif_pct']}% | Delay: {prior['avg_delay_days']}d | Cost/ship: ${prior['cost_per_ship']} | Shipments: {prior['total_shipments']}

Respond with this exact JSON schema:
{{
  "anomaly_detected": true or false,
  "severity": "None | Minor | Significant | Severe",
  "description": "1–2 sentences describing what changed and whether it is likely signal or noise.",
  "likely_cause": "Most probable explanation given APAC logistics context. Null if no anomaly.",
  "watch_next_month": true or false
}}"""
