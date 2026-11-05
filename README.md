# TaskForge — Background Job Processing System

A backend system that allows clients to submit background jobs that are processed asynchronously by independent worker processes, instead of making clients wait for the work to finish.

TaskForge uses FastAPI, Redis, RQ, and SQLite to manage job submission, execution, status tracking, retries, priorities, and cancellation.

## Problem It Solves

When a client submits work that takes time, making them wait for the operation to finish creates a poor user experience and limits scalability.

TaskForge solves this by accepting job submissions, responding immediately with a job ID, and processing the work in the background. Clients can check job status and results separately.

This follows the background job processing pattern used by systems such as Celery, Sidekiq, and AWS SQS with Lambda.

## Architecture

```text
Client → FastAPI → SQLite (create job record)
                      |
                      v
                 Redis Queue
                      |
                      v
                 RQ Worker
                      |
                 Execute Task
                      |
                      v
              Update SQLite Status

Client → FastAPI (GET job status) → SQLite
```

### Two Independent Process Types

**API (FastAPI)**
- Accepts and validates job submissions.
- Stores job records in SQLite.
- Enqueues jobs through Redis and RQ.
- Provides endpoints to retrieve and cancel jobs.

**Worker (RQ)**
- Retrieves jobs from Redis.
- Executes tasks asynchronously.
- Updates job status and results.
- Handles retries, failures, and cancellation checks.

The API and worker operate as separate processes and communicate through Redis and the shared database.

## Tech Stack

| Component | Technology | Purpose |
|---|---|---|
| API framework | FastAPI | REST API and request validation |
| Job queue | Redis | Queue storage |
| Worker framework | RQ | Background job execution |
| Database | SQLite | Persistent job records |
| ORM | SQLAlchemy | Database operations |
| Migrations | Alembic | Schema versioning |
| Testing | pytest | Automated testing |
| Containerization | Docker | Application containers |
| Orchestration | Docker Compose | Runs API, Redis, and worker |
| Language | Python 3.12 | Application development |

## Project Structure

```text
TaskForge/
├── main.py                 # FastAPI application and endpoints
├── tasks.py                # Background task execution
├── models.py               # SQLAlchemy job model
├── schemas.py              # Pydantic schemas
├── database.py             # Database configuration
├── queue_config.py         # Redis and RQ configuration
├── callbacks.py             # Job failure handling
├── cancellation.py         # Cancellation coordination
├── migrations/             # Alembic migrations
├── tests/
│   ├── conftest.py
│   ├── test_health.py
│   ├── test_jobs.py
│   ├── test_tasks.py
│   └── test_callbacks.py
├── Dockerfile.worker
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## What's Built — Feature Checklist

### Core Pipeline
- FastAPI application with health-check endpoint.
- POST `/jobs` — submits background jobs.
- GET `/jobs` — retrieves job records.
- GET `/jobs/{job_id}` — retrieves an individual job.
- DELETE `/jobs/{job_id}` — requests job cancellation.
- Redis-backed job queues using RQ.
- SQLite database with SQLAlchemy.
- Database migrations using Alembic.
- Separate API and worker processes.

### Job Types
- **sum:** Calculates the sum of a list of numbers.
- **slow_sum:** Simulates a long-running task and calculates the sum, with cancellation checks.

*These are currently basic testing tasks used to verify the job-processing infrastructure. More practical job types will be implemented in future iterations.*

### Reliability and Job Management
- Job lifecycle tracking: queued, running, completed, retrying, failed, cancellation_requested, and cancelled.
- Automatic retries using RQ, with up to 3 retries.
- Failure callbacks to update job status.
- Three priority queues: high, medium, and low.
- Priority-based worker queue consumption.
- Job cancellation using database status and Redis cancellation signals.
- Idempotency using unique keys.
- Conflict detection for reused idempotency keys with different payloads.

### Testing
- pytest-based automated tests.
- API, worker execution, cancellation, priority, and failure callback tests.
- 17 automated tests passing.

### Containerization
- Dockerfile for the application.
- Docker Compose setup for API, Redis, and worker.
- Shared persistent volume for the SQLite database.
- Redis health checks and service dependency management.

## Current Limitations / Future Improvements

- Replace temporary testing tasks with practical background operations.
- Add authentication and authorization.
- Introduce rate limiting.
- Improve production deployment and monitoring.
- Consider migrating to PostgreSQL or MySQL for production use.

## How to Run Locally

### 1. Create and activate a virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Start Redis

Make sure Redis is running locally or configure the Redis connection using `REDIS_URL`.

### 4. Start the API

```powershell
uvicorn main:app --reload
```

### 5. Start the worker

In a separate terminal:

```powershell
rq worker --with-scheduler high medium low
```

## Run Using Docker Compose

Build and start all services:

```powershell
docker compose up --build -d
```

Check running containers:

```powershell
docker compose ps
```

View logs:

```powershell
docker compose logs -f
```

Stop services:

```powershell
docker compose down
```

## How to Test the Full Flow

1. Open `http://localhost:8000/health` to check whether the API is running.
2. Open `http://localhost:8000/docs` to access Swagger UI.
3. Submit a job using POST `/jobs`.

Example request:

```json
{
  "task_type": "sum",
  "input_data": {
    "numbers": [10, 20, 30, 40]
  },
  "priority": "medium"
}
```

4. The API returns a job ID immediately.
5. The worker retrieves and executes the job.
6. Use GET `/jobs/{job_id}` to check its status and result.

Expected result after successful execution:

```json
{
  "status": "completed",
  "result": {
    "result": 100
  }
}
```

The `slow_sum` task can also be used to observe long-running execution and cancellation behaviour.

---

**TaskForge demonstrates an asynchronous background job processing system with independent workers, Redis-based queues, retries, priority handling, cancellation, idempotency, and persistent job tracking.**