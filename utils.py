"""
Data loading and stats computation.
Python/Pandas does all the number-crunching here — the LLM only sees
pre-computed summaries, keeping token usage low and outputs reliable.
"""

import pandas as pd
import numpy as np
from pathlib import Path


def load_vendor_data(path: str = None) -> pd.DataFrame:
    """Load vendor summary CSV. Falls back to Project 1 data if no path given."""
    if path is None:
        candidates = [
            Path("data/vendor_summary.csv"),
            Path("../apac-scm-dashboard/data/vendor_summary.csv"),
        ]
        for c in candidates:
            if c.exists():
                path = str(c)
                break
    if path is None:
        raise FileNotFoundError(
            "vendor_summary.csv not found. Either run Project 1's generate_data.py "
            "or upload your own CSV (columns: courier_vendor, month, otif_pct, "
            "avg_delay_days, total_shipments, sla_score, cost_per_ship, "
            "total_freight_usd, invoiced_usd, invoice_variance_usd)."
        )
    df = pd.read_csv(path)
    df["month"] = df["month"].astype(str)
    return df


def get_available_months(df: pd.DataFrame) -> list[str]:
    return sorted(df["month"].unique().tolist())


def get_vendor_metrics(df: pd.DataFrame, vendor: str, month: str) -> dict:
    """Return flat metrics dict for one vendor in one month."""
    row = df[(df["courier_vendor"] == vendor) & (df["month"] == month)]
    if row.empty:
        return {}
    r = row.iloc[0]
    freight    = r["total_freight_usd"]
    invoiced   = r["invoiced_usd"]
    variance   = r["invoice_variance_usd"]
    variance_pct = (variance / freight * 100) if freight else 0.0

    return {
        "vendor":               vendor,
        "month":                month,
        "otif_pct":             round(float(r["otif_pct"]), 1),
        "avg_delay_days":       round(float(r["avg_delay_days"]), 1),
        "total_shipments":      int(r["total_shipments"]),
        "sla_score":            round(float(r["sla_score"]), 1),
        "cost_per_ship":        round(float(r["cost_per_ship"]), 2),
        "total_freight_usd":    round(float(freight), 2),
        "invoiced_usd":         round(float(invoiced), 2),
        "invoice_variance_usd": round(float(variance), 2),
        "invoice_variance_pct": round(variance_pct, 1),
    }


def get_trend_context(df: pd.DataFrame, vendor: str, month: str) -> dict:
    """Compute MoM deltas and region/category impact (inferred from vendor type)."""
    months = sorted(df["month"].unique().tolist())
    idx    = months.index(month) if month in months else -1

    defaults = {
        "otif_delta":          0.0,
        "cost_delta":          0.0,
        "volume_delta":        0.0,
        "top_miss_regions":    ["Singapore", "Indonesia", "Malaysia"],
        "top_miss_categories": ["IT Equipment", "Consumer Electronics"],
    }

    if idx <= 0:
        return defaults

    prior_month = months[idx - 1]
    curr_row  = df[(df["courier_vendor"] == vendor) & (df["month"] == month)]
    prior_row = df[(df["courier_vendor"] == vendor) & (df["month"] == prior_month)]

    if curr_row.empty or prior_row.empty:
        return defaults

    c, p = curr_row.iloc[0], prior_row.iloc[0]

    otif_delta   = float(c["otif_pct"])   - float(p["otif_pct"])
    cost_delta   = (float(c["cost_per_ship"]) - float(p["cost_per_ship"])) / max(float(p["cost_per_ship"]), 1) * 100
    volume_delta = (float(c["total_shipments"]) - float(p["total_shipments"])) / max(float(p["total_shipments"]), 1) * 100

    # Infer likely miss regions from OTIF level (heuristic — real data would have order-level breakdown)
    if float(c["otif_pct"]) < 80:
        regions = ["Indonesia", "Philippines", "Vietnam"]
    elif float(c["otif_pct"]) < 88:
        regions = ["Thailand", "Malaysia", "Australia"]
    else:
        regions = ["Singapore", "Malaysia"]

    return {
        "otif_delta":          round(otif_delta, 1),
        "cost_delta":          round(cost_delta, 1),
        "volume_delta":        round(volume_delta, 1),
        "top_miss_regions":    regions,
        "top_miss_categories": ["IT Equipment", "Consumer Electronics"],
    }


def fleet_summary(df: pd.DataFrame, month: str) -> pd.DataFrame:
    """Return all vendors for a given month, sorted by SLA score."""
    return (
        df[df["month"] == month]
        .sort_values("sla_score", ascending=False)
        [["courier_vendor", "otif_pct", "avg_delay_days",
          "total_shipments", "sla_score", "cost_per_ship",
          "invoice_variance_usd"]]
        .reset_index(drop=True)
    )


def get_vendor_type(vendor: str) -> str:
    courier = {"DHL Express", "FedEx", "Ninja Van", "J&T Express", "SingPost"}
    return "courier" if vendor in courier else "3PL"
