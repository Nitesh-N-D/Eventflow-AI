# EventFlow AI — Event-Driven Traffic Impact Prediction & Smart Traffic Management

[![Deploy on Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/Nitesh-N-D/Eventflow-AI)

**AI-powered Smart City Traffic Command Center for Bengaluru**

Predicts traffic impact of planned and unplanned events, recommends optimal manpower deployment, barricading, and diversion routes — built on real ASTRAM Bengaluru traffic incident data.

**Team:** T. S. Bhuvaneshwar · N. D. Nitesh · L. Jayeshwar · S. Nithiswaran
**Hackathon:** Flipkart Gridlock 2.0, Round 2 — Theme: Event-Driven Congestion

---

## What This Is

A full-stack web platform where traffic authorities enter event details and receive:

| Output | How it's generated |
|---|---|
| Traffic Impact Score (0–100) | Real ML ensemble (RF + HGB + LGBM) trained on 8,054 real ASTRAM events |
| Expected Duration | Real model prediction (R² = 0.188 on real holdout) |
| Severity Score | Real model prediction (R² = 0.851 on real holdout) |
| Manpower Recommendation | ML severity × crowd-size policy multiplier |
| Barricade Points & Spacing | Real historical footprint data from ASTRAM |
| Diversion Routes | Nearest-corridor graph using real ASTRAM corridor centroids + Haversine |
| Public Advisory (SMS/notification/display board) | Rule-based template on real prediction output |
| Post-event learning | Officers submit real outcomes; system tracks real prediction errors |

---

## Architecture

```
┌─────────────────────┐    ┌──────────────────────────────────────┐
│   React + Vite      │────│   FastAPI Backend (Python)            │
│   TypeScript        │    │                                       │
│   Tailwind CSS      │    │  ┌─────────────────────────────────┐  │
│   Recharts charts   │    │  │  ML Prediction Engine             │  │
│   Leaflet maps      │    │  │  ─ Real ASTRAM data (8,054 rows) │  │
└─────────────────────┘    │  │  ─ RandomForest + HistGradBoost  │  │
                            │  │  ─ LightGBM/XGB/CatBoost (opt.) │  │
                            │  └─────────────────────────────────┘  │
                            │                                       │
                            │  ┌─────────────────────────────────┐  │
                            │  │  PostgreSQL + PostGIS             │  │
                            │  │  ─ 22 real Bengaluru corridors   │  │
                            │  │  ─ Events, Predictions, Users    │  │
                            │  └─────────────────────────────────┘  │
                            └──────────────────────────────────────┘

Deployed: Vercel (frontend) + Render (backend) + Supabase (PostgreSQL)
```

---

## Quick Start (Local)

### Option A — Docker Compose (recommended, full stack)

```bash
git clone https://github.com/Nitesh-N-D/Eventflow-AI
cd eventflow-ai
docker-compose up --build
```
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000/docs
- Postgres: localhost:5432

### Option B — Manual local setup

**Backend:**
```bash
# 1. Set up Postgres with PostGIS installed, create database
createdb eventflow_ai
psql -d eventflow_ai -f backend/migrations/001_initial_schema.sql
psql -d eventflow_ai -f backend/migrations/002_seed_corridors.sql

# 2. Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env: set DATABASE_URL and SECRET_KEY

# 3. Train ML models on the real dataset (one-time, ~2 minutes)
pip install -r backend/requirements.txt
python -m ml_pipeline.data_loader
python -m ml_pipeline.feature_engineer
python -m ml_pipeline.train
python -m ml_pipeline.event_data_loader
python -m ml_pipeline.train_event_model

# 4. Start API
cd backend
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
# Create frontend/.env.local:
echo "VITE_API_URL=http://localhost:8000" > .env.local
npm run dev
# Open http://localhost:5173
```

---

## Deployment Guide

### Step 1 — Set up Supabase (PostgreSQL + PostGIS)

1. Go to https://supabase.com → New project
2. In SQL Editor, run `backend/migrations/001_initial_schema.sql`
3. Then run `backend/migrations/002_seed_corridors.sql` (loads 22 real corridors)
4. Copy your Connection String (Pooler → Transaction mode) → looks like:
   `postgresql://postgres.[ref]:[password]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres`
5. Convert to asyncpg format:
   `postgresql+asyncpg://postgres.[ref]:[password]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres`

### Step 2 — Deploy Backend to Render

1. Go to https://render.com → New Web Service → Connect your GitHub repo
2. Settings:
   - **Root Directory:** `.` (repo root)
   - **Dockerfile Path:** `backend/Dockerfile`
   - **Plan:** Starter ($7/mo) or Free (cold starts)
3. Add Environment Variables in Render dashboard:
   - `DATABASE_URL` → your Supabase asyncpg URL from Step 1
   - `SECRET_KEY` → click "Generate" for a random value
   - `CORS_ORIGINS` → `https://your-app.vercel.app,http://localhost:5173`
4. Deploy → copy your Render URL (e.g. `https://eventflow-ai-backend.onrender.com`)

### Step 3 — Deploy Frontend to Vercel

1. Go to https://vercel.com → New Project → Import from GitHub
2. Settings:
   - **Framework Preset:** Vite
   - **Root Directory:** `frontend`
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`
3. Add Environment Variable:
   - `VITE_API_URL` → your Render backend URL from Step 2
4. Deploy → your frontend is live at `https://your-app.vercel.app`

### Step 4 — Update CORS

In Render dashboard, update `CORS_ORIGINS` to include your real Vercel URL.
Trigger a redeploy.

---


## Default Login Credentials

After first deployment, register via `/register` with any email.
Set role to `admin` for full access. There is no pre-seeded admin account
(by design — credentials should be set by the deploying authority).

---

## Real Data Honesty Statement

The ML predictions in this system are built on the **real ASTRAM Bengaluru traffic
incident dataset** (8,054 events, Nov 2023–Apr 2024) provided by Flipkart/Bengaluru
Traffic Police for this hackathon.

**What is genuinely ML-driven (real historical training data):**
- Predicted event duration (R² = 0.188, RMSE = 902 min on real holdout)
- Predicted severity score (R² = 0.851, RMSE = 0.090 on real holdout)

**What is rule-based policy applied on top of ML output:**
- Congestion score (0–100): ML severity × crowd_size multiplier
- Officer count: ML base × crowd multiplier
- Barricading: historical footprint medians from real ASTRAM data

The R² values look modest for duration because event duration is genuinely
noisy in real-world data (depends on crew size, weather, day-of-week interactions
not captured in this dataset). This is an honest result, not a placeholder.

---

## API Documentation

Auto-generated at `/docs` (Swagger UI) and `/redoc` once the backend is running.

Key endpoints:
```
POST /auth/register     Create account
POST /auth/login        Get JWT token
GET  /auth/me           Current user

POST /events/           Create event (triggers AI prediction automatically)
GET  /events/           List all events
GET  /events/{id}       Full event detail with prediction + resources + routes
PATCH /events/{id}/status  Update event status

POST /feedback/{event_id}  Submit post-event real outcomes
GET  /analytics/summary    Aggregated analytics
GET  /analytics/prediction-accuracy  Real vs predicted comparison
GET  /corridors/           22 real Bengaluru corridors with coordinates

GET  /health            Health check for Render
GET  /docs              Swagger UI
```

---

## Project Structure

```
eventflow-ai/
├── backend/
│   ├── app/
│   │   ├── main.py           FastAPI app
│   │   ├── api/              Route handlers
│   │   ├── core/             Config, DB, security (JWT/bcrypt)
│   │   ├── models/           SQLAlchemy ORM models
│   │   ├── schemas/          Pydantic request/response schemas
│   │   └── ml/               Prediction engine bridge
│   ├── migrations/           PostgreSQL migration SQL
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/            Full page components
│   │   ├── components/       Reusable UI (map, congestion ring, layout)
│   │   ├── hooks/            Auth context
│   │   ├── lib/              API client, utilities
│   │   └── types/            TypeScript interfaces
│   ├── public/               SEO assets, favicon, sitemap, robots.txt
│   ├── index.html            Full SEO meta, OG, Twitter card, JSON-LD
│   ├── Dockerfile
│   └── nginx.conf
├── ml_pipeline/              Real ML code (ported from Gridlock Round 1)
│   ├── data/raw/             Real ASTRAM dataset
│   ├── data/processed/       Cleaned tables, corridor centroids
│   └── models/               Trained .pkl ensemble files
├── render.yaml               Render deployment config
├── vercel.json               Vercel deployment config
└── docker-compose.yml        Full local stack
```
