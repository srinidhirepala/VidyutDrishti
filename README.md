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
- One **Facebook Prophet** model per feeder, trained on 15-minute readings aggregated to feeder level.
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

**Confidence Engine**
- **HIGH** = L0 + ≥2 of {L1, L2, L3} → immediate inspection.
- **MEDIUM** = ≥2 of {L1, L2, L3} → inspect within 7 days.
- **REVIEW** = 1 layer → monitor 7 more days.
- **NORMAL** = none.

**Behavioural classifier** labels flags as Hook Bypass, Meter Tampering, Meter Stop, Vacant/Legitimate, or Equipment Fault.

**Leakage quantifier** = `(peer_median_kwh − actual_kwh) × tariff_rate` → ranked inspection queue.

### Feedback Loop
Inspectors log outcomes (`Confirmed Theft / False Positive / Equipment Fault / Vacant`), which recalibrate L1 Z-thresholds and L2 σ multipliers weekly after the 90-day warm-up period.

---

## 4. System Architecture

```
  Synthetic AMI  ──►  Ingestion (APScheduler)  ──►  TimescaleDB (hypertables + continuous aggregates)
  Mock MDM       ──►                                       │
                                                           ├──►  Prophet Forecasting  ──►  Zone Risk
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
| **Forecasting** | Facebook Prophet |
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
- `GET /api/v1/meters/{id}/status` — Get anomaly detection status (L0-L3 + Confidence)
- `GET /api/v1/queue/daily` — Prioritized inspection queue
- `GET /api/v1/forecast/{feeder_id}` — 24-hour demand forecast
- `POST /api/v1/feedback` — Submit inspection feedback

**Run Prototype Evaluation:**
```bash
# Generate synthetic data, run all detection layers, output evaluation metrics
python run_prototype.py
```

---

## 8. Evaluation Targets

| Metric | Target |
|--------|--------|
| Forecast RMSE vs historical-hour avg | ≥ 15% better |
| Forecast RMSE vs persistence / seasonal naive | ≥ 15% better |
| P10–P90 empirical coverage | ≥ 95% |
| Precision @ HIGH confidence | ≥ 70% |
| Recall for hook bypass | ≥ 85% |
| Mean detection lag | < 10 days |
| False positive rate | < 15% |

Evaluation is run against an `injected_events` ground-truth table produced by the simulator.

---

## 9. Build Phases

| Phase | Scope | Features covered |
|-------|-------|------------------|
| **1 — Foundation** | Ingestion, schema, synthetic data | 01–04 |
| **2 — Forecasting** | Prophet + baselines + zone risk | 05–07 |
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
