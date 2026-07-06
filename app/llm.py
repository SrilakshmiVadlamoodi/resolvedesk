"""Provider-agnostic LLM layer. Swapping providers touches only this file."""

from dataclasses import dataclass, field

import anthropic

from app.config import settings

MODEL = "claude-sonnet-4-6"


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[dict] = field(default_factory=list)


def _to_anthropic_messages(messages: list[dict]) -> tuple[str, list[dict]]:
    """Convert our provider-agnostic message list into an Anthropic
    (system, messages) pair. `system` messages are pulled out of the list;
    `tool` results become `tool_result` blocks on a synthetic user turn."""
    system = ""
    anthropic_messages: list[dict] = []

    for message in messages:
        role = message["role"]
        if role == "system":
            system = message["content"]
        elif role == "user":
            anthropic_messages.append({"role": "user", "content": message["content"]})
        elif role == "assistant":
            content = []
            if message.get("content"):
                content.append({"type": "text", "text": message["content"]})
            for call in message.get("tool_calls", []):
                content.append(
                    {"type": "tool_use", "id": call["id"], "name": call["name"], "input": call["arguments"]}
                )
            anthropic_messages.append({"role": "assistant", "content": content})
        elif role == "tool":
            anthropic_messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": message["tool_call_id"],
                            "content": message["content"],
                        }
                    ],
                }
            )
        else:
            raise ValueError(f"unknown message role: {role}")

    return system, anthropic_messages


def complete(messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    system, anthropic_messages = _to_anthropic_messages(messages)

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=system,
        messages=anthropic_messages,
        tools=tools or [],
    )

    text = None
    tool_calls = []
    for block in response.content:
        if block.type == "text":
            text = (text or "") + block.text
        elif block.type == "tool_use":
            tool_calls.append({"id": block.id, "name": block.name, "arguments": block.input})

    return LLMResponse(content=text, tool_calls=tool_calls)
