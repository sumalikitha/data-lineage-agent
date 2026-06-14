# Data Lineage Agent

An LLM-powered agent that autonomously discovers, traces, and documents data lineage across a relational database. Claude (`claude-sonnet-4-6`) controls every exploration decision via tool use — no hardcoded traversal logic.

---

## Quick Start

```bash
# 1. Clone the repo
git clone <repo-url> && cd data-lineage-agent

# 2. Set your API key
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=your-key

# 3. Start the service
docker-compose up --build
```

The API is now live at `http://localhost:8000`.  
Swagger UI: `http://localhost:8000/docs`

---

## Running Locally (without Docker)

```bash
# 1. Install dependencies
pip install -e ".[dev]"

# 2. Set your API key
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=your-actual-key

# 3. Start the server
uvicorn src.api.app:app --reload
```

The service is now live at `http://localhost:8000`.

| URL | Description |
|---|---|
| `http://localhost:8000` | Lineage graph UI — trigger analysis and view results visually |
| `http://localhost:8000/docs` | Swagger UI — interactive API reference |

---

## API Reference

### Trigger an analysis

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{}'
```

Response:
```json
{
  "run_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "pending",
  "message": "Analysis started. Poll GET /api/v1/report/{run_id} for results."
}
```

### Poll for results

```bash
curl http://localhost:8000/api/v1/report/3fa85f64-5717-4562-b3fc-2c963f66afa6
```

Response (completed):
```json
{
  "run_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "completed",
  "nodes": [
    {
      "table_name": "customers",
      "columns": ["id", "name", "email", "phone", "address", "created_at"],
      "row_count": 5,
      "description": "Core customer master table storing personal details"
    }
  ],
  "edges": [
    {
      "source_table": "accounts",
      "target_table": "customers",
      "relationship_type": "foreign_key",
      "join_columns": ["customer_id"]
    }
  ],
  "summary": "## Data Lineage Summary\n\nThe banking database contains 5 tables...",
  "created_at": "2026-06-14T10:00:00",
  "completed_at": "2026-06-14T10:01:30"
}
```

### List all runs

```bash
curl http://localhost:8000/api/v1/runs
```

### Health check

```bash
curl http://localhost:8000/api/v1/health
# → {"status": "ok"}
```

---

## How the Agent Works

The agent uses Claude's tool use (function calling) to drive its own exploration. There is no hardcoded traversal — Claude decides which tool to call next based on what it has discovered so far.

**Agent loop:**

```
1. Claude receives the task: "Analyze the database, build the lineage graph, call finalize_report"
2. Claude calls list_tables → gets all 5 table names
3. Claude iterates through each table:
   - get_table_schema   → column names, types, PK flags
   - get_foreign_keys   → explicit FK relationships
   - get_row_count      → data volume signal
   - get_sample_data    → semantic understanding of values
   - find_column_references → implicit join detection
   - save_lineage_node  → persists the table to the graph
4. For each relationship found:
   - save_lineage_edge  → persists the edge to the graph
5. Claude calls finalize_report(summary=...) when done
6. The agent loop exits and the report is assembled
```

**Why this design?**

- Claude controls all traversal decisions — the order, depth, and termination point are LLM-driven, not hardcoded
- `finalize_report` is the terminal condition: the loop only exits when Claude explicitly signals it is done
- Each tool call returns a JSON dict; Claude uses the results to inform its next decision
- The tool use loop correctly handles multiple `tool_use` blocks in a single response (Claude may call several tools at once)

---

## Database Schema

The service ships with a pre-seeded SQLite banking database (`banking.db`). The seeder runs automatically on startup.

| Table | Description |
|---|---|
| `customers` | Customer master: name, email, phone, address |
| `accounts` | Bank accounts linked to customers (checking, savings, credit) |
| `transactions` | Money movements between accounts |
| `loans` | Loan records linked to customers and accounts |
| `audit_log` | Change audit trail across all entities |

**Relationships:**
- `accounts.customer_id` → `customers.id` (FK)
- `transactions.from_account_id` → `accounts.id` (FK)
- `transactions.to_account_id` → `accounts.id` (FK)
- `loans.customer_id` → `customers.id` (FK)
- `loans.account_id` → `accounts.id` (FK)
- `audit_log.record_id` ↔ various tables (implicit join on `entity_type`)

---

## Running Tests

```bash
pytest tests/ -v
```

All 25 tests run with zero live API calls — Claude responses are mocked via `unittest.mock`.

```
tests/unit/test_tools.py          - 12 tests: each DB tool handler + graph mutations
tests/unit/test_agent_service.py  -  4 tests: agent loop correctness (mocked Claude)
tests/integration/test_api.py     -  9 tests: all route happy-paths and error paths
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | — | Your Anthropic API key |
| `CLAUDE_MODEL` | No | `claude-sonnet-4-6` | Claude model to use |
| `DATABASE_PATH` | No | `banking.db` | Path to the SQLite database file |
