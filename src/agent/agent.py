import json
from typing import Any

import anthropic

from src.agent.prompts import SYSTEM_PROMPT
from src.agent.tools import TOOL_DEFINITIONS, get_lineage_graph, handle_tool_call, init_lineage_graph


class LineageAgent:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def run(
        self,
        run_id: str,
        db_path: str,
        logger: Any = None,
    ) -> dict:
        log = logger or _noop_logger()
        init_lineage_graph(run_id)

        messages: list[dict] = [
            {
                "role": "user",
                "content": (
                    f"Analyze the SQLite database at path: {db_path}\n"
                    f"Run ID: {run_id}\n\n"
                    "Discover all tables, trace every relationship, build the complete "
                    "lineage graph, then call finalize_report."
                ),
            }
        ]

        iteration = 0
        while True:
            iteration += 1
            log.info(f"Agent iteration {iteration}")

            response = await self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )

            # Append the full assistant response (including tool_use blocks)
            messages.append({"role": "assistant", "content": response.content})

            log.info(f"Stop reason: {response.stop_reason}")

            if response.stop_reason == "end_turn":
                log.info("Agent finished without finalize_report — returning graph as-is")
                break

            if response.stop_reason == "tool_use":
                tool_results = []
                done = False

                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    log.info(f"Tool call: {block.name} input={json.dumps(block.input)[:200]}")

                    result = await handle_tool_call(
                        tool_name=block.name,
                        tool_input=block.input,
                        run_id=run_id,
                        db_path=db_path,
                    )

                    log.info(f"Tool result: {json.dumps(result)[:200]}")

                    # Tool result content must be a string
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        }
                    )

                    if block.name == "finalize_report":
                        done = True

                # Send all tool results back together in one user message
                messages.append({"role": "user", "content": tool_results})

                if done:
                    log.info("Agent called finalize_report — analysis complete")
                    break
            else:
                log.info(f"Unexpected stop reason: {response.stop_reason} — exiting loop")
                break

        return get_lineage_graph(run_id)


class _noop_logger:
    def info(self, *_): pass
    def error(self, *_): pass
    def warning(self, *_): pass
