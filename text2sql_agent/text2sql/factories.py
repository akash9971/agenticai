"""
factories.py — turns a warehouse name into the right LLM and executor.

This is where dependency injection happens. Once these factories return
their objects, downstream graph code is fully warehouse-agnostic.

Cloud SDK imports are *lazy* so users don't need to install Snowflake
or Google libs to run the local SQLite demo.
"""
import os
import sqlite3
from typing import Literal, Tuple, List, Optional, Any
from langchain_core.language_models import BaseChatModel


Warehouse = Literal["snowflake", "bigquery", "sqlite"]


# =================================================================
# LLM FACTORY
# =================================================================
def get_llm(warehouse: Warehouse, **cfg) -> BaseChatModel:
    """Return a configured LangChain chat model for the given warehouse."""

    if warehouse == "sqlite":
        # Local demo uses Anthropic's API directly (no warehouse-hosted LLM)
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=cfg.get("model", "claude-sonnet-4-5"),
            temperature=0,
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
        )

    if warehouse == "snowflake":
        from snowflake.snowpark import Session as SnowSession
        from text2sql.cortex_llm import CortexChatModel
        session = SnowSession.builder.configs(cfg["snowflake_conn"]).create()
        return CortexChatModel(
            model_name=cfg.get("model", "claude-3-5-sonnet"),
            session=session,
        )

    if warehouse == "bigquery":
        from langchain_google_vertexai import ChatVertexAI
        return ChatVertexAI(
            model_name=cfg.get("model", "gemini-2.0-flash"),
            project=cfg["gcp_project"],
            location=cfg.get("gcp_location", "us-central1"),
            temperature=0,
        )

    raise ValueError(f"Unknown warehouse: {warehouse}")


# =================================================================
# EXECUTOR FACTORY
# =================================================================
class QueryExecutor:
    """Common interface every executor must satisfy."""
    def run(self, sql: str) -> Tuple[List[dict], List[str]]:
        raise NotImplementedError


class SQLiteExecutor(QueryExecutor):
    """Tiny executor for the local demo. Uses a file-backed SQLite DB."""
    def __init__(self, db_path: str = "demo.db"):
        self.db_path = db_path

    def run(self, sql: str) -> Tuple[List[dict], List[str]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute(sql)
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = [dict(r) for r in cur.fetchall()]
            return rows, cols
        finally:
            conn.close()


class SnowflakeExecutor(QueryExecutor):
    def __init__(self, conn_cfg: dict):
        import snowflake.connector
        self.conn = snowflake.connector.connect(**conn_cfg)

    def run(self, sql: str) -> Tuple[List[dict], List[str]]:
        cur = self.conn.cursor()
        try:
            cur.execute(sql)
            cols = [c[0] for c in cur.description] if cur.description else []
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            return rows, cols
        finally:
            cur.close()


class BigQueryExecutor(QueryExecutor):
    """
    Auth resolution order:
    1. If credentials_path is given -> load that JSON service-account file.
    2. Else if GOOGLE_APPLICATION_CREDENTIALS env var is set -> use it.
    3. Else fall back to gcloud's Application Default Credentials.
    """
    def __init__(
        self,
        project: str,
        credentials_path: Optional[str] = None,
        location: str = "US",
    ):
        from google.cloud import bigquery
        if credentials_path:
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_file(
                credentials_path
            )
            self.client = bigquery.Client(
                project=project, credentials=creds, location=location
            )
        else:
            self.client = bigquery.Client(project=project, location=location)

    def run(self, sql: str) -> Tuple[List[dict], List[str]]:
        job = self.client.query(sql)
        result = job.result()  # blocks until query finishes
        cols = [f.name for f in result.schema]
        rows = [dict(r.items()) for r in result]
        return rows, cols


def get_executor(warehouse: Warehouse, **cfg) -> QueryExecutor:
    if warehouse == "sqlite":
        return SQLiteExecutor(cfg.get("db_path", "demo.db"))

    if warehouse == "snowflake":
        return SnowflakeExecutor(cfg["snowflake_conn"])

    if warehouse == "bigquery":
        return BigQueryExecutor(
            project=cfg["gcp_project"],
            credentials_path=cfg.get("gcp_credentials_path"),
            location=cfg.get("bq_location", "US"),
        )

    raise ValueError(f"Unknown warehouse: {warehouse}")
