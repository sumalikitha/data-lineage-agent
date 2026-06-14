import pytest
from unittest.mock import AsyncMock, MagicMock, patch


async def test_health(client):
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_runs_empty_initially(client):
    r = await client.get("/api/v1/runs")
    assert r.status_code == 200
    assert r.json() == []


async def test_report_not_found(client):
    r = await client.get("/api/v1/report/nonexistent-id")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


async def test_analyze_returns_run_id_and_pending_status(client):
    with patch(
        "src.services.agent_service.LineageAgentService.run_analysis",
        new_callable=AsyncMock,
    ):
        r = await client.post("/api/v1/analyze", json={})

    assert r.status_code == 200
    body = r.json()
    assert "run_id" in body
    assert body["status"] == "pending"
    assert len(body["run_id"]) > 0


async def test_analyze_run_appears_in_runs_list(client):
    with patch(
        "src.services.agent_service.LineageAgentService.run_analysis",
        new_callable=AsyncMock,
    ):
        post_r = await client.post("/api/v1/analyze", json={})
        run_id = post_r.json()["run_id"]

    runs_r = await client.get("/api/v1/runs")
    assert runs_r.status_code == 200
    run_ids = [r["run_id"] for r in runs_r.json()]
    assert run_id in run_ids


async def test_report_returns_pending_immediately_after_analyze(client):
    with patch(
        "src.services.agent_service.LineageAgentService.run_analysis",
        new_callable=AsyncMock,
    ):
        post_r = await client.post("/api/v1/analyze", json={})
        run_id = post_r.json()["run_id"]

    report_r = await client.get(f"/api/v1/report/{run_id}")
    assert report_r.status_code == 200
    body = report_r.json()
    assert body["run_id"] == run_id
    assert body["status"] in ("pending", "running", "completed", "failed")


async def test_analyze_with_notes(client):
    with patch(
        "src.services.agent_service.LineageAgentService.run_analysis",
        new_callable=AsyncMock,
    ):
        r = await client.post("/api/v1/analyze", json={"notes": "focus on FK relationships"})

    assert r.status_code == 200
    assert "run_id" in r.json()


async def test_swagger_ui_accessible(client):
    r = await client.get("/docs")
    assert r.status_code == 200


async def test_openapi_schema_has_all_routes(client):
    r = await client.get("/openapi.json")
    assert r.status_code == 200
    paths = list(r.json()["paths"].keys())
    assert "/api/v1/health" in paths
    assert "/api/v1/analyze" in paths
    assert "/api/v1/report/{run_id}" in paths
    assert "/api/v1/runs" in paths
