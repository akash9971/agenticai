"""
main.py — entry point for running the agent.

Defaults to LOCAL DEMO MODE (SQLite + Anthropic API) so you can try it
without any cloud setup. Snowflake and BigQuery sections are commented
out — uncomment whichever one you have credentials for.
"""
import json
import os
import sys

from text2sql.factories import get_llm, get_executor, Warehouse
from text2sql.dialects import PROFILES
from text2sql.graph import build_app


# Schema description fed into the SQL generator prompt.
# In production you'd fetch this dynamically from INFORMATION_SCHEMA.
DEMO_SCHEMA = """
Table: supplychain
  product_id   INTEGER
  product_name TEXT          -- e.g. 'hairfall shampoo', 'face wash'
  region       TEXT          -- e.g. 'Germany', 'France', 'India'
  stock        INTEGER

Table: sales
  sale_id       INTEGER
  customer_name TEXT
  product_id    INTEGER       -- FK to supplychain.product_id
  quantity      INTEGER       -- bottles purchased
  region        TEXT
  sale_date     DATE
"""


def run_agent(warehouse: Warehouse, question: str, schema: str, **cfg) -> dict:
    """Build the graph, inject dependencies, run, return final state."""
    llm     = get_llm(warehouse, **cfg)
    db      = get_executor(warehouse, **cfg)
    profile = PROFILES[warehouse]

    app = build_app()
    return app.invoke(
        {
            "user_query":     question,
            "schema_context": schema,
            "warehouse":      warehouse,
            "llm":            llm,
            "db":             db,
            "dialect":        profile,
        },
        config={"configurable": {"thread_id": f"{warehouse}-demo"}},
    )


def main():
    question = (
        "Read tables supplychain and sales and give me the list of people "
        "who purchased the most bottles of hairfall shampoo in the Germany region."
    )

    # ===========================================================
    # MODE 1 — Local demo (SQLite + Anthropic). Default.
    # ===========================================================
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: set ANTHROPIC_API_KEY in your environment first.")
        print("  export ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    if not os.path.exists("demo.db"):
        print("ERROR: demo.db not found. Run `python seed_demo_db.py` first.")
        sys.exit(1)

    result = run_agent(
        "sqlite",
        question=question,
        schema=DEMO_SCHEMA,
        db_path="demo.db",
        model="claude-sonnet-4-5",
    )

    # ===========================================================
    # MODE 2 — Snowflake (uncomment to use)
    # ===========================================================
    # result = run_agent(
    #     "snowflake",
    #     question=question,
    #     schema=DEMO_SCHEMA,
    #     snowflake_conn={
    #         "account":   "xy12345.eu-central-1",
    #         "user":      "YOUR_USER",
    #         "password":  "YOUR_PASSWORD",
    #         "warehouse": "COMPUTE_WH",
    #         "database":  "RETAIL",
    #         "schema":    "PUBLIC",
    #     },
    #     model="claude-3-5-sonnet",
    # )

    # ===========================================================
    # MODE 3 — BigQuery (uncomment to use)
    # ===========================================================
    # Prerequisites:
    #   gcloud auth application-default login
    #   gcloud config set project YOUR_GCP_PROJECT
    #
    # result = run_agent(
    #     "bigquery",
    #     question=question,
    #     schema=DEMO_SCHEMA,
    #     gcp_project="YOUR_GCP_PROJECT",
    #     gcp_location="us-central1",   # for Vertex AI Gemini
    #     bq_location="US",             # for BigQuery dataset
    #     model="gemini-2.0-flash",
    # )

    # ===========================================================
    # Print results
    # ===========================================================
    print("\n" + "=" * 60)
    print("FINAL SQL")
    print("=" * 60)
    print(result.get("validated_sql", "(no SQL generated)"))

    print("\n" + "=" * 60)
    print(f"COMPLEXITY: {result.get('complexity')}")
    print("=" * 60)

    print("\n" + "=" * 60)
    print("STRUCTURED INSIGHTS")
    print("=" * 60)
    print(json.dumps(result.get("final_output", {}), indent=2))


if __name__ == "__main__":
    main()
