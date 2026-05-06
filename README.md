# Async Document Processing Workflow System

Production-style full stack assignment using async background processing with progress tracking.

## Stack

- Frontend: React + TypeScript (Vite)
- Backend: FastAPI (Python)
- Database: PostgreSQL
- Async jobs: Celery
- Broker + Pub/Sub: Redis

## Architecture Overview

1. User uploads one or more files from frontend.
2. FastAPI saves file + metadata in PostgreSQL and marks job as `queued`.
3. FastAPI enqueues `process_document` Celery task.
4. Celery worker executes multi-step pipeline and publishes progress events to Redis Pub/Sub (`progress:{document_id}`).
5. Frontend subscribes to FastAPI SSE endpoint (`/documents/{id}/progress`) for live updates.
6. Extracted result is stored in DB, reviewed/edited in UI, finalized, and exportable as JSON/CSV.

### Backend Layers

- `app/main.py`: API routes + SSE
- `app/services.py`: upload/list/export helpers
- `app/tasks.py`: async workflow logic and progress publishing
- `app/models.py`: SQLAlchemy entities
- `app/schemas.py`: response/request DTOs
- `app/redis_client.py`: Pub/Sub abstraction

### Workflow Stages Published

- `job_started`
- `document_parsing_started`
- `document_parsing_completed`
- `field_extraction_started`
- `field_extraction_completed`
- `job_completed`
- `job_failed`

## API Surface

- `POST /documents/upload` - upload one or more files
- `GET /documents` - list/search/filter/sort documents
- `GET /documents/{document_id}` - get details
- `GET /documents/{document_id}/progress` - SSE progress stream
- `POST /documents/{document_id}/retry` - retry failed job
- `PUT /documents/{document_id}/review` - save edited output
- `POST /documents/{document_id}/finalize` - finalize completed record
- `GET /documents/export/json` - export finalized as JSON
- `GET /documents/export/csv` - export finalized as CSV

## Local Setup (Without Docker)

### Prerequisites

- Python 3.11+
- Node 20+
- PostgreSQL
- Redis

### Backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

### Worker

```bash
cd backend
celery -A app.tasks worker --loglevel=info
```

### Frontend

```bash
cd frontend
copy .env.example .env
npm install
npm run dev
```

## Docker Compose (Bonus)

```bash
copy backend\.env.example backend\.env
docker compose up
```

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`

## Test Samples

Use sample input files from `samples/`:
- `sample_invoice.txt`
- `sample_resume.txt`

Sample export outputs:
- `sample_export.json`
- `sample_export.csv`

## Assumptions

- File storage is local filesystem (`backend/storage`).
- Processing logic is intentionally mocked/simulated but async infrastructure is real.
- Finalization is allowed only after successful completion.

## Tradeoffs

- Used SQLAlchemy `create_all` for quick setup instead of full migration workflow.
- SSE chosen for simpler one-way realtime updates; WebSockets can be added later.
- Minimal UI to focus on workflow correctness and async architecture.

## Limitations

- No auth/multi-tenant access control.
- No object storage abstraction (e.g., S3) yet.
- Retry is simple and does not yet include strict idempotency guards.
- No cancellation endpoint yet.

## Demo Video

Record a 3-5 min walkthrough and add link here:
- `<add-demo-video-link>`

## AI Usage Note

AI tooling was used to accelerate scaffolding and implementation support.
