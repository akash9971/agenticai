
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from text2sql.state import AgentState
from text2sql.nodes import (
    sql_generator_node,
    sql_validator_node,
    complexity_router,
    simple_executor_node,
    complex_executor_node,
    insight_generator_node,
)


def build_app():
    g = StateGraph(AgentState)

    g.add_node("generate_sql",      sql_generator_node)
    g.add_node("validate_sql",      sql_validator_node)
    g.add_node("simple_exec",       simple_executor_node)
    g.add_node("complex_exec",      complex_executor_node)
    g.add_node("generate_insights", insight_generator_node)

    g.add_edge(START,          "generate_sql")
    g.add_edge("generate_sql", "validate_sql")


    g.add_conditional_edges(
        "validate_sql",
        complexity_router,
        {"simple": "simple_exec", "complex": "complex_exec"},
    )

    g.add_edge("simple_exec",       "generate_insights")
    g.add_edge("complex_exec",      "generate_insights")
    g.add_edge("generate_insights", END)

    return g.compile(checkpointer=MemorySaver())
