import os
import uuid
from datetime import datetime

from src.agent.agent import LineageAgent
from src.models.lineage import LineageEdge, LineageNode, LineageReport, RunStatus
from src.utils.logger import get_run_logger


class LineageAgentService:
    def __init__(self) -> None:
        self._runs: dict[str, LineageReport] = {}
        self._agent = LineageAgent(
            api_key=os.environ["ANTHROPIC_API_KEY"],
            model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6"),
        )
        self._db_path = os.getenv("DATABASE_PATH", "banking.db")

    async def start_analysis(self) -> str:
        run_id = str(uuid.uuid4())
        self._runs[run_id] = LineageReport(run_id=run_id, status=RunStatus.pending)
        return run_id

    async def run_analysis(self, run_id: str) -> None:
        log = get_run_logger(run_id)
        report = self._runs[run_id]
        report.status = RunStatus.running
        log.info("Analysis started")

        try:
            graph = await self._agent.run(
                run_id=run_id,
                db_path=self._db_path,
                logger=log,
            )

            report.nodes = [LineageNode(**n) for n in graph.get("nodes", [])]
            report.edges = [LineageEdge(**e) for e in graph.get("edges", [])]
            report.summary = graph.get("summary")
            report.status = RunStatus.completed
            report.completed_at = datetime.utcnow()
            log.info(f"Analysis complete: {len(report.nodes)} nodes, {len(report.edges)} edges")

        except Exception as exc:
            report.status = RunStatus.failed
            report.error = str(exc)
            log.error(f"Analysis failed: {exc}")

    def get_report(self, run_id: str) -> LineageReport | None:
        return self._runs.get(run_id)

    def list_runs(self) -> list[LineageReport]:
        return list(self._runs.values())
