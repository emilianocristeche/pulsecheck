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
cp ../.env.example .env   # edit if you want email alerts (loaded automatically)
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
| `CORS_ORIGINS` | `*` | Dashboard origin(s) allowed by CORS, comma-separated |
| `PULSECHECK_ALLOW_PRIVATE_TARGETS` | `false` | `true` allows monitoring localhost / private-network URLs (see Security) |
| `ALERT_FROM_EMAIL` | — | Gmail address to send alerts from |
| `ALERT_TO_EMAIL` | — | Where to receive alerts |
| `SMTP_PASSWORD` | — | Gmail App Password |
| `VITE_API_URL` | *(empty)* | Backend URL for production (Vercel env var) |

Email alerts are optional — leave the SMTP vars blank to disable.

The backend loads `backend/.env` and then the repo-root `.env` on startup (via
`python-dotenv`). Variables already set in the real environment always win, so
Render/Docker settings are never overridden by a stray file.
`backend/.dockerignore` keeps `.env` out of the Docker image.

---

## Security: SSRF protection

PulseCheck makes HTTP requests to URLs that users type in, from wherever the
backend runs. Without limits, an endpoint like
`http://169.254.169.254/latest/meta-data/` (cloud credentials) or
`http://localhost:5432` would turn the monitor into a proxy for internal
services. `backend/netguard.py` applies these rules to every check and to every
redirect hop:

1. Only `http` and `https` URLs.
2. The hostname is resolved once, and **every** returned address must be
   public (`ipaddress.is_global`; IPv4-mapped IPv6 is unwrapped first). Any
   loopback, private, link-local or reserved address rejects the request.
3. The request connects to the validated IP: the URL is rewritten to that IP,
   the original `Host` header is kept, and for HTTPS the SNI and certificate
   check still use the hostname. The HTTP client never resolves the name a
   second time, so the address that was checked is the address connected to.
4. Redirects are not followed automatically. Each `Location` (max 5 hops) is
   checked by rules 1-3 before it is requested, so a public URL that redirects
   to an internal one is blocked at that hop.
5. Proxy environment variables are ignored, so the connection really goes to
   the pinned IP.

Adding an endpoint whose URL is already disallowed returns `422`. Because DNS
can change later, the scheduler re-validates on every check, and a blocked
check is recorded as down with `error_msg` starting with `blocked:`.

Limits: every check (and every hop) does its own fresh lookup, which is
validated before use; the protection is about where PulseCheck connects, not
about what a public server does with the request on its side. To monitor
internal services on purpose (a self-hosted install on your LAN), set
`PULSECHECK_ALLOW_PRIVATE_TARGETS=true`.

---

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest -q
```

The SSRF tests run against a local HTTP server: blocked ranges, redirects to
internal addresses, redirect loops, proxy env vars, and a DNS answer that
changes between lookups (the request must stay on the first, validated IP).

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
│   ├── netguard.py      # SSRF-safe HTTP fetch (IP pinning, redirect checks)
│   ├── alerts.py        # SMTP email on DOWN/RECOVERY
│   ├── routers/
│   │   ├── endpoints.py # CRUD + pause/resume
│   │   └── checks.py    # History + uptime stats
│   └── tests/           # pytest (SSRF protections)
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

---

## What I Learned

_TODO: section to be written by the author._
