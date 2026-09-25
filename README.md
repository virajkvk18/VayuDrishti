# VayuDRISHTI

A prototype for **PS-26079** — using AI to catch medium-range weather forecasts
that are about to be badly wrong, before anyone finds out the hard way.

It answers one question for 20 regions across India and every lead day from 1 to
10: **how much should I trust this forecast?**

## How it works

A forecast is called a *bust* when the model's 24-hour accumulated precipitation
turns out to be off by more than 25 mm. For each region and lead day, VayuDRIShti
returns the probability of that happening. The confidence you see in the UI is
just `1 - probability`, expressed as a percentage.

So a region showing 42% confidence is telling you there's a 58% chance the
rainfall forecast is off by more than 25 mm. That's the whole idea.

```
abs(forecast precipitation - verifying precipitation) > 25 mm
```

## The important caveat

**The training data is synthetic.** Read this before you quote any number.

There's no open, licence-free archive of Indian 24-hour accumulated-precipitation
forecasts paired with their verifying observations at the resolution this needs.
So `app/core/archive.py` *generates* the archive, using a physically-motivated
error model tuned so its labelled events resemble the published regional bust
characteristics in `app/core/regions.py`.

The consequence: every metric below describes how well the pipeline works, not
how well it would predict real weather. The ML is genuine — real training, real
held-out split, real calibration. What's synthetic is the world it learned from.

If you only remember one thing from this repo, remember that. The numbers are
demonstration values.

## What the model is

| | |
|---|---|
| Bust probability | `HistGradientBoostingClassifier` + isotonic calibration |
| Error magnitude | `HistGradientBoostingRegressor` on `sqrt` error |
| Attribution | Exact interventional Shapley over all 2^13 subsets |
| Baseline for skill | Regional climatology, fit on the training split only |

Thirteen features: sea-level pressure, precipitable water, 850–200 hPa shear
divergence, 850–500 hPa lapse rate, CAPE, geopotential anomaly, 700 hPa relative
humidity, surface wind, NWP forecast precipitation, ensemble spread, plus lead
day and the region's own historical bust frequency and mean absolute error.

I went with a calibrated gradient-boosted tree rather than a neural net because
the input is 13 heterogeneous, interacting, mixed-scale physical parameters and
we have 60,000 cases — a regime where trees genuinely are the better tool and
the prediction is inspectable. A neural net would have added a dependency and
bought nothing.

### Held-out results

15% of 60,000 cases held out, never used for fitting, calibration, or
climatology.

| Metric | Value |
|---|---|
| ROC-AUC | 0.7108 (region-cluster 90% CI 0.6876–0.7327) |
| Brier score | 0.2079 |
| Brier skill score | +0.1290 vs climatology |
| Expected calibration error | 0.0080 |
| Error MAE | 19.09 mm vs 22.44 mm climatology (+14.9%) |
| Day 1 AUC | 0.7166 |
| Day 10 AUC | 0.5914 |

Brier skill stays positive at every individual lead day, and AUC decays from
Day 1 to Day 10. Both are the behaviour you'd want — a model that didn't degrade
with horizon would be a bug, since forecast error physically grows with lead
time.

Reproduce with `python -m app.core.train`. The artifacts are committed, so a
fresh clone serves predictions without training.

## Why exact Shapley

`app/core/explain.py` enumerates every one of the 8192 feature subsets rather
than sampling. It's slow enough that the grid uses 8 background samples (~7 ms
warm, memoised per cell) while the inspector uses 24 (~310 ms) for a steadier
decomposition. That split is a deliberate latency trade.

The payoff is that additivity is exact, not approximate. The API returns
`shap_base_value`, so a client can confirm for itself that
`shap_base_value + sum(shap_values) == bust_probability` instead of taking the
server's word for it. Residual on a live cell is 0.0000.

The Shapley algorithm itself is checked against a naive implementation in the
test suite (agreement to 7e-18).

## Running it

Backend needs Python 3.10+, frontend Node 18+.

```bash
cd backend
python -m pip install -r requirements.txt
python run.py            # http://127.0.0.1:8000, docs at /docs
```

```bash
cd frontend
npm install
npm run dev              # http://localhost:3000
```

Configuration lives in `backend/.env.example`. Secrets go in `backend/.env.local`,
which is git-ignored and overrides `.env`.

## API

Base URL `http://127.0.0.1:8000/api/v1`.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Health, plus whether the model artifacts loaded |
| `GET` | `/forecast-grid?lead_day={1-10}` | Per-region probability, confidence, error-prone areas, historical context |
| `GET` | `/lead-time-profile` | Day 1–10 risk curve, domain-wide and per region |
| `POST` | `/explain-bust` | Shapley breakdown, regime classification, advisory |
| `GET` | `/model-info` | Algorithm, archive provenance, held-out skill, reliability table |

Two behaviours worth knowing. `POST /explain-bust` accepts optional
`custom_features` for what-if analysis, and anything out of physical range comes
back in `ignored_custom_features` rather than being silently clamped — a
rejected value is never echoed back as though it were used. And an unregistered
`grid_id` is accepted as an ad-hoc sounding against the nearest reference region,
clearly labelled `Ad-Hoc Sounding`.

## Tests

```bash
cd backend
python -m pytest tests -v      # 36 tests
```

```bash
cd frontend
npm run lint
npm run build
```

A few of those backend tests exist because of a bug worth remembering. The
Pydantic response models didn't declare `error_prone_areas`,
`historical_error_context`, `weather_event_classification` or
`reliability_flag`, so FastAPI discarded them on the way out. The engine computed
every one correctly and shipped `{}`. Pydantic doesn't warn about undeclared
response fields, so nothing looked broken — the dashboard was just quietly
missing two of the problem statement's deliverables. There are now explicit
assertions on each of those fields.

## Layout

```
backend/
  app/
    main.py              FastAPI app, explicit CORS origins
    api/endpoints.py     response models covering the full engine output
    core/
      config.py          settings and thresholds
      regions.py         20-region registry, physical priors
      archive.py         synthetic verification archive + climatology
      train.py           training, calibration, held-out evaluation
      explain.py         exact interventional Shapley
      ml_engine.py       scoring, history, profiles, advisories
    data/                demo grid generator
    ml_models/           committed artifacts + training_report.json
  tests/                 API contract, model layer, integration report

frontend/src/
  app/                   landing page + dashboard
  components/
    ErrorProneAreasPanel.tsx
    HistoricalComparisonCard.tsx
    LeadTimeProfilePanel.tsx
    ModelProvenanceBadge.tsx
    MapContainer.tsx
    XAIExplanationCard.tsx
  lib/api.ts             typed client, no silent failures
  types/index.ts
```

## Things that will surprise you

**At long lead times, nearly every region trips the error-prone flag.** The
threshold is a fixed 0.35 probability, but the base rate itself climbs with
horizon, so by Day 10 about 19 of 20 regions are above it. The panel sorts
worst-first and says so explicitly, because a saturated count otherwise reads
like a broken detector. The ranking is the useful signal at that point, not the
count.

**Moving one parameter barely changes the score.** It's a tree ensemble, so the
response is piecewise constant — nudge CAPE alone and you may see nothing. Several
parameters have to move together. The what-if panel says this rather than letting
you conclude the model is broken.

**The generative briefing is off by default** and never touches the deterministic
`operational_advisory`. When enabled it returns prose. The advisory is arithmetic.
