from sqlalchemy import update

from database import SessionLocal
from models import Job


def handle_job_failure(job, connection, exc_type, exc_value, traceback):
    db = SessionLocal()

    try:
        print(f"FAILURE CALLBACK TRIGGERED: {job.id}, exception: {exc_type.__name__}")
        job_id = job.args[0] if job.args else None

        if not job_id:
            return

        # RQ will retry the job if retries remain.
        if job.retries_left is not None and job.retries_left > 0:

            # A hard worker crash leaves the DB status as running.
            # Move it to retrying so the next attempt can claim it.
            statement = (
                update(Job)
                .where(
                    Job.id == job_id,
                    Job.status == "running"
                )
                .values(
                    status="retrying",
                    retry_count=Job.retry_count + 1,
                    error=str(exc_value)
                )
            )

        else:
            # No retries remain: mark the job as finally failed.
            statement = (
                update(Job)
                .where(
                    Job.id == job_id,
                    Job.status.in_(["queued", "running", "retrying"])
                )
                .values(
                    status="failed",
                    error=str(exc_value)
                )
            )

        db.execute(statement)
        print(f"DATABASE STATUS UPDATE ATTEMPTED: {job_id}")
        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()