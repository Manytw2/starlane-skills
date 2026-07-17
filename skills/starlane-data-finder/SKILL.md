---
name: starlane-data-finder
description: Find and collect empirical research data. Use when a user needs to identify a supported data source, explore an authorized CSMAR account's databases, tables, and fields, preflight a CSMAR query, or download an approved CSMAR query result.
---

# Starlane Data Finder

Use the CSMAR MCP server only with the user's authorized CSMAR account. It collects source data; it does not clean data, construct research variables, or run regressions.

## CSMAR Workflow

1. Ask for the research question, target observation grain, required fields, sample, and time range.
2. Use `csmar_list_databases`, then `csmar_list_tables`, then `csmar_describe_table`. Only select tables returned for the current account.
3. Use `csmar_probe_query` before every download. Treat its row count, sample rows, and warnings as a user-facing checkpoint.
4. Download only after the user accepts the preflight result, using `csmar_download_validated_query` and its `validation_id`.
5. Report the downloaded archive path, table, fields, conditions, and time range. Do not claim that the archive was cleaned or is ready for regression.

Never attempt to bypass CSMAR account permissions, the 200,000-row request ceiling, or upstream rate limits. Do not retry a query merely by changing pagination syntax to evade a repeated-query restriction.

## Setup

Read [CSMAR MCP setup](references/csmar-mcp.md) before configuring credentials or starting the server.
