# Roadmap

Items deferred from the MVP, prioritised by value.

## Near-term

| Priority | Item | Notes |
|---|---|---|
| P1 | **PostgreSQL / MySQL connectivity** | Replace SQLite connector with asyncpg/aiomysql. Schema introspection tools already use PRAGMA-style queries; these need adapters per dialect. |
| P1 | **Persistent run store** | Persist `LineageReport` to a database table so runs survive restarts. SQLAlchemy async or a lightweight `aiosqlite`-backed store. |
| P2 | **Streaming output via SSE** | Stream agent tool calls and log messages to the client in real time so users can see progress without polling. |
| P2 | **API key authentication** | Add `Authorization: Bearer <key>` header validation via FastAPI middleware. |

## Medium-term

| Priority | Item | Notes |
|---|---|---|
| P2 | **Celery task queue** | Replace `BackgroundTasks` with Celery + Redis for durable, retryable analysis jobs with proper failure handling. |
| P3 | **Visual lineage graph UI** | D3.js or React Flow front-end rendering the node-edge graph returned by `/report/{run_id}`. |
| P3 | **LLM cost tracking** | Log token usage per run and expose it in the report. Add per-run token budget with early termination. |
| P3 | **Prometheus metrics** | Expose `/metrics` with run counts, latencies, and failure rates. Grafana dashboard for oncall. |

## Long-term

| Priority | Item | Notes |
|---|---|---|
| P4 | **Multi-database cross-system lineage** | Connect multiple databases and trace lineage across system boundaries. Integration with Collibra or Informatica APIs. |
| P4 | **Kubernetes manifests** | Helm chart for production deployment with horizontal scaling for the API tier. |
| P4 | **Scheduled re-analysis** | Cron-triggered re-runs when schema changes are detected. Diff reports showing what changed between runs. |
