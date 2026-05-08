# VidyutDrishti

**AT&C Loss Recovery Intelligence System for BESCOM** — a read-only intelligence layer that turns smart-meter data into rupee-quantified, actionable leads for field inspection teams.

> Status: **Prototype** on synthetic data. Zero integration with real AMI, SCADA, MDM, or billing systems. No real consumer PII. No LLMs.

---

## 1. Core Proposition

BESCOM's smart meters generate 15-minute interval data that, if systematically analysed, exposes crores in annual commercial losses. VidyutDrishti:

1. **Finds the leaks** — multi-layer anomaly detection distinguishes theft from legitimate consumption drops.
2. **Quantifies them in rupees** — peer-median expected consumption × applicable tariff slab.
3. **Ranks field work by recovery value** — highest-rupee leakage leads appear at the top of the inspection queue.

The system is strictly **read-only** above existing BESCOM systems and produces deterministic, auditable, rule-based explanations for every flag it raises.

---

## 2. Problem Framing

BESCOM distributes power to ~8.5 million consumers. At 17% AT&C loss and ~Rs. 6.50/unit, annual revenue loss runs into thousands of crores. Three operational failures drive this:

- **No top-down loss attribution** below section level.
- **No peer-aware anomaly detection** — a meter using 40% less in June could be AC removal or a bypass hook.
- **No inspection ROI prioritisation** — a Rs. 500/month case and a Rs. 8,000/month case share queue priority today.

VidyutDrishti addresses all three.

---

## 3. What the Prototype Delivers

### Part A — Localised Demand Forecasting & Zone Risk Detection
- One **seasonal baseline forecasting model** per feeder, trained on 15-minute readings aggregated to feeder level.
- Regressors: Indian holidays, Karnataka regional holidays, summer (Mar–Jun) and monsoon (Jun–Sep) flags, lag-7 and lag-14 same-hour features.
- 24-hour forecast at 15-minute resolution with 10th/90th percentile bands, refreshed hourly.
- Zone risk classification (**HIGH / MEDIUM / LOW**) rendered as a Bengaluru locality heatmap.

### Part B — Anomaly & Theft Detection
Four independent detection layers; confidence scales with the number of layers that fire simultaneously.

| Layer | Rule |
|-------|------|
| **L0 — DT Energy Balance** | `units_in − Σ consumer_units > 8%` sustained for 3 days |
| **L1 — Statistical Baseline** | 90-day rolling Z-score; `|Z| > 3` across ≥4 consecutive 15-min slots |
| **L2 — Peer Group** | Daily total `< median − 2.5σ` for 5 consecutive days |
| **L3 — Isolation Forest** | Pattern-shift features; `contamination = 0.03`; monthly retrain |

**Confidence Engine** (weighted aggregation, thresholds match live `/api/v1/metrics/evaluation`)
- **HIGH** (≥ 0.85) = L0 + ≥2 of {L1, L2, L3} → immediate inspection.
- **MEDIUM** (0.65–0.85) = ≥2 of {L1, L2, L3} → inspect within 7 days.
- **REVIEW** (0.50–0.65) = 1 layer → monitor 7 more days.
- **NORMAL** (< 0.50) = no action.

**Behavioural classifier** labels flags as: `sudden_drop`, `gradual_decline`, `spike`, `flatline`, `erratic`, or `normal_pattern`.

**Leakage quantifier** = `(peer_median_kwh − actual_kwh) × tariff_rate` → ranked inspection queue.

### Feedback Loop
Inspectors log outcomes (`Confirmed Theft / False Positive / Equipment Fault / Vacant`), which recalibrate L1 Z-thresholds and L2 σ multipliers weekly after the 90-day warm-up period.

---

## 4. System Architecture

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

Full architecture details, data model, and scheduling plan are in [`features.md`](./features.md).

---

## 5. Tech Stack

| Layer | Technology |
|-------|------------|
| **Language (backend)** | Python 3.11 |
| **Scheduler** | APScheduler |
| **Data frame** | Pandas, NumPy |
| **Database** | PostgreSQL 15 + TimescaleDB 2.x |
| **Migrations** | Alembic |
| **Forecasting** | Seasonal Baseline Forecasting (STL-style decomposition, Indian holidays, lag regressors) |
| **Anomaly ML** | scikit-learn (Isolation Forest) |
| **Holidays** | `holidays` package (`IN`, subdivision `KA`) |
| **API** | FastAPI + Pydantic |
| **Frontend** | React + Vite + TypeScript |
| **Charts** | Recharts |
| **Maps** | Leaflet |
| **Containerisation** | Docker Compose |
| **Testing** | pytest, vitest |
| **Lint/format** | ruff, black, mypy, eslint, prettier |

No cloud dependencies. No LLMs. All flags use deterministic rule-based explanations with a full audit log.

---

## 6. Repository Layout

```
VidyutDrishti/
├── README.md                   # this file
├── features.md                 # ordered feature list + implementation details
├── .gitignore
├── docker-compose.yml          # (added in Feature 01)
├── backend/                    # Python services (ingestion, forecasting, detection, API)
│   ├── app/
│   ├── tests/
│   └── pyproject.toml
├── simulator/                  # Synthetic data generator
├── frontend/                   # React + Vite dashboard
├── db/
│   ├── migrations/             # Alembic migrations
│   └── seed/
├── infra/                      # Docker files, compose overrides, env samples
└── logs/                       # Per-feature implementation logs
    ├── 01-project-scaffolding/
    │   ├── tests/              # test file(s) or folder
    │   ├── test_review.md      # results + observations
    │   ├── changes.md          # modifications + deviations from plan
    │   └── errors.md           # errors encountered + resolutions
    ├── 02-synthetic-data-simulator/
    │   └── …
    └── …
```

---

## 7. Quickstart

The prototype is fully wired and ready to run:

```bash
git clone https://github.com/srinidhirepala/VidyutDrishti.git
cd VidyutDrishti
# Copy and edit env file (set passwords)
cp infra/.env.sample infra/.env
# Start all services
docker compose up --build
```

**Access Points:**
- Dashboard:      http://localhost:5173
- API docs:       http://localhost:8000/docs
- Health check:   http://localhost:8000/health
- TimescaleDB:    localhost:5432 (credentials in `infra/.env`)

**API Endpoints (all functional with real algorithms):**
- `POST /api/v1/ingest/batch` — Ingest meter readings
- `GET /api/v1/meters/{id}/status` — 4-layer anomaly status + confidence score
- `GET /api/v1/queue/daily` — Prioritized inspection queue (ranked by Rs. × confidence)
- `GET /api/v1/forecast/{feeder_id}` — 24-hour seasonal baseline forecast
- `POST /api/v1/feedback` — Inspector feedback (triggers queue + dashboard refresh)
- `GET /api/v1/zones/summary` — Per-zone risk aggregation for Leaflet heatmap
- `GET /api/v1/metrics/evaluation` — Live precision, recall, F1, detection lag
- `GET /api/v1/metrics/roi` — Interactive BESCOM-scale ROI projection

**Run Prototype Evaluation:**
```bash
# Generate synthetic data, run all detection layers, output evaluation metrics
python run_prototype.py
```

---

## 8. Live Demo

**Demo video:** https://drive.google.com/file/d/1LOgpMxeu2LzAK52B-go-8gtAn6rHe1Eu/view?usp=sharing

### 7 Working Modules

| Module | What it shows |
|--------|---------------|
| **Dashboard** | KPIs · 6 live charts · feeder forecast · loss by zone |
| **Inspection Queue** | Ranked by Rs. × confidence · 14 active leads |
| **Meter Lookup** | 4-layer drill-down · rule trace · confidence score |
| **Zone Risk Map** | Bengaluru Leaflet heatmap · 8 DT localities |
| **Feedback** | Inspector outcome capture · live queue + dashboard refresh |
| **Evaluation Metrics** | Live precision=78% · recall=85% · F1=0.81 · detection lag=6.2d |
| **ROI Calculator** | Interactive sliders · BESCOM-scale projection · 5-yr NPV |

---

## 9. Evaluation Results (live at `/api/v1/metrics/evaluation`)

| Metric | Target | Achieved |
|--------|--------|----------|
| Precision @ HIGH confidence | ≥ 70% | **78%** ✅ |
| Recall (hook bypass) | ≥ 85% | **85%** ✅ |
| F1 score | — | **0.81** ✅ |
| Mean detection lag | < 10 days | **6.2 days** ✅ |

## 9b. Financial Impact (live at `/api/v1/metrics/roi`)

| Metric | Value |
|--------|-------|
| BESCOM consumers | 8.5 million |
| Theft prevalence (conservative) | 1.5% |
| Annual recovery (85% detection rate) | **Rs. 455 Cr** |
| Annual platform cost | Rs. 15 Cr |
| Payback period | **< 1 month** |
| 5-year NPV (10% discount) | **Rs. 1,669 Cr** |
| All-India TAM | Rs. 25,000+ Cr |

---

## 9. Build Phases

| Phase | Scope | Features covered |
|-------|-------|------------------|
| **1 — Foundation** | Ingestion, schema, synthetic data | 01–04 |
| **2 — Forecasting** | Seasonal baseline forecasting + zone risk | 05–07 |
| **3 — Detection** | L0–L3, confidence, behaviour, leakage, queue | 08–16 |
| **4 — UI & Ops** | API, dashboard, feedback, audit, eval, Docker | 17–22 |

Exact sequence and per-feature details: [`features.md`](./features.md).

---

## 10. Development Protocol

Every feature is delivered using the same protocol:

1. Implement the feature end-to-end in the appropriate package (`backend/`, `simulator/`, `frontend/`, `db/`, `infra/`).
2. Write prototype-grade tests under `logs/<NN-feature-name>/tests/` — enough to validate no functional gaps, constraint handling, and documented behaviour. Production-grade coverage is explicitly **out of scope**.
3. Run the tests and record results in `logs/<NN-feature-name>/test_review.md`.
4. Record any deviations from the plan in `logs/<NN-feature-name>/changes.md`.
5. Record every error encountered and its resolution in `logs/<NN-feature-name>/errors.md`.
6. Commit with a detailed message covering the feature, its logs, and any supporting docs.
7. Push to `origin/main`.

---

## 11. Out of Scope (prototype)

- Real AMI / SCADA / MDM / billing integration
- Any write-back to BESCOM systems
- Real consumer PII
- LLM-based explanations
- Mobile app, SMS/IVR dispatch, workforce management
- Multi-tenant auth (a mock inspector identity is sufficient)

---

## 12. License & Data

Synthetic data only. No real consumer information is committed to this repository. Tariff slabs used in the prototype are illustrative and live in a YAML file under `backend/app/config/`.
