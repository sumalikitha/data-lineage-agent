import pytest

from src.agent.tools import (
    find_column_references,
    get_foreign_keys,
    get_row_count,
    get_sample_data,
    get_table_schema,
    get_lineage_graph,
    init_lineage_graph,
    list_tables,
    save_lineage_edge,
    save_lineage_node,
    finalize_report,
)


async def test_list_tables_returns_all_five(db_path):
    result = await list_tables(db_path)
    assert "tables" in result
    tables = result["tables"]
    assert len(tables) == 5
    for name in ("customers", "accounts", "transactions", "loans", "audit_log"):
        assert name in tables


async def test_get_table_schema_customers(db_path):
    result = await get_table_schema(db_path, "customers")
    assert result["table"] == "customers"
    col_names = [c["name"] for c in result["columns"]]
    assert "id" in col_names
    assert "email" in col_names
    assert "created_at" in col_names
    pk_cols = [c["name"] for c in result["columns"] if c["pk"]]
    assert pk_cols == ["id"]


async def test_get_foreign_keys_accounts(db_path):
    result = await get_foreign_keys(db_path, "accounts")
    assert result["table"] == "accounts"
    fks = result["foreign_keys"]
    assert len(fks) == 1
    assert fks[0]["from_column"] == "customer_id"
    assert fks[0]["to_table"] == "customers"


async def test_get_foreign_keys_transactions(db_path):
    result = await get_foreign_keys(db_path, "transactions")
    to_tables = {fk["to_table"] for fk in result["foreign_keys"]}
    assert "accounts" in to_tables


async def test_get_row_count(db_path):
    result = await get_row_count(db_path, "customers")
    assert result["table"] == "customers"
    assert result["count"] == 5


async def test_get_sample_data(db_path):
    result = await get_sample_data(db_path, "customers", limit=3)
    assert result["table"] == "customers"
    assert len(result["rows"]) == 3
    assert "name" in result["rows"][0]
    assert "email" in result["rows"][0]


async def test_find_column_references_customer_id(db_path):
    result = await find_column_references(db_path, "customer_id")
    assert result["column"] == "customer_id"
    found_tables = {r["table"] for r in result["found_in"]}
    assert "accounts" in found_tables
    assert "loans" in found_tables


async def test_find_column_references_unknown_column(db_path):
    result = await find_column_references(db_path, "nonexistent_xyz")
    assert result["found_in"] == []


async def test_save_lineage_node_and_get_graph():
    run_id = "test-node-run"
    init_lineage_graph(run_id)
    result = await save_lineage_node(
        run_id, "customers", ["id", "name", "email"], row_count=5, description="Customer master"
    )
    assert result["saved"] is True
    assert result["node"] == "customers"
    graph = get_lineage_graph(run_id)
    assert len(graph["nodes"]) == 1
    assert graph["nodes"][0]["table_name"] == "customers"


async def test_save_lineage_node_deduplicates():
    run_id = "test-dedup-run"
    init_lineage_graph(run_id)
    await save_lineage_node(run_id, "customers", ["id"])
    await save_lineage_node(run_id, "customers", ["id"])  # duplicate
    graph = get_lineage_graph(run_id)
    assert len(graph["nodes"]) == 1


async def test_save_lineage_edge():
    run_id = "test-edge-run"
    init_lineage_graph(run_id)
    result = await save_lineage_edge(
        run_id, "accounts", "customers", "foreign_key", ["customer_id"]
    )
    assert result["saved"] is True
    graph = get_lineage_graph(run_id)
    assert len(graph["edges"]) == 1
    edge = graph["edges"][0]
    assert edge["source_table"] == "accounts"
    assert edge["target_table"] == "customers"
    assert edge["relationship_type"] == "foreign_key"


async def test_finalize_report_sets_summary():
    run_id = "test-finalize-run"
    init_lineage_graph(run_id)
    result = await finalize_report(run_id, "All 5 tables discovered.")
    assert result["finalized"] is True
    graph = get_lineage_graph(run_id)
    assert graph["summary"] == "All 5 tables discovered."
