# AI Supply Chain Analyst

An AI-powered tool that automates vendor performance reporting for APAC logistics operations.
Python computes the metrics; Claude writes the root cause analysis, risk assessment, and recommended actions.

> **Portfolio project** — demonstrates applied AI / LLM engineering for supply chain process automation.

---

## What Problem This Solves

A supply chain analyst reviewing 8+ vendors across 12 months would typically spend **30–60 minutes per vendor** writing performance commentary, identifying root causes, and drafting recommendations — manually cross-referencing data, then writing a report.

This tool reduces that to **under 60 seconds per vendor** by:
1. Computing all KPIs in Python (fast, deterministic, no hallucination risk)
2. Sending a structured metric summary to Claude (not raw data — keeps prompts lean and outputs reliable)
3. Returning a structured JSON response that populates the report template

The output matches what a senior analyst would write, using real APAC logistics domain context (customs complexity, last-mile challenges, peak season patterns).

---

## Three Modules

### 🔍 Single Vendor Deep Dive
Select any vendor and reporting period → get AI-generated:
- Executive performance summary (with real numbers)
- Root cause analysis (why the metrics look the way they do)
- 3 specific, time-bound recommended actions
- Risk level (Low / Medium / High / Critical) with rationale
- Escalation flag with reason

### 📋 Full Fleet Report
Runs analysis on all vendors sequentially for a selected month, then generates:
- Executive summary with fleet health rating
- Per-vendor analysis cards (auto-expanded for high-risk vendors)
- Downloadable full fleet report (.txt)

### 📈 Anomaly Detection
Flags vendors with significant MoM changes (±3pp OTIF or ±8% cost), then:
- Visualises OTIF delta for all vendors
- Gets AI explanation for flagged vendors: is it signal or noise? What's the likely cause?

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| UI framework | Streamlit |
| Data computation | Pandas, NumPy |
| Visualisations | Plotly |
| LLM backend | Anthropic API (claude-haiku-4-5) |
| Prompt engineering | Custom structured prompts with APAC SC domain context |
| Output | Structured JSON → rendered UI + downloadable .txt report |

**Why claude-haiku-4-5?** Fast (~2s per call) and inexpensive (~$0.002 per vendor analysis). The full fleet report (8 vendors + exec summary) costs under $0.02.

---

## Running Locally

**Prerequisites:** Python 3.9+, an Anthropic API key (free at [console.anthropic.com](https://console.anthropic.com))

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/sc-ai-analyst.git
cd sc-ai-analyst

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up your API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# 4. Add data (use Project 1's output or your own CSV)
mkdir data
cp ../apac-scm-dashboard/data/vendor_summary.csv data/

# 5. Launch
streamlit run app.py
```

> **No API key yet?** Enable **Demo Mode** in the sidebar — the full UI works with pre-generated responses so you can explore and demo without spending credits.

---

## Data Format

The tool works with any `vendor_summary.csv` with these columns:

| Column | Type | Description |
|--------|------|-------------|
| `courier_vendor` | string | Vendor name |
| `month` | string | Period (e.g. `2024-01`) |
| `otif_pct` | float | On-Time In-Full % |
| `avg_delay_days` | float | Average delay on late shipments |
| `total_shipments` | int | Shipment volume |
| `sla_score` | float | Composite SLA score 0–100 |
| `cost_per_ship` | float | Average freight cost per shipment (USD) |
| `total_freight_usd` | float | Total expected freight cost |
| `invoiced_usd` | float | Total invoiced amount |
| `invoice_variance_usd` | float | Invoice − freight (positive = overbilled) |

Out of the box it reads `data/vendor_summary.csv` or `../apac-scm-dashboard/data/vendor_summary.csv`, so it works seamlessly alongside Project 1.

---

## Design Decisions

**Why not send raw CSV to the LLM?**
Raw data is token-expensive and the LLM might miscalculate. Python computes the numbers; the LLM only sees a compact metric summary with pre-computed deltas. This keeps costs low, outputs accurate, and prompts auditable.

**Why structured JSON output?**
Free-form text is hard to render consistently. Every LLM response is parsed as JSON — if it can't be parsed, the app surfaces a clean error rather than broken output. This is production-grade prompt engineering.

**Why batched with rate-limit delay?**
One call per vendor with a 0.5s delay keeps well within Anthropic's rate limits even on a free tier key, and means the progress bar updates in real time rather than the UI freezing.

**Why claude-haiku and not GPT?**
Claude's instruction-following on structured JSON schemas is very reliable. Haiku is fast enough for an interactive UI and cheap enough for regular use. The model is configurable in `analyst.py`.

---

## Key Supply Chain Concepts Demonstrated

| Concept | Where |
|---------|-------|
| OTIF (On-Time In-Full) | All modules — primary KPI |
| SLA governance & scorecards | Fleet Report, Single Vendor |
| MoM trend analysis | Anomaly Detection |
| Invoice variance audit | Single Vendor metrics |
| Root cause analysis | AI output — all modules |
| Vendor escalation process | Risk flag + escalation reason |
| APAC logistics domain knowledge | Embedded in system prompt |
| LLM prompt engineering | `prompts.py` |
| Structured LLM output | `analyst.py` — JSON schema enforcement |
| Process automation | Reduces 60-min manual task to <60 seconds |

---

## Project Structure

```
sc-ai-analyst/
├── app.py           — Streamlit UI (3 tabs)
├── analyst.py       — LLM orchestration, batching, demo mode
├── prompts.py       — All prompt templates (system + task prompts)
├── utils.py         — Data loading and metric computation
├── requirements.txt
├── .env.example     — API key setup template
├── README.md
└── data/
    └── vendor_summary.csv   (symlink or copy from Project 1)
```

---

## Author

Suneeth Gokul  
MSc Supply Chain Engineering, Nanyang Technological University  
[LinkedIn](https://linkedin.com/in/YOUR_PROFILE) · [GitHub](https://github.com/YOUR_USERNAME)
