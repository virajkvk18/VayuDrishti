# VayuDRISHTI

> **AI-Based Forecast Bust Detection for Medium-Range Weather Forecasts**
> Day 1–10 calibrated bust probability, region-wise confidence, error-prone
> area detection and exact Shapley attribution over the Indian domain.

Built against problem statement **PS-26079**.

---

## 1. What this is

VayuDRISHTI answers one question: **how much should I trust this forecast?**
For each of 20 Indian regions and each lead day from 1 to 10 it returns a
calibrated probability that the model's 24-hour accumulated precipitation will
be wrong by more than 25 mm, plus the physical reasons why.

A **bust** is defined as:

```
abs(forecast precipitation - verifying precipitation) > 25 mm
```

The reported **confidence** is `100 x (1 - bust_probability)`.

### Deliverable coverage

| Expected outcome | Where it is delivered |
|---|---|
| Region-wise confidence, Day 1–10 | `GET /forecast-grid?lead_day=`, `GET /lead-time-profile`, dashboard map + profile panel |
| Calibrated large-error probability | Isotonic-calibrated `HistGradientBoostingClassifier`, held-out metrics in `GET /model-info` |
| Error-prone area identification | `error_prone_areas` in `GET /forecast-grid`, `ErrorProneAreasPanel` |
| Explainable meteorological drivers | Exact interventional Shapley in `POST /explain-bust`, `XAIExplanationCard` |
| Comparison with historical errors | `historical_error_context` on every cell, `HistoricalComparisonCard` |
| Prototype dashboard and API | Next.js dashboard, FastAPI service |

---

## 2. Honest limitations

These matter more than the feature list, so they are stated first.

1. **The verification archive is synthetic.** There is no open, licence-free
   archive of Indian 24-hour accumulated precipitation forecasts paired with
   their verifying observations at the resolution this project needs. The
   training data is therefore *generated* by a physically-motivated error model
   (`app/core/archive.py`) that is tuned so its labelled events resemble the
   published regional bust characteristics in `app/core/regions.py`. The
   reported metrics are a property of that generator, **not** a measured
   operational score. Treat every number as a demonstration of the pipeline,
   never as evidence of real-world skill.
2. **The demo grid is generated, not ingested.** `app/data/generate_data.py`
   synthesises the live grid. Upstream source keys are stubbed in
   `.env.example` for future ingestion work.
3. **"Station" is a region.** The 20 grid cells are meteorological regions
   (subdivisions, basins, coastal arcs and two ocean boxes), not physical
   stations.
4. **Single-feature sensitivity moves the score little.** The model is a
   gradient-boosted tree ensemble and its response is piecewise constant, so
   nudging one parameter often does nothing visible. Several parameters must
   move together. The what-if panel says so rather than pretending otherwise.
5. **The generative briefing is optional and non-authoritative.** It is off by
   default and never feeds the deterministic `operational_advisory`.

---

## 3. The model

### 3.1 Architecture

| Component | Choice | Why |
|---|---|---|
| Bust probability | `HistGradientBoostingClassifier` + isotonic calibration | Handles the 13 interacting, mixed-scale features and yields a probability that can be calibrated to an honest frequency |
| Error magnitude | `HistGradientBoostingRegressor` on `sqrt` error | Skewed error distribution; predicts a typical absolute error to size the advisory |
| Attribution | Exact interventional Shapley, all `2^13` subsets | Provably consistent, local accuracy holds exactly. No sampling error |
| Baseline | Regional climatology from the training split only | Brier skill and error skill are measured against this, with no leakage |

### 3.2 Features (13)

Physical state: sea-level pressure, precipitable water, 850–200 hPa shear
divergence, 850–500 hPa lapse rate, CAPE, geopotential anomaly, 700 hPa
relative humidity, surface wind, NWP forecast precipitation, ensemble spread.
Context: lead day, regional historical bust frequency, regional historical mean
absolute error.

### 3.3 Held-out results

15% of a 60,000-case archive is held out and never used for fitting,
calibration or climatology.

| Metric | Value |
|---|---|
| ROC-AUC | 0.7108 (region-cluster 90% CI 0.6876–0.7327) |
| Brier score | 0.2079 |
| Brier skill score | +0.1290 (vs climatology) |
| Log loss | 0.6001 |
| Expected calibration error | 0.0080 |
| Error MAE | 19.09 mm vs 22.44 mm climatology (+14.9% skill) |
| Error MAE R² | 0.1006 |
| Day 1 AUC | 0.7166 |
| Day 10 AUC | 0.5914 |

Skill is positive at every individual lead day and degrades monotonically with
horizon, which is the behaviour the challenge asks for. Reproduce with:

```bash
cd backend
python -m app.core.train
```

Artifacts are committed under `backend/app/ml_models/`, so a fresh clone serves
predictions without retraining.

---

## 4. API

Base URL `http://127.0.0.1:8000/api/v1`. Interactive docs at `/docs`.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health plus whether the trained artifacts loaded |
| `GET` | `/forecast-grid?lead_day={1-10}` | Per-region probability, confidence, error-prone areas, historical context |
| `GET` | `/lead-time-profile` | Day 1–10 risk curve, domain-wide and per region |
| `POST` | `/explain-bust` | Exact Shapley breakdown, regime classification, advisory |
| `GET` | `/model-info` | Algorithm, archive provenance, held-out skill, reliability table |

`POST /explain-bust` accepts optional `custom_features` for what-if analysis.
Out-of-range or unknown keys are **not** silently applied; they come back in
`ignored_custom_features`. The response includes `shap_base_value` so a client
can verify that `shap_base_value + sum(shap_values) == bust_probability`
instead of trusting the server.

An unregistered `grid_id` is accepted and evaluated as an ad-hoc sounding
against the nearest reference region, and is labelled `Ad-Hoc Sounding`.

---

## 5. Quick start

Prerequisites: Python 3.10+, Node.js 18+.

### Backend

```bash
cd backend
python -m pip install -r requirements.txt
python run.py
```

API at `http://127.0.0.1:8000`, docs at `http://127.0.0.1:8000/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard at `http://localhost:3000`.

### Configuration

`backend/.env.example` is the tracked template. Secrets belong in
`backend/.env.local`, which is git-ignored and overrides `.env`. Rotate any key
that was ever committed.

---

## 6. Tests

```bash
cd backend
python -m pytest tests -v
```

36 tests covering the API contract, the model layer, Shapley exactness against
a naive reference implementation, calibration, lead-time decay, and archive
leakage. Several assertions exist specifically to catch the previous
revision's silent Pydantic field stripping, which removed
`error_prone_areas`, `historical_error_context`,
`weather_event_classification` and `reliability_flag` from the wire format
while the code that produced them kept working.

```bash
cd frontend
npm run lint
npm run build
```

---

## 7. Layout

```
VayuDRISHTI/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI app, explicit CORS origins
│   │   ├── api/endpoints.py           # Response models covering full engine output
│   │   ├── core/
│   │   │   ├── config.py              # Settings, thresholds, env layering
│   │   │   ├── regions.py             # 20-region registry and physical priors
│   │   │   ├── archive.py             # Synthetic verification archive + climatology
│   │   │   ├── train.py               # Training, calibration, held-out evaluation
│   │   │   ├── explain.py             # Exact interventional Shapley
│   │   │   └── ml_engine.py           # Scoring, history, profiles, advisories
│   │   ├── data/                      # Demo grid generator + generated grid
│   │   └── ml_models/                 # Committed artifacts + training_report.json
│   ├── tests/
│   │   ├── test_api.py                # API contract and field-presence guards
│   │   ├── test_ml_core.py            # Model, Shapley, calibration, leakage
│   │   └── test_integration_sanity.py # Readable end-to-end report
│   ├── requirements.txt
│   ├── .env.example
│   └── run.py
├── frontend/src/
│   ├── app/                           # Landing page + dashboard
│   ├── components/
│   │   ├── ErrorProneAreasPanel.tsx   # Error-prone area detection
│   │   ├── HistoricalComparisonCard.tsx
│   │   ├── LeadTimeProfilePanel.tsx   # Day 1-10 decay curve + region matrix
│   │   ├── ModelProvenanceBadge.tsx   # Algorithm, held-out skill, live/offline
│   │   ├── MapContainer.tsx           # Leaflet map, bust/confidence/error layers
│   │   ├── XAIExplanationCard.tsx
│   │   └── ...
│   ├── lib/api.ts                     # Typed client, no silent failures
│   └── types/index.ts
└── README.md
```

---

## 8. Model behaviour worth knowing

- **Risk rises with lead time.** Domain mean bust probability runs from roughly
  0.19 on Day 1 to roughly 0.57 on Day 10.
- **The historical baseline is a real feature, not decoration.** Regional
  `hist_bust_freq_pct` and `hist_mae_mm` are among the strongest predictors,
  which is why `HistoricalComparisonCard` reports a ratio to archive rather
  than an absolute number.
- **Confidence is exactly `1 - probability`.** A test asserts this, because
  presenting the two as independent measures would be misleading.
- **Grid attribution uses 8 background samples** and is memoised per cell
  (~7 ms warm); the inspector uses 24 for a more stable decomposition
  (~310 ms). The difference is a deliberate latency/accuracy trade-off.
