---
name: snowflake-cortex
description: >
  Expert skill for building, optimizing, and debugging Snowflake Cortex AI
  pipelines. Use this skill whenever the user mentions Cortex, AI_COMPLETE,
  AI_CLASSIFY, AI_EMBED, AI_EXTRACT, AI_SUMMARIZE, Cortex Search, Cortex
  Agents, Snowflake Intelligence, Cortex Analyst, or any Snowflake AI/LLM
  work. Also triggers for: writing Cortex SQL functions, selecting LLM models
  inside Snowflake, controlling Cortex token costs, building RAG pipelines
  inside Snowflake, setting up AI observability, fine-tuning inside Snowflake,
  or designing multi-step Cortex Agents. If the user's task involves AI or
  LLMs running directly on Snowflake data, use this skill — even if they
  don't use the word "Cortex".
---

# Snowflake Cortex Skill

A structured workflow for designing, building, optimizing, and debugging
Snowflake Cortex AI pipelines — covering AISQL functions, Cortex Search,
Cortex Agents, Snowflake Intelligence, and cost management.

---

## Phase 0 — Brainstorm Before You Build

**Always run this phase first.** Cortex model selection alone creates a
10–40x cost variance. Answering these questions before writing SQL prevents
expensive surprises.

Ask the user:

1. **Data shape** — What table/view is the source? Estimated row count?
   Average tokens per row (use `SNOWFLAKE.CORTEX.COUNT_TOKENS` on a sample)?
2. **Task type** — Classification, extraction, summarization, generation,
   embedding, or search?
3. **Quality bar** — Is near-frontier accuracy required, or will a smaller
   model suffice for this task?
4. **Latency requirement** — Interactive (online) or batch acceptable?
5. **Token budget** — Is there a monthly credit ceiling?
6. **Data residency** — Must data stay in a specific Snowflake region?

Only proceed to Phase 1 once these are answered.

---

## Phase 1 — Model Selection (Biggest Cost Lever)

Cortex LLM pricing ranges from **~$0.12 to ~$24+ per million tokens**
depending on model and surface. Pick the cheapest model that clears the
quality bar.

### Decision Tree

```
Task type?
├── Classification / routing / sentiment / filtering
│   └── Use: mistral-7b or snowflake-arctic-instruct (~$0.12–0.50/M)
│
├── Extraction / summarization (structured output)
│   └── Use: mistral-large2 or llama3.1-70b (~$1–2/M)
│
├── Complex reasoning / generation / long-context
│   └── Start with: claude-sonnet-4-5 (~$4–6/M effective via Cortex)
│   └── Only escalate to: claude-opus-4 (~$24/M) if Sonnet fails evals
│
└── Embeddings / semantic search
    └── Use: e5-base-v2 or snowflake-arctic-embed (~$0.05–0.10/M)
```

### Cost Reference Table (Cortex AI Functions, ~2026)

| Model | Effective $/M tokens | Best for |
|---|---|---|
| mistral-7b | ~$0.12 | Classification, routing, simple tasks |
| snowflake-arctic-instruct | ~$0.25 | General Snowflake workloads |
| mistral-large2 | ~$1.00 | Extraction, summarization |
| llama3.1-70b | ~$1.50 | Reasoning, complex extraction |
| llama3.1-405b | ~$3.50 | Near-frontier, cost-sensitive |
| claude-sonnet-4-5 | ~$4–6 | High-accuracy generation |
| claude-opus-4 | ~$24 | Maximum accuracy (avoid unless justified) |

> ⚠️ Note: Cortex bills input + output tokens. If you generate 3,000 output
> tokens per row across 1M rows on claude-opus-4, you're looking at >$72,000.
> Always estimate before running on full datasets.

**Cost estimation query — run before any large job:**

```sql
-- Sample 100 rows, extrapolate total cost
WITH sample AS (
  SELECT SNOWFLAKE.CORTEX.COUNT_TOKENS('mistral-large2', your_column) AS tok
  FROM your_table
  LIMIT 100
),
avg_tokens AS (SELECT AVG(tok) AS avg_tok FROM sample),
total_rows AS (SELECT COUNT(*) AS n FROM your_table)
SELECT
  avg_tok,
  n,
  ROUND((avg_tok * n / 1000000) * 1.00, 2) AS estimated_credits_mistral_large2,
  ROUND((avg_tok * n / 1000000) * 4.00, 2) AS estimated_credits_claude_sonnet,
  ROUND((avg_tok * n / 1000000) * 12.0, 2) AS estimated_credits_claude_opus
FROM avg_tokens, total_rows;
```

---

## Phase 2 — Function Selection

### AISQL Functions Cheat Sheet

| Function | Charges | Use when |
|---|---|---|
| `AI_COMPLETE(model, prompt)` | Input + Output | Open-ended generation |
| `AI_CLASSIFY(text, labels)` | Input + Output | Route into fixed categories |
| `AI_FILTER(text, condition)` | Input + Output | Boolean filter on text |
| `AI_EXTRACT(text, schema)` | Input + Output | Pull structured fields |
| `AI_SUMMARIZE(text)` | Input + Output | Summarize documents |
| `AI_SENTIMENT(text)` | Input only | Positive/neutral/negative |
| `AI_TRANSLATE(text, lang)` | Input + Output | Language translation |
| `AI_EMBED(model, text)` | Input only | Vector embeddings |
| `AI_SIMILARITY(text1, text2)` | Input only | Semantic similarity score |

**Rule: Don't use AI where SQL is free.**

```sql
-- ❌ Waste — costs credits for a regex task
SELECT AI_FILTER(email, 'Does this mention refund?') FROM emails;

-- ✅ Free
SELECT * FROM emails WHERE email ILIKE '%refund%';
```

---

## Phase 3 — Pipeline Patterns

### Pattern A: Batch Classification Pipeline

```sql
-- Step 1: Classify in a staging table (not production directly)
CREATE OR REPLACE TABLE support_classified AS
SELECT
  ticket_id,
  ticket_text,
  AI_CLASSIFY(
    ticket_text,
    ['billing', 'technical', 'general', 'refund']
  )['label']::VARCHAR AS category,
  AI_CLASSIFY(
    ticket_text,
    ['billing', 'technical', 'general', 'refund']
  )['score']::FLOAT AS confidence
FROM support_tickets
WHERE processed_at IS NULL;  -- Incremental: only new rows

-- Step 2: Review distribution before committing
SELECT category, COUNT(*), AVG(confidence)
FROM support_classified
GROUP BY category
ORDER BY COUNT(*) DESC;
```

### Pattern B: Structured Extraction

```sql
-- Extract multiple fields in one AI_COMPLETE call (cheaper than multiple calls)
SELECT
  contract_id,
  AI_COMPLETE(
    'mistral-large2',
    CONCAT(
      'Extract the following from this contract as JSON with keys: ',
      'party_a, party_b, start_date, end_date, value_usd, jurisdiction. ',
      'Return ONLY valid JSON, no explanation. Contract: ',
      LEFT(contract_text, 3000)  -- Trim to control tokens
    )
  )::VARIANT AS extracted
FROM contracts;
```

### Pattern C: RAG Pipeline with Cortex Search

```sql
-- Step 1: Create search service (one-time setup)
CREATE OR REPLACE CORTEX SEARCH SERVICE docs_search
  ON text_column
  ATTRIBUTES doc_id, category, created_at
  WAREHOUSE = my_wh
  TARGET_LAG = '1 hour'
AS SELECT doc_id, text_column, category, created_at FROM knowledge_base;

-- Step 2: Query at runtime via REST API or Snowpark
-- (Cortex Search is typically called via Python Snowpark or REST, not SQL)
```

### Pattern D: Incremental Processing with Task

```sql
-- Only process new rows — never reprocess what's done
CREATE OR REPLACE TASK process_new_tickets
  WAREHOUSE = xs_wh  -- Use smallest warehouse that works
  SCHEDULE = 'USING CRON 0 * * * * UTC'  -- Hourly
AS
INSERT INTO tickets_enriched
SELECT
  t.ticket_id,
  t.ticket_text,
  AI_CLASSIFY(t.ticket_text, ['billing','technical','general']) AS classification
FROM tickets t
LEFT JOIN tickets_enriched e ON t.ticket_id = e.ticket_id
WHERE e.ticket_id IS NULL;  -- Only unprocessed rows
```

---

## Phase 4 — Cost Controls

### Set Resource Monitors (Critical — no native AI spend alerts)

```sql
-- Snowflake does NOT have native Cortex AI spend alerts.
-- Set warehouse resource monitors as a proxy guard.
CREATE RESOURCE MONITOR cortex_guard
  WITH CREDIT_QUOTA = 500  -- Monthly credit limit
  TRIGGERS
    ON 75 PERCENT DO NOTIFY
    ON 90 PERCENT DO NOTIFY
    ON 100 PERCENT DO SUSPEND;

ALTER WAREHOUSE cortex_wh SET RESOURCE_MONITOR = cortex_guard;
```

### Caching Strategy

Cortex prompt caching reduces repeated-context costs by ~90%. For agent
sessions, context accumulates and gets cached from turn 2 onward.

```sql
-- For REST API / Cortex Agents: enable caching in your session config
-- Cache reads bill at ~10% of input price
-- Longer agent sessions = cheaper per-turn cost (cache amortizes)
```

### Token Trimming

```sql
-- Trim inputs before sending to AI — every token costs money
SELECT AI_SUMMARIZE(LEFT(document_text, 2000))  -- Cap at 2K tokens
FROM documents;

-- Clean whitespace before sending
CREATE FUNCTION clean_for_ai(raw VARCHAR)
RETURNS VARCHAR AS $$
  SELECT REGEXP_REPLACE(
    REGEXP_REPLACE(raw, '\\n{2,}', ' '),
    '\\s{2,}', ' '
  )
$$;
```

---

## Phase 5 — Observability & Cost Monitoring

### Daily Cost Dashboard

```sql
-- AI spend by model, last 30 days
SELECT
  DATE_TRUNC('day', START_TIME)       AS day,
  MODEL_NAME,
  FUNCTION_NAME,
  SUM(TOKENS_USED)                    AS total_tokens,
  SUM(CREDITS_USED)                   AS total_credits,
  ROUND(SUM(CREDITS_USED) * 2.0, 2)  AS estimated_usd  -- $2/AI Credit
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY
WHERE START_TIME >= CURRENT_DATE - 30
GROUP BY 1, 2, 3
ORDER BY total_credits DESC;
```

### Find Expensive Queries

```sql
-- Top 20 most expensive individual queries
SELECT
  QUERY_ID,
  MODEL_NAME,
  TOKENS_USED,
  CREDITS_USED,
  ROUND(CREDITS_USED * 2.0, 2) AS usd_cost
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_QUERY_USAGE_HISTORY
ORDER BY CREDITS_USED DESC
LIMIT 20;
```

### Spend by User

```sql
-- Who is spending the most on AI?
SELECT
  USER_NAME,
  SUM(CREDITS_USED) AS total_credits,
  ROUND(SUM(CREDITS_USED) * 2.0, 2) AS estimated_usd
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_FUNCTIONS_USAGE_HISTORY
WHERE START_TIME >= CURRENT_DATE - 7
GROUP BY USER_NAME
ORDER BY total_credits DESC;
```

---

## Phase 6 — Cortex Agents (Multi-Step Workflows)

Use Cortex Agents when the task requires: tool use, multi-step reasoning,
combining structured + unstructured data, or orchestrating Cortex Search +
Cortex Analyst together.

**Costs are additive** — each sub-call (Analyst, Search, LLM) bills separately.

```python
# Python Snowpark: Cortex Agents via REST API
import snowflake.connector
import requests, json

# Cortex Agent REST call pattern
headers = {
    "Authorization": f"Bearer {session_token}",
    "Content-Type": "application/json"
}

payload = {
    "model": "claude-sonnet-4-5",  # Orchestrator model
    "messages": [{"role": "user", "content": user_query}],
    "tools": [
        {"tool_type": "cortex_analyst_text_to_sql",
         "cortex_analyst_text_to_sql": {"semantic_model_file": "@stage/model.yaml"}},
        {"tool_type": "cortex_search",
         "cortex_search": {"service_name": "docs_search", "max_results": 5}}
    ]
}

response = requests.post(
    f"https://{account}.snowflakecomputing.com/api/v2/cortex/agent:run",
    headers=headers,
    json=payload
)
```

**Agent cost tip:** From turn 2 onward, conversation history lands in cache
at ~10% input price. Design for longer focused sessions over many short ones.

---

## Phase 7 — Fine-Tuning (Optional)

Use Cortex Fine-Tuning when:
- You have 100+ labeled examples of your specific task
- The base model underperforms on domain-specific terminology
- You want to reduce token usage (fine-tuned models need shorter prompts)

```sql
-- Trigger fine-tuning job inside Snowflake
SELECT SNOWFLAKE.CORTEX.FINETUNE(
  'CREATE',
  'MY_DB.MY_SCHEMA.my_finetuned_model',
  'mistral-7b',                           -- Base model
  'SELECT prompt, completion FROM my_training_data',
  'SELECT prompt, completion FROM my_validation_data'
);

-- Check status
SELECT SNOWFLAKE.CORTEX.FINETUNE('SHOW');
```

Fine-tuned models typically reduce prompt length by 30–60% (less few-shot
examples needed), which lowers ongoing token costs.

---

## Phase 8 — Debugging Checklist

When something goes wrong with a Cortex pipeline, work through this order:

1. **Output quality issues**
   - [ ] Is the prompt too vague? Add explicit output format instructions.
   - [ ] Is the input being trimmed too aggressively? Check `LEFT()` limits.
   - [ ] Would a larger model clear the quality bar? Test on 100 rows first.
   - [ ] Is the model hallucinating structure? Switch to `AI_EXTRACT` with
         a schema instead of `AI_COMPLETE` with format instructions.

2. **Cost spikes**
   - [ ] Run the cost estimation query (Phase 1) on the actual dataset.
   - [ ] Check `CORTEX_FUNCTIONS_QUERY_USAGE_HISTORY` for the runaway query.
   - [ ] Is the model outputting unexpectedly long responses? Add
         `'Return in under 100 words.'` to your prompt.
   - [ ] Are you re-processing rows that already have results? Add
         incremental filter (`WHERE processed_id IS NULL`).

3. **Null / error outputs**
   - [ ] Check for rows where input is NULL — wrap in `COALESCE`.
   - [ ] Check for rows exceeding context window — trim input further.
   - [ ] Model may be rate-limited — add retry logic or reduce concurrency.

4. **Serving charges (Cortex Search)**
   - [ ] Is `TARGET_LAG` set too low? Increase to `'1 hour'` or `'1 day'`.
   - [ ] Suspend the search service in dev/staging when not in use.
   - [ ] Schema changes trigger full re-indexing — plan schema before launch.

---

## Quick Reference

### Warehouse Sizing for Cortex

Cortex AI inference does **not** benefit from larger warehouses.
- Recommended: **MEDIUM** or smaller for all Cortex AI Function calls
- Larger warehouse = same inference speed + higher compute cost
- Use `XS` or `S` for monitoring and admin queries

### Context Window by Model (inside Cortex)

| Model | Max Context |
|---|---|
| mistral-7b | 32K tokens |
| mistral-large2 | 128K tokens |
| llama3.1-70b | 128K tokens |
| llama3.1-405b | 128K tokens |
| claude-sonnet-4-5 | 200K tokens |
| claude-opus-4 | 200K tokens |

### Billing Surface Summary

| Surface | Billing unit |
|---|---|
| AISQL functions (AI_COMPLETE etc.) | Snowflake Credits/M tokens |
| Cortex REST API | AI Credits/M tokens ($2.00/credit) |
| Cortex Agents / Intelligence | AI Credits/M tokens |
| Cortex Code | AI Credits/M tokens |
| Cortex Search serving | Credits/GB/month (always-on) |

---

## References

- Snowflake Cortex pricing: `docs.snowflake.com/en/user-guide/snowflake-cortex/pricing`
- AISQL cost guide: `docs.snowflake.com/en/user-guide/snowflake-cortex/aisql-cost`
- Cortex Search cost guide: `docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-costs`
- Consumption Table (live credit rates): Snowflake Service Consumption Table (updated continuously)
- Cortex Agents API: `docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agent`
