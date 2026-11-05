from types import SimpleNamespace

from app.callbacks import handle_job_failure
from app.models import Job


# TEST 17: Worker crash with retries remaining
def test_failure_callback_marks_job_retrying(
    client, monkeypatch, test_session_local
):
    def fake_enqueue(*args, **kwargs):
        pass

    monkeypatch.setattr("app.main.high_queue.enqueue", fake_enqueue)
    monkeypatch.setattr(
        "app.callbacks.SessionLocal",
        test_session_local
    )

    response = client.post(
        "/jobs",
        json={
            "task_type": "sum",
            "input_data": {"numbers": [10, 20]},
            "priority": "high"
        }
    )

    job_id = response.json()["id"]

    with test_session_local() as db:
        job = db.query(Job).filter(Job.id == job_id).first()
        job.status = "running"
        db.commit()

    fake_job = SimpleNamespace(
        id="rq-test-job",
        args=(job_id,),
        retries_left=2
    )

    error = ValueError("Simulated worker crash")

    handle_job_failure(
        fake_job,
        None,
        ValueError,
        error,
        None
    )

    with test_session_local() as db:
        job = db.query(Job).filter(Job.id == job_id).first()

        assert job.status == "retrying"
        assert job.retry_count == 1


# TEST 18: Retry exhaustion marks job failed
def test_failure_callback_marks_job_failed(
    client, monkeypatch, test_session_local
):
    def fake_enqueue(*args, **kwargs):
        pass

    monkeypatch.setattr("app.main.high_queue.enqueue", fake_enqueue)
    monkeypatch.setattr(
        "app.callbacks.SessionLocal",
        test_session_local
    )

    response = client.post(
        "/jobs",
        json={
            "task_type": "sum",
            "input_data": {"numbers": [10, 20]},
            "priority": "high"
        }
    )

    job_id = response.json()["id"]

    with test_session_local() as db:
        job = db.query(Job).filter(Job.id == job_id).first()
        job.status = "running"
        db.commit()

    fake_job = SimpleNamespace(
        id="rq-test-job",
        args=(job_id,),
        retries_left=0
    )

    error = ValueError("Retries exhausted")

    handle_job_failure(
        fake_job,
        None,
        ValueError,
        error,
        None
    )

    with test_session_local() as db:
        job = db.query(Job).filter(Job.id == job_id).first()

        assert job.status == "failed"
        assert job.error == "Retries exhausted"



