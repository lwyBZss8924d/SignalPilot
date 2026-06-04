---
sidebar_position: 1
---

# Tools Reference

All 40 SignalPilot MCP tools, grouped by category. Click a category for full parameter and example documentation.

## Query Intelligence (7 tools)

See [Query Intelligence tools](/docs/reference/tools-query).

| Tool | Description |
|------|-------------|
| `query_database` | Execute governed, read-only SQL with auto-LIMIT, DDL blocking, dangerous function blocking, audit, PII redaction |
| `validate_sql` | Syntax + semantic validation via EXPLAIN (no execution, no budget charge) |
| `explain_query` | Execution plan with row estimates and cost warnings |
| `estimate_query_cost` | Dry-run cost estimate before executing (BigQuery: exact bytes) |
| `debug_cte_query` | Break CTE query into steps, validate each independently |
| `check_budget` | Remaining query budget for a session |
| `query_history` | Recent successful queries for a connection (session memory) |

## Schema & Exploration (10 tools)

See [Schema & Exploration tools](/docs/reference/tools-schema).

| Tool | Description |
|------|-------------|
| `list_tables` | Compact one-line-per-table overview: columns, PKs, FKs, row counts |
| `describe_table` | Full column details: types, nullability, PKs, annotations, PII flags |
| `explore_table` | Deep-dive: column details + FK refs + sample values + referenced tables |
| `explore_column` | Distinct values with counts, NULL stats, optional LIKE filter |
| `explore_columns` | Multi-column stats: distinct counts, uniqueness, min/max/avg, samples |
| `schema_overview` | Database-wide summary: table count, total rows, FK density, hub tables |
| `schema_ddl` | Full schema as CREATE TABLE DDL with FK constraints |
| `schema_statistics` | High-level stats: table sizes, FK connectivity (sorted by row count) |
| `schema_diff` | Compare current schema against last cached version (DDL changes) |
| `get_date_boundaries` | MIN/MAX dates across all DATE/TIMESTAMP columns |

## Relationships (3 tools)

See [Schema & Exploration tools](/docs/reference/tools-schema).

| Tool | Description |
|------|-------------|
| `get_relationships` | Full ERD: all FK relationships as arrows or adjacency list |
| `find_join_path` | FK-based join path discovery between two tables (1–6 hops) |
| `schema_link` | Find tables relevant to a natural-language question (NL → schema) |

## dbt & Verification (8 tools)

See [dbt tools](/docs/reference/tools-dbt).

| Tool | Description |
|------|-------------|
| `dbt_error_parser` | Parse raw dbt error output into structured diagnosis + fix suggestion |
| `generate_sql_skeleton` | Generate a SQL template from YML column spec + ref tables |
| `check_model_schema` | Compare materialized columns vs YML-declared columns |
| `validate_model_output` | Row count validation + fan-out detection + empty model detection |
| `verify_model_values` | Cross-validate model aggregate values against raw source data |
| `audit_model_sources` | Upstream audit: source row counts, fan-out/over-filter ratios, NULL scan |
| `analyze_grain` | Cardinality analysis: per-key distinct counts, fan-out factors |
| `compare_join_types` | Compare row counts across INNER/LEFT/RIGHT/FULL OUTER JOIN |

## Workspaces (2 tools)

See [Operational tools](/docs/reference/tools-ops).

| Tool | Description |
|------|-------------|
| `list_workspace_projects` | List the dbt/notebook projects in the user's workspace |
| `run_notebook` | Run a `.py` notebook in a sandboxed cloud pod, return output + view URL |

## Knowledge Base (3 tools)

See [Operational tools](/docs/reference/tools-ops).

| Tool | Description |
|------|-------------|
| `get_knowledge` | Load baseline docs + task-relevant knowledge entries |
| `search_knowledge` | Agent-directed search across the knowledge base |
| `propose_knowledge` | Propose a new knowledge entry after a run |

## Notion Integration (4 tools)

See [Operational tools](/docs/reference/tools-ops).

| Tool | Description |
|------|-------------|
| `list_notion_integrations` | List configured Notion integrations with search scope and report destination |
| `notion_search` | Search Notion pages visible to an integration's access token |
| `notion_fetch_page` | Fetch full content of a Notion page by ID |
| `notion_create_page` | Create a page under the configured report destination |

## Connections (3 tools)

See [Operational tools](/docs/reference/tools-ops).

| Tool | Description |
|------|-------------|
| `list_database_connections` | List all configured database connections |
| `connection_health` | Latency percentiles (p50/p95/p99), error rates, status per connection |
| `connector_capabilities` | Connector tier classification (Tier 1/2/3) and available features |

---

## Removed tools

The following tools were removed because the gateway runs in Docker and cannot access local filesystems. Their functionality is available via standalone scripts in the plugin:

- `execute_code` / `sandbox_status` — sandbox disabled in cloud
- `dbt_project_map` / `dbt_project_validate` — use `scan_project.py` and `validate_project.py` in the plugin
- `fix_date_spine_hazards` / `fix_nondeterminism_hazards` — use the `dbt-date-spines` skill
- `create_project` — use the web UI or API
