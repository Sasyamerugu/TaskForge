from app.queue_config import redis_connection


def cancellation_key(job_id: str) -> str:
    return f"taskforge:cancel:{job_id}"


def request_cancellation(job_id: str):
    redis_connection.set(
        cancellation_key(job_id),
        "1",
        ex=3600
    )


def is_cancellation_requested(job_id: str) -> bool:
    return redis_connection.exists(cancellation_key(job_id)) == 1


def clear_cancellation(job_id: str):
    redis_connection.delete(cancellation_key(job_id))

