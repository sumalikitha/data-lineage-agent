# Architecture

## Design Decisions

### 1. Raw Anthropic SDK instead of LangChain

The agent loop is implemented directly against `anthropic.AsyncAnthropic` with no framework in between. This was deliberate:

- **Full control over the messages list.** Frameworks abstract the conversation state, making it hard to reason about exactly what Claude sees on each call. Here, the `messages` list is plain Python — inspectable, testable, and easy to extend.
- **Deterministic tests.** Mocking `AsyncMock(side_effect=[resp1, resp2])` directly against the client is straightforward. Frameworks add indirection that makes unit testing the loop logic harder.
- **No hidden retry or fallback logic.** The caller decides how to handle errors.
- **Easier to explain.** The entire agent loop is ~50 lines in `src/agent/agent.py`. There is no "magic."

### 2. Tool Use as the Control Flow Primitive

Claude drives every decision via tool calls. The loop contract is:

```
while True:
    response = await client.messages.create(..., tools=TOOL_DEFINITIONS, messages=messages)
    messages.append({"role": "assistant", "content": response.content})

    if stop_reason == "end_turn":
        break
    if stop_reason == "tool_use":
        results = [dispatch each tool_use block]
        messages.append({"role": "user", "content": results})
        if "finalize_report" was called:
            break
```

Two critical correctness rules:
1. **Append the full `response.content` list** (not just text blocks) as the assistant message. Dropping `tool_use` blocks from the assistant turn causes the API to reject the next call.
2. **Serialize tool result content as JSON strings.** The `content` field of a `tool_result` block must be `str`, not `dict`.

### 3. `finalize_report` as the Termination Signal

Rather than polling for some "done" condition or counting tool calls, the agent loop exits when Claude explicitly calls `finalize_report`. This means:

- Claude decides when it has gathered enough information — the loop has no hardcoded stop condition
- The system prompt instructs Claude not to call `finalize_report` until every table has a `save_lineage_node` call — so completeness is enforced by the prompt, not the framework
- If Claude calls `finalize_report` mid-loop (before finishing all tables), the prompt is the place to fix it, not the loop logic

### 4. In-Memory Run Store

`LineageAgentService._runs` is a plain Python dict keyed by `run_id`. This is sufficient for the MVP because:

- Analysis runs are ephemeral: the interesting output is the report, not the run metadata
- A persistent run store (PostgreSQL, Redis) would add a deployment dependency without adding value for a demo/assessment
- The seeded SQLite database already provides persistence for the data being analyzed

**Trade-off:** Runs are lost on restart. The roadmap item for persistent run storage covers this.

### 5. Async Throughout

Every layer is async:

- `AsyncAnthropic` — non-blocking Claude API calls
- `aiosqlite` — non-blocking SQLite queries inside tool handlers
- `FastAPI` routes — `async def` throughout
- `BackgroundTasks` — the long-running agent loop runs in the background so `POST /analyze` returns immediately with a `run_id`

Each tool handler opens its own `aiosqlite.connect()` connection rather than sharing one. SQLite connections are not concurrency-safe across coroutines, and the connection overhead is negligible for introspection queries.

### 6. Thin Routes, Rich Service Layer

API routes handle only HTTP concerns: parsing the request, calling the service, returning the response. All orchestration lives in `LineageAgentService`. This makes the service layer independently testable without HTTP.

```
routes.py          → HTTP in/out, BackgroundTasks wiring
agent_service.py   → run lifecycle, agent invocation, report assembly
agent.py           → tool use loop, message management
tools.py           → DB introspection, graph mutations, Claude schemas
```

---

## Component Diagram

```
POST /analyze
     │
     ▼
LineageAgentService.start_analysis()   ← creates run_id, stores pending report
     │
     ├── returns run_id immediately (HTTP 200)
     │
     └── BackgroundTask: run_analysis(run_id)
              │
              ▼
         LineageAgent.run()
              │
              ├── init_lineage_graph(run_id)
              │
              └── Tool use loop
                    │
                    ├── AsyncAnthropic.messages.create()
                    │
                    ├── handle_tool_call(name, input, run_id, db_path)
                    │     ├── list_tables → aiosqlite query
                    │     ├── get_table_schema → PRAGMA table_info
                    │     ├── get_foreign_keys → PRAGMA foreign_key_list
                    │     ├── get_sample_data → SELECT * LIMIT N
                    │     ├── get_row_count → SELECT COUNT(*)
                    │     ├── find_column_references → sqlite_master scan
                    │     ├── save_lineage_node → _lineage_graphs[run_id]
                    │     ├── save_lineage_edge → _lineage_graphs[run_id]
                    │     └── finalize_report → sets summary, signals done
                    │
                    └── returns get_lineage_graph(run_id)
              │
              ▼
         LineageAgentService assembles LineageReport
         sets status = "completed"
```
