import asyncio
import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.app.core.scheduler import job_scheduler
from backend.app.core.task_runner import task_runner
from backend.app.db.database import SessionLocal
from backend.app.main import app
from backend.app.models.application import Application, VALID_STATUSES
from backend.app.models.job import Job
from backend.app.services.application_service import application_service

client = TestClient(app)


def test_status_lifecycle_and_history_logging():
    """
    Phase 40: Test lifecycle state progression, status history audit recording,
    and rejection of invalid statuses.
    """
    with SessionLocal() as db_session:
        uid = uuid.uuid4().hex[:8]
        test_job = Job(
            title=f"Full Stack Engineer {uid}",
            company="Automation Labs",
            location="Remote",
            remote=True,
            description="Looking for Full Stack engineer with Python and React.",
            url=f"data:text/html,<html><body><h1>Job Form</h1></body></html><!-- {uid} -->",
            source="greenhouse"
        )
        db_session.add(test_job)
        db_session.commit()
        db_session.refresh(test_job)

        now = datetime.now(timezone.utc)
        app_record = Application(
            job_id=test_job.id,
            status="READY",
            application_url=test_job.url,
            source="greenhouse",
            filled_fields={"first_name": "Test"},
            unfilled_fields=[],
            status_history=[{
                "from_status": None,
                "to_status": "READY",
                "timestamp": now.isoformat(),
                "actor": "system",
                "note": "Initial draft prepared"
            }],
            created_at=now,
            updated_at=now
        )
        db_session.add(app_record)
        db_session.commit()
        db_session.refresh(app_record)

        # 1. Transition READY -> APPROVED via approve_application
        approved_app = application_service.approve_application(
            db=db_session,
            app_id=app_record.id,
            note="Candidate reviewed and approved draft"
        )
        assert approved_app.status == "APPROVED"
        assert approved_app.approved_at is not None
        assert len(approved_app.status_history) == 2
        assert approved_app.status_history[-1]["from_status"] == "READY"
        assert approved_app.status_history[-1]["to_status"] == "APPROVED"

        # 2. Transition APPROVED -> INTERVIEW via API
        resp = client.post(
            f"/applications/{app_record.id}/status",
            json={
                "status": "INTERVIEW",
                "note": "HR invited to round 1 technical screen",
                "actor": "user",
                "interview_details": {
                    "round": "Technical Screen",
                    "date": "2026-09-15",
                    "interviewer": "Alice Smith"
                }
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "INTERVIEW"
        assert data["interview_details"]["round"] == "Technical Screen"
        assert len(data["status_history"]) == 3

        # 3. Transition INTERVIEW -> OFFER via API
        resp = client.post(
            f"/applications/{app_record.id}/status",
            json={
                "status": "OFFER",
                "note": "Received offer letter!",
                "actor": "user"
            }
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "OFFER"
        assert len(resp.json()["status_history"]) == 4

        # 4. Verify GET /applications/{id}/history returns complete audit log
        hist_resp = client.get(f"/applications/{app_record.id}/history")
        assert hist_resp.status_code == 200
        history = hist_resp.json()
        assert len(history) == 4
        assert history[0]["to_status"] == "READY"
        assert history[1]["to_status"] == "APPROVED"
        assert history[2]["to_status"] == "INTERVIEW"
        assert history[3]["to_status"] == "OFFER"

        # 5. Invalid status rejection
        invalid_resp = client.post(
            f"/applications/{app_record.id}/status",
            json={"status": "INVALID_RANDOM_STAGE"}
        )
        assert invalid_resp.status_code == 400
        assert "Invalid status" in invalid_resp.json()["detail"]


def test_async_task_runner_execution():
    """
    Phase 42: Test background task runner executes coroutines asynchronously,
    tracks status, progress, and results.
    """
    async def _test():
        async def sample_task(multiplier: int):
            await asyncio.sleep(0.05)
            return {"result": 42 * multiplier}

        task_id = task_runner.submit_task("sample_multiplier_task", sample_task, multiplier=2)
        assert task_id is not None

        # Wait for completion
        for _ in range(25):
            info = task_runner.get_task(task_id)
            if info and info.status in ["SUCCESS", "FAILED"]:
                break
            await asyncio.sleep(0.02)

        final_info = task_runner.get_task(task_id)
        assert final_info is not None
        assert final_info.status == "SUCCESS"
        assert final_info.result == {"result": 84}
        assert final_info.progress == 100
        assert final_info.started_at is not None
        assert final_info.completed_at is not None

    asyncio.run(_test())


def test_tasks_api_endpoints():
    """
    Phase 42: Test GET /tasks and GET /tasks/{task_id} endpoints.
    """
    async def _test():
        async def dummy_work():
            return {"done": True}

        task_id = task_runner.submit_task("dummy_task", dummy_work)

        # Poll via API
        resp = client.get(f"/tasks/{task_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == task_id
        assert data["name"] == "dummy_task"

        # List tasks via API
        list_resp = client.get("/tasks")
        assert list_resp.status_code == 200
        items = list_resp.json()
        assert any(t["task_id"] == task_id for t in items)

    asyncio.run(_test())


def test_async_job_search_endpoint():
    """
    Phase 42: Test POST /jobs/search/async executes job collection in background.
    """
    resp = client.post(
        "/jobs/search/async",
        json={
            "keywords": ["AI Engineer"],
            "locations": ["Remote"],
            "limit_per_source": 5
        }
    )
    assert resp.status_code == 202
    data = resp.json()
    assert "task_id" in data
    assert data["status"] == "PENDING"

    task = task_runner.get_task(data["task_id"])
    assert task is not None
    assert task.name == "job_search_and_collection"


def test_scheduler_lifecycle_and_execution():
    """
    Phase 43: Test scheduler activation, interval updates, stop, and run-now execution.
    """
    async def _test():
        # 1. Initial status
        status_resp = client.get("/scheduler/status")
        assert status_resp.status_code == 200
        init_data = status_resp.json()
        assert "is_active" in init_data

        # 2. Start scheduler
        start_resp = client.post("/scheduler/start")
        assert start_resp.status_code == 200
        assert start_resp.json()["is_active"] is True
        assert start_resp.json()["next_run_at"] is not None

        # 3. Update interval
        interval_resp = client.post("/scheduler/interval", json={"interval_minutes": 30})
        assert interval_resp.status_code == 200
        assert interval_resp.json()["interval_minutes"] == 30

        # 4. Stop scheduler
        stop_resp = client.post("/scheduler/stop")
        assert stop_resp.status_code == 200
        assert stop_resp.json()["is_active"] is False

        # 5. Trigger immediate discovery run via API
        run_now_resp = client.post("/scheduler/run-now")
        assert run_now_resp.status_code == 202
        run_data = run_now_resp.json()
        assert run_data["status"] == "triggered"
        assert "task_id" in run_data

        # 6. Execute direct discovery cycle
        direct_result = await job_scheduler.run_discovery_cycle()
        assert direct_result["status"] == "success"
        assert "new_jobs_added" in direct_result
        assert "total_jobs_scanned" in direct_result

    asyncio.run(_test())
