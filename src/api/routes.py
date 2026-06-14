from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from src.api.deps import get_agent_service
from src.models.lineage import AnalyzeRequest, AnalyzeResponse, LineageReport, RunStatus
from src.services.agent_service import LineageAgentService

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    service: LineageAgentService = Depends(get_agent_service),
):
    run_id = await service.start_analysis()
    background_tasks.add_task(service.run_analysis, run_id)
    return AnalyzeResponse(
        run_id=run_id,
        status=RunStatus.pending,
        message="Analysis started. Poll GET /api/v1/report/{run_id} for results.",
    )


@router.get("/report/{run_id}", response_model=LineageReport)
async def get_report(
    run_id: str,
    service: LineageAgentService = Depends(get_agent_service),
):
    report = service.get_report(run_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return report


@router.get("/runs", response_model=list[LineageReport])
async def list_runs(
    service: LineageAgentService = Depends(get_agent_service),
):
    return service.list_runs()
