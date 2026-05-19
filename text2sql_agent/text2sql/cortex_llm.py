"""
cortex_llm.py — wraps Snowflake Cortex Complete as a LangChain BaseChatModel.

Once wrapped, Cortex behaves like any other LangChain chat model:
- Works with `prompt | llm | parser` pipelines
- Supports `.invoke()`, `.batch()`, fallbacks, structured output
- LangGraph nodes don't need to know it's Cortex

Import is guarded so the rest of the project still runs without the
Snowflake SDK installed (e.g., when using local SQLite mode).
"""
from typing import Any, List, Optional
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class CortexChatModel(BaseChatModel):
    """Minimal LangChain wrapper around Snowflake Cortex Complete."""

    model_name:  str   = "claude-3-5-sonnet"
    session:     Any   = None
    temperature: float = 0.0

    @property
    def _llm_type(self) -> str:
        return "snowflake-cortex"

    def _format(self, messages: List[BaseMessage]) -> str:
        """Cortex takes a single string; serialize role-tagged messages."""
        role_map = {"system": "System", "human": "User", "ai": "Assistant"}
        return "\n\n".join(
            f"{role_map.get(m.type, m.type).upper()}:\n{m.content}"
            for m in messages
        )

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        **kwargs,
    ) -> ChatResult:
        # Lazy import — only required when Snowflake mode is actually used.
        from snowflake.cortex import complete as cortex_complete

        prompt = self._format(messages)
        text = cortex_complete(
            model=self.model_name,
            prompt=prompt,
            session=self.session,
            options={"temperature": self.temperature},
        )
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=text))]
        )
