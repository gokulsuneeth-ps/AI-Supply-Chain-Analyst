"""
AI Supply Chain Analyst — Streamlit UI
Automates vendor performance reporting using LLM-generated narratives,
root cause analysis, and recommended actions.
"""

import os, json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv

load_dotenv()

from utils import (
    load_vendor_data, get_available_months, get_vendor_metrics,
    get_trend_context, fleet_summary, get_vendor_type,
)
from analyst import (
    analyse_vendor, analyse_all_vendors, detect_anomaly,
    get_demo_vendor_analysis, DEMO_EXEC_SUMMARY, _get_client,
)

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Supply Chain Analyst",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

RISK_COLOR = {
    "Low":      "#16A34A",
    "Medium":   "#D97706",
    "High":     "#DC2626",
    "Critical": "#7C3AED",
    "Unknown":  "#6B7280",
}

# ── Sidebar ────────────────────────────────────────────────────────────────────
st.sidebar.markdown("## 🤖 AI SC Analyst")

# API key input
st.sidebar.markdown("### Configuration")
api_key_input = st.sidebar.text_input(
    "Anthropic API Key",
    type="password",
    value=os.environ.get("ANTHROPIC_API_KEY", ""),
    help="Get a free key at https://console.anthropic.com",
    placeholder="sk-ant-...",
)
if api_key_input:
    os.environ["ANTHROPIC_API_KEY"] = api_key_input

demo_mode = st.sidebar.checkbox(
    "🎭 Demo Mode (no API key needed)",
    value=not bool(api_key_input),
    help="Uses pre-generated analysis so you can explore the UI without spending API credits.",
)

st.sidebar.markdown("---")

# Data source
st.sidebar.markdown("### Data Source")
use_upload = st.sidebar.checkbox("Upload my own CSV", value=False)
uploaded_file = None
if use_upload:
    uploaded_file = st.sidebar.file_uploader(
        "vendor_summary.csv",
        type=["csv"],
        help="Needs columns: courier_vendor, month, otif_pct, avg_delay_days, "
             "total_shipments, sla_score, cost_per_ship, total_freight_usd, "
             "invoiced_usd, invoice_variance_usd",
    )

# Load data
try:
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        df["month"] = df["month"].astype(str)
    else:
        df = load_vendor_data()
    data_ok = True
except FileNotFoundError as e:
    st.error(str(e))
    data_ok = False
    st.stop()

months  = get_available_months(df)
vendors = sorted(df["courier_vendor"].unique().tolist())

st.sidebar.markdown("---")
st.sidebar.caption(
    f"Dataset: {len(df)} vendor-month rows · {len(vendors)} vendors · {len(months)} months"
)

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("🤖 AI Supply Chain Analyst")
st.caption(
    "Automates vendor performance reporting — Python computes the metrics, "
    "Claude writes the analysis, root causes, and recommended actions."
)
if demo_mode:
    st.info("**Demo mode active** — analysis is pre-generated. Toggle off and add an API key to run live AI analysis.", icon="🎭")
st.markdown("---")

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "🔍  Single Vendor Deep Dive",
    "📋  Full Fleet Report",
    "📈  Anomaly Detection",
])


# ════════════════════════════════════════════════════════════════════════════════
# TAB 1 — SINGLE VENDOR DEEP DIVE
# ════════════════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("Single Vendor Analysis")
    st.caption("Select a vendor and reporting period — the AI generates root cause analysis and recommended actions.")

    col_a, col_b = st.columns([1, 1])
    with col_a:
        sel_vendor = st.selectbox("Vendor", vendors, key="t1_vendor")
    with col_b:
        sel_month  = st.selectbox("Reporting Period", months[::-1], key="t1_month")

    metrics = get_vendor_metrics(df, sel_vendor, sel_month)
    context = get_trend_context(df, sel_vendor, sel_month)

    if not metrics:
        st.warning("No data for this vendor / period combination.")
        st.stop()

    # ── Stats row ──
    st.markdown("#### Performance Metrics")
    m1, m2, m3, m4, m5 = st.columns(5)
    otif      = metrics["otif_pct"]
    sla_score = metrics["sla_score"]
    delay     = metrics["avg_delay_days"]
    shipments = metrics["total_shipments"]
    inv_var   = metrics["invoice_variance_pct"]

    m1.metric("OTIF %", f"{otif}%",
              delta=f"{otif-90:.1f}pp vs target",
              delta_color="normal" if otif >= 90 else "inverse")
    m2.metric("SLA Score", f"{sla_score}/100")
    m3.metric("Avg Delay (late)", f"{delay}d")
    m4.metric("Shipments", f"{shipments:,}",
              delta=f"{context['volume_delta']:+.1f}% MoM",
              delta_color="off")
    m5.metric("Invoice Variance", f"{inv_var:+.1f}%",
              delta=None,
              help="Positive = invoiced more than expected freight cost")

    st.markdown("---")

    # ── Run analysis ──
    run_col, _ = st.columns([1, 3])
    with run_col:
        run_btn = st.button("▶ Run AI Analysis", type="primary", use_container_width=True)

    if run_btn or st.session_state.get(f"analysis_{sel_vendor}_{sel_month}"):
        cache_key = f"analysis_{sel_vendor}_{sel_month}"

        if run_btn:
            with st.spinner(f"Analysing {sel_vendor}..."):
                if demo_mode:
                    result = get_demo_vendor_analysis(sel_vendor, sel_month, metrics)
                else:
                    try:
                        client = _get_client()
                        result = analyse_vendor(
                            client, sel_vendor, get_vendor_type(sel_vendor),
                            sel_month, metrics, context,
                        )
                    except ValueError as e:
                        st.error(str(e))
                        st.stop()
                    except Exception as e:
                        st.error(f"API error: {e}")
                        st.stop()
            st.session_state[cache_key] = result

        result = st.session_state.get(cache_key, {})
        if not result:
            st.stop()

        # ── Render analysis ──
        risk     = result.get("risk_level", "Unknown")
        escalate = result.get("escalate_flag", False)

        risk_badge = f'<span style="background:{RISK_COLOR.get(risk,"#6B7280")};color:white;padding:3px 10px;border-radius:12px;font-size:13px;font-weight:600;">{risk} Risk</span>'
        esc_badge  = '<span style="background:#DC2626;color:white;padding:3px 10px;border-radius:12px;font-size:13px;font-weight:600;">⚠ Escalate</span>' if escalate else ""

        st.markdown(f"### {sel_vendor} — {sel_month} &nbsp; {risk_badge} &nbsp; {esc_badge}", unsafe_allow_html=True)

        box_l, box_r = st.columns(2)

        with box_l:
            st.markdown("#### 📝 Performance Summary")
            st.info(result.get("performance_summary", "—"))

            st.markdown("#### 🔍 Root Cause Analysis")
            st.warning(result.get("root_cause_analysis", "—"))

        with box_r:
            st.markdown("#### ✅ Recommended Actions")
            for i, action in enumerate(result.get("recommended_actions", []), 1):
                st.markdown(f"**{i}.** {action}")

            st.markdown("#### ⚠️ Risk Assessment")
            st.markdown(
                f"**Level:** {risk}  \n"
                f"**Rationale:** {result.get('risk_rationale', '—')}"
            )
            if escalate:
                st.error(f"**Escalation Required:** {result.get('escalation_reason', '—')}")

        # ── OTIF sparkline for this vendor ──
        st.markdown("#### 📈 OTIF Trend — All Periods")
        vendor_trend = df[df["courier_vendor"] == sel_vendor].sort_values("month")
        fig_spark = go.Figure()
        fig_spark.add_trace(go.Scatter(
            x=vendor_trend["month"], y=vendor_trend["otif_pct"],
            mode="lines+markers", name="OTIF %",
            line=dict(color="#2563EB", width=2), marker=dict(size=6),
        ))
        fig_spark.add_hline(y=90, line_dash="dash", line_color="#DC2626",
                            annotation_text="Target 90%")
        # Highlight selected month
        sel_val = vendor_trend[vendor_trend["month"] == sel_month]["otif_pct"]
        if not sel_val.empty:
            fig_spark.add_trace(go.Scatter(
                x=[sel_month], y=[sel_val.values[0]],
                mode="markers", name="Current period",
                marker=dict(size=14, color="#D97706", symbol="star"),
            ))
        fig_spark.update_layout(height=260, showlegend=True,
                                 legend=dict(orientation="h"),
                                 yaxis=dict(range=[60, 100]))
        st.plotly_chart(fig_spark, use_container_width=True)

        # ── Export ──
        st.markdown("#### 💾 Export Report")
        report_text = f"""VENDOR PERFORMANCE REPORT
{'='*60}
Vendor:  {sel_vendor}
Period:  {sel_month}
Risk:    {risk}
{'ESCALATION REQUIRED' if escalate else ''}

METRICS
-------
OTIF %:            {otif}%
SLA Score:         {sla_score}/100
Avg Delay:         {delay} days
Shipments:         {shipments:,}
Invoice Variance:  {inv_var:+.1f}%

PERFORMANCE SUMMARY
-------------------
{result.get('performance_summary', '')}

ROOT CAUSE ANALYSIS
-------------------
{result.get('root_cause_analysis', '')}

RISK RATIONALE
--------------
{result.get('risk_rationale', '')}

RECOMMENDED ACTIONS
-------------------
{chr(10).join(f"{i}. {a}" for i, a in enumerate(result.get('recommended_actions', []), 1))}

{'ESCALATION REASON'+chr(10)+'-'*20+chr(10)+result.get('escalation_reason','') if escalate else ''}
"""
        st.download_button(
            "⬇ Download Report (.txt)",
            data=report_text,
            file_name=f"vendor_report_{sel_vendor.replace(' ','_')}_{sel_month}.txt",
            mime="text/plain",
        )


# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 — FULL FLEET REPORT
# ════════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("Full Fleet Performance Report")
    st.caption(
        "Runs AI analysis on every vendor for a selected month in sequence, "
        "then generates an executive summary. ~30–60 seconds with live API."
    )

    fleet_month = st.selectbox("Reporting Period", months[::-1], key="t2_month")
    fleet_df    = fleet_summary(df, fleet_month)

    # Static fleet table first
    st.markdown("#### Fleet Overview — " + fleet_month)

    def color_otif(val):
        if val >= 90: return "color: #16A34A; font-weight:600"
        if val >= 80: return "color: #D97706; font-weight:600"
        return "color: #DC2626; font-weight:600"

    st.dataframe(
        fleet_df.style.map(color_otif, subset=["otif_pct"])
                      .format({"otif_pct": "{:.1f}%", "sla_score": "{:.1f}",
                               "cost_per_ship": "${:.2f}", "avg_delay_days": "{:.1f}d",
                               "invoice_variance_usd": "${:,.0f}"}),
        use_container_width=True, hide_index=True,
    )

    # OTIF comparison bar
    fig_fleet = px.bar(
        fleet_df.sort_values("otif_pct"),
        x="otif_pct", y="courier_vendor",
        orientation="h",
        color="otif_pct",
        color_continuous_scale=["#DC2626", "#D97706", "#16A34A"],
        range_color=[70, 100],
        text="otif_pct",
        title=f"OTIF % — All Vendors ({fleet_month})",
    )
    fig_fleet.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig_fleet.add_vline(x=90, line_dash="dash", line_color="#DC2626",
                         annotation_text="Target 90%")
    fig_fleet.update_layout(coloraxis_showscale=False, height=340)
    st.plotly_chart(fig_fleet, use_container_width=True)

    st.markdown("---")
    run_fleet = st.button("▶ Run Full Fleet AI Analysis", type="primary")

    fleet_cache_key = f"fleet_{fleet_month}"

    if run_fleet:
        vendor_data_list = []
        for v in vendors:
            m = get_vendor_metrics(df, v, fleet_month)
            if m:
                vendor_data_list.append({
                    "vendor":      v,
                    "vendor_type": get_vendor_type(v),
                    "period":      fleet_month,
                    "metrics":     m,
                    "context":     get_trend_context(df, v, fleet_month),
                })

        if demo_mode:
            from analyst import DEMO_EXEC_SUMMARY, get_demo_vendor_analysis
            results  = [get_demo_vendor_analysis(vd["vendor"], fleet_month, vd["metrics"]) for vd in vendor_data_list]
            exec_sum = DEMO_EXEC_SUMMARY
        else:
            progress_bar  = st.progress(0)
            progress_text = st.empty()

            def update_progress(vendor_name, i, total):
                progress_bar.progress((i + 1) / (total + 1))
                progress_text.text(f"Analysing {vendor_name}... ({i+1}/{total})")

            try:
                results, exec_sum = analyse_all_vendors(vendor_data_list, update_progress)
                progress_bar.progress(1.0)
                progress_text.text("Done.")
            except ValueError as e:
                st.error(str(e))
                st.stop()

        st.session_state[fleet_cache_key] = {"results": results, "exec_sum": exec_sum}

    fleet_data = st.session_state.get(fleet_cache_key)

    if fleet_data:
        results  = fleet_data["results"]
        exec_sum = fleet_data["exec_sum"]

        # Executive summary card
        health       = exec_sum.get("fleet_health", "—")
        health_color = {"Good": "#16A34A", "Watchlist": "#D97706",
                        "At Risk": "#DC2626", "Critical": "#7C3AED"}.get(health, "#6B7280")

        st.markdown("---")
        st.markdown(
            f"### Fleet Health: "
            f'<span style="color:{health_color};font-weight:700;">{health}</span>',
            unsafe_allow_html=True,
        )
        st.markdown(f"**{exec_sum.get('headline', '')}**")
        st.info(exec_sum.get("summary_paragraph", ""))

        col_pos, col_act = st.columns([1, 1])
        with col_pos:
            st.markdown("#### 💚 Positive Callout")
            st.success(exec_sum.get("positive_callout", "—"))
        with col_act:
            st.markdown("#### 🎯 Priority Actions")
            for i, act in enumerate(exec_sum.get("priority_actions", []), 1):
                st.markdown(f"**{i}.** {act}")

        # Per-vendor result cards
        st.markdown("---")
        st.markdown("### Per-Vendor Analysis")
        for r in results:
            if "error" in r:
                st.error(f"**{r['vendor']}**: Analysis failed — {r['error']}")
                continue
            risk   = r.get("risk_level", "Unknown")
            esc    = r.get("escalate_flag", False)
            color  = RISK_COLOR.get(risk, "#6B7280")
            label  = f"{'⚠ ' if esc else ''}{r['vendor']} — {risk} Risk"
            with st.expander(label, expanded=(risk in ["High", "Critical"] or esc)):
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**OTIF:** {r.get('otif_pct','')}% &nbsp;|&nbsp; **SLA Score:** {r.get('sla_score','')}/100")
                    st.markdown("**Summary**")
                    st.write(r.get("performance_summary", "—"))
                    st.markdown("**Root Cause**")
                    st.write(r.get("root_cause_analysis", "—"))
                with c2:
                    st.markdown("**Recommended Actions**")
                    for i, a in enumerate(r.get("recommended_actions", []), 1):
                        st.markdown(f"{i}. {a}")
                    if esc:
                        st.error(r.get("escalation_reason", ""))

        # Full report download
        report_lines = [
            f"APAC FLEET PERFORMANCE REPORT — {fleet_month}",
            "=" * 60,
            f"Fleet Health: {health}",
            "",
            f"HEADLINE: {exec_sum.get('headline','')}",
            "",
            "EXECUTIVE SUMMARY",
            "-" * 40,
            exec_sum.get("summary_paragraph", ""),
            "",
            "PRIORITY ACTIONS",
            "-" * 40,
        ]
        for i, a in enumerate(exec_sum.get("priority_actions", []), 1):
            report_lines.append(f"{i}. {a}")
        report_lines += ["", "POSITIVE CALLOUT", "-" * 40, exec_sum.get("positive_callout", ""), "", "=" * 60, "VENDOR DETAILS", "=" * 60]
        for r in results:
            if "error" in r:
                continue
            report_lines += [
                "",
                f"VENDOR: {r['vendor']} | OTIF: {r.get('otif_pct','')}% | Risk: {r.get('risk_level','')}",
                "-" * 40,
                "Summary: " + r.get("performance_summary", ""),
                "Root Cause: " + r.get("root_cause_analysis", ""),
                "Actions: " + " | ".join(r.get("recommended_actions", [])),
            ]
            if r.get("escalate_flag"):
                report_lines.append(f"ESCALATION: {r.get('escalation_reason','')}")

        st.download_button(
            "⬇ Download Full Fleet Report (.txt)",
            data="\n".join(report_lines),
            file_name=f"fleet_report_{fleet_month}.txt",
            mime="text/plain",
        )


# ════════════════════════════════════════════════════════════════════════════════
# TAB 3 — ANOMALY DETECTION
# ════════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("Month-on-Month Anomaly Detection")
    st.caption(
        "Flags vendors whose metrics changed significantly vs the prior month. "
        "The AI explains whether the change is signal or noise."
    )

    anom_month = st.selectbox("Current Month", months[1:][::-1], key="t3_month")
    idx        = months.index(anom_month)
    prior_month = months[idx - 1]

    st.markdown(f"Comparing **{anom_month}** vs **{prior_month}**")

    # Compute MoM deltas for all vendors (no LLM needed for this)
    rows = []
    for v in vendors:
        curr  = get_vendor_metrics(df, v, anom_month)
        prior = get_vendor_metrics(df, v, prior_month)
        if not curr or not prior:
            continue
        rows.append({
            "vendor":           v,
            "otif_current":     curr["otif_pct"],
            "otif_prior":       prior["otif_pct"],
            "otif_delta":       round(curr["otif_pct"] - prior["otif_pct"], 1),
            "cost_current":     curr["cost_per_ship"],
            "cost_prior":       prior["cost_per_ship"],
            "cost_delta_pct":   round((curr["cost_per_ship"] - prior["cost_per_ship"]) / max(prior["cost_per_ship"], 1) * 100, 1),
            "volume_delta_pct": round((curr["total_shipments"] - prior["total_shipments"]) / max(prior["total_shipments"], 1) * 100, 1),
        })

    delta_df = pd.DataFrame(rows)

    # Flag significant changes (±3pp OTIF or ±8% cost)
    delta_df["otif_flag"] = delta_df["otif_delta"].abs() >= 3
    delta_df["cost_flag"] = delta_df["cost_delta_pct"].abs() >= 8
    delta_df["flagged"]   = delta_df["otif_flag"] | delta_df["cost_flag"]

    fig_delta = px.bar(
        delta_df.sort_values("otif_delta"),
        x="otif_delta", y="vendor",
        orientation="h",
        color="otif_delta",
        color_continuous_scale=["#DC2626", "#F0FFF4", "#16A34A"],
        color_continuous_midpoint=0,
        title=f"OTIF Change vs Prior Month ({prior_month} → {anom_month})",
        text="otif_delta",
    )
    fig_delta.update_traces(texttemplate="%{text:+.1f}pp", textposition="outside")
    fig_delta.add_vline(x=0, line_color="#6B7280", line_width=1)
    fig_delta.add_vline(x=3,  line_dash="dot", line_color="#16A34A", annotation_text="+3pp threshold")
    fig_delta.add_vline(x=-3, line_dash="dot", line_color="#DC2626", annotation_text="-3pp threshold")
    fig_delta.update_layout(coloraxis_showscale=False, height=340)
    st.plotly_chart(fig_delta, use_container_width=True)

    n_flagged = delta_df["flagged"].sum()
    if n_flagged:
        st.warning(f"**{n_flagged} vendor(s) flagged** for significant MoM change.")
    else:
        st.success("No significant changes detected vs prior month.")

    st.dataframe(
        delta_df[["vendor", "otif_current", "otif_prior", "otif_delta",
                   "cost_current", "cost_prior", "cost_delta_pct", "volume_delta_pct", "flagged"]]
        .style.map(
            lambda v: "color:#DC2626;font-weight:600" if isinstance(v, float) and v < -3
                 else ("color:#16A34A;font-weight:600" if isinstance(v, float) and v > 3 else ""),
            subset=["otif_delta"]
        )
        .format({"otif_current": "{:.1f}%", "otif_prior": "{:.1f}%",
                  "otif_delta": "{:+.1f}pp", "cost_delta_pct": "{:+.1f}%",
                  "volume_delta_pct": "{:+.1f}%", "cost_current": "${:.2f}", "cost_prior": "${:.2f}"}),
        use_container_width=True, hide_index=True,
    )

    # AI anomaly explanations for flagged vendors
    flagged_vendors = delta_df[delta_df["flagged"]]["vendor"].tolist()
    if flagged_vendors:
        st.markdown("---")
        run_anom = st.button("▶ Get AI Explanation for Flagged Vendors", type="primary")

        if run_anom:
            anom_results = {}
            for v in flagged_vendors:
                curr_m  = get_vendor_metrics(df, v, anom_month)
                prior_m = get_vendor_metrics(df, v, prior_month)
                if demo_mode:
                    anom_results[v] = {
                        "anomaly_detected": True,
                        "severity": "Significant",
                        "description": (
                            f"{v} shows a notable OTIF shift of "
                            f"{delta_df[delta_df.vendor==v]['otif_delta'].values[0]:+.1f}pp. "
                            "The change is likely signal rather than noise given its persistence across regions."
                        ),
                        "likely_cause": (
                            "Volume surge in Indonesia corridor combined with Eid holiday congestion "
                            "is the most probable driver. Recommend reviewing Indonesia-specific SLA compliance separately."
                        ),
                        "watch_next_month": True,
                    }
                else:
                    try:
                        client = _get_client()
                        anom_results[v] = detect_anomaly(client, v, curr_m, prior_m)
                    except Exception as e:
                        anom_results[v] = {"error": str(e)}
                time.sleep(0.3)

            st.session_state[f"anom_{anom_month}"] = anom_results

        anom_data = st.session_state.get(f"anom_{anom_month}", {})
        if anom_data:
            st.markdown("### AI Anomaly Explanations")
            for v, res in anom_data.items():
                if "error" in res:
                    st.error(f"**{v}**: {res['error']}")
                    continue
                sev   = res.get("severity", "Unknown")
                watch = res.get("watch_next_month", False)
                sev_color = {"None":"#16A34A","Minor":"#D97706","Significant":"#DC2626","Severe":"#7C3AED"}.get(sev,"#6B7280")
                with st.expander(f"{'👀 ' if watch else ''}{v} — {sev} change", expanded=True):
                    st.markdown(
                        f"**Anomaly detected:** {'Yes' if res.get('anomaly_detected') else 'No'} &nbsp;|&nbsp; "
                        f'<span style="color:{sev_color};font-weight:600;">Severity: {sev}</span> &nbsp;|&nbsp; '
                        f"**Watch next month:** {'Yes' if watch else 'No'}",
                        unsafe_allow_html=True,
                    )
                    st.write(res.get("description", "—"))
                    if res.get("likely_cause"):
                        st.info(f"**Likely cause:** {res['likely_cause']}")

import time  # needed for anomaly tab sleep
