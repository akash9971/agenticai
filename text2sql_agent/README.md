# Text-to-SQL LangGraph Agent (Snowflake + BigQuery)

A multi-warehouse Text-to-SQL-to-Insight agent built with LangGraph, supporting:
- **Snowflake** via Cortex Complete (Claude/Mistral/Llama hosted in Snowflake)
- **BigQuery** via Vertex AI Gemini
- **Local demo mode** with SQLite — runs with no cloud accounts needed

## What to Ask 


Takes a natural-language question like:

> *"Read tables supplychain and sales and give me the list of people who purchased the most bottles of hairfall shampoo in the Germany region."*

And returns:

```json
{
  "key_indicators": ["Top buyer concentration", "Total bottles sold in DE"],
  "key_values": ["Hans Müller — 142 bottles", "Total: 1,210 bottles"],
  "key_attributes": ["customer_name", "region=Germany", "product=hairfall shampoo"],
  "analysis_paragraph": "In the Germany region, hairfall-shampoo purchases are..."
}
```

## Architecture

```
User NL → SQL Generator → SQL Validator → Complexity Router
                                                ├── simple_exec ──┐
                                                └── complex_exec ─┤
                                                                  ▼
                                                         Insight Generator → END
```

The graph is **warehouse-agnostic**. Swap Snowflake↔BigQuery↔SQLite by passing a different `warehouse` flag. Same nodes, same edges, same prompts.

## Quickstart (Local Demo, No Cloud Needed)

```bash
# 1. Clone / unzip the project
cd text2sql_agent

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate          # on Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set your Anthropic API key (used by the local demo's LLM)
export ANTHROPIC_API_KEY="sk-ant-..."   # on Windows: set ANTHROPIC_API_KEY=...

# 5. Seed the demo SQLite database
python seed_demo_db.py

# 6. Run the agent end-to-end
python main.py
```

You should see SQL get generated, validated, executed against SQLite, and turned into structured insights.

## Running Against Snowflake

```bash
pip install -r requirements-snowflake.txt
```

Edit `main.py` and uncomment the Snowflake block:

```python
result = run_agent(
    "snowflake",
    question="...",
    schema="...",
    snowflake_conn={
        "account":   "xy12345.eu-central-1",
        "user":      "...",
        "password":  "...",
        "warehouse": "COMPUTE_WH",
        "database":  "RETAIL",
        "schema":    "PUBLIC",
    },
    model="claude-3-5-sonnet",   # any Cortex-hosted model
)
```

## Running Against BigQuery

```bash
pip install -r requirements-bigquery.txt

# Authenticate locally (one-time)
gcloud auth application-default login
gcloud config set project YOUR_GCP_PROJECT
```

Edit `main.py` and uncomment the BigQuery block:

```python
result = run_agent(
    "bigquery",
    question="...",
    schema="...",
    gcp_project="your-gcp-project",
    gcp_location="us-central1",
    bq_location="US",
    model="gemini-2.0-flash",
)
```

## Project Layout

```
text2sql_agent/
├── README.md                       this file
├── requirements.txt                core deps (works for local demo)
├── requirements-snowflake.txt      add Snowflake stack
├── requirements-bigquery.txt       add BigQuery + Vertex AI stack
├── seed_demo_db.py                 creates a sample SQLite DB
├── main.py                         entry point
├── text2sql/
│   ├── __init__.py
│   ├── state.py                    AgentState + Pydantic schemas
│   ├── dialects.py                 per-warehouse SQL profiles
│   ├── cortex_llm.py               Snowflake Cortex wrapper for LangChain
│   ├── factories.py                LLM + Executor factories
│   ├── nodes.py                    all graph nodes
│   └── graph.py                    graph assembly
└── demo.db                         created by seed_demo_db.py
```

## Reading Order (If You're New to LangGraph)

1. `text2sql/state.py` — what data flows through the graph
2. `text2sql/dialects.py` — per-warehouse SQL personality
3. `text2sql/nodes.py` — the actual work each step does
4. `text2sql/graph.py` — wiring nodes into a graph
5. `main.py` — the entry point that ties it together

## Troubleshooting

**`ModuleNotFoundError: No module named 'langgraph'`** — activate your venv and `pip install -r requirements.txt`.

**`AnthropicException: API key not provided`** — `export ANTHROPIC_API_KEY=...` before running.

**`google.auth.exceptions.DefaultCredentialsError`** — run `gcloud auth application-default login` for BigQuery mode.

**`snowflake.connector.errors.ProgrammingError`** — check your account identifier format; Snowflake uses `xy12345.region.cloud`.

## Next Steps

Once this works, try:
- Adding an error-retry edge (failed SQL → back to validator with the error)
- Replacing `MemorySaver` with `SqliteSaver` for durable checkpoints
- Adding a `tools` subgraph so the agent can fetch table schemas dynamically
