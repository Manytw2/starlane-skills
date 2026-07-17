from __future__ import annotations

from scripts.csmar_client import CsmarQuery
from scripts.csmar_mcp import MAX_QUERY_ROWS, QueryRegistry


def test_validation_registry_returns_same_query() -> None:
    registry = QueryRegistry()
    query = CsmarQuery("FS_Combas", ["Stkcd"], "1=1", None, None)

    validation_id = registry.add(query, 3)

    assert registry.get(validation_id).query == query
    assert registry.get(validation_id).row_count == 3


def test_csmar_row_limit_matches_documented_service_limit() -> None:
    assert MAX_QUERY_ROWS == 200_000
