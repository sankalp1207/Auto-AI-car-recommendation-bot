# 🚀 Deploying AutoAI Backend to Render (Free Tier)

This guide walks you through deploying the **AutoAI** backend to **[Render](https://render.com)** on the 100% Free Plan (512 MB RAM).

---

## 📋 Prerequisites

1. A free **[Render.com](https://render.com)** account.
2. A free PostgreSQL database from **[Neon.tech](https://neon.tech)** (or Supabase).
   * Copy your connection string (e.g. `postgres://user:password@ep-xyz.region.aws.neon.tech/neondb?sslmode=require`).
3. *(Optional)* A Google Gemini API key from **[Google AI Studio](https://aistudio.google.com/)**.

---

## Option 1: Automatic 1-Click Blueprint (Recommended)

1. Push your repository to **GitHub**.
2. Log in to [Render Dashboard](https://dashboard.render.com).
3. Click **New +** → **Blueprint**.
4. Connect your GitHub repository.
5. Render will automatically detect [`render.yaml`](file:///d:/sankalp/projects/AutoAI/render.yaml) and configure:
   - **Service Type:** Web Service
   - **Runtime:** Python 3.11.9
   - **Build Command:** `pip install --upgrade pip && pip install -r requirements-prod.txt`
   - **Start Command:** `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`
   - **Health Check:** `/health`
6. Enter the required environment variables:
   - `DATABASE_URL`: Your Neon.tech PostgreSQL connection string.
   - `GEMINI_API_KEY`: Your Google AI Studio API key.
   - `CORS_ORIGINS`: Your frontend URL (e.g. `https://your-frontend.pages.dev` or `*`).
7. Click **Apply**. Render will build and deploy your backend automatically!

---

## Option 2: Manual Web Service Setup

If you prefer setting up the Web Service manually:

1. In Render Dashboard, click **New +** → **Web Service**.
2. Connect your GitHub repository.
3. Configure the settings:
   - **Name:** `autoai-backend`
   - **Region:** Closest to your database (e.g., Singapore, Frankfurt, or Oregon).
   - **Branch:** `main`
   - **Root Directory:** `AutoAI/backend`
   - **Runtime:** `Python 3`
   - **Build Command:**
     ```bash
     pip install --upgrade pip && pip install -r requirements-prod.txt
     ```
   - **Start Command:**
     ```bash
     python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
     ```
   - **Instance Type:** `Free` (512 MB RAM, 0.1 CPU).

4. Under **Advanced** → **Environment Variables**, add:
   | Key | Value | Notes |
   | :--- | :--- | :--- |
   | `PYTHON_VERSION` | `3.11.9` | Ensures Python 3.11 runtime |
   | `DATABASE_URL` | `postgresql://...neon.tech/neondb?sslmode=require` | Your Neon database string |
   | `SECRET_KEY` | *(Click "Generate" or enter 32+ random characters)* | JWT Auth Secret |
   | `GEMINI_API_KEY` | *(Your Gemini API key)* | Optional, powers AI chat |
   | `GEMINI_MODEL` | `gemini-3.6-flash` | Low latency model |
   | `GEMINI_TIMEOUT` | `10` | Seconds |
   | `ENVIRONMENT` | `production` | Production mode |
   | `CORS_ORIGINS` | `*` or your frontend URL | Allowed frontend origins |

5. Under **Health Check Path**, enter: `/health`
6. Click **Create Web Service**.

---

## 🗄️ Database Auto-Seeding

On first startup, AutoAI checks if your database is empty. If empty, it will automatically:
1. Create all PostgreSQL tables.
2. Seed all 2,245 car records from `data/cars_current.csv` and `data/cars_upcoming.csv`.
3. Build the in-memory cache in ~60ms.

---

## 🔍 Verification

Once deployed, test your endpoints:
- **Root status:** `https://<your-service>.onrender.com/` → `{"status":"running","project":"AutoAI"}`
- **Health check:** `https://<your-service>.onrender.com/health` → `{"status":"healthy","database":"connected"}`
- **Interactive Swagger Docs:** `https://<your-service>.onrender.com/docs`
