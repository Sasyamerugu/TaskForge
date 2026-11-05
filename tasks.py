
import json
import time

from sqlalchemy import update

from database import SessionLocal
from models import Job
from cancellation import clear_cancellation


class JobCancelled(Exception):
    pass


def mark_cancelled(db, job_id):
    """
    Move a job from cancellation_requested to cancelled.
    Only this transition is allowed to finalize cancellation.
    """
    statement = (
        update(Job)
        .where(
            Job.id == job_id,
            Job.status == "cancellation_requested"
        )
        .values(
            status="cancelled",
            result=None,
            error=None
        )
    )

    result = db.execute(statement)
    db.commit()

    if result.rowcount > 0:
        clear_cancellation(job_id)


def check_cancellation(db, job_id):
    """
    Check the database for a cancellation request.
    The database is the authoritative source of cancellation state.
    """
    job = db.query(Job.status).filter(Job.id == job_id).first()

    if job is None:
        raise ValueError(f"Job {job_id} not found")

    if job.status in ("cancellation_requested", "cancelled"):
        if job.status == "cancellation_requested":
            mark_cancelled(db, job_id)
        else:
            clear_cancellation(job_id)

        raise JobCancelled("Job cancellation requested")


def execute_task(job_id: str):
    db = SessionLocal()

    try:
        job = db.query(Job).filter(Job.id == job_id).first()

        if job is None:
            raise ValueError(f"Job {job_id} not found")

        # Atomically claim either a new job or a retry attempt.
        claim = (
            update(Job)
            .where(
                Job.id == job_id,
                Job.status.in_(["queued", "retrying"])
            )
            .values(
                status="running",
                error=None
            )
        )

        claim_result = db.execute(claim)
        db.commit()

        if claim_result.rowcount == 0:
            check_cancellation(db, job_id)

            return {
                "job_id": job_id,
                "status": "not_started"
            }

        # Read the job after successfully claiming it.
        job = db.query(Job).filter(Job.id == job_id).first()

        task_type = job.task_type
        input_data = json.loads(job.input_data)

        check_cancellation(db, job_id)

        # Execute the requested task.
        if task_type == "sum":
            numbers = input_data.get("numbers", [])

            if not isinstance(numbers, list) or not numbers:
                raise ValueError(
                    "numbers must be a non-empty list"
                )

            if any(
                isinstance(n, bool) or not isinstance(n, (int, float))
                for n in numbers
            ):
                raise ValueError(
                    "numbers must contain only numeric values"
                )

            result_value = sum(numbers)

        elif task_type == "slow_sum":
            numbers = input_data.get("numbers", [])

            if not isinstance(numbers, list) or not numbers:
                raise ValueError(
                    "numbers must be a non-empty list"
                )

            if any(
                isinstance(n, bool) or not isinstance(n, (int, float))
                for n in numbers
            ):
                raise ValueError(
                    "numbers must contain only numeric values"
                )

            for _ in range(30):
                time.sleep(1)
                check_cancellation(db, job_id)

            result_value = sum(numbers)

        else:
            raise ValueError(
                f"Unsupported task type: {task_type}"
            )

        # Check cancellation immediately before completing.
        check_cancellation(db, job_id)

        # Complete only if the job is still in running state.
        completion = (
            update(Job)
            .where(
                Job.id == job_id,
                Job.status == "running"
            )
            .values(
                status="completed",
                result=json.dumps({"result": result_value}),
                error=None
            )
        )

        completion_result = db.execute(completion)
        db.commit()

        if completion_result.rowcount == 0:
            check_cancellation(db, job_id)

            return {
                "job_id": job_id,
                "status": "not_completed"
            }

        return {
            "job_id": job_id,
            "result": result_value
        }

    except JobCancelled:
        db.rollback()

        mark_cancelled(db, job_id)

        return {
            "job_id": job_id,
            "status": "cancelled"
        }

    except Exception as exc:
        db.rollback()

        # Mark the job retrying only if it is still running.
        failure = (
            update(Job)
            .where(
                Job.id == job_id,
                Job.status == "running"
            )
            .values(
                status="retrying",
                retry_count=Job.retry_count + 1,
                error=str(exc)
            )
        )

        failure_result = db.execute(failure)
        db.commit()

        if failure_result.rowcount == 0:
            # Cancellation may have arrived while the task was failing.
            try:
                check_cancellation(db, job_id)
            except JobCancelled:
                return {
                    "job_id": job_id,
                    "status": "cancelled"
                }

        # Let RQ handle the retry.
        raise

    finally:
        db.close()
