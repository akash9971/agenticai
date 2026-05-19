"""
dialects.py — per-warehouse SQL personality.

Each profile holds:
- name: identifier used in prompts
- sql_rules: dialect-specific guidance injected into the SQL-generator prompt
- complex_tokens: keywords the complexity router scans for

Adding a new warehouse = adding a new DialectProfile entry to PROFILES.
No graph code changes needed.
"""
from dataclasses import dataclass
from typing import List


@dataclass
class DialectProfile:
    name:           str
    sql_rules:      str
    complex_tokens: List[str]


SNOWFLAKE_PROFILE = DialectProfile(
    name="snowflake",
    sql_rules=(
        "Target dialect: Snowflake SQL.\n"
        "- Use DOUBLE QUOTES for case-sensitive identifiers, single quotes for strings.\n"
        "- Use FLATTEN / LATERAL for nested data, VARIANT for JSON columns.\n"
        "- Date functions: DATEADD, DATEDIFF, TO_DATE.\n"
        "- ILIKE for case-insensitive matching.\n"
    ),
    complex_tokens=[
        "SUM(", "AVG(", "COUNT(", "MIN(", "MAX(",
        "GROUP BY", "HAVING", "OVER(",
        "FLATTEN", "LATERAL", "VARIANT", "OBJECT_CONSTRUCT", "ARRAY_AGG",
    ],
)


BIGQUERY_PROFILE = DialectProfile(
    name="bigquery",
    sql_rules=(
        "Target dialect: GoogleSQL (BigQuery).\n"
        "- Always fully qualify tables: `project.dataset.table`.\n"
        "- Use BACKTICKS for identifiers, single quotes for strings.\n"
        "- Use UNNEST for ARRAYs, dot-notation for STRUCTs.\n"
        "- Date functions: DATE_ADD, DATE_DIFF, PARSE_DATE.\n"
    ),
    complex_tokens=[
        "SUM(", "AVG(", "COUNT(", "MIN(", "MAX(",
        "GROUP BY", "HAVING", "OVER(",
        "UNNEST", "STRUCT(", "ARRAY(", "ARRAY<", "ARRAY_AGG",
    ],
)


SQLITE_PROFILE = DialectProfile(
    name="sqlite",
    sql_rules=(
        "Target dialect: SQLite.\n"
        "- Use single quotes for strings.\n"
        "- LIKE is case-insensitive for ASCII by default.\n"
        "- Date functions: DATE(), STRFTIME().\n"
        "- No native nested types — work with flat columns only.\n"
    ),
    complex_tokens=[
        "SUM(", "AVG(", "COUNT(", "MIN(", "MAX(",
        "GROUP BY", "HAVING", "OVER(",
    ],
)


PROFILES = {
    "snowflake": SNOWFLAKE_PROFILE,
    "bigquery":  BIGQUERY_PROFILE,
    "sqlite":    SQLITE_PROFILE,
}
