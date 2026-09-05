# AutoAI — Production Free-Tier Deployment Guide

This guide provides step-by-step instructions for deploying the entire **AutoAI** platform completely within **100% free hosting tiers**.

---

## 1. Architecture Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                       End User Client                       │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTPS
                               ▼
┌─────────────────────────────────────────────────────────────┐
│         Frontend: Cloudflare Pages / Vercel (Free)          │
│  - React 19 + Vite + TypeScript                             │
│  - Global CDN edge caching & SSL                            │
│  - Configured via: VITE_API_URL                             │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTPS REST API
                               ▼
┌─────────────────────────────────────────────────────────────┐
│            Backend: Render / Koyeb Web Service (Free)       │
│  - FastAPI + Uvicorn (1 worker)                             │
│  - Lightweight runtime: requirements-prod.txt (<512MB RAM)  │
│  - Auto cold-start cache (~60ms) from DB                    │
│  - Configured via: DATABASE_URL, CORS_ORIGINS, GEMINI_API_KEY│
└──────────────────────────────┬──────────────────────────────┘
                               │ Encrypted TLS (sslmode=require)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│          Database: Neon.tech / Supabase (Free Tier)         │
│  - Managed PostgreSQL 16                                    │
│  - 2,245 Car Records (2,076 CURRENT, 169 UPCOMING)          │
│  - Connection pooling enabled (pool_pre_ping=True)          │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Step 1: Create a Free PostgreSQL Database (Neon.tech or Supabase)

AutoAI requires a PostgreSQL instance. The recommended free-tier provider is **[Neon.tech](https://neon.tech)** (serverless PostgreSQL with 0.5 GB free storage; AutoAI's dataset takes ~12 MB).

1. Sign up for a free account at **[https://neon.tech](https://neon.tech)**.
2. Click **Create Project**, name it `autoai`, and select the region nearest to your target users (e.g., Singapore, Frankfurt, or US East).
3. Once created, copy the **Pooled connection string**. It looks like:
   ```text
   postgres://username:password@ep-sample-123.region.aws.neon.tech/neondb?sslmode=require
   ```
4. **Note:** AutoAI automatically translates `postgres://` to `postgresql://` and enables connection recycling and pinging.

---

## 3. Step 2: Deploy the Backend (Render Free Tier)

1. Sign up for a free account at **[https://render.com](https://render.com)**.
2. In the dashboard, click **New +** > **Web Service**.
3. Connect your GitHub repository containing the AutoAI project.
4. Configure the service settings:
   - **Name:** `autoai-backend`
   - **Region:** Choose the region closest to your Neon database.
   - **Branch:** `main`
   - **Root Directory:** `AutoAI/backend` (or `backend` if deploying from the subfolder).
   - **Runtime:** `Python 3`
   - **Build Command:**
     ```bash
     pip install -r requirements-prod.txt
     ```
   - **Start Command:**
     ```bash
     python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
     ```
   - **Instance Type:** `Free` (512 MB RAM, 0.1 CPU).
5. Open **Environment Variables** and add:
   | Variable | Value | Description |
   | :--- | :--- | :--- |
   | `DATABASE_URL` | `postgresql://...neon.tech/neondb?sslmode=require` | Your Neon database connection URI |
   | `SECRET_KEY` | *(Generate a 32+ character random string)* | JWT signing secret |
   | `GEMINI_API_KEY` | *(Your Google AI Studio API key)* | Optional, powers conversational AI layer |
   | `GEMINI_MODEL` | `gemini-3.6-flash` | Fast, low-latency default model |
   | `GEMINI_TIMEOUT` | `10` | Timeout in seconds |
   | `ENVIRONMENT` | `production` | Production environment flag |
   | `CORS_ORIGINS` | `http://localhost:5173` *(Update with frontend URL after Step 3)* | Allowed frontend origins |
6. Click **Create Web Service**.
7. **Automatic Database Seeding:** On the very first boot, AutoAI will detect an empty database (`count == 0`), create all tables, and seed all 2,245 vehicles automatically from the included CSVs. Subsequent startups will load from the database cache in ~60ms.
8. Note down your backend service URL (e.g. `https://autoai-backend.onrender.com`).

---

## 4. Step 3: Deploy the Frontend (Cloudflare Pages or Vercel)

### Option A: Cloudflare Pages (Recommended - 100% Free, Unlimited Bandwidth)
1. Sign up at **[https://dash.cloudflare.com](https://dash.cloudflare.com)**.
2. Go to **Workers & Pages** > **Create application** > **Pages** > **Connect to Git**.
3. Select your repository.
4. Configure the build settings:
   - **Project Name:** `autoai-cars`
   - **Production Branch:** `main`
   - **Root Directory:** `AutoAI/frontend`
   - **Framework Preset:** `None` or `Vite`
   - **Build Command:** `npm run build`
   - **Build Output Directory:** `.output/public`
5. Under **Environment Variables**, add:
   | Variable | Value |
   | :--- | :--- |
   | `VITE_API_URL` | `https://autoai-backend.onrender.com` (Your Render backend URL from Step 2) |
6. Click **Save and Deploy**.
7. Note your frontend URL (e.g., `https://autoai-cars.pages.dev`).

### Option B: Vercel (Alternative)
1. Import repository on **[https://vercel.com](https://vercel.com)**.
2. Set **Root Directory** to `AutoAI/frontend`.
3. Set **Output Directory** to `.output/public`.
4. Add environment variable `VITE_API_URL=https://autoai-backend.onrender.com`.
5. Deploy.

---

## 5. Step 4: Link Frontend & Backend (Update CORS)

Once you know your frontend URL (e.g., `https://autoai-cars.pages.dev`):

1. Go back to your **Render Dashboard** > `autoai-backend` > **Environment**.
2. Update the `CORS_ORIGINS` variable:
   ```text
   CORS_ORIGINS=https://autoai-cars.pages.dev,http://localhost:5173
   ```
3. Save changes. Render will automatically perform a zero-downtime reload with the new CORS origin permitted.

---

## 6. Step 5: Post-Deployment Verification Checklist

Run these HTTP requests against your live backend URL (`https://your-backend.onrender.com`):

### 1. Health Check
```bash
curl https://your-backend.onrender.com/health
```
**Expected Response (200 OK):**
```json
{
  "status": "healthy",
  "database": "connected"
}
```

### 2. Vehicle Catalog & Inventory Counts
```bash
curl https://your-backend.onrender.com/cars/stats
```
**Expected Response (200 OK):**
```json
{
  "total_cars": 2245,
  "current_cars": 2076,
  "upcoming_cars": 169,
  "total_brands": 38
}
```

### 3. Recommendation Engine
```bash
curl -X POST https://your-backend.onrender.com/recommend/ \
  -H "Content-Type: application/json" \
  -d '{"budget_max": 2000000, "fuel_preference": ["Petrol"], "body_types": ["SUV"], "top_n": 3}'
```
**Expected Response:** 200 OK with top 3 recommended vehicles and match scores.

### 4. Interactive Frontend
1. Open your frontend URL (`https://your-frontend.pages.dev`).
2. Verify:
   - Featured vehicle carousel loads on home page.
   - Search page filters by brand, price, body style, and fuel.
   - Quiz recommendation flow generates personalized suggestions.
   - Chatbot responds with AI context and vehicle cards.
   - Car comparison compares specifications side-by-side.

---

## 7. Troubleshooting & FAQ

### Issue 1: Render Free Tier "Spin Down" (Cold Start)
- **Symptom:** The first request to the backend takes 20–40 seconds after being idle.
- **Cause:** Render free tier spins down web services after 15 minutes of inactivity.
- **Resolution:** AutoAI's database caching is designed for rapid cold-starts (~60ms). If continuous uptime is desired on free hosting, you can set up a free monitor (e.g. [UptimeRobot](https://uptimerobot.com)) to ping `https://your-backend.onrender.com/health` every 10 minutes.

### Issue 2: CORS Error (`Cross-Origin Request Blocked`)
- **Symptom:** Browser console shows `CORS error` when calling the backend.
- **Resolution:** Verify `CORS_ORIGINS` in your backend Render dashboard exactly matches your frontend domain (including `https://` and without trailing slashes). Multiple origins can be comma-separated.

### Issue 3: Database Connection Failed
- **Symptom:** `/health` returns `503 Service Unavailable` with `database: disconnected`.
- **Resolution:** Ensure `?sslmode=require` is appended to the connection string in `DATABASE_URL`. Neon and Supabase require TLS connections.

### Issue 4: Gemini Quota Exceeded (429)
- **Symptom:** Chat returns deterministic fallback recommendations with note about quota.
- **Resolution:** AutoAI has built-in graceful degradation. If the Gemini free-tier quota is reached, the deterministic scoring engine handles the request automatically so users never see a 500 error.
