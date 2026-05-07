# Prompts, Spec & Plans

This file contains the full specification, design decisions, and planning prompts used to create this repository.

---

## Original Engineering Challenge Specification

Build a resilient Incident Management System (IMS) designed to monitor a complex distributed stack (APIs, MCP Hosts, Distributed Caches, Async Queues, RDBMS, and NoSQL stores) and manage failure mediation workflow.

### Requirements Summary

**Ingestion & In-Memory Processing**
- Signal ingestion supporting high-throughput (up to 10,000 signals/sec)
- System must not crash if persistence layer is slow → use in-memory buffer
- Debouncing: 100 signals for same Component ID within 10s → 1 Work Item, 100 signals linked in NoSQL

**Storage**
- NoSQL (data lake) for raw signal payloads and audit log
- RDBMS (source of truth) for Work Items and RCA — transactional
- Cache (hot-path) for real-time dashboard state
- Time-series aggregations support

**Design Patterns**
- Strategy Pattern for alerting (P0 for RDBMS, P2 for Cache, etc.)
- State Pattern for work item lifecycle (OPEN → INVESTIGATING → RESOLVED → CLOSED)

**Functional Requirements**
- Async processing throughout
- Mandatory RCA before CLOSED transition
- MTTR auto-calculation (incident_end - incident_start)
- Concurrency primitives (no race conditions on status updates)
- Rate limiting on ingestion API
- `/health` endpoint + throughput metrics every 5 seconds
- React/Vue/HTMX dashboard with live feed, incident detail, RCA form

**Evaluation Rubric**
- Concurrency & Scaling (10%): No race conditions, handles 10k signals/sec
- Data Handling (20%): Correct separation — MongoDB for signals, PostgreSQL for work items, Redis for cache
- LLD (20%): Strategy + State patterns, clean code structure
- UI/UX & Integration (20%): Functional dashboard with live backend API integration
- Resilience & Testing (10%): DB write retry logic, unit tests for RCA validation
- Documentation (10%): Architecture diagram, setup instructions, backpressure explanation
- Tech Stack choices (10%): Justified technology selection

---

## Design Decisions & Rationale

### Protocol Choice: HTTP REST + WebSocket

**Why not gRPC?** gRPC requires proto file compilation and is less browser-friendly. HTTP REST is universally supported, has excellent FastAPI integration, and the auto-generated OpenAPI docs (Swagger UI) provide zero-friction testing. WebSocket handles the real-time push requirement without long-polling overhead.

### Backpressure: asyncio.Queue

The central backpressure mechanism is an `asyncio.Queue(maxsize=500_000)` that decouples the fast HTTP ingestion path from the slower DB write path. The key insight:

- **HTTP handler**: enqueue signal → return 202 immediately (microseconds)
- **Worker pool** (10 coroutines): drain queue → write PostgreSQL + MongoDB (milliseconds)
- **Queue full**: return 503 with `retry_after_ms` (never crash, just signal backpressure)

At 10,000 signals/sec input rate and 10 workers each doing ~1ms writes, the system drains at ~10,000 writes/sec — matching peak load. The 500k queue provides ~50 seconds of buffer.

### Debouncing: Redis SET NX EX (atomic)

The naive approach (GET → check → SET) has a race condition: two concurrent workers can both find no key and both create a Work Item for the same component.

The correct approach uses Redis's atomic `SET key value NX EX ttl`:
- NX = set only if Not eXists
- EX = TTL in seconds
- Returns True if set, False if key already existed

Only one worker wins the NX race. All others GET the existing key. This is a single atomic Redis round-trip with no locking overhead.

### Strategy Pattern: Alert Escalation

```
AlertContext.set_strategy_for_component("RDBMS")
→ selects P0CriticalAlert (pages on-call immediately)

AlertContext.set_strategy_for_component("CACHE")
→ selects P2MediumAlert (Slack notification)
```

The strategy is swappable at runtime — you can escalate a P2 to a P0 by calling `set_strategy_for_component("RDBMS")` on an existing context, or inject a custom strategy for testing. The mapping is table-driven in `COMPONENT_ALERT_MAP`, making it trivial to add new component types.

### State Pattern: Incident Lifecycle

```
OPEN → INVESTIGATING → RESOLVED → CLOSED
         ↑                ↑
         └────────────────┘  (can re-investigate a "resolved" incident)
```

Each state encodes its own allowed transitions via `can_transition_to()`. The terminal `ClosedState` overrides `validate_entry()` to enforce the mandatory RCA gate — raising `ValueError` if the RCA is missing or incomplete. This means **the validation logic lives in the state object, not scattered in the service layer**.

### Mandatory RCA Gate

```python
class ClosedState(IncidentState):
    def validate_entry(self, work_item_data: dict) -> None:
        if not work_item_data.get("rca"):
            raise ValueError("RCA record is missing")
        required = ["root_cause_category", "fix_applied", "prevention_steps",
                    "incident_start", "incident_end"]
        missing = [f for f in required if not work_item_data["rca"].get(f)]
        if missing:
            raise ValueError(f"RCA incomplete: missing {missing}")
```

The `update_status` endpoint catches `ValueError` and returns HTTP 400 — the frontend displays this as an actionable error message.

### MTTR Calculation

MTTR (Mean Time To Repair) is stored on the work item at closure:

```python
mttr_seconds = abs((rca.incident_end - rca.incident_start).total_seconds())
```

Using the RCA's `incident_start/end` rather than `work_item.start_time/end_time` gives a more accurate MTTR — the RCA author provides the precise window, accounting for incidents noticed after the fact.

### Concurrency Safety

- **PostgreSQL writes** use `WITH FOR UPDATE` (pessimistic row-level locking) during status transitions, preventing two concurrent requests from creating conflicting state changes
- **Redis debouncing** uses atomic SET NX — no Python-level locks needed
- **WebSocket broadcasts** use `asyncio.Lock` to protect the connection set during iteration

### Rate Limiter: Sliding Window in Redis

```python
pipe.zremrangebyscore(key, 0, window_start)  # evict old entries
pipe.zadd(key, {str(now): now})              # add current request
pipe.zcard(key)                               # count in window
pipe.expire(key, window_seconds)             # clean up
```

Pipelining makes this 4 Redis commands in one round-trip. The fail-open design (`except Exception: pass`) ensures rate limiter Redis failures don't cascade to block ingestion.

### MongoDB Indexing Strategy

```python
# For signal lookup by incident (most common query)
await signals.create_index([("work_item_id", 1)])

# For debounce window queries (component recency check)
await signals.create_index([("component_id", 1), ("timestamp", -1)])

# For time-range aggregations
await signals.create_index([("timestamp", -1)])
```

### Single-Worker Uvicorn

The backend runs with 1 Uvicorn worker (not multiple). This is a deliberate choice: the `asyncio.Queue` and `WebSocketManager` connection set are in-process memory. Multiple workers would mean separate queues and separate WebSocket sets, breaking debouncing and broadcasting.

**For horizontal scaling**: replace `asyncio.Queue` with Redis Streams or Kafka, and use Redis Pub/Sub for WebSocket fan-out. The service interface is unchanged — only the queue backend swaps.

---

## Implementation Plan (used during development)

```
Phase 1: Infrastructure
  [x] docker-compose.yml (postgres, mongodb, redis, backend, frontend)
  [x] backend requirements.txt + Dockerfile
  [x] frontend package.json + vite.config.js + Dockerfile + nginx.conf

Phase 2: Backend Core
  [x] config.py (Pydantic settings)
  [x] database.py (async engines + init functions)
  [x] models/db_models.py (SQLAlchemy ORM)
  [x] models/signal.py, incident.py, rca.py (Pydantic schemas)

Phase 3: Design Patterns
  [x] patterns/alert_strategy.py (Strategy: P0–P3)
  [x] patterns/incident_state.py (State: OPEN→CLOSED + RCA gate)
  [x] utils/retry.py (exponential backoff decorator)

Phase 4: Services
  [x] services/metrics_service.py (throughput counter + 5s reporter)
  [x] services/websocket_manager.py (connection set + broadcast)
  [x] services/ingestion_service.py (queue + workers + debounce)
  [x] services/incident_service.py (CRUD + state machine + RCA)

Phase 5: API Layer
  [x] api/signals.py (POST /api/signals, POST /api/signals/batch)
  [x] api/incidents.py (CRUD + /status + /rca + /signals)
  [x] api/health.py (GET /health, GET /metrics)
  [x] api/websocket_handler.py (WS /ws/dashboard)
  [x] middleware/rate_limiter.py (sliding window)
  [x] main.py (app assembly + lifespan)

Phase 6: Tests
  [x] tests/test_rca_validation.py (state machine RCA gate)
  [x] tests/test_alert_strategy.py (strategy selection)

Phase 7: Frontend
  [x] src/services/api.js (Axios REST client)
  [x] src/services/websocket.js (WS client + auto-reconnect)
  [x] src/components/MetricsBar.jsx
  [x] src/components/PriorityBadge.jsx, StatusBadge.jsx
  [x] src/components/LiveFeed.jsx (real-time WS event stream)
  [x] src/components/IncidentList.jsx (sorted by priority)
  [x] src/components/RCAForm.jsx (date pickers + validation)
  [x] src/components/IncidentDetail.jsx (signals tab + RCA tab)
  [x] src/components/Dashboard.jsx (list + filters + live feed)
  [x] src/App.jsx (root + WS connect + layout)

Phase 8: Scripts + Docs
  [x] scripts/seed_data.json (5-wave cascading failure scenario)
  [x] scripts/mock_failure_event.py (async simulation script)
  [x] README.md (architecture diagram + setup + backpressure)
  [x] PROMPTS.md (this file)
```
