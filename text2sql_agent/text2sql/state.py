
from typing import TypedDict, List, Any, Optional
from pydantic import BaseModel, Field


class AgentState(TypedDict, total=False):
    user_query:     str
    schema_context: str
    warehouse:      str
    llm:            Any
    db:             Any
    dialect:        Any
    sql_query:      str
    validated_sql:  str
    complexity:     str
    columns:        List[str]
    raw_results:    List[dict]
    final_output:   dict
    error:          Optional[str]


class SQLOutput(BaseModel):
    sql: str = Field(description="A single SQL SELECT statement, no markdown fences")
    reasoning: str = Field(description="One-line explanation of the approach")


class InsightOutput(BaseModel):
    key_indicators: List[str] = Field(
        description="3-5 KPIs or signals that stand out in the data"
    )
    key_values: List[str] = Field(
        description="Concrete numbers, names, or top entities from the rows"
    )
    key_attributes: List[str] = Field(
        description="Dimensions or categories represented in the data"
    )
    analysis_paragraph: str = Field(
        description="A refined narrative paragraph the user can drop into a report"
    )
