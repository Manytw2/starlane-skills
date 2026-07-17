"""Run the CSMAR collection MCP server.

IN:  CSMAR_ACCOUNT and CSMAR_PASSWORD environment variables.
OUT: MCP tools that discover authorized CSMAR metadata and materialize approved ZIP archives.
"""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from scripts.csmar_client import CsmarClient, CsmarError, CsmarQuery

MAX_QUERY_ROWS = 200_000
MAX_SAMPLE_ROWS = 10
POLL_INTERVAL_SECONDS = 3
POLL_TIMEOUT_SECONDS = 900


@dataclass(frozen=True)
class ValidatedQuery:
    query: CsmarQuery
    row_count: int


class QueryRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, ValidatedQuery] = {}

    def add(self, query: CsmarQuery, row_count: int) -> str:
        digest = hashlib.sha256(repr((asdict(query), row_count)).encode()).hexdigest()[:16]
        validation_id = f"csmar-{digest}"
        self._entries[validation_id] = ValidatedQuery(query, row_count)
        return validation_id

    def get(self, validation_id: str) -> ValidatedQuery:
        try:
            return self._entries[validation_id]
        except KeyError as error:
            raise CsmarError("Unknown validation_id. Run csmar_probe_query again in this server session.") from error


def _client_from_env() -> CsmarClient:
    account = os.environ.get("CSMAR_ACCOUNT")
    password = os.environ.get("CSMAR_PASSWORD")
    if not account or not password:
        raise CsmarError("Set CSMAR_ACCOUNT and CSMAR_PASSWORD before starting or calling this server.")
    return CsmarClient(account, password)


def create_server(client: CsmarClient | None = None) -> FastMCP:
    csmar = client
    validations = QueryRegistry()
    mcp = FastMCP("starlane-csmar")

    def active_client() -> CsmarClient:
        nonlocal csmar
        if csmar is None:
            csmar = _client_from_env()
        return csmar

    @mcp.tool()
    def csmar_list_databases() -> dict[str, Any]:
        """List databases available to the configured CSMAR account."""
        return {"databases": active_client().list_databases()}

    @mcp.tool()
    def csmar_list_tables(database_name: str) -> dict[str, Any]:
        """List tables in one CSMAR database available to the configured account."""
        return {"database_name": database_name, "tables": active_client().list_tables(database_name)}

    @mcp.tool()
    def csmar_describe_table(table_code: str) -> dict[str, Any]:
        """Return field metadata for an authorized CSMAR table."""
        return {"table_code": table_code, "fields": active_client().describe_table(table_code)}

    @mcp.tool()
    def csmar_probe_query(table_code: str, columns: list[str], condition: str = "1=1", start_date: str | None = None, end_date: str | None = None, sample_rows: int = 3) -> dict[str, Any]:
        """Count and sample a query before allowing a CSMAR archive download."""
        if not columns:
            raise CsmarError("columns must contain at least one field.")
        if not 1 <= sample_rows <= MAX_SAMPLE_ROWS:
            raise CsmarError(f"sample_rows must be between 1 and {MAX_SAMPLE_ROWS}.")
        query = CsmarQuery(table_code, columns, condition, start_date, end_date)
        row_count = active_client().query_count(query)
        if row_count > MAX_QUERY_ROWS:
            return {"approved": False, "row_count": row_count, "limit": MAX_QUERY_ROWS, "warning": "Narrow the filters. This prototype does not paginate or bypass CSMAR query limits."}
        validation_id = validations.add(query, row_count)
        return {"approved": True, "validation_id": validation_id, "row_count": row_count, "sample_rows": active_client().query_sample(query, sample_rows), "query": asdict(query)}

    @mcp.tool()
    def csmar_download_validated_query(validation_id: str, output_dir: str) -> dict[str, Any]:
        """Materialize an approved query as a CSMAR ZIP archive in output_dir."""
        validated = validations.get(validation_id)
        target_dir = Path(output_dir).expanduser().resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        sign_code = active_client().start_download(validated.query)
        deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            status = active_client().package_status(sign_code)
            if status.get("status") == "1":
                file_url = str(status.get("filePath") or "")
                if not file_url:
                    raise CsmarError("CSMAR marked the package complete without a download URL.")
                archive_path = target_dir / f"{sign_code}.zip"
                archive_path.write_bytes(active_client().download(file_url))
                return {"validation_id": validation_id, "row_count": validated.row_count, "archive_path": str(archive_path), "sign_code": sign_code}
            if status.get("status") == "0":
                raise CsmarError("CSMAR failed to package this query. Refine it and probe again.")
            time.sleep(POLL_INTERVAL_SECONDS)
        raise CsmarError("Timed out while CSMAR prepared the archive. Retry later; do not alter the query to bypass limits.")

    return mcp


def main() -> None:
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
