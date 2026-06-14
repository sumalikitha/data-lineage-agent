import json
from typing import Any

import aiosqlite

# ---------------------------------------------------------------------------
# In-memory lineage graph store, keyed by run_id
# ---------------------------------------------------------------------------

_lineage_graphs: dict[str, dict[str, Any]] = {}


def init_lineage_graph(run_id: str) -> None:
    _lineage_graphs[run_id] = {"nodes": [], "edges": [], "summary": None}


def get_lineage_graph(run_id: str) -> dict[str, Any]:
    return _lineage_graphs.get(run_id, {"nodes": [], "edges": [], "summary": None})


# ---------------------------------------------------------------------------
# Database introspection tool handlers
# ---------------------------------------------------------------------------


async def list_tables(db_path: str) -> dict:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        rows = await cursor.fetchall()
    return {"tables": [row[0] for row in rows]}


async def get_table_schema(db_path: str, table_name: str) -> dict:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(f"PRAGMA table_info({table_name})")
        rows = await cursor.fetchall()
    columns = [
        {
            "name": row[1],
            "type": row[2],
            "notnull": bool(row[3]),
            "default": row[4],
            "pk": bool(row[5]),
        }
        for row in rows
    ]
    return {"table": table_name, "columns": columns}


async def get_foreign_keys(db_path: str, table_name: str) -> dict:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(f"PRAGMA foreign_key_list({table_name})")
        rows = await cursor.fetchall()
    fks = [
        {
            "from_column": row[3],
            "to_table": row[2],
            "to_column": row[4],
        }
        for row in rows
    ]
    return {"table": table_name, "foreign_keys": fks}


async def get_sample_data(db_path: str, table_name: str, limit: int = 5) -> dict:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(f"SELECT * FROM {table_name} LIMIT {limit}")
        rows = await cursor.fetchall()
    return {"table": table_name, "rows": [dict(row) for row in rows]}


async def get_row_count(db_path: str, table_name: str) -> dict:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(f"SELECT COUNT(*) FROM {table_name}")
        row = await cursor.fetchone()
    return {"table": table_name, "count": row[0]}


async def find_column_references(db_path: str, column_name: str) -> dict:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        tables = [row[0] for row in await cursor.fetchall()]

        found_in = []
        for table in tables:
            col_cursor = await db.execute(f"PRAGMA table_info({table})")
            cols = await col_cursor.fetchall()
            for col in cols:
                if col[1].lower() == column_name.lower():
                    found_in.append({"table": table, "column": col[1]})

    return {"column": column_name, "found_in": found_in}


# ---------------------------------------------------------------------------
# Lineage graph mutation tool handlers
# ---------------------------------------------------------------------------


async def save_lineage_node(
    run_id: str,
    table_name: str,
    columns: list[str],
    row_count: int | None = None,
    description: str | None = None,
) -> dict:
    graph = _lineage_graphs.setdefault(run_id, {"nodes": [], "edges": [], "summary": None})
    # Deduplicate by table_name
    existing = {n["table_name"] for n in graph["nodes"]}
    if table_name not in existing:
        graph["nodes"].append(
            {
                "table_name": table_name,
                "columns": columns,
                "row_count": row_count,
                "description": description,
            }
        )
    return {"saved": True, "node": table_name}


async def save_lineage_edge(
    run_id: str,
    source_table: str,
    target_table: str,
    relationship_type: str,
    join_columns: list[str] | None = None,
) -> dict:
    graph = _lineage_graphs.setdefault(run_id, {"nodes": [], "edges": [], "summary": None})
    graph["edges"].append(
        {
            "source_table": source_table,
            "target_table": target_table,
            "relationship_type": relationship_type,
            "join_columns": join_columns or [],
        }
    )
    return {"saved": True}


async def finalize_report(run_id: str, summary: str) -> dict:
    graph = _lineage_graphs.setdefault(run_id, {"nodes": [], "edges": [], "summary": None})
    graph["summary"] = summary
    return {"finalized": True, "run_id": run_id}


# ---------------------------------------------------------------------------
# Tool call dispatcher
# ---------------------------------------------------------------------------


async def handle_tool_call(
    tool_name: str,
    tool_input: dict,
    run_id: str,
    db_path: str,
) -> dict:
    match tool_name:
        case "list_tables":
            return await list_tables(db_path)
        case "get_table_schema":
            return await get_table_schema(db_path, tool_input["table_name"])
        case "get_foreign_keys":
            return await get_foreign_keys(db_path, tool_input["table_name"])
        case "get_sample_data":
            return await get_sample_data(
                db_path,
                tool_input["table_name"],
                tool_input.get("limit", 5),
            )
        case "get_row_count":
            return await get_row_count(db_path, tool_input["table_name"])
        case "find_column_references":
            return await find_column_references(db_path, tool_input["column_name"])
        case "save_lineage_node":
            return await save_lineage_node(
                run_id,
                tool_input["table_name"],
                tool_input.get("columns", []),
                tool_input.get("row_count"),
                tool_input.get("description"),
            )
        case "save_lineage_edge":
            return await save_lineage_edge(
                run_id,
                tool_input["source_table"],
                tool_input["target_table"],
                tool_input["relationship_type"],
                tool_input.get("join_columns"),
            )
        case "finalize_report":
            return await finalize_report(run_id, tool_input["summary"])
        case _:
            return {"error": f"Unknown tool: {tool_name}"}


# ---------------------------------------------------------------------------
# Claude tool schema definitions
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "list_tables",
        "description": "Returns all table names in the connected SQLite database. Call this first to discover what tables exist.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_table_schema",
        "description": "Returns column names, types, nullability, defaults, and primary key flags for a specific table.",
        "input_schema": {
            "type": "object",
            "properties": {
                "table_name": {"type": "string", "description": "Name of the table to inspect"}
            },
            "required": ["table_name"],
        },
    },
    {
        "name": "get_foreign_keys",
        "description": "Returns all foreign key constraints defined on a table, showing which columns reference which tables.",
        "input_schema": {
            "type": "object",
            "properties": {
                "table_name": {"type": "string", "description": "Name of the table to inspect"}
            },
            "required": ["table_name"],
        },
    },
    {
        "name": "get_sample_data",
        "description": "Returns up to N sample rows from a table to help understand the data semantics and values.",
        "input_schema": {
            "type": "object",
            "properties": {
                "table_name": {"type": "string", "description": "Name of the table"},
                "limit": {
                    "type": "integer",
                    "description": "Maximum rows to return (default 5)",
                    "default": 5,
                },
            },
            "required": ["table_name"],
        },
    },
    {
        "name": "get_row_count",
        "description": "Returns the total number of rows in a table.",
        "input_schema": {
            "type": "object",
            "properties": {
                "table_name": {"type": "string", "description": "Name of the table"}
            },
            "required": ["table_name"],
        },
    },
    {
        "name": "find_column_references",
        "description": "Searches all tables for columns with a given name to detect implicit join relationships not captured by foreign key constraints.",
        "input_schema": {
            "type": "object",
            "properties": {
                "column_name": {
                    "type": "string",
                    "description": "Column name to search for across all tables",
                }
            },
            "required": ["column_name"],
        },
    },
    {
        "name": "save_lineage_node",
        "description": "Persists a discovered table as a node in the lineage graph. Call this once you have fully inspected a table.",
        "input_schema": {
            "type": "object",
            "properties": {
                "table_name": {"type": "string", "description": "Name of the table"},
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of column names",
                },
                "row_count": {
                    "type": "integer",
                    "description": "Total row count for this table",
                },
                "description": {
                    "type": "string",
                    "description": "Human-readable description of what this table stores",
                },
            },
            "required": ["table_name", "columns"],
        },
    },
    {
        "name": "save_lineage_edge",
        "description": "Persists a discovered relationship between two tables as an edge in the lineage graph.",
        "input_schema": {
            "type": "object",
            "properties": {
                "source_table": {
                    "type": "string",
                    "description": "The table that holds the reference (child/dependent table)",
                },
                "target_table": {
                    "type": "string",
                    "description": "The table being referenced (parent table)",
                },
                "relationship_type": {
                    "type": "string",
                    "enum": ["foreign_key", "implicit_join"],
                    "description": "Whether this is an explicit FK constraint or an inferred implicit join",
                },
                "join_columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Column names involved in the join",
                },
            },
            "required": ["source_table", "target_table", "relationship_type"],
        },
    },
    {
        "name": "finalize_report",
        "description": "Call this when you have fully explored all tables and recorded all nodes and edges. This signals that analysis is complete and triggers report generation. Do not call this until every table has a corresponding save_lineage_node call.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Markdown-formatted summary of the discovered data lineage, including key relationships and data flow patterns",
                }
            },
            "required": ["summary"],
        },
    },
]
