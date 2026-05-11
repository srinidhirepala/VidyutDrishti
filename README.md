# VidyutDrishti
**AT&C Loss Detection and Inspection Intelligence System** — a read-only analytics layer that processes smart-meter interval data to surface anomalies, quantify revenue leakage in rupees, and prioritise field inspection queues by recovery value.

> Status: Prototype on synthetic data. No integration with real AMI, SCADA, MDM, or billing systems. No real consumer PII. No LLMs.

---

## Overview

Smart meters generate 15-minute interval data that, if systematically analysed, can expose significant commercial losses in power distribution. VidyutDrishti processes this data through a multi-layer detection pipeline to:

1. **Detect anomalies** — distinguishes theft patterns from legitimate consumption drops using four independent detection layers
2. **Quantify leakage in rupees** — peer-median expected consumption × applicable tariff slab
3. **Prioritise inspection queues** — highest-rupee leakage leads ranked at the top for field teams

The system is strictly read-only and produces deterministic, rule-based, auditable explanations for every flag it raises.

---

## Detection Pipeline

Four independent anomaly detection layers; confidence scales with the number of layers that fire simultaneously.

| Layer | Rule |
|-------|------|
| **L0 — DT Energy Balance** | `units_in − Σ consumer_units > 8%` sustained for 3 days |
| **L1 — Statistical Baseline** | 90-day rolling Z-score; `|Z| > 3` across ≥4 consecutive 15-min slots |
| **L2 — Peer Group** | Daily total `< median − 2.5σ` for 5 consecutive days |
| **L3 — Isolation Forest** | Pattern-shift features; `contamination = 0.03`; monthly retrain |

**Confidence Engine**
- **HIGH** (≥ 0.85) — L0 + ≥2 of {L1, L2, L3} → immediate inspection
- **MEDIUM** (0.65–0.85) — ≥2 of {L1, L2, L3} → inspect within 7 days
- **REVIEW** (0.50–0.65) — 1 layer → monitor 7 more days
- **NORMAL** (< 0.50) — no action

**Behavioural classifier** labels flags as: `sudden_drop`, `gradual_decline`, `spike`, `flatline`, `erratic`, or `normal_pattern`.

**Feedback loop** — inspectors log outcomes (Confirmed / False Positive / Equipment Fault / Vacant), which recalibrate L1 Z-thresholds and L2 σ multipliers weekly after the 90-day warm-up period.

---

## Forecasting

One seasonal baseline forecasting model per feeder, trained on 15-minute readings aggregated to feeder level.

- Regressors: public holidays, seasonal flags (summer Mar–Jun, monsoon Jun–Sep), lag-7 and lag-14 same-hour features
- 24-hour forecast at 15-minute resolution with 10th/90th percentile bands, refreshed hourly
- Zone risk classification (HIGH / MEDIUM / LOW) rendered as a locality heatmap

---

## Evaluation Results

| Metric | Target | Achieved |
|--------|--------|----------|
| Precision @ HIGH confidence | ≥ 70% | **78%** ✅ |
| Recall (hook bypass) | ≥ 85% | **85%** ✅ |
| F1 score | — | **0.81** ✅ |
| Mean detection lag | < 10 days | **6.2 days** ✅ |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11, FastAPI, Pydantic |
| Scheduler | APScheduler |
| Data | Pandas, NumPy |
| Database | PostgreSQL 15 + TimescaleDB 2.x |
| Migrations | Alembic |
| Forecasting | STL-style seasonal decomposition with lag regressors |
| Anomaly ML | scikit-learn (Isolation Forest) |
| Frontend | React + Vite + TypeScript, Recharts, Leaflet |
| Containerisation | Docker Compose |
| Testing | pytest, vitest |

No cloud dependencies. No LLMs. All flags use deterministic rule-based explanations with a full audit log.

---

## System Architecture

```
Synthetic AMI  ──►  Ingestion (APScheduler)  ──►  TimescaleDB (hypertables + continuous aggregates)
Mock MDM       ──►                                       │
                                                         ├──►  Seasonal Baseline Forecasting  ──►  Zone Risk
                                                         │
                                                         └──►  Detection Engine (L0/L1/L2/L3)
                                                                     │
                                                                     ▼
                                                         Confidence Engine → Behaviour → Leakage (Rs.)
                                                                     │
                                                                     ▼
                                                                 FastAPI  ──►  React + Leaflet + Recharts
                                                                     │
                                                                     └──►  Feedback → Recalibration
```

---

## Quickstart

```bash
git clone https://github.com/srinidhirepala/VidyutDrishti.git
cd VidyutDrishti
cp infra/.env.sample infra/.env
docker compose up --build
```

**Access Points:**
- Dashboard: http://localhost:5173
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

**Key API Endpoints:**
- `POST /api/v1/ingest/batch` — Ingest meter readings
- `GET /api/v1/meters/{id}/status` — 4-layer anomaly status + confidence score
- `GET /api/v1/queue/daily` — Prioritised inspection queue ranked by Rs. × confidence
- `GET /api/v1/forecast/{feeder_id}` — 24-hour seasonal baseline forecast
- `POST /api/v1/feedback` — Inspector feedback
- `GET /api/v1/zones/summary` — Per-zone risk aggregation for Leaflet heatmap
- `GET /api/v1/metrics/evaluation` — Live precision, recall, F1, detection lag

**Run Prototype Evaluation:**
```bash
python run_prototype.py
```

---

## Repository Structure

```
VidyutDrishti/
├── backend/
│   ├── app/
│   ├── tests/
│   └── pyproject.toml
├── simulator/
├── frontend/
├── db/
│   ├── migrations/
│   └── seed/
├── infra/
├── logs/
├── docker-compose.yml
└── README.md
```

---

## Live Demo

**Demo video:** https://drive.google.com/file/d/1LOgpMxeu2LzAK52B-go-8gtAn6rHe1Eu/view?usp=sharing

### 7 Working Modules

| Module | What it shows |
|--------|---------------|
| **Dashboard** | KPIs, 6 live charts, feeder forecast, loss by zone |
| **Inspection Queue** | Ranked by Rs. × confidence, 14 active leads |
| **Meter Lookup** | 4-layer drill-down, rule trace, confidence score |
| **Zone Risk Map** | Leaflet heatmap, 8 DT localities |
| **Feedback** | Inspector outcome capture, live queue and dashboard refresh |
| **Evaluation Metrics** | Live precision=78%, recall=85%, F1=0.81, detection lag=6.2d |
| **ROI Calculator** | Interactive sliders, scale projection, 5-yr NPV |

---

## Build Phases

| Phase | Scope | Features |
|-------|-------|----------|
| **1 — Foundation** | Ingestion, schema, synthetic data | 01–04 |
| **2 — Forecasting** | Seasonal baseline forecasting + zone risk | 05–07 |
| **3 — Detection** | L0–L3, confidence, behaviour, leakage, queue | 08–16 |
| **4 — UI & Ops** | API, dashboard, feedback, audit, eval, Docker | 17–22 |

---

## Development Protocol

Every feature follows the same protocol:

1. Implement the feature end-to-end in the appropriate package (`backend/`, `simulator/`, `frontend/`, `db/`, `infra/`)
2. Write prototype-grade tests under `logs/<NN-feature-name>/tests/`
3. Record test results in `logs/<NN-feature-name>/test_review.md`
4. Record deviations from plan in `logs/<NN-feature-name>/changes.md`
5. Record errors and resolutions in `logs/<NN-feature-name>/errors.md`
6. Commit with a detailed message covering the feature, logs, and supporting docs
7. Push to `origin/main`

---

## Out of Scope

- Real AMI / SCADA / MDM / billing integration
- Any write-back to live systems
- Real consumer PII
- LLM-based explanations
- Mobile app or workforce management tooling

---

## License

Synthetic data only. No real consumer information is committed to this repository.
