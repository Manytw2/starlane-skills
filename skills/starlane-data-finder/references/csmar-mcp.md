# CSMAR MCP Setup

The server uses the CSMAR Python data-service endpoints with the account supplied by the user. It can only see databases licensed to that account or institution.

Set credentials outside the repository:

```bash
export CSMAR_ACCOUNT='your-account'
export CSMAR_PASSWORD='your-password'
uv run --project skills/starlane-data-finder starlane-csmar-mcp
```

The server exposes five tools:

- `csmar_list_databases`
- `csmar_list_tables`
- `csmar_describe_table`
- `csmar_probe_query`
- `csmar_download_validated_query`

`csmar_probe_query` rejects queries over 200,000 rows. The returned `validation_id` is valid only while that MCP server process remains running. `csmar_download_validated_query` asks CSMAR to build a ZIP archive, waits for the service to finish, then writes the archive into the explicit `output_dir` supplied by the caller.

The prototype intentionally has no automatic pagination, no condition rewriting, and no retry loop for rate-limit errors. Respect the CSMAR account agreement and upstream limits.
