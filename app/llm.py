"""Provider-agnostic LLM layer. Swapping providers touches only this file."""

from dataclasses import dataclass


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[dict]


def complete(messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
    raise NotImplementedError
