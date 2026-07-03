# PulseCheck

API & endpoint health monitor with a live status dashboard. Add any HTTP URL, set a polling interval, and PulseCheck tracks uptime, response time, and alerts you on state changes.

Built with FastAPI + SQLite + APScheduler (backend) and React + Recharts (frontend).

---

## Quick start (local, no Docker)

**Backend**

```bash
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
cp ../.env.example .env   # edit if you want email alerts
uvicorn main:app --reload
# API running at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
# Dashboard at http://localhost:5173
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./pulsecheck.db` | SQLite or Postgres URL |
| `ALERT_FROM_EMAIL` | — | Gmail address to send alerts from |
| `ALERT_TO_EMAIL` | — | Where to receive alerts |
| `SMTP_PASSWORD` | — | Gmail App Password |
| `VITE_API_URL` | *(empty)* | Backend URL for production (Vercel env var) |

Email alerts are optional — leave the SMTP vars blank to disable.

---

## Deploy

**Backend → Render (free tier)**

1. Push repo to GitHub
2. New Web Service → connect repo → Root Directory: `backend`
3. Build: `pip install -r requirements.txt`
4. Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add env vars from `.env.example`

**Frontend → Vercel (free tier)**

1. Import repo → Root Directory: `frontend`
2. Framework: Vite
3. Add env var: `VITE_API_URL=https://your-api.onrender.com`

---

## Docker (backend only)

```bash
cp .env.example .env
docker compose up
```

---

## Project structure

```
pulsecheck/
├── backend/
│   ├── main.py          # FastAPI app + CORS + lifespan
│   ├── models.py        # SQLAlchemy: Endpoint, CheckResult
│   ├── scheduler.py     # APScheduler polling + state-change alerts
│   ├── alerts.py        # SMTP email on DOWN/RECOVERY
│   └── routers/
│       ├── endpoints.py # CRUD + pause/resume
│       └── checks.py    # History + uptime stats
└── frontend/
    └── src/
        ├── App.jsx               # Main layout + state
        ├── api.js                # Fetch wrapper
        └── components/
            ├── StatusCard.jsx    # Per-endpoint card with live stats
            ├── UptimeChart.jsx   # Recharts response-time line chart
            ├── IncidentTable.jsx # Last 50 checks table
            └── AddEndpointForm.jsx
```
