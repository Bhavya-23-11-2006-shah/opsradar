# OpsRadar — AI-powered operational intelligence & early warning

OpsRadar ingests messy operational exports (orders, deliveries, complaints, reviews, inventory, sales), cleans and
links them, detects recurring issues, complaint spikes, delivery risk, inventory risk and anomalies, and turns the
detected problems into evidence-backed findings with a recommended action.

The product is built against **CONTRACT v1**, which is frozen: field names, casing, enums, date formats and error
envelopes are fixed. Every number in a finding is computed by the deterministic engine; the LLM may only propose
hypotheses and wording, never facts.

```
backend/   FastAPI + pandas detection engine, SQLite persistence, provider-agnostic LLM layer
frontend/  Next.js App Router UI (TypeScript, Tailwind, Recharts, Zustand, zod)
```

## Quick start

### 1. Backend (Python 3.11+)

```bash
cd backend
python -m venv .venv
# Windows: ./.venv/Scripts/activate      macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- API docs: <http://localhost:8000/docs>
- Health: `GET http://localhost:8000/api/health` → `{"ok":true,"contractVersion":"1","llmMode":"template"}`

### 2. Frontend (Node 18+)

```bash
cd frontend
npm install
cp .env.example .env.local     # already present in this workspace
npm run dev                    # http://localhost:3000
```

`.env.local`:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_USE_MOCK=false
```

`NEXT_PUBLIC_API_URL` is the only source of the API origin. `NEXT_PUBLIC_USE_MOCK=true` replays the JSON files in
`frontend/mocks/` (exported real responses) and needs no backend.

> Do not run two Next dev servers from the same `frontend/` directory at once: they share `.next`. Stop one before
> starting the other (or build first and use `npm start`).

## Demo walkthrough

1. Open <http://localhost:3000>. Click **Load fashion demo** (or **skincare demo**). Six CSVs are generated and ingested.
2. The column mapping is pre-filled from column-name detection. Review the confidence badges and click
   **Confirm mapping**.
3. Click **Run analysis**. The pipeline reports Cleaning → Linking → Detecting → Assessing → Recommendations, polled once
   per second; the demo finishes in a couple of seconds.
4. Read **Data quality**: health score, missing values, duplicates, and inconsistent rows (delivered before shipped,
   negative stock), each with concrete row IDs.

The fashion demo plants these problems:

| Planted problem | Where it surfaces |
| --- | --- |
| Damaged-packaging complaints concentrated on MetroDash / WH-North / Leeds | Critical recurring-issue findings |
| 36 complaints on Tailored Shorts in the last four days | Complaint-spike finding |
| Late deliveries at WH-South (recent late share above baseline) | Delivery-risk finding, orders at risk |
| Wide-Leg Trousers ~3 days of cover, 3 items at/below reorder | Inventory-risk findings |
| Daily sales drop for Ribbed Cardigan | Anomaly finding |
| 8 duplicate rows, missing values, negative stock, delivered-before-shipped | Data-quality panel |

5. **Overview** shows KPIs, annotated trends, category breakdown and risk by courier/warehouse/city; filters refetch
   the overview.
6. **Findings** → open one. Verified facts are green, AI hypotheses are purple with confidence and a "requires
   investigation" label, and the evidence table lists every row (the list endpoint caps evidence at 5, the detail
   endpoint returns all).
7. **Approve / Reject / Escalate** with a note. Status becomes `investigating` / `rejected` / `escalated`; create an
   investigation task; the action is written to the log. **Action Tracker** shows the kanban (drag to change status),
   the full decision history and a CSV export.
8. **Management Report** generates markdown from the current dataset, with **Download .md** and **Print / PDF**.

The hidden contract self-test lives at <http://localhost:3000/dev/contract>: it calls every endpoint in sequence and
validates each response against the zod mirrors, printing any failing JSON path.

## API

All responses are camelCase JSON. Dates are ISO `YYYY-MM-DD`. Enums are lowercase. Arrays are never `null`. Every
non-2xx response is `{"error": string, "detail": string}`.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Contract version + LLM mode |
| POST | `/api/demo/generate` | Generate a seeded demo dataset (`fashion` \| `skincare`) |
| POST | `/api/upload` | Multipart upload, field name `files` |
| POST | `/api/map-schema` | Confirm the canonical column mapping |
| POST | `/api/analyze/{datasetId}` | Start analysis (returns immediately, runs in background) |
| GET | `/api/progress/{datasetId}` | `status`, `step`, `percent`, `message` |
| GET | `/api/quality/{datasetId}` | Missing / duplicate / inconsistent rows + health score |
| GET | `/api/overview/{datasetId}` | KPIs, trends, categories, risk distribution, filters |
| GET | `/api/findings/{datasetId}` | Findings list (`?type=&severity=&status=&search=`) |
| GET | `/api/findings/{datasetId}/{findingId}` | Full finding incl. all evidence rows |
| POST | `/api/findings/{datasetId}/{findingId}/decision` | `approve` → investigating, `reject` → rejected, `escalate` → escalated |
| PATCH | `/api/findings/{datasetId}/{findingId}/status` | Direct status change |
| POST | `/api/findings/{datasetId}/{findingId}/task` | Create an investigation task |
| GET | `/api/actions/{datasetId}` | Action log + tasks |
| POST | `/api/report/{datasetId}` | Markdown management report |

### curl examples

```bash
# Health
curl http://localhost:8000/api/health

# Demo dataset (capture the datasetId)
curl -s -X POST http://localhost:8000/api/demo/generate \
  -H 'Content-Type: application/json' -d '{"industry":"fashion"}'

# Upload your own files — field name MUST be "files"
curl -s -X POST http://localhost:8000/api/upload \
  -F 'files=@orders.csv' -F 'files=@complaints.xlsx'

# Confirm the mapping (use suggestedMapping from upload/demo)
curl -s -X POST http://localhost:8000/api/map-schema \
  -H 'Content-Type: application/json' \
  -d '{"datasetId":"demo-fashion-95c27e367b","mapping":{"files":[]}}'

# Start analysis, then poll
curl -s -X POST http://localhost:8000/api/analyze/demo-fashion-95c27e367b
curl -s http://localhost:8000/api/progress/demo-fashion-95c27e367b

# Quality, overview, findings
curl -s http://localhost:8000/api/quality/demo-fashion-95c27e367b
curl -s 'http://localhost:8000/api/overview/demo-fashion-95c27e367b?courier=MetroDash'
curl -s 'http://localhost:8000/api/findings/demo-fashion-95c27e367b?severity=critical'

# Decision, direct status change, task
curl -s -X POST http://localhost:8000/api/findings/demo-fashion-95c27e367b/<findingId>/decision \
  -H 'Content-Type: application/json' \
  -d '{"decision":"approve","note":"Approved for investigation"}'

curl -s -X PATCH http://localhost:8000/api/findings/demo-fashion-95c27e367b/<findingId>/status \
  -H 'Content-Type: application/json' -d '{"status":"resolved"}'

curl -s -X POST http://localhost:8000/api/findings/demo-fashion-95c27e367b/<findingId>/task \
  -H 'Content-Type: application/json' -d '{"title":"Call carrier about damaged parcels"}'

# Actions and report
curl -s http://localhost:8000/api/actions/demo-fashion-95c27e367b
curl -s -X POST http://localhost:8000/api/report/demo-fashion-95c27e367b
```

Error envelope example:

```bash
curl -s http://localhost:8000/api/findings/demo-fashion-95c27e367b/nope
# {"error":"not_found","detail":"Finding nope not found"}
```

## How detection works

- **Cleaning** standardises types, trims text, parses dates, drops exact duplicates (keeping row IDs), flags missing
  required values and impossible values (delivered before shipped, negative stock).
- **Linking** joins orders → deliveries, complaints/reviews → products, inventory → sales using the confirmed mapping
  plus fuzzy product-name matching.
- **Recurring issues** group complaints by category and shared factor (product, courier, warehouse, city), and score
  volume against the rest of the data.
- **Complaint spikes** compare the trailing 7 days with the prior baseline per product; **anomalies** use a robust
  z-score on daily complaint sums.
- **Delivery risk** computes one per-order probability from the courier's and warehouse's recent late rates, with an
  imminent-deadline nudge and an overdue floor, then groups flagged orders.
- **Inventory risk** computes days of cover from stock and recent daily sales.
- **Scoring** combines volume, value, source breadth, trend, confidence and entity spread into 0–100 risk and
  `critical` ≥ 80, `high` ≥ 60, `medium` ≥ 40, `low` otherwise.
- **Facts vs hypotheses**: facts and recommendations are template-generated from computed values; AI hypotheses are
  validated, confidence-clamped, numeric-token-checked, and fall back to templates if the provider is unavailable.

## LLM configuration (optional)

`backend/.env` or environment variables:

```dotenv
LLM_PROVIDER=none          # none | openai | anthropic | openai_compatible
LLM_API_KEY=
LLM_MODEL=
LLM_BASE_URL=              # for openai_compatible
```

With `none` the product is fully functional in template mode. Provider failures never break a request: the engine
falls back to templates, and hypotheses are cached in `backend/data/cache/ai_cache.json`.

## Tests and contract fixtures

```bash
cd backend
./.venv/Scripts/python.exe -m pytest tests -q      # Windows
# python -m pytest tests -q                        # macOS/Linux

./.venv/Scripts/python.exe scripts/export_examples.py
```

`backend/contract_examples/` holds real responses for every endpoint (used as the frontend's mock fixtures and as
living contract documentation). The suite covers schema round-trips, the mapper, every detector, fact/hypothesis
separation and decision mapping.

## Frontend checks

```bash
cd frontend
npx tsc --noEmit
npm run build
```

## Notes

- `pandas==3.0.0` is pinned in this environment because another wheel was blocked by a Windows Application Control
  policy. `scipy` is a dependency but is kept off the request path (the two-proportion test uses `math.erfc`) so a cold
  import cannot stall the first analysis.
- SQLite lives at `backend/data/opsradar.db`; uploaded and demo raw files are kept under
  `backend/data/datasets/{datasetId}/raw`.
- CORS defaults to `http://localhost:3000` (override with `CORS_ORIGINS`).
