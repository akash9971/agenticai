import sqlparse
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, PydanticOutputParser

from text2sql.state import AgentState, SQLOutput, InsightOutput

def sql_generator_node(state: AgentState) -> dict:
    parser = PydanticOutputParser(pydantic_object=SQLOutput)
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are an expert SQL writer.\n{rules}\n\n"
         "Use only tables and columns from the schema below. Do not invent names.\n"
         "SCHEMA:\n{schema}\n\n"
         "{format_instructions}"),
        ("human", "{question}"),
    ])
    chain = prompt | state["llm"] | parser
    out: SQLOutput = chain.invoke({
        "rules":               state["dialect"].sql_rules,
        "schema":              state["schema_context"],
        "question":            state["user_query"],
        "format_instructions": parser.get_format_instructions(),
    })
    print(f"[generate_sql] {out.sql}")
    return {"sql_query": out.sql}


def sql_validator_node(state: AgentState) -> dict:
    # Step 1: deterministic pretty-printing — free, never wrong
    pretty = sqlparse.format(
        state["sql_query"], reindent=True, keyword_case="upper"
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are a {dialect} SQL syntax expert.\n"
         "- Fix syntax errors only; preserve semantics.\n"
         "- If the SQL contains DROP/DELETE/UPDATE/INSERT/ALTER/TRUNCATE, "
         "  replace the entire statement with: SELECT 1\n"
         "- Return ONLY the SQL. No fences, no commentary, no explanation."),
        ("human", "{sql}"),
    ])
    chain = prompt | state["llm"] | StrOutputParser()
    fixed = chain.invoke({"dialect": state["dialect"].name, "sql": pretty})

    # Defensive cleanup — sometimes LLMs add fences despite being told not to
    cleaned = fixed.strip().strip("`").strip()
    if cleaned.lower().startswith("sql\n"):
        cleaned = cleaned[4:].strip()

    print(f"[validate_sql] {cleaned}")
    return {"validated_sql": cleaned}


def complexity_router(state: AgentState) -> str:
    """Returns 'complex' if SQL has aggregates / nested ops, else 'simple'."""
    sql = state["validated_sql"].upper()
    is_complex = any(t in sql for t in state["dialect"].complex_tokens)
    label = "complex" if is_complex else "simple"
    print(f"[complexity_router] -> {label}")
    return label


def simple_executor_node(state: AgentState) -> dict:
    rows, cols = state["db"].run(state["validated_sql"])
    print(f"[simple_exec] {len(rows)} rows, {len(cols)} cols")
    return {
        "raw_results": rows,
        "columns":     cols,
        "complexity":  "simple",
    }


def complex_executor_node(state: AgentState) -> dict:
    rows, cols = state["db"].run(state["validated_sql"])
    flat = [
        {k: (str(v) if isinstance(v, (list, dict)) else v) for k, v in r.items()}
        for r in rows
    ]
    print(f"[complex_exec] {len(flat)} rows, {len(cols)} cols")
    return {
        "raw_results": flat,
        "columns":     cols,
        "complexity":  "complex",
    }


def insight_generator_node(state: AgentState) -> dict:
    parser = PydanticOutputParser(pydantic_object=InsightOutput)
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are a senior data analyst. Given the SQL result rows, produce a "
         "structured analysis with EXACTLY these four sections:\n"
         "1. key_indicators - 3-5 metrics or signals that stand out\n"
         "2. key_values - concrete numbers / names / top entities\n"
         "3. key_attributes - dimensions and categories present\n"
         "4. analysis_paragraph - a refined narrative the user can drop in a report\n\n"
         "Original question: {question}\n"
         "SQL executed: {sql}\n\n"
         "{format_instructions}"),
        ("human", "Columns: {columns}\nRows (first 50): {rows}"),
    ])
    chain = prompt | state["llm"] | parser
    out: InsightOutput = chain.invoke({
        "question":            state["user_query"],
        "sql":                 state["validated_sql"],
        "columns":             state["columns"],
        "rows":                state["raw_results"][:50],
        "format_instructions": parser.get_format_instructions(),
    })
    print("[generate_insights] done")
    return {"final_output": out.model_dump()}
