# Mission-Critical Incident Management System (IMS)

A production-grade IMS that ingests high-volume failure signals from distributed infrastructure, debounces them into trackable Work Items, and provides a real-time React dashboard for managing incidents to closure with mandatory Root Cause Analysis.

<img width="959" height="470" alt="Screenshot 2026-05-08 013210" src="https://github.com/user-attachments/assets/41405b46-1b66-4663-9834-ccedd900eb4d" />

---

## Architecture Diagram

![Architecture Diagram](docs/architecture.png)

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Backend runtime | Python 3.12 + FastAPI + asyncio | Native async I/O, high-concurrency, auto OpenAPI docs |
| In-memory buffer | `asyncio.Queue` (500k capacity) | Decouples fast ingestion from slow DB writes; handles 10k signals/sec bursts |
| Source of Truth | PostgreSQL 16 (asyncpg) | ACID transactions for Work Items and RCA; row-level locking prevents race conditions |
| Data Lake | MongoDB 7 (Motor async driver) | Schema-flexible, horizontally scalable; stores raw signal payloads with indexed queries |
| Hot-path cache | Redis Stack | Sub-millisecond dashboard state reads; atomic SET NX for race-free debouncing; sliding-window rate limiter; TimeSeries for signal aggregations |
| Real-time push | FastAPI WebSocket | Server-push to all connected dashboard clients on every state change |
| Frontend | React 18 + Vite + Tailwind CSS | Reactive UI with hooks, fast HMR in dev, tiny production bundle |
| Container | Docker Compose | One-command local setup; health-checks ensure correct startup order |

### Design Patterns

| Pattern | Where | Purpose |
|---|---|---|
| **Strategy** | `app/patterns/alert_strategy.py` | Swap alert logic (P0–P3) at runtime based on component type |
| **State** | `app/patterns/incident_state.py` | Enforce OPEN→INVESTIGATING→RESOLVED→CLOSED lifecycle; block illegal transitions |

---

## Setup Instructions

### Prerequisites
- **Docker Desktop** (includes Compose) — [install](https://docs.docker.com/get-docker/)
- No other installs required — Python, Node, and all databases run inside containers

### Option A — Docker Compose (recommended)

```bash
# Clone and enter the repo
cd "Incident Management System"

# Build and start all services
docker compose up --build
```

That's it. Docker automatically:
1. Starts PostgreSQL, MongoDB, Redis Stack, backend, and frontend
2. Runs the **seeder** — simulates a cascading failure scenario so the dashboard is pre-populated with real incidents on first load

| URL | Description |
|---|---|
| http://localhost:3000 | React dashboard |
| http://localhost:8000/docs | Interactive API docs (Swagger) |
| http://localhost:8000/health | Liveness + readiness probe |
| http://localhost:8001 | RedisInsight (Redis GUI) |

> **Data persistence:** All data is stored in Docker named volumes (`postgres_data`, `mongodb_data`, `redis_data`). Data survives container restarts. Only `docker compose down -v` wipes it.

### Option B — Local Development (without Docker)

**Backend:**
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt

# Set env vars
$env:DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/ims_db"
$env:MONGODB_URL="mongodb://localhost:27017/ims_signals"
$env:REDIS_URL="redis://localhost:6379"

uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev    # http://localhost:3000
```

**Run tests:**
```bash
cd backend
pip install -r requirements-dev.txt
pytest tests/ -v
```

---

## Failure Simulation

The seeder service runs **automatically** when you start the project with `docker compose up --build`. It simulates a realistic cascading outage across the stack in 5 waves:

| Wave | Component | Priority | Signals |
|---|---|---|---|
| 1 — RDBMS Primary Failure | `RDBMS_PRIMARY_01`, `RDBMS_REPLICA_01` | P0 | 3 |
| 2 — API Connection Pool Exhaustion | `API_GATEWAY_01`, `API_GATEWAY_02` | P1 | 3 |
| 3 — MCP Host Failures | `MCP_HOST_PROD_01`, `MCP_HOST_PROD_02` | P1 | 2 |
| 4 — Cache Miss Storm | `CACHE_CLUSTER_01` | P2 | 2 |
| 5 — Async Queue Backlog | `NOSQL_EVENTS_01`, `ASYNC_QUEUE_ORDERS` | P3 | 2 |

After the 5 waves, it fires **100 concurrent signals** to `CACHE_CLUSTER_01` to demonstrate debouncing — only **1 work item** is created while all 100 signals are stored in MongoDB.

**To run the simulation manually** (e.g. to add more incidents later):
```bash
pip install httpx
python scripts/mock_failure_event.py --fast --burst

# Point at a custom backend
python scripts/mock_failure_event.py --host http://my-backend:8000
```

---

## How Backpressure is Handled

The system is designed to **never crash under load**, even when the persistence layer is slow.

### The Buffer

```
Producer (HTTP) ──202 Accepted──► asyncio.Queue(maxsize=500,000)
                                          │
                                  10 worker coroutines
                                          │
                                  PostgreSQL / MongoDB writes
```

1. The HTTP handler enqueues the signal and immediately returns `202 Accepted`. The database write happens asynchronously in a worker pool.

2. The queue acts as an elastic buffer. At 10,000 signals/sec with ~1 ms per DB write and 10 workers, the queue drains at ~10,000 writes/sec — matching peak ingest rate.

3. **If the queue fills** (DB is down for >50 s at peak load), the handler returns `503 Service Unavailable` with `retry_after_ms: 1000` — a backpressure signal to upstream producers. The response body includes the current queue depth so producers can make intelligent retry decisions.

4. **Rate limiting** (Redis sliding-window, 10,000 req/60 s per IP) provides a second layer: it prevents a single rogue producer from monopolising the queue, leaving capacity for other components.

### DB Write Resilience

All PostgreSQL and MongoDB writes use `@with_retry(max_attempts=3, initial_delay=0.1, backoff_factor=2)`. A transient DB hiccup triggers a 100 ms → 200 ms → 400 ms retry sequence before the signal is dropped, covering typical restart windows.

### Debounce Race Safety

The debounce check uses a single atomic `SET key value NX EX 10` Redis command. Even under concurrent workers, only one will win the NX race and create a Work Item — preventing duplicate incidents for the same component.

---

## API Reference

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/signals` | Ingest a signal (async, rate-limited) |
| `POST` | `/api/signals/batch` | Batch ingest (up to 1000 signals) |
| `GET` | `/api/incidents` | List incidents (filterable by status/priority) |
| `GET` | `/api/incidents/{id}` | Get incident + RCA |
| `PATCH` | `/api/incidents/{id}/status` | Transition state machine |
| `POST` | `/api/incidents/{id}/rca` | Submit / update RCA |
| `GET` | `/api/incidents/{id}/signals` | Raw signal audit log from MongoDB |
| `GET` | `/health` | Liveness + readiness probe |
| `GET` | `/metrics` | Throughput metrics (also printed to console every 5 s) |
| `GET` | `/api/metrics/timeseries` | Per-component signal counts (Redis TimeSeries, 1-min buckets) |
| `GET` | `/api/metrics/top-components` | Top 10 noisiest components in last 24 h (MongoDB aggregation) |
| `WS` | `/ws/dashboard` | Real-time push channel |

Full interactive docs: **http://localhost:8000/docs**

---

## Dashboard

The React dashboard provides a clean, light-themed incident management interface:

- **Live Feed** — left sidebar showing all incidents sorted P0 → P3, with component, status, and signal count
- **Incident Detail** — click any incident to see the info table (Incident ID, Component, Severity, Status, First Signal, Signal Count, MTTR) alongside the raw signal payloads from MongoDB
- **MTTR** — automatically calculated from `RCA.incident_end − RCA.incident_start` and displayed in green once the incident is closed
- **RCA Form** — Incident Start/End date pickers, Root Cause Category dropdown, Fix Applied and Prevention Steps text areas
- **Save Draft** — saves form state locally to `localStorage` (no API call, no validation required)
- **Submit RCA** — validates all fields client-side, then persists to backend
- **Close Incident** — auto-chains `OPEN → INVESTIGATING → RESOLVED → CLOSED` in one click once RCA is complete; no manual state transitions required
- **Toast notifications** — all errors and confirmations surface as non-blocking toasts (top-right corner)

---

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py                   # FastAPI app + lifespan
│   │   ├── config.py                 # Pydantic settings
│   │   ├── database.py               # PostgreSQL, MongoDB, Redis init
│   │   ├── models/
│   │   │   ├── db_models.py          # SQLAlchemy ORM (WorkItem, RCARecord)
│   │   │   ├── signal.py             # Pydantic schemas
│   │   │   ├── incident.py
│   │   │   └── rca.py
│   │   ├── patterns/
│   │   │   ├── alert_strategy.py     # Strategy pattern (P0–P3 alerts)
│   │   │   └── incident_state.py     # State pattern (lifecycle FSM)
│   │   ├── services/
│   │   │   ├── ingestion_service.py  # Queue + debounce + workers
│   │   │   ├── incident_service.py   # CRUD + state transitions + MTTR
│   │   │   ├── websocket_manager.py  # Broadcast to all WS clients
│   │   │   └── metrics_service.py    # Throughput tracking + console reporting
│   │   ├── api/
│   │   │   ├── signals.py            # POST /api/signals, /batch
│   │   │   ├── incidents.py          # Incident CRUD + RCA + status
│   │   │   ├── health.py             # /health, /metrics, timeseries, top-components
│   │   │   └── websocket_handler.py  # WS /ws/dashboard
│   │   ├── middleware/
│   │   │   └── rate_limiter.py       # Sliding-window rate limiter
│   │   └── utils/
│   │       └── retry.py              # Exponential backoff decorator
│   └── tests/
│       ├── test_rca_validation.py    # RCA gate unit tests
│       ├── test_alert_strategy.py    # Strategy pattern unit tests
│       ├── test_debounce.py          # Concurrent debounce correctness
│       └── test_state_machine.py     # State guard unit tests
├── frontend/
│   └── src/
│       ├── App.jsx                   # Layout, health status, WebSocket lifecycle
│       ├── lib/
│       │   ├── colors.js             # Canonical color palette (badges + charts)
│       │   └── toast.js              # Event-bus toast system
│       ├── components/
│       │   ├── IncidentList.jsx      # Live Feed sidebar cards
│       │   ├── IncidentDetail.jsx    # Info table + raw signals + auto-chain close
│       │   ├── RCAForm.jsx           # RCA form with draft save + validation
│       │   └── Toast.jsx             # Fixed toast notification renderer
│       └── services/
│           ├── api.js                # Axios REST client
│           └── websocket.js          # WS client with auto-reconnect
├── scripts/
│   ├── mock_failure_event.py         # Failure simulation (runs automatically via seeder)
│   └── seed_data.json                # 5-wave cascading failure scenario definition
├── docs/
│   └── architecture.png              # Architecture diagram
├── docker-compose.yml                # All 6 services: postgres, mongo, redis, backend, frontend, seeder
├── PROMPTS.md
└── README.md
```
