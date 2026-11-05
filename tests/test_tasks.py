import json
import pytest
import tasks

from models import Job


def create_test_job(client, monkeypatch, task_type, input_data):
    def fake_enqueue(*args, **kwargs):
        pass

    monkeypatch.setattr(
        "main.high_queue.enqueue",
        fake_enqueue
    )

    response = client.post(
        "/jobs",
        json={
            "task_type": task_type,
            "input_data": input_data,
            "priority": "high"
        }
    )

    assert response.status_code == 200

    return response.json()["id"]


# TEST 14: Successful background execution
def test_execute_sum_task(client, monkeypatch, test_session_local):
    monkeypatch.setattr(tasks, "SessionLocal", test_session_local)

    job_id = create_test_job(
        client, monkeypatch, "sum",
        {"numbers": [10, 20, 30]}
    )

    result = tasks.execute_task(job_id)

    assert result["result"] == 60

    response = client.get(f"/jobs/{job_id}")

    assert response.json()["status"] == "completed"
    assert json.loads(response.json()["result"]) == {"result": 60}


# TEST 15: Invalid numeric input
def test_execute_invalid_numbers(client, monkeypatch, test_session_local):
    monkeypatch.setattr(tasks, "SessionLocal", test_session_local)

    job_id = create_test_job(
        client, monkeypatch, "sum",
        {"numbers": ["hello", "world"]}
    )

    with pytest.raises(ValueError, match="numbers must contain only numeric values"):
        tasks.execute_task(job_id)

    response = client.get(f"/jobs/{job_id}")

    assert response.json()["status"] == "retrying"
    assert response.json()["retry_count"] == 1


# TEST 16: Cancellation before execution
def test_execute_cancelled_job(client, monkeypatch, test_session_local):
    monkeypatch.setattr(tasks, "SessionLocal", test_session_local)
    monkeypatch.setattr(tasks, "clear_cancellation", lambda job_id: None)

    job_id = create_test_job(
        client, monkeypatch, "sum",
        {"numbers": [10, 20]}
    )

    with test_session_local() as db:
        job = db.query(Job).filter(Job.id == job_id).first()
        job.status = "cancellation_requested"
        db.commit()

    result = tasks.execute_task(job_id)

    assert result["status"] == "cancelled"

    response = client.get(f"/jobs/{job_id}")

    assert response.json()["status"] == "cancelled"