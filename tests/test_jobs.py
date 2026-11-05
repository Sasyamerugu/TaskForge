def test_create_job(client, monkeypatch):
    # Mock Redis queue submission.
    def fake_enqueue(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.main.high_queue.enqueue",
        fake_enqueue
    )

    response = client.post(
        "/jobs",
        json={
            "task_type": "sum",
            "input_data": {
                "numbers": [10, 20, 30]
            },
            "priority": "high"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["task_type"] == "sum"
    assert data["status"] == "queued"
    assert data["priority"] == "high"
    assert data["retry_count"] == 0
    assert data["id"] is not None

def test_idempotency_prevents_duplicate_jobs(client, monkeypatch):
    enqueue_calls = []

    def fake_enqueue(*args, **kwargs):
        enqueue_calls.append(kwargs)

    monkeypatch.setattr(
        "app.main.high_queue.enqueue",
        fake_enqueue
    )

    headers = {"Idempotency-Key": "test-key-123"}

    payload = {
        "task_type": "sum",
        "input_data": {"numbers": [10, 20]},
        "priority": "high"
    }

    first_response = client.post(
        "/jobs", json=payload, headers=headers
    )

    second_response = client.post(
        "/jobs", json=payload, headers=headers
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_job = first_response.json()
    second_job = second_response.json()

    assert first_job["id"] == second_job["id"]
    assert len(enqueue_calls) == 1

def test_idempotency_key_conflict(client, monkeypatch):
    def fake_enqueue(*args, **kwargs):
        pass

    monkeypatch.setattr(
        "app.main.high_queue.enqueue",
        fake_enqueue
    )

    headers = {"Idempotency-Key": "same-key"}

    client.post(
        "/jobs",
        json={
            "task_type": "sum",
            "input_data": {"numbers": [10, 20]},
            "priority": "high"
        },
        headers=headers
    )

    response = client.post(
        "/jobs",
        json={
            "task_type": "sum",
            "input_data": {"numbers": [100, 200]},
            "priority": "high"
        },
        headers=headers
    )

    assert response.status_code == 409

def test_get_job_by_id(client, monkeypatch):
    def fake_enqueue(*args, **kwargs):
        pass

    monkeypatch.setattr(
        "app.main.high_queue.enqueue",
        fake_enqueue
    )

    create_response = client.post(
        "/jobs",
        json={
            "task_type": "sum",
            "input_data": {"numbers": [10, 20]},
            "priority": "high"
        }
    )

    job_id = create_response.json()["id"]

    response = client.get(f"/jobs/{job_id}")

    assert response.status_code == 200
    assert response.json()["id"] == job_id
    assert response.json()["task_type"] == "sum"
    assert response.json()["status"] == "queued"

def test_get_nonexistent_job(client):
    response = client.get("/jobs/nonexistent-job-id")

    assert response.status_code == 404

def test_create_job_with_empty_task_type(client):
    response = client.post(
        "/jobs",
        json={
            "task_type": "",
            "input_data": {"numbers": [10, 20]},
            "priority": "high"
        }
    )

    assert response.status_code == 422

def test_create_job_with_invalid_priority(client):
    response = client.post(
        "/jobs",
        json={
            "task_type": "sum",
            "input_data": {"numbers": [10, 20]},
            "priority": "urgent"
        }
    )

    assert response.status_code == 422


def test_list_jobs(client, monkeypatch):
    def fake_enqueue(*args, **kwargs):
        pass

    monkeypatch.setattr("app.main.high_queue.enqueue", fake_enqueue)

    client.post(
        "/jobs",
        json={
            "task_type": "sum",
            "input_data": {"numbers": [10, 20]},
            "priority": "high"
        }
    )

    response = client.get("/jobs")

    assert response.status_code == 200
    assert len(response.json()) == 1

def test_cancel_queued_job(client, monkeypatch):
    def fake_enqueue(*args, **kwargs):
        pass

    monkeypatch.setattr("app.main.high_queue.enqueue", fake_enqueue)

    create_response = client.post(
        "/jobs",
        json={
            "task_type": "sum",
            "input_data": {"numbers": [10, 20]},
            "priority": "high"
        }
    )

    job_id = create_response.json()["id"]

    response = client.delete(f"/jobs/{job_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "cancellation_requested"

def test_cancel_completed_job(client, monkeypatch):
    def fake_enqueue(*args, **kwargs):
        pass

    monkeypatch.setattr("app.main.high_queue.enqueue", fake_enqueue)

    create_response = client.post(
        "/jobs",
        json={
            "task_type": "sum",
            "input_data": {"numbers": [10, 20]},
            "priority": "high"
        }
    )

    job_id = create_response.json()["id"]

    import app.main as main
    from app.models import Job

    test_get_db = main.app.dependency_overrides[main.get_db]
    db_generator = test_get_db()
    db = next(db_generator)

    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        job.status = "completed"
        db.commit()
    finally:
        db_generator.close()

    response = client.delete(f"/jobs/{job_id}")

    assert response.status_code == 409

def test_priority_routes_to_correct_queue(client, monkeypatch):
    calls = {"high": 0, "medium": 0, "low": 0}

    def fake_high(*args, **kwargs):
        calls["high"] += 1

    def fake_medium(*args, **kwargs):
        calls["medium"] += 1

    def fake_low(*args, **kwargs):
        calls["low"] += 1

    monkeypatch.setattr("app.main.high_queue.enqueue", fake_high)
    monkeypatch.setattr("app.main.medium_queue.enqueue", fake_medium)
    monkeypatch.setattr("app.main.low_queue.enqueue", fake_low)

    response = client.post(
        "/jobs",
        json={
            "task_type": "sum",
            "input_data": {"numbers": [10, 20]},
            "priority": "low"
        }
    )

    assert response.status_code == 200
    assert calls == {"high": 0, "medium": 0, "low": 1}


