
import json
from uuid import uuid4

from fastapi import FastAPI, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from database import Base, engine, SessionLocal
from models import Job
from schemas import JobCreate, JobResponse
from queue_config import (
                        high_queue,
                        medium_queue,
                        low_queue,
                        job_retry
)
from tasks import execute_task
from callbacks import handle_job_failure

from cancellation import request_cancellation
from sqlalchemy import update

from sqlalchemy.exc import IntegrityError


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TaskForge",
    description="A background job processing system",
    version="0.1.0"
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/health")
def health_check():
    return {"status": "healthy"}



@app.post("/jobs", response_model=JobResponse)
def create_job(
    request: JobCreate,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        min_length=1,
        max_length=255
    ),
    db: Session = Depends(get_db)
):
    input_json = json.dumps(request.input_data, sort_keys=True)

    # 1. Check whether this key has already been used.
    if idempotency_key is not None:
        existing_job = (
            db.query(Job)
            .filter(Job.idempotency_key == idempotency_key)
            .first()
        )

        if existing_job is not None:
            # A key must not be reused for a different operation.
            if (
                existing_job.task_type != request.task_type
                or json.loads(existing_job.input_data) != request.input_data
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Idempotency key already used with a different request"
                )

            # Return the original job without creating or enqueueing another.
            return existing_job

    # 2. Create a new job.
    job = Job(
        id=str(uuid4()),
        task_type=request.task_type,
        input_data=input_json,
        status="queued",
        idempotency_key=idempotency_key,
        priority=request.priority,
        effective_priority=request.priority
)

    db.add(job)

    try:
        db.commit()
        db.refresh(job)

    except IntegrityError:
        db.rollback()

        # Another simultaneous request may have inserted this key first.
        if idempotency_key is not None:
            existing_job = (
                db.query(Job)
                .filter(Job.idempotency_key == idempotency_key)
                .first()
            )

            if existing_job is not None:
                if (
                    existing_job.task_type != request.task_type
                    or json.loads(existing_job.input_data) != request.input_data
                ):
                    raise HTTPException(
                        status_code=409,
                        detail="Idempotency key already used with a different request"
                    )

                return existing_job

        raise

    # 3. Enqueue only the newly created job.
    try:
        priority_queues = {
            "high": high_queue,
            "medium": medium_queue,
            "low": low_queue
        }

        selected_queue = priority_queues[job.effective_priority]

        selected_queue.enqueue(
            execute_task,
            job.id,
            job_id=job.id,
            retry=job_retry,
            on_failure=handle_job_failure
        )

    except Exception as exc:
        job.status = "failed"
        job.error = f"Queue submission failed: {exc}"
        db.commit()

        raise HTTPException(
            status_code=503,
            detail="Could not submit job to the queue"
        )

    return job




@app.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return job


@app.delete("/jobs/{job_id}")
def cancel_job(
    job_id: str,
    db: Session = Depends(get_db)
):
    statement = (
        update(Job)
        .where(
            Job.id == job_id,
            Job.status.in_(["queued", "running", "retrying"])
        )
        .values(status="cancellation_requested")
    )

    result = db.execute(statement)
    db.commit()

    if result.rowcount == 0:
        job = db.query(Job).filter(Job.id == job_id).first()

        if job is None:
            raise HTTPException(
                status_code=404,
                detail="Job not found"
            )

        raise HTTPException(
            status_code=409,
            detail=f"Job cannot be cancelled from status: {job.status}"
        )

    request_cancellation(job_id)

    return {
        "message": "Cancellation requested",
        "job_id": job_id,
        "status": "cancellation_requested"
    }
    
@app.get("/jobs")
def list_jobs(db: Session = Depends(get_db)):
    return db.query(Job).order_by(Job.created_at.desc()).all()
