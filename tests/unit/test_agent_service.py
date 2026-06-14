import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agent.agent import LineageAgent
from src.agent.tools import init_lineage_graph, _lineage_graphs


def _make_tool_use_block(id_: str, name: str, input_: dict):
    block = MagicMock()
    block.type = "tool_use"
    block.id = id_
    block.name = name
    block.input = input_
    return block


def _make_text_block(text: str):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _make_response(stop_reason: str, *blocks):
    resp = MagicMock()
    resp.stop_reason = stop_reason
    resp.content = list(blocks)
    return resp


async def test_agent_loop_calls_finalize_and_returns_graph(db_path):
    # Simulate: Claude calls list_tables, then finalize_report
    resp1 = _make_response(
        "tool_use",
        _make_tool_use_block("tu_1", "list_tables", {}),
    )
    resp2 = _make_response(
        "tool_use",
        _make_tool_use_block("tu_2", "finalize_report", {"summary": "5 tables found."}),
    )

    agent = LineageAgent.__new__(LineageAgent)
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=[resp1, resp2])
    agent.client = mock_client
    agent.model = "claude-sonnet-4-6"

    graph = await agent.run("test-loop-run", db_path)

    assert mock_client.messages.create.call_count == 2
    assert graph["summary"] == "5 tables found."


async def test_agent_loop_handles_multiple_tool_calls_in_one_response(db_path):
    # Simulate Claude calling two tools in one response, then finalize
    resp1 = _make_response(
        "tool_use",
        _make_tool_use_block("tu_a", "list_tables", {}),
        _make_tool_use_block("tu_b", "get_row_count", {"table_name": "customers"}),
    )
    resp2 = _make_response(
        "tool_use",
        _make_tool_use_block("tu_c", "finalize_report", {"summary": "Done."}),
    )

    agent = LineageAgent.__new__(LineageAgent)
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=[resp1, resp2])
    agent.client = mock_client
    agent.model = "claude-sonnet-4-6"

    graph = await agent.run("test-multi-tool-run", db_path)

    # Two responses → exactly two API calls (one per batch of tool results)
    assert mock_client.messages.create.call_count == 2
    # Graph should be populated from the finalize call
    assert graph["summary"] == "Done."
    # Second call must have received more messages than the first (grew by 2: assistant + tool results)
    first_msg_count = len(mock_client.messages.create.call_args_list[0].kwargs["messages"])
    second_msg_count = len(mock_client.messages.create.call_args_list[1].kwargs["messages"])
    assert second_msg_count == first_msg_count + 2  # +assistant response +user tool_results


async def test_agent_loop_stops_on_end_turn(db_path):
    resp = _make_response("end_turn", _make_text_block("I'm done."))

    agent = LineageAgent.__new__(LineageAgent)
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=resp)
    agent.client = mock_client
    agent.model = "claude-sonnet-4-6"

    graph = await agent.run("test-end-turn-run", db_path)

    assert mock_client.messages.create.call_count == 1
    assert isinstance(graph, dict)


async def test_agent_tool_results_are_json_strings(db_path):
    resp1 = _make_response(
        "tool_use",
        _make_tool_use_block("tu_1", "list_tables", {}),
    )
    resp2 = _make_response(
        "tool_use",
        _make_tool_use_block("tu_2", "finalize_report", {"summary": "done"}),
    )

    agent = LineageAgent.__new__(LineageAgent)
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=[resp1, resp2])
    agent.client = mock_client
    agent.model = "claude-sonnet-4-6"

    await agent.run("test-json-run", db_path)

    # Check second call's tool results are strings (not dicts)
    second_call_messages = mock_client.messages.create.call_args_list[1].kwargs["messages"]
    user_follow_up = [m for m in second_call_messages if m["role"] == "user"][-1]
    for tr in user_follow_up["content"]:
        assert isinstance(tr["content"], str), "tool_result content must be a JSON string"
        json.loads(tr["content"])  # must be valid JSON
