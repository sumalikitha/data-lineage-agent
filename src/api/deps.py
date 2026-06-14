from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.services.agent_service import LineageAgentService

_service: "LineageAgentService | None" = None


def get_agent_service() -> "LineageAgentService":
    global _service
    if _service is None:
        from src.services.agent_service import LineageAgentService

        _service = LineageAgentService()
    return _service
