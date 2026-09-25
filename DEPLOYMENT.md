# Deployment Guide

Two deployables: the **Next.js frontend** (Vercel) and the **FastAPI backend**
(any container host). They are linked by one environment variable and one CORS
setting. Get those two right and everything works; get them wrong and the site
loads but silently shows synthetic fallback data.

---

## The two settings that matter

| Setting | Where | Value |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | Vercel project env (build time) | `https://<your-backend>/api/v1` |
| `CORS_ORIGIN_REGEX` | Backend env (runtime) | `https://.*\.vercel\.app` |

`NEXT_PUBLIC_*` variables are **inlined into the JavaScript bundle at build
time**. Changing it in the Vercel dashboard requires a redeploy, not just a
restart.

`CORS_ORIGIN_REGEX` exists because every Vercel preview deployment gets a unique
random subdomain. Enumerating them in `CORS_ORIGINS` is impossible, so the regex
covers production and preview alike. It is anchored, so it will not match an
arbitrary host.

---

## 1. Frontend on Vercel

```bash
npm install -g vercel
cd frontend
vercel login

# Set the API URL before the first production build.
vercel env add NEXT_PUBLIC_API_URL production
# paste: https://<your-backend-host>/api/v1

vercel --prod          # production
vercel                 # preview
```

Or connect the GitHub repo in the Vercel dashboard and set the env var under
**Settings → Environment Variables** for both Production and Preview.

Vercel auto-detects Next.js. Do not override the build command; the defaults
(`npm run build`) are correct. No `vercel.json` is needed.

> **Map tiles:** the map uses public CartoDB dark tiles, so it works with no
> token. If you add Mapbox, put `NEXT_PUBLIC_MAPBOX_TOKEN` in the Vercel env.

---

## 2. Backend options

The backend is **not** well suited to Vercel serverless functions: it loads
scikit-learn and two model artifacts on import, and `/explain-bust` enumerates
2¹³ subsets (~300 ms). Serverless cold starts and execution limits would make it
slow and fragile. Use a long-running container host.

As of 2026 the realistic options:

| Platform | Cost | Cold start | Verdict |
|---|---|---|---|
| **Railway** | $5/mo Hobby (one-time $5 trial credit for new accounts) | None, stays warm | **Best fit.** Best DX, CLI-driven, connects to GitHub |
| Render | ~$7/mo Starter | Free tier sleeps after 15 min, 30–60 s wake | Only the **paid** tier is usable; free tier kills a public demo link |
| Fly.io | Pay-per-second (~$2–8/mo) | 300 ms–2 s with autostop | Cheapest, but needs a Dockerfile and more config |
| Google Cloud Run | Pay-per-use, scales to zero | ~1 s | Good if you already use GCP |

**Recommendation: Railway.** For a public demo link, cold start is the only row
that matters, and Render's free tier is disqualifying.

### Option A — Railway (recommended)

```bash
npm install -g @railway/cli
railway login
cd backend
railway init
railway up
railway domain          # gives you https://xxx.up.railway.app
railway variables set CORS_ORIGIN_REGEX 'https://.*\.vercel\.app'
```

Set the Dockerfile path to `backend/Dockerfile` with build context `backend/` in
the Railway dashboard if auto-detection does not find it.

### Option B — Render

Dashboard only. New → Web Service → connect the repo:

- Root directory: `backend`
- Dockerfile: `backend/Dockerfile`
- Health check path: `/api/v1/health`

Then add `CORS_ORIGIN_REGEX` under Environment.

### Option C — Docker anywhere

```bash
cd backend
docker build -t vayudrishti-api .
docker run -p 8000:8000 -e CORS_ORIGIN_REGEX='https://.*\.vercel\.app' vayudrishti-api
```

---

## 3. Wire them together

**Order matters.** Deploy the backend first so you know its URL.

1. Deploy the backend, confirm `https://<backend>/api/v1/health` returns
   `"status": "OPERATIONAL"` in a browser.
2. Confirm `https://<backend>/api/v1/forecast-grid?lead_day=1` returns JSON in a
   browser. If it does, the backend is publicly reachable.
3. Set `NEXT_PUBLIC_API_URL=https://<backend>/api/v1` in Vercel.
4. Deploy the frontend.
5. Open the Vercel URL, open DevTools → Network, and confirm the API calls
   return 200 rather than being blocked.

### Verify

```bash
curl -i https://<backend>/api/v1/health \
  -H "Origin: https://<your-app>.vercel.app" | grep -i access-control
```

You want `access-control-allow-origin` to echo your Vercel origin. If the header
is missing, `CORS_ORIGIN_REGEX` is not set or is malformed.

### Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Site loads, amber "BACKEND OFFLINE" banner | `NEXT_PUBLIC_API_URL` wrong, or build predates the change | Set env var, then redeploy |
| Banner shown, Network tab shows CORS error | Backend missing the Vercel origin | Set `CORS_ORIGIN_REGEX` on the backend and restart it |
| Banner shown, request pending then fails | Backend asleep/cold | Use a paid tier, not a free one |
| API returns 200 but page shows old data | Bundle is stale | Hard-reload; confirm redeploy happened |
| `model_ready: false` | Artifacts missing from the image | Confirm `app/ml_models/*.joblib` copied; rebuild |

---

## 4. Behaviour when the backend is down

The dashboard is designed not to white-screen. If the API is unreachable it
renders a deterministic synthetic baseline and shows an amber banner plus a
`OFFLINE SYNTHETIC BASELINE` badge. This is intentional for demos, but be aware
that a visitor can see plausible-looking numbers that are not model output. The
banner is the only thing distinguishing them.

If you would rather the site fail loudly in production, remove the fallback
branch in `frontend/src/lib/api.ts` and let the request reject.

---

## 5. Security before going public

- The API has **no authentication**. Anyone who finds the URL can call it. Add
  rate limiting or an API key before exposing it widely.
- Rotate any API key that was ever committed. `.env` and `.env.local` are
  git-ignored, and `backend/.env.example` holds no secrets.
- `ENABLE_AI_BRIEFING` is `false` by default. Turning it on requires
  `GEMINI_API_KEY` as a backend env var, never a `NEXT_PUBLIC_` one, or it ships
  to the browser.

---

## 6. Cost and expectations

- Frontend on Vercel: free for a hobby project.
- Backend: $0 if you accept a sleeping free-tier service on Render; ~$5–8/mo on
  Railway or Render paid for an always-on demo link.
- The model artifacts total ~0.8 MB, so image size and bandwidth are not
  concerns.
